"""
ASTRATRACK — Optical Beacon

Represents a single moving optical beacon/target in the virtual world.
"""

import math
import random
import cv2
import numpy as np
from core.config import BeaconConfig, WorldConfig
from sim.motion_models import MOTION_MODELS, ABSOLUTE_MODELS


class Beacon:
    """
    A single optical beacon that moves through the virtual world.

    The beacon has a position, velocity, visual appearance (with glow),
    and a configurable motion model.
    """

    def __init__(self, config: BeaconConfig, world_config: WorldConfig,
                 beacon_id: int = 0):
        """
        Initialize a beacon at a random position near world center.

        Args:
            config: Beacon configuration parameters.
            world_config: World dimensions for boundary clamping.
            beacon_id: Unique identifier for this beacon.
        """
        self.config = config
        self.world_config = world_config
        self.beacon_id = beacon_id

        # Position — start near center with some randomness
        cx, cy = world_config.width // 2, world_config.height // 2
        self.x = cx + random.randint(-200, 200)
        self.y = cy + random.randint(-150, 150)

        # Velocity (for linear / random_walk models)
        self.vx = 0.0
        self.vy = 0.0

        # Motion model
        self.motion_model_name = config.motion_model
        self.motion_fn = MOTION_MODELS.get(config.motion_model, MOTION_MODELS["sinusoidal"])
        self.is_absolute = config.motion_model in ABSOLUTE_MODELS

        # Motion parameters
        self.speed = config.speed
        self.time = 0.0
        self.direction_deg = random.uniform(0, 360)  # For linear motion

        # Acceleration disturbance state
        self.accel_timer = 0.0
        self.accel_interval = random.uniform(2.0, 5.0)

    def update(self, dt: float, max_accel: float = 0.0):
        """
        Advance the beacon's position by one time step.

        Args:
            dt: Time step in seconds.
            max_accel: Maximum random acceleration (disturbance).
        """
        self.time += dt

        if self.is_absolute:
            # Absolute position models (sinusoidal, orbital)
            center = (self.world_config.width // 2, self.world_config.height // 2)
            result = self.motion_fn(
                t=self.time,
                speed=self.speed,
                center=center,
            )
            self.x, self.y = result
        else:
            # Delta-based models (linear, random_walk)
            result = self.motion_fn(
                t=self.time,
                speed=self.speed,
                angle_deg=self.direction_deg,
                dt=dt,
                pos=(self.x, self.y),
            )
            dx, dy = result

            # Apply acceleration disturbance
            if max_accel > 0:
                self.accel_timer += dt
                if self.accel_timer >= self.accel_interval:
                    self.accel_timer = 0.0
                    self.accel_interval = random.uniform(1.5, 4.0)
                    self.direction_deg += random.uniform(-45, 45)
                    self.speed += random.uniform(-max_accel * 0.3, max_accel * 0.3)
                    self.speed = max(30, min(self.speed, 400))

            self.x += dx * dt
            self.y += dy * dt

        # Boundary bounce / clamp
        self._enforce_bounds()

    def _enforce_bounds(self):
        """Keep beacon within world boundaries, bouncing off edges."""
        margin = self.config.radius + 20
        w, h = self.world_config.width, self.world_config.height

        if self.x < margin:
            self.x = margin
            self.direction_deg = 180 - self.direction_deg
        elif self.x > w - margin:
            self.x = w - margin
            self.direction_deg = 180 - self.direction_deg

        if self.y < margin:
            self.y = margin
            self.direction_deg = -self.direction_deg
        elif self.y > h - margin:
            self.y = h - margin
            self.direction_deg = -self.direction_deg

    def draw(self, frame: np.ndarray):
        """
        Draw the beacon onto the world frame with a glow effect.

        Args:
            frame: World image (BGR numpy array) to draw onto.
        """
        cx, cy = int(self.x), int(self.y)

        # Outer glow (larger, semi-transparent circle)
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), self.config.glow_radius,
                   self.config.glow_color_bgr, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

        # Inner beacon (solid bright circle)
        cv2.circle(frame, (cx, cy), self.config.radius,
                   self.config.color_bgr, -1, cv2.LINE_AA)

        # Bright center spot
        cv2.circle(frame, (cx, cy), max(3, self.config.radius // 3),
                   (200, 255, 200), -1, cv2.LINE_AA)

    @property
    def position(self) -> tuple:
        """Current (x, y) position."""
        return (self.x, self.y)

    def set_motion_model(self, model_name: str):
        """Switch motion model at runtime."""
        if model_name in MOTION_MODELS:
            self.motion_model_name = model_name
            self.motion_fn = MOTION_MODELS[model_name]
            self.is_absolute = model_name in ABSOLUTE_MODELS
