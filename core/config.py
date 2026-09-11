"""
ASTRATRACK — Application Configuration

Central configuration using dataclasses. All tunable parameters live here.
Can be loaded from a YAML file or constructed with defaults.
"""

from dataclasses import dataclass, field
from typing import Optional
import yaml
import os


@dataclass
class WorldConfig:
    """Virtual world dimensions and appearance."""
    width: int = 1600          # World width in pixels
    height: int = 1200         # World height in pixels
    background_color: tuple = (10, 10, 30)  # Dark blue-black (BGR)


@dataclass
class BeaconConfig:
    """Optical beacon parameters."""
    radius: int = 12                       # Beacon radius in pixels
    color_bgr: tuple = (0, 255, 100)       # Bright green (BGR)
    color_hsv_low: tuple = (35, 100, 100)  # HSV lower bound for detection
    color_hsv_high: tuple = (85, 255, 255) # HSV upper bound for detection
    glow_radius: int = 25                  # Outer glow radius
    glow_color_bgr: tuple = (0, 180, 60)   # Glow color (BGR)
    speed: float = 120.0                   # Base speed in pixels/second
    motion_model: str = "sinusoidal"       # Default: linear, sinusoidal, random_walk, orbital


@dataclass
class CameraConfig:
    """Virtual camera parameters."""
    fov_width: int = 640       # Camera field-of-view width in pixels
    fov_height: int = 480      # Camera field-of-view height in pixels
    initial_pan: float = 0.0   # Initial pan angle (degrees)
    initial_tilt: float = 0.0  # Initial tilt angle (degrees)
    max_pan: float = 80.0      # Max pan angle (±degrees)
    max_tilt: float = 60.0     # Max tilt angle (±degrees)
    max_slew_rate: float = 8.0 # Max angular velocity (degrees/frame)
    inertia: float = 0.85      # Smoothing factor (0=instant, 1=no movement)
    deg_per_pixel: float = 0.1 # Conversion factor: degrees per world pixel


@dataclass
class PIDConfig:
    """PID controller gains."""
    kp: float = 0.40           # Proportional gain
    ki: float = 0.010          # Integral gain
    kd: float = 0.10           # Derivative gain
    integral_limit: float = 100.0  # Anti-windup integral clamp
    dead_zone: float = 2.0     # Error dead zone in pixels
    output_limit: float = 10.0 # Max output (degrees/frame)


@dataclass
class KalmanConfig:
    """Kalman filter tuning."""
    process_noise: float = 1e-2   # Q matrix diagonal scale
    measurement_noise: float = 5.0 # R matrix diagonal value
    initial_covariance: float = 1.0 # P0 diagonal
    coast_limit: int = 60          # Max frames to coast without measurement
    prediction_horizon: int = 30   # Frames to predict ahead


@dataclass
class DisturbanceConfig:
    """Disturbance model parameters."""
    # Atmospheric turbulence (Perlin warp)
    turbulence_strength: float = 0.0   # Warp magnitude (0=off, 10=extreme)
    turbulence_scale: float = 0.01     # Spatial frequency of noise

    # Platform vibration
    vibration_amplitude: float = 0.0   # Degrees of camera jitter
    vibration_frequency: float = 5.0   # Hz

    # Image noise
    noise_sigma: float = 0.0          # Gaussian noise std dev (0–50)
    salt_pepper_density: float = 0.0  # Salt-and-pepper noise density (0–0.05)

    # Scintillation
    scintillation_variance: float = 0.0  # Brightness fluctuation (0–0.5)

    # Target acceleration
    target_max_accel: float = 0.0      # Max sudden acceleration (px/s²)


@dataclass
class UIConfig:
    """UI layout and appearance."""
    window_width: int = 1280
    window_height: int = 800
    viewport_width: int = 640
    viewport_height: int = 480
    plot_history: int = 300         # Number of data points in rolling plot
    update_rate: float = 60.0       # Target FPS


@dataclass
class AppConfig:
    """Top-level application configuration."""
    world: WorldConfig = field(default_factory=WorldConfig)
    beacon: BeaconConfig = field(default_factory=BeaconConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    pid: PIDConfig = field(default_factory=PIDConfig)
    kalman: KalmanConfig = field(default_factory=KalmanConfig)
    disturbance: DisturbanceConfig = field(default_factory=DisturbanceConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def load_config(path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from a YAML file, falling back to defaults.

    Args:
        path: Path to YAML config file. If None, returns default config.

    Returns:
        AppConfig instance with all parameters.
    """
    config = AppConfig()

    if path and os.path.exists(path):
        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}

        # Merge YAML values into config dataclasses
        for section_name, section_data in data.items():
            if hasattr(config, section_name) and isinstance(section_data, dict):
                section = getattr(config, section_name)
                for key, value in section_data.items():
                    if hasattr(section, key):
                        # Convert lists to tuples for color fields
                        if isinstance(value, list):
                            value = tuple(value)
                        setattr(section, key, value)

    return config
