"""
ASTRATRACK — 10-Channel Configurable Disturbance Engine

Central orchestrator for 10 independently configurable disturbance channels:
1. Image noise
2. Camera vibration
3. Platform jitter
4. Target acceleration
5. Target angular motion
6. Atmospheric turbulence-like image distortion
7. Temporary blur
8. Brightness variation
9. Target occlusion
10. Random target loss

Note: These models are configurable engineering approximations
for algorithm robustness testing, not physically exact atmospheric models.
"""

from typing import Dict, Optional, Tuple, Any
import numpy as np

from core.config import DisturbanceConfig
from disturbance.channel import DisturbanceChannelConfig
from disturbance.presets import get_preset_channels, PRESET_NAMES
from disturbance.models import (
    apply_image_noise,
    compute_camera_vibration,
    compute_platform_jitter,
    compute_target_acceleration,
    compute_target_angular_motion,
    apply_turbulence_distortion,
    apply_temporary_blur,
    apply_brightness_variation,
    apply_target_occlusion,
    is_random_target_loss_active,
)


class DisturbanceEngine:
    """
    Unified 10-Channel Disturbance Engine with:
    - Independent channel toggles, intensities, frequencies, seeds, durations, start delays
    - 5 standard presets (NORMAL, LIGHT, MODERATE, SEVERE, EXTREME STRESS TEST)
    - Deterministic PRNG execution under fixed seed
    """

    def __init__(self, config: Optional[DisturbanceConfig] = None,
                 preset: str = "NORMAL",
                 master_seed: Optional[int] = None):
        """
        Args:
            config: Optional legacy DisturbanceConfig for backwards compatibility.
            preset: Initial preset name.
            master_seed: Optional PRNG seed for deterministic runs.
        """
        self.config = config or DisturbanceConfig()
        self.master_seed = master_seed
        self.active_preset_name = preset
        self.channels: Dict[str, DisturbanceChannelConfig] = get_preset_channels(preset)

        # Isolated PRNG streams per channel
        self._rngs: Dict[str, np.random.RandomState] = {}
        self._init_rngs()

        # Telemetry cache
        self.active_channels_now = []

    def _init_rngs(self):
        """Initialize deterministic PRNG streams for all channels."""
        self._rngs = {
            name: ch.get_rng(self.master_seed)
            for name, ch in self.channels.items()
        }

    def set_master_seed(self, seed: Optional[int]):
        """Set or reset master PRNG seed for complete determinism."""
        self.master_seed = seed
        self._init_rngs()

    def load_preset(self, preset_name: str):
        """Load one of the 5 standard presets."""
        self.active_preset_name = preset_name
        self.channels = get_preset_channels(preset_name)
        self._init_rngs()

        # Update legacy config fields for backward compatibility
        self.config.turbulence_strength = self.channels["turbulence"].intensity if self.channels["turbulence"].enabled else 0.0
        self.config.vibration_amplitude = self.channels["camera_vibration"].intensity if self.channels["camera_vibration"].enabled else 0.0
        self.config.noise_sigma = self.channels["image_noise"].intensity if self.channels["image_noise"].enabled else 0.0
        self.config.target_max_accel = self.channels["target_acceleration"].intensity if self.channels["target_acceleration"].enabled else 0.0

    def reset(self):
        """Reset internal RNG states and temporal generators."""
        self._init_rngs()


    def configure_channel(self, name: str,
                          enabled: Optional[bool] = None,
                          intensity: Optional[float] = None,
                          frequency: Optional[float] = None,
                          duration: Optional[float] = None,
                          start_delay: Optional[float] = None,
                          seed: Optional[int] = None):
        """Dynamically configure an individual disturbance channel."""
        if name not in self.channels:
            return
        ch = self.channels[name]
        if enabled is not None:
            ch.enabled = bool(enabled)
        if intensity is not None:
            ch.intensity = float(intensity)
        if frequency is not None:
            ch.frequency = float(frequency)
        if duration is not None:
            ch.duration = float(duration)
        if start_delay is not None:
            ch.start_delay = float(start_delay)
        if seed is not None:
            ch.seed = int(seed)
            self._rngs[name] = ch.get_rng(self.master_seed)

    # ------------------------------------------------------------------ #
    # Multi-Domain Disturbance Applications
    # ------------------------------------------------------------------ #

    def get_camera_perturbations(self, t: float) -> Tuple[float, float, float, float]:
        """
        Compute camera-side perturbations: vibration and platform jitter.

        Returns:
            (jitter_x_px, jitter_y_px, vib_pan_deg, vib_tilt_deg)
        """
        jitter_x, jitter_y = 0.0, 0.0
        vib_pan, vib_tilt = 0.0, 0.0

        # Channel 2: Camera Vibration
        ch_vib = self.channels["camera_vibration"]
        if ch_vib.is_active(t):
            vib_pan, vib_tilt = compute_camera_vibration(
                t, ch_vib.intensity, ch_vib.frequency, self._rngs["camera_vibration"]
            )

        # Channel 3: Platform Jitter
        ch_jit = self.channels["platform_jitter"]
        if ch_jit.is_active(t):
            jx, jy = compute_platform_jitter(
                t, ch_jit.intensity, ch_jit.frequency, self._rngs["platform_jitter"]
            )
            jitter_x += jx
            jitter_y += jy

        return (jitter_x, jitter_y, vib_pan, vib_tilt)

    def get_vibration_jitter(self, t: float) -> Tuple[float, float]:
        """Backward-compatible helper returning pixel jitter."""
        jx, jy, vp, vt = self.get_camera_perturbations(t)
        # Convert deg to approx 10 px/deg if vibration present
        return (jx + vp * 10.0, jy + vt * 10.0)

    def get_target_kinematic_perturbations(self, t: float) -> Tuple[float, float, float]:
        """
        Compute target-side kinematic perturbations: acceleration burst and angular turn.

        Returns:
            (ax_px_s2, ay_px_s2, d_theta_rad_s)
        """
        ax, ay = 0.0, 0.0
        d_theta = 0.0

        # Channel 4: Target Acceleration
        ch_acc = self.channels["target_acceleration"]
        if ch_acc.is_active(t):
            ax, ay = compute_target_acceleration(
                t, ch_acc.intensity, ch_acc.frequency, self._rngs["target_acceleration"]
            )

        # Channel 5: Target Angular Motion
        ch_ang = self.channels["target_angular_motion"]
        if ch_ang.is_active(t):
            d_theta = compute_target_angular_motion(
                t, ch_ang.intensity, ch_ang.frequency, self._rngs["target_angular_motion"]
            )

        return (ax, ay, d_theta)

    def is_target_loss_active(self, t: float) -> bool:
        """Channel 10: Check if random target signal loss is active."""
        ch_loss = self.channels["random_target_loss"]
        if not ch_loss.is_active(t):
            return False
        return is_random_target_loss_active(
            t, ch_loss.intensity, ch_loss.frequency, self._rngs["random_target_loss"]
        )

    def apply_image_disturbances(self, frame: np.ndarray, t: float,
                                 target_fov_pos: Optional[Tuple[float, float]] = None) -> np.ndarray:
        """
        Apply image-domain disturbances in proper optical sequence:
        Turbulence Warp -> Blur -> Brightness/Scintillation -> Occlusion -> Sensor Noise.
        """
        self.active_channels_now = [
            name for name, ch in self.channels.items() if ch.is_active(t)
        ]

        out = frame

        # Channel 6: Turbulence-like distortion
        ch_turb = self.channels["turbulence"]
        if ch_turb.is_active(t):
            out = apply_turbulence_distortion(
                out, t, ch_turb.intensity, ch_turb.frequency, self._rngs["turbulence"]
            )

        # Channel 7: Temporary blur
        ch_blur = self.channels["temporary_blur"]
        if ch_blur.is_active(t):
            out = apply_temporary_blur(
                out, t, ch_blur.intensity, ch_blur.frequency, self._rngs["temporary_blur"]
            )

        # Channel 8: Brightness variation
        ch_bright = self.channels["brightness_variation"]
        if ch_bright.is_active(t):
            out = apply_brightness_variation(
                out, t, ch_bright.intensity, ch_bright.frequency, self._rngs["brightness_variation"]
            )

        # Channel 9: Target occlusion
        ch_occ = self.channels["target_occlusion"]
        if ch_occ.is_active(t):
            out = apply_target_occlusion(
                out, target_fov_pos, ch_occ.intensity, self._rngs["target_occlusion"]
            )

        # Channel 1: Image Noise
        ch_noise = self.channels["image_noise"]
        if ch_noise.is_active(t):
            out = apply_image_noise(
                out, ch_noise.intensity, self._rngs["image_noise"]
            )

        return out
