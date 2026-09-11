"""
ASTRATRACK — 3D Target / Optical Beacon Model

Represents a moving optical beacon in 3D space with configurable
position, velocity, acceleration, and trajectory patterns.

Supports deterministic mode via fixed random seed.
"""

import math
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TrajectoryType(Enum):
    """Supported trajectory patterns for the optical beacon."""
    STATIC = "static"
    LINEAR = "linear"
    SINUSOIDAL = "sinusoidal"
    ORBITAL = "orbital"
    FIGURE_EIGHT = "figure_eight"
    ACCELERATING = "accelerating"
    RANDOM_WALK = "random_walk"


@dataclass
class TargetConfig:
    """Full configuration for a 3D target."""
    initial_position: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 300.0, 500.0]))
    initial_velocity: np.ndarray = field(
        default_factory=lambda: np.zeros(3))
    acceleration: np.ndarray = field(
        default_factory=lambda: np.zeros(3))
    trajectory_type: TrajectoryType = TrajectoryType.SINUSOIDAL
    speed: float = 50.0
    orbit_radius: float = 200.0
    orbit_center: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 300.0, 500.0]))
    amplitude: np.ndarray = field(
        default_factory=lambda: np.array([200.0, 50.0, 150.0]))
    frequency: np.ndarray = field(
        default_factory=lambda: np.array([0.15, 0.2, 0.1]))
    noise_sigma: float = 0.0
    max_accel: float = 0.0
    # Deterministic mode seed (None = non-deterministic)
    random_seed: Optional[int] = None


