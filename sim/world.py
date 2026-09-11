"""
ASTRATRACK — Virtual World

Manages the simulation world: background, beacons, and rendering.
"""

import cv2
import numpy as np
from core.config import AppConfig
from sim.beacon import Beacon


class World:
    """
    The virtual simulation world containing beacons and background.

    Renders the full world frame each tick, then the VirtualCamera
    crops its FOV from this frame.
    """

    def __init__(self, config: AppConfig):
        """
        Initialize the world with beacons.

        Args:
            config: Full application configuration.
        """
        self.config = config
        self.width = config.world.width
        self.height = config.world.height
        self.bg_color = config.world.background_color
        self.time = 0.0

        # Create beacons
        self.beacons: list[Beacon] = []
        self.add_beacon()

        # Pre-render static background with grid
        self._bg_frame = self._create_background()

    def add_beacon(self) -> Beacon:
        """Add a new beacon to the world and return it."""
        beacon = Beacon(
            config=self.config.beacon,
            world_config=self.config.world,
            beacon_id=len(self.beacons),
        )
        self.beacons.append(beacon)
        return beacon

    def _create_background(self) -> np.ndarray:
        """
        Create a dark background with subtle grid lines.
        Gives the simulation a professional, technical appearance.

        Returns:
            BGR numpy array of the background.
        """
        bg = np.full((self.height, self.width, 3), self.bg_color, dtype=np.uint8)

        # Subtle grid
        grid_color = (20, 20, 45)
        grid_spacing = 100

        for x in range(0, self.width, grid_spacing):
            cv2.line(bg, (x, 0), (x, self.height), grid_color, 1)
        for y in range(0, self.height, grid_spacing):
            cv2.line(bg, (0, y), (self.width, y), grid_color, 1)

        # Center cross
        cx, cy = self.width // 2, self.height // 2
        cross_color = (30, 30, 55)
        cv2.line(bg, (cx - 50, cy), (cx + 50, cy), cross_color, 1)
        cv2.line(bg, (cx, cy - 50), (cx, cy + 50), cross_color, 1)

        return bg

    def tick(self, dt: float, max_accel: float = 0.0):
        """
        Advance the world simulation by one time step.

        Args:
            dt: Time step in seconds.
            max_accel: Target acceleration disturbance parameter.
        """
        self.time += dt
        for beacon in self.beacons:
            beacon.update(dt, max_accel=max_accel)

    def render(self) -> np.ndarray:
        """
        Render the full world frame with all beacons.

        Returns:
            BGR numpy array (world_height × world_width × 3).
        """
        frame = self._bg_frame.copy()

        for beacon in self.beacons:
            beacon.draw(frame)

        return frame

    @property
    def primary_beacon(self) -> Beacon:
        """The primary (first) beacon being tracked."""
        return self.beacons[0]
