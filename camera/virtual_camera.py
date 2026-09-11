"""
ASTRATRACK — Virtual Camera & Actuator Dynamics

Simulates a pan/tilt camera with a bounded field of view (FOV).
Crops the world frame to produce the camera's view and models
physical constraints like angular rate limits, inertia smoothing,
and real-time rate telemetry.
"""

from typing import Tuple, Optional
import cv2
import numpy as np
from core.config import CameraConfig, WorldConfig
from core.math_utils import clamp


class VirtualCamera:
    """
    A virtual pan/tilt camera that views a portion of the world.

    Computes:
        horizontal_error = target_x - camera_center_x
        vertical_error   = target_y - camera_center_y
    and actuates according to pan_command and tilt_command with
    configurable slew rate limits, dead zone, and smoothing.
    """

    def __init__(self, camera_config: CameraConfig, world_config: WorldConfig):
        """
        Initialize the camera centered on the world.

        Args:
            camera_config: Camera parameters (FOV size, slew rate, etc.).
            world_config: World dimensions for coordinate mapping.
        """
        self.config = camera_config
        self.world_config = world_config

        # Camera state: position in world pixels (center of FOV)
        self.center_x = world_config.width / 2.0
        self.center_y = world_config.height / 2.0

        # Pan/tilt angles (degrees)
        self.pan = camera_config.initial_pan
        self.tilt = camera_config.initial_tilt

        # Configurable actuator dynamics
        self.max_angular_velocity = float(getattr(camera_config, "max_slew_rate", 8.0))
        self.smoothing = float(getattr(camera_config, "inertia", 0.85))
        self.dead_zone = 0.0

        # Smoothed velocity (pixels/frame)
        self._vel_x = 0.0
        self._vel_y = 0.0

        # Real-time rates (degrees/second)
        self.pan_rate = 0.0
        self.tilt_rate = 0.0

        # Last tracking error & command cache
        self.last_pan_error_deg = 0.0
        self.last_tilt_error_deg = 0.0
        self.last_pan_error_px = 0.0
        self.last_tilt_error_px = 0.0
        self.last_control_output: Tuple[float, float] = (0.0, 0.0)

        # FOV dimensions
        self.fov_w = camera_config.fov_width
        self.fov_h = camera_config.fov_height

    def compute_tracking_error(self, target_world_pos: Tuple[float, float]) -> Tuple[float, float, float, float]:
        """
        Compute horizontal and vertical tracking error:
            target_position - camera_center

        Args:
            target_world_pos: Target (x, y) in world coordinates.

        Returns:
            (pan_error_deg, tilt_error_deg, pan_error_px, tilt_error_px)
        """
        err_x_px = target_world_pos[0] - self.center_x
        err_y_px = target_world_pos[1] - self.center_y

        deg_per_px = self.config.deg_per_pixel
        err_pan_deg = err_x_px * deg_per_px
        err_tilt_deg = err_y_px * deg_per_px

        self.last_pan_error_px = err_x_px
        self.last_tilt_error_px = err_y_px
        self.last_pan_error_deg = err_pan_deg
        self.last_tilt_error_deg = err_tilt_deg

        return err_pan_deg, err_tilt_deg, err_x_px, err_y_px

    def actuate(self, delta_pan: float, delta_tilt: float, dt: float = 0.02):
        """
        Apply pan/tilt rate commands to the camera.
        Models inertia, dead zone, and slew rate limits.

        Args:
            delta_pan: Desired pan command (degrees/frame or degrees).
            delta_tilt: Desired tilt command (degrees/frame or degrees).
            dt: Time step in seconds.
        """
        max_slew = self.max_angular_velocity
        smoothing = self.smoothing
        deg_per_px = self.config.deg_per_pixel

        self.last_control_output = (float(delta_pan), float(delta_tilt))

        # Dead zone check on commands
        cmd_pan = 0.0 if abs(delta_pan) < self.dead_zone else delta_pan
        cmd_tilt = 0.0 if abs(delta_tilt) < self.dead_zone else delta_tilt

        # Convert degree commands to pixel commands clamped to max angular velocity
        cmd_x = clamp(cmd_pan, -max_slew, max_slew) / deg_per_px
        cmd_y = clamp(cmd_tilt, -max_slew, max_slew) / deg_per_px

        # Apply inertia smoothing
        self._vel_x = smoothing * self._vel_x + (1.0 - smoothing) * cmd_x
        self._vel_y = smoothing * self._vel_y + (1.0 - smoothing) * cmd_y

        # Update real-time rates (degrees/second)
        effective_dt = max(1e-4, dt)
        self.pan_rate = (self._vel_x * deg_per_px) / effective_dt
        self.tilt_rate = (self._vel_y * deg_per_px) / effective_dt

        # Update camera center position
        self.center_x += self._vel_x
        self.center_y += self._vel_y

        # Clamp to world bounds (ensure FOV stays inside the world)
        half_w = self.fov_w / 2.0
        half_h = self.fov_h / 2.0
        self.center_x = clamp(self.center_x, half_w, self.world_config.width - half_w)
        self.center_y = clamp(self.center_y, half_h, self.world_config.height - half_h)

        # Update angles for display purposes
        world_cx = self.world_config.width / 2.0
        world_cy = self.world_config.height / 2.0
        self.pan = (self.center_x - world_cx) * deg_per_px
        self.tilt = (self.center_y - world_cy) * deg_per_px

    def add_jitter(self, jitter_x: float, jitter_y: float):
        """
        Add vibration/jitter to camera position (disturbance injection point).

        Args:
            jitter_x: Horizontal jitter in pixels.
            jitter_y: Vertical jitter in pixels.
        """
        self.center_x += jitter_x
        self.center_y += jitter_y

        # Re-clamp
        half_w = self.fov_w / 2.0
        half_h = self.fov_h / 2.0
        self.center_x = clamp(self.center_x, half_w, self.world_config.width - half_w)
        self.center_y = clamp(self.center_y, half_h, self.world_config.height - half_h)

    def capture(self, world_frame: np.ndarray) -> np.ndarray:
        """
        Crop the camera's FOV from the full world frame.

        Args:
            world_frame: Full world image (BGR numpy array).

        Returns:
            Cropped FOV image (fov_height × fov_width × 3).
        """
        x1 = int(self.center_x - self.fov_w / 2)
        y1 = int(self.center_y - self.fov_h / 2)
        x2 = x1 + self.fov_w
        y2 = y1 + self.fov_h

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(world_frame.shape[1], x2)
        y2 = min(world_frame.shape[0], y2)

        cropped = world_frame[y1:y2, x1:x2].copy()

        if cropped.shape[0] != self.fov_h or cropped.shape[1] != self.fov_w:
            padded = np.zeros((self.fov_h, self.fov_w, 3), dtype=np.uint8)
            ph, pw = cropped.shape[:2]
            padded[:ph, :pw] = cropped
            cropped = padded

        return cropped

    @property
    def fov_rect(self) -> tuple:
        """(x1, y1, x2, y2) in world coordinates."""
        x1 = int(self.center_x - self.fov_w / 2)
        y1 = int(self.center_y - self.fov_h / 2)
        return (x1, y1, x1 + self.fov_w, y1 + self.fov_h)

    @property
    def fov_center(self) -> tuple:
        """Center of the FOV in FOV-local pixel coordinates."""
        return (self.fov_w // 2, self.fov_h // 2)

    def world_to_fov(self, world_x: float, world_y: float) -> tuple:
        """Convert world coordinates to FOV-local pixel coordinates."""
        fov_x = world_x - (self.center_x - self.fov_w / 2.0)
        fov_y = world_y - (self.center_y - self.fov_h / 2.0)
        return (fov_x, fov_y)

    def fov_to_world(self, fov_x: float, fov_y: float) -> tuple:
        """Convert FOV-local coordinates to world coordinates."""
        world_x = fov_x + (self.center_x - self.fov_w / 2.0)
        world_y = fov_y + (self.center_y - self.fov_h / 2.0)
        return (world_x, world_y)

    def reset(self):
        """Reset camera position, angles, velocities, and telemetry."""
        self.center_x = self.world_config.width / 2.0
        self.center_y = self.world_config.height / 2.0
        self.pan = self.config.initial_pan
        self.tilt = self.config.initial_tilt
        self._vel_x = 0.0
        self._vel_y = 0.0
        self.pan_rate = 0.0
        self.tilt_rate = 0.0
        self.last_pan_error_deg = 0.0
        self.last_tilt_error_deg = 0.0
        self.last_pan_error_px = 0.0
        self.last_tilt_error_px = 0.0
        self.last_control_output = (0.0, 0.0)
