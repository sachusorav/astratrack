"""
ASTRATRACK — Disturbance Engineering Models

Implements the 10 disturbance channel effects as configurable engineering approximations
for algorithm robustness testing (not claimed as physically exact atmospheric models):

1. Image noise (Gaussian + salt-and-pepper)
2. Camera vibration (multi-harmonic gimbal oscillation)
3. Platform jitter (high-frequency micro-sway)
4. Target acceleration (sudden translational acceleration bursts)
5. Target angular motion (heading turns / weave oscillation)
6. Atmospheric turbulence-like distortion (geometric displacement field)
7. Temporary blur (defocus / motion blur)
8. Brightness variation (scintillation / attenuation fade)
9. Target occlusion (synthetic geometric mask over beacon)
10. Random target loss (signal blackout / null detection)
"""

import math
import cv2
import numpy as np
from typing import Tuple, Optional


def apply_image_noise(frame: np.ndarray, intensity: float,
                      rng: np.random.RandomState) -> np.ndarray:
    """
    1. Image Noise: Additive Gaussian sensor noise + Salt-and-Pepper noise.
    Intensity: 0.0 to 50.0 (maps to sigma and pepper density).
    """
    if intensity <= 0.0:
        return frame

    sigma = intensity
    noise = rng.normal(0, sigma, frame.shape).astype(np.float32)
    noisy = np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # Salt and pepper if intensity is elevated
    if intensity > 15.0:
        density = min(0.04, (intensity - 15.0) * 0.001)
        h, w = frame.shape[:2]
        num_sp = int(h * w * density)
        ys = rng.randint(0, h, num_sp)
        xs = rng.randint(0, w, num_sp)
        noisy[ys, xs] = rng.choice([0, 255], size=num_sp)[:, None]

    return noisy


def compute_camera_vibration(t: float, intensity: float, frequency: float,
                             rng: np.random.RandomState) -> Tuple[float, float]:
    """
    2. Camera Vibration: Multi-harmonic gimbal oscillations.
    Intensity: Peak amplitude in degrees.
    Frequency: Fundamental frequency in Hz.
    Returns: (pan_jitter_deg, tilt_jitter_deg)
    """
    if intensity <= 0.0:
        return (0.0, 0.0)

    f = max(0.1, frequency)
    amp = intensity

    vib_pan = (
        amp * 0.60 * math.sin(2 * math.pi * f * t) +
        amp * 0.28 * math.sin(2 * math.pi * f * 1.73 * t + 0.4) +
        amp * 0.12 * math.sin(2 * math.pi * f * 3.11 * t + 1.1)
    )
    vib_tilt = (
        amp * 0.50 * math.sin(2 * math.pi * f * 0.82 * t + 0.2) +
        amp * 0.35 * math.sin(2 * math.pi * f * 2.29 * t + 0.7) +
        amp * 0.15 * math.sin(2 * math.pi * f * 4.05 * t + 1.8)
    )
    return (vib_pan, vib_tilt)


def compute_platform_jitter(t: float, intensity: float, frequency: float,
                            rng: np.random.RandomState) -> Tuple[float, float]:
    """
    3. Platform Jitter: High-frequency stochastic micro-sway and band-limited noise.
    Intensity: Amplitude in pixels.
    Returns: (jitter_x_px, jitter_y_px)
    """
    if intensity <= 0.0:
        return (0.0, 0.0)

    # Combine fast pseudo-random walking with small stochastic perturbations
    f = max(0.5, frequency)
    noise_x = rng.normal(0, intensity * 0.35)
    noise_y = rng.normal(0, intensity * 0.35)
    harm_x = intensity * 0.65 * math.sin(2 * math.pi * f * 3.7 * t)
    harm_y = intensity * 0.65 * math.cos(2 * math.pi * f * 4.3 * t)

    return (harm_x + noise_x, harm_y + noise_y)


def compute_target_acceleration(t: float, intensity: float, frequency: float,
                               rng: np.random.RandomState) -> Tuple[float, float]:
    """
    4. Target Acceleration: Translational burst perturbations.
    Intensity: Max acceleration magnitude in px/s^2.
    Frequency: Burst cycle frequency in Hz.
    Returns: (ax_burst, ay_burst) in px/s^2
    """
    if intensity <= 0.0:
        return (0.0, 0.0)

    # Periodic burst waveform
    f = max(0.1, frequency)
    burst_gate = max(0.0, math.sin(2 * math.pi * f * t)) ** 3
    dir_angle = (t * 1.5) % (2 * math.pi)

    ax = intensity * burst_gate * math.cos(dir_angle)
    ay = intensity * burst_gate * math.sin(dir_angle)
    return (ax, ay)