class Target3D:
    """
    A 3D optical beacon that moves through space.

    Manages its own kinematics, trajectory history, and random state.
    Supports multiple trajectory types and deterministic replay.
    """

    MAX_TRAIL = 600  # Maximum trajectory history length

    def __init__(self, config: TargetConfig):
        self.config = config
        self.position = config.initial_position.copy().astype(np.float64)
        self.velocity = config.initial_velocity.copy().astype(np.float64)
        self.acceleration = config.acceleration.copy().astype(np.float64)
        self.time: float = 0.0
        self.trajectory_history: List[np.ndarray] = []

        # Independent RNG for deterministic mode
        self._rng = np.random.RandomState(config.random_seed)

        # Random walk state
        self._walk_dir = self._rng.randn(3)
        self._walk_dir /= np.linalg.norm(self._walk_dir) + 1e-10
        self._walk_timer: float = 0.0

        # Visibility flag (for target-loss scenarios)
        self.visible: bool = True
        self._occlusion_timer: float = 0.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def update(self, dt: float):
        """Advance the target by one time step."""
        self.time += dt

        dispatch = {
            TrajectoryType.STATIC: self._update_static,
            TrajectoryType.LINEAR: self._update_linear,
            TrajectoryType.SINUSOIDAL: self._update_sinusoidal,
            TrajectoryType.ORBITAL: self._update_orbital,
            TrajectoryType.FIGURE_EIGHT: self._update_figure_eight,
            TrajectoryType.ACCELERATING: self._update_accelerating,
            TrajectoryType.RANDOM_WALK: self._update_random_walk,
        }
        updater = dispatch.get(self.config.trajectory_type, self._update_static)
        updater(dt)

        # Position noise injection
        if self.config.noise_sigma > 0:
            noise = self._rng.normal(0, self.config.noise_sigma, 3)
            self.position = self.position + noise

        # Record trail
        self.trajectory_history.append(self.position.copy())
        if len(self.trajectory_history) > self.MAX_TRAIL:
            self.trajectory_history = self.trajectory_history[-self.MAX_TRAIL:]

    def reset(self):
        """Reset target to initial configuration."""
        self.position = self.config.initial_position.copy().astype(np.float64)
        self.velocity = self.config.initial_velocity.copy().astype(np.float64)
        self.acceleration = self.config.acceleration.copy().astype(np.float64)
        self.time = 0.0
        self.trajectory_history.clear()
        self.visible = True
        self._occlusion_timer = 0.0
        self._rng = np.random.RandomState(self.config.random_seed)
        self._walk_dir = self._rng.randn(3)
        self._walk_dir /= np.linalg.norm(self._walk_dir) + 1e-10
        self._walk_timer = 0.0

    @property
    def speed_magnitude(self) -> float:
        """Current speed (magnitude of velocity vector)."""
        return float(np.linalg.norm(self.velocity))

    # ------------------------------------------------------------------ #
    # Trajectory Implementations
    # ------------------------------------------------------------------ #

    def _update_static(self, dt: float):
        """No movement — beacon holds position."""
        pass

    def _update_linear(self, dt: float):
        """Constant-velocity straight-line motion."""
        self.velocity = self.velocity + self.acceleration * dt
        self.position = self.position + self.velocity * dt

    def _update_sinusoidal(self, dt: float):
        """3D Lissajous / sinusoidal pattern."""
        t = self.time
        amp = self.config.amplitude
        freq = self.config.frequency
        center = self.config.orbit_center

        prev = self.position.copy()
        self.position = np.array([
            center[0] + amp[0] * math.sin(2 * math.pi * freq[0] * t),
            center[1] + amp[1] * math.sin(2 * math.pi * freq[1] * t + math.pi / 3),
            center[2] + amp[2] * math.sin(2 * math.pi * freq[2] * t + math.pi / 5),
        ], dtype=np.float64)
        self.velocity = (self.position - prev) / max(dt, 1e-6)

    def _update_orbital(self, dt: float):
        """Circular orbit in the XZ plane at fixed altitude."""
        t = self.time
        r = self.config.orbit_radius
        center = self.config.orbit_center
        omega = self.config.speed / max(r, 1.0)

        prev = self.position.copy()
        self.position = np.array([
            center[0] + r * math.cos(omega * t),
            center[1],
            center[2] + r * math.sin(omega * t),
        ], dtype=np.float64)
        self.velocity = (self.position - prev) / max(dt, 1e-6)

    def _update_figure_eight(self, dt: float):
        """Figure-8 trajectory in 3D space."""
        t = self.time
        r = self.config.orbit_radius
        center = self.config.orbit_center
        omega = self.config.speed / max(r, 1.0) * 0.5

        prev = self.position.copy()
        self.position = np.array([
            center[0] + r * math.sin(omega * t),
            center[1] + r * 0.3 * math.sin(2 * omega * t),
            center[2] + r * math.sin(omega * t) * math.cos(omega * t),
        ], dtype=np.float64)
        self.velocity = (self.position - prev) / max(dt, 1e-6)

    def _update_accelerating(self, dt: float):
        """Target with increasing velocity."""
        accel_mag = self.config.max_accel if self.config.max_accel > 0 else 15.0

        # Time-varying acceleration direction
        direction = np.array([
            math.sin(self.time * 0.15),
            0.05 * math.cos(self.time * 0.08),
            math.cos(self.time * 0.15),
        ], dtype=np.float64)
        direction = direction / (np.linalg.norm(direction) + 1e-10)

        # Pulsating acceleration magnitude
        mag = accel_mag * (1.0 + 0.5 * math.sin(self.time * 0.3))
        self.acceleration = direction * mag
        self.velocity = self.velocity + self.acceleration * dt

        # Speed clamp
        speed = np.linalg.norm(self.velocity)
        if speed > 500:
            self.velocity = self.velocity / speed * 500.0

        self.position = self.position + self.velocity * dt

    def _update_random_walk(self, dt: float):
        """Brownian-motion random walk with momentum."""
        self._walk_timer += dt

        # Periodically change direction
        if self._walk_timer > 0.8 + self._rng.uniform(0, 1.5):
            self._walk_timer = 0.0
            perturbation = self._rng.randn(3) * 0.6
            self._walk_dir = self._walk_dir + perturbation
            norm = np.linalg.norm(self._walk_dir)
            if norm > 1e-10:
                self._walk_dir = self._walk_dir / norm

        speed = self.config.speed
        jitter = self._rng.randn(3) * speed * 0.08
        self.velocity = self._walk_dir * speed + jitter
        self.position = self.position + self.velocity * dt

        # Soft boundary enforcement
        center = self.config.orbit_center
        for i in range(3):
            dist_from_center = self.position[i] - center[i]
            if abs(dist_from_center) > 600:
                self._walk_dir[i] = -abs(self._walk_dir[i]) * np.sign(dist_from_center)
                self.position[i] = center[i] + np.clip(dist_from_center, -600, 600)
