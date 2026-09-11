"""
ASTRATRACK — Motion Models

Pluggable motion functions for optical beacons.
Each function takes current state and returns (dx, dy) displacement per tick.
"""

import math
import random
import numpy as np


def linear(t: float, speed: float, angle_deg: float = 45.0,
           bounds: tuple = None, pos: tuple = (0, 0), **kwargs) -> tuple:
    """
    Constant-velocity linear motion at a fixed angle.
    Bounces off world boundaries.

    Args:
        t: Current time (seconds).
        speed: Speed in pixels/second.
        angle_deg: Direction of motion in degrees.
        bounds: (width, height) of the world.
        pos: Current (x, y) position.

    Returns:
        (dx, dy) displacement this tick.
    """
    angle_rad = math.radians(angle_deg)
    dx = speed * math.cos(angle_rad)
    dy = speed * math.sin(angle_rad)
    return dx, dy


def sinusoidal(t: float, speed: float, amplitude: float = 200.0,
               freq_x: float = 0.3, freq_y: float = 0.5,
               center: tuple = (800, 600), **kwargs) -> tuple:
    """
    Lissajous / sinusoidal motion pattern.
    Returns absolute target position (used differently — see Beacon).

    Args:
        t: Current time (seconds).
        speed: Not used directly (amplitude controls range).
        amplitude: Oscillation amplitude in pixels.
        freq_x: X-axis frequency in Hz.
        freq_y: Y-axis frequency in Hz.
        center: Center of oscillation (x, y).

    Returns:
        (target_x, target_y) — absolute position.
    """
    x = center[0] + amplitude * math.sin(2 * math.pi * freq_x * t)
    y = center[1] + amplitude * math.sin(2 * math.pi * freq_y * t + math.pi / 3)
    return x, y


def random_walk(t: float, speed: float, dt: float = 1 / 60,
                pos: tuple = (0, 0), **kwargs) -> tuple:
    """
    Brownian-motion-like random walk.

    Args:
        t: Current time (seconds).
        speed: Step size scale.
        dt: Time step.
        pos: Current position (unused, included for interface).

    Returns:
        (dx, dy) displacement this tick.
    """
    dx = random.gauss(0, speed * dt * 2)
    dy = random.gauss(0, speed * dt * 2)
    return dx, dy


def orbital(t: float, speed: float, radius: float = 250.0,
            center: tuple = (800, 600), omega: float = 0.5, **kwargs) -> tuple:
    """
    Circular orbital motion around a center point.

    Args:
        t: Current time (seconds).
        speed: Not used directly (omega controls speed).
        radius: Orbit radius in pixels.
        center: Center of orbit (x, y).
        omega: Angular velocity in rad/s.

    Returns:
        (target_x, target_y) — absolute position.
    """
    x = center[0] + radius * math.cos(omega * t)
    y = center[1] + radius * math.sin(omega * t)
    return x, y


def static_motion(t: float, speed: float = 0.0, pos: tuple = (0, 0), **kwargs) -> tuple:
    """
    Static stationary target (zero displacement).

    Args:
        t: Current time (seconds).
        speed: Unused.
        pos: Current (x, y) position.

    Returns:
        (0.0, 0.0) displacement.
    """
    return 0.0, 0.0


# Registry of available motion models
MOTION_MODELS = {
    "static": static_motion,
    "linear": linear,
    "sinusoidal": sinusoidal,
    "random_walk": random_walk,
    "orbital": orbital,
}

# Models that return absolute position (vs. delta)
ABSOLUTE_MODELS = {"sinusoidal", "orbital"}
