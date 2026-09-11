"""
ASTRATRACK — 3D Tracking Camera Model

Simulates a ground-station FSOC tracking camera with pan/tilt gimbal,
configurable FOV, angular rate limits, and inertia.

The camera is positioned at a fixed point and rotates to track a target.
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, List

from simulator.math3d import normalize, spherical_to_cartesian


@dataclass
class CameraConfig3D:
    """Configuration for the 3D tracking camera."""
    position: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 10.0, 0.0]))  # Ground station
    initial_pan_deg: float = 0.0         # Initial azimuth (degrees)
    initial_tilt_deg: float = 30.0       # Initial elevation (degrees)
    fov_deg: float = 8.0                 # Full-cone FOV (degrees)
    pan_limit_deg: float = 170.0         # Max pan ±degrees
    tilt_limit_deg: float = 85.0         # Max tilt (0=horizon, 90=zenith)
    tilt_min_deg: float = 2.0            # Min tilt (above horizon)
    max_angular_velocity: float = 30.0   # Max slew rate (deg/s)
    inertia: float = 0.88                # Smoothing factor (0=instant, 1=frozen)
    tracking_gain: float = 2.5           # Proportional tracking gain
    vibration_amplitude: float = 0.0     # Camera jitter (degrees)
    vibration_frequency: float = 5.0     # Jitter frequency (Hz)


class TrackingCamera3D:
    """
    A ground-based FSOC tracking camera with pan/tilt gimbal.

    Tracks a 3D target by computing the desired pointing angles and
    slewing toward them with rate limits and inertia.
    """

    def __init__(self, config: CameraConfig3D):
        self.config = config
        self.position = config.position.copy().astype(np.float64)
        self.pan_deg: float = config.initial_pan_deg
        self.tilt_deg: float = config.initial_tilt_deg

        # Smoothed angular velocities
        self._pan_rate: float = 0.0
        self._tilt_rate: float = 0.0

        # Tracking state
        self.is_locked: bool = False
        self.angular_error_deg: float = 0.0
        self.coast_frames: int = 0
        self._lock_threshold_deg: float = config.fov_deg * 0.4

        # Time (for vibration)
        self._time: float = 0.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def update(self, dt: float, target_pos: np.ndarray,
               target_visible: bool = True):
        """
        Update camera pointing toward the target.

        Args:
            dt: Time step (seconds).
            target_pos: Target position in world coordinates (3,).
            target_visible: Whether the target is detectable.
        """
        self._time += dt

        if target_visible:
            # Compute desired pointing angles
            desired_pan, desired_tilt = self._compute_target_angles(target_pos)

            # Compute angular error
            pan_error = desired_pan - self.pan_deg
            tilt_error = desired_tilt - self.tilt_deg

            # Wrap pan error to [-180, 180]
            while pan_error > 180:
                pan_error -= 360
            while pan_error < -180:
                pan_error += 360

            self.angular_error_deg = math.sqrt(pan_error ** 2 + tilt_error ** 2)

            # Proportional tracking with gain
            gain = self.config.tracking_gain
            cmd_pan_rate = gain * pan_error
            cmd_tilt_rate = gain * tilt_error

            # Clamp to max angular velocity
            max_rate = self.config.max_angular_velocity
            cmd_pan_rate = np.clip(cmd_pan_rate, -max_rate, max_rate)
            cmd_tilt_rate = np.clip(cmd_tilt_rate, -max_rate, max_rate)

            # Inertia smoothing
            inertia = self.config.inertia
            self._pan_rate = inertia * self._pan_rate + (1 - inertia) * cmd_pan_rate
            self._tilt_rate = inertia * self._tilt_rate + (1 - inertia) * cmd_tilt_rate

            # Lock detection
            self.is_locked = self.angular_error_deg < self._lock_threshold_deg
            self.coast_frames = 0
        else:
            # Coast: maintain last known rates, decaying
            self._pan_rate *= 0.98
            self._tilt_rate *= 0.98
            self.is_locked = False
            self.coast_frames += 1

        # Apply angular rates
        self.pan_deg += self._pan_rate * dt
        self.tilt_deg += self._tilt_rate * dt

        # Apply vibration disturbance
        if self.config.vibration_amplitude > 0:
            vib = self._compute_vibration()
            self.pan_deg += vib[0]
            self.tilt_deg += vib[1]

        # Enforce limits
        self.pan_deg = np.clip(self.pan_deg,
                               -self.config.pan_limit_deg,
                               self.config.pan_limit_deg)
        self.tilt_deg = np.clip(self.tilt_deg,
                                self.config.tilt_min_deg,
                                self.config.tilt_limit_deg)

    def reset(self):
        """Reset camera to initial state."""
        self.pan_deg = self.config.initial_pan_deg
        self.tilt_deg = self.config.initial_tilt_deg
        self._pan_rate = 0.0
        self._tilt_rate = 0.0
        self.is_locked = False
        self.angular_error_deg = 0.0
        self.coast_frames = 0
        self._time = 0.0

    # ------------------------------------------------------------------ #
    # Geometry Queries
    # ------------------------------------------------------------------ #

    @property
    def direction(self) -> np.ndarray:
        """Unit vector in the camera's pointing direction."""
        return spherical_to_cartesian(self.pan_deg, self.tilt_deg, 1.0)

    @property
    def direction_horizontal(self) -> np.ndarray:
        """Horizontal component of the pointing direction (XZ plane)."""
        d = self.direction
        h = np.array([d[0], 0.0, d[2]])
        norm = np.linalg.norm(h)
        return h / norm if norm > 1e-10 else np.array([0.0, 0.0, 1.0])

    def get_fov_corners(self, distance: float = 400.0) -> List[np.ndarray]:
        """
        Compute the four corners of the FOV rectangle at a given distance.

        Returns:
            List of 4 world-space positions [TL, TR, BR, BL].
        """
        half_fov = math.radians(self.config.fov_deg / 2.0)
        pan_rad = math.radians(self.pan_deg)
        tilt_rad = math.radians(self.tilt_deg)

        # Camera local axes
        forward = self.direction
        right = normalize(np.cross(forward, np.array([0.0, 1.0, 0.0])))
        if np.linalg.norm(right) < 1e-6:
            right = np.array([1.0, 0.0, 0.0])
        up = np.cross(right, forward)

        # Half-extents at the given distance
        half_h = distance * math.tan(half_fov)
        half_w = half_h  # Square FOV for simplicity

        center = self.position + forward * distance
        corners = [
            center - right * half_w + up * half_h,  # TL
            center + right * half_w + up * half_h,  # TR
            center + right * half_w - up * half_h,  # BR
            center - right * half_w - up * half_h,  # BL
        ]
        return corners

    def get_los_point(self, target_pos: np.ndarray) -> np.ndarray:
        """Get a point along the line-of-sight from camera toward target."""
        direction = normalize(target_pos - self.position)
        dist = np.linalg.norm(target_pos - self.position)
        return self.position + direction * dist

    def is_target_in_fov(self, target_pos: np.ndarray) -> bool:
        """Check if a target position falls within the camera's FOV."""
        to_target = target_pos - self.position
        to_target_norm = normalize(to_target)
        cam_dir = self.direction
        angle = math.degrees(math.acos(
            np.clip(np.dot(to_target_norm, cam_dir), -1.0, 1.0)
        ))
        return angle <= self.config.fov_deg / 2.0

    # ------------------------------------------------------------------ #
    # Private Helpers
    # ------------------------------------------------------------------ #

    def _compute_target_angles(self, target_pos: np.ndarray
                               ) -> Tuple[float, float]:
        """Compute the azimuth and elevation angles to a target position."""
        delta = target_pos - self.position
        horizontal_dist = math.sqrt(delta[0] ** 2 + delta[2] ** 2)

        azimuth = math.degrees(math.atan2(delta[0], delta[2]))
        elevation = math.degrees(math.atan2(delta[1], max(horizontal_dist, 1e-6)))

        return azimuth, elevation

    def _compute_vibration(self) -> Tuple[float, float]:
        """Compute vibration-induced angular jitter."""
        amp = self.config.vibration_amplitude
        freq = self.config.vibration_frequency
        t = self._time

        jitter_pan = (
            amp * 0.6 * math.sin(2 * math.pi * freq * t) +
            amp * 0.3 * math.sin(2 * math.pi * freq * 1.7 * t + 0.5) +
            amp * 0.1 * math.sin(2 * math.pi * freq * 3.1 * t + 1.2)
        )
        jitter_tilt = (
            amp * 0.5 * math.sin(2 * math.pi * freq * 0.8 * t + 0.3) +
            amp * 0.35 * math.sin(2 * math.pi * freq * 2.3 * t + 0.8) +
            amp * 0.15 * math.sin(2 * math.pi * freq * 4.0 * t + 2.0)
        )

        return (jitter_pan, jitter_tilt)