def compute_target_angular_motion(t: float, intensity: float, frequency: float,
                                 rng: np.random.RandomState) -> float:
    """
    5. Target Angular Motion: Centripetal heading turns & weave rate.
    Intensity: Heading turn rate amplitude in rad/s.
    Returns: angular_velocity_offset (rad/s)
    """
    if intensity <= 0.0:
        return 0.0

    f = max(0.05, frequency)
    return intensity * math.sin(2 * math.pi * f * t)


def apply_turbulence_distortion(frame: np.ndarray, t: float, intensity: float,
                                frequency: float,
                                rng: np.random.RandomState) -> np.ndarray:
    """
    6. Atmospheric Turbulence-like Distortion: Smooth spatial displacement field.
    Intensity: Warp magnitude in pixels (0 to 10).
    """
    if intensity <= 0.0:
        return frame

    h, w = frame.shape[:2]
    grid_h = max(8, int(h * 0.05))
    grid_w = max(8, int(w * 0.05))

    # Time evolution
    phase = int(t * max(1.0, frequency * 10)) % 100000
    temp_rng = np.random.RandomState(rng.randint(1, 100000) + phase)

    small_dx = temp_rng.randn(grid_h, grid_w).astype(np.float32)
    small_dy = temp_rng.randn(grid_h, grid_w).astype(np.float32)

    dx_field = cv2.resize(small_dx, (w, h), interpolation=cv2.INTER_CUBIC) * intensity
    dy_field = cv2.resize(small_dy, (w, h), interpolation=cv2.INTER_CUBIC) * intensity

    base_x = np.arange(w, dtype=np.float32)[np.newaxis, :].repeat(h, axis=0)
    base_y = np.arange(h, dtype=np.float32)[:, np.newaxis].repeat(w, axis=1)

    map_x = base_x + dx_field
    map_y = base_y + dy_field

    warped = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return warped


def apply_temporary_blur(frame: np.ndarray, t: float, intensity: float,
                         frequency: float,
                         rng: np.random.RandomState) -> np.ndarray:
    """
    7. Temporary Blur: Intermittent optical defocus / motion blur.
    Intensity: Kernel size factor (0 to 15).
    Frequency: Intermittent cycle in Hz.
    """
    if intensity <= 0.0:
        return frame

    # Modulation factor: blur pulses intermittently
    f = max(0.1, frequency)
    pulse = max(0.0, math.sin(2 * math.pi * f * t))
    if pulse < 0.25:
        return frame

    k_size = int(intensity * pulse)
    if k_size % 2 == 0:
        k_size += 1
    k_size = max(1, min(31, k_size))

    if k_size <= 1:
        return frame
    return cv2.GaussianBlur(frame, (k_size, k_size), 0)


def apply_brightness_variation(frame: np.ndarray, t: float, intensity: float,
                               frequency: float,
                               rng: np.random.RandomState) -> np.ndarray:
    """
    8. Brightness Variation: Scintillation and transmission attenuation.
    Intensity: Variance magnitude (0 to 0.8).
    """
    if intensity <= 0.0:
        return frame

    f = max(0.1, frequency)
    mod = 1.0 + intensity * 0.6 * math.sin(2 * math.pi * f * t) + rng.normal(0, intensity * 0.2)
    mod = max(0.15, min(2.2, mod))

    result = np.clip(frame.astype(np.float32) * mod, 0, 255).astype(np.uint8)
    return result


def apply_target_occlusion(frame: np.ndarray, target_fov_pos: Optional[Tuple[float, float]],
                           intensity: float, rng: np.random.RandomState) -> np.ndarray:
    """
    9. Target Occlusion: Synthetic geometric mask occulting the beacon in FOV.
    Intensity: Occlusion opacity and coverage (0.0 to 1.0).
    """
    if intensity <= 0.0 or target_fov_pos is None:
        return frame

    result = frame.copy()
    tx, ty = int(target_fov_pos[0]), int(target_fov_pos[1])
    h, w = frame.shape[:2]

    # Draw dark cloud/occluder over the target region
    r = int(24 * intensity)
    overlay = result.copy()
    cv2.circle(overlay, (tx, ty), r, (15, 12, 10), -1)
    cv2.ellipse(overlay, (tx + 8, ty - 4), (r + 10, r), 25, 0, 360, (20, 18, 15), -1)

    alpha = min(1.0, max(0.0, intensity))
    cv2.addWeighted(overlay, alpha, result, 1.0 - alpha, 0, result)
    return result


def is_random_target_loss_active(t: float, intensity: float, frequency: float,
                                 rng: np.random.RandomState) -> bool:
    """
    10. Random Target Loss: Complete signal blackout / drop.
    Intensity: Drop probability / duration severity (0.0 to 1.0).
    Returns True if target signal is blacked out this instant.
    """
    if intensity <= 0.0:
        return False

    # Periodic probability check
    f = max(0.05, frequency)
    # Cyclical blackout window
    cycle = (t * f) % 1.0
    # Drop window proportional to intensity
    drop_window = intensity * 0.35  # up to 35% of time dropped
    return cycle < drop_window
