"""
ASTRATRACK — Math Utilities

Shared math functions: angle wrapping, coordinate conversions, distances.
"""

import math
import numpy as np


def angle_wrap(angle: float, limit: float = 180.0) -> float:
    """
    Wrap an angle to the range [-limit, +limit].

    Args:
        angle: Angle in degrees.
        limit: Wrapping bound (default ±180°).

    Returns:
        Wrapped angle in degrees.
    """
    while angle > limit:
        angle -= 2 * limit
    while angle < -limit:
        angle += 2 * limit
    return angle


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min_val and max_val."""
    return max(min_val, min(max_val, value))


def euclidean_dist(p1: tuple, p2: tuple) -> float:
    """
    Euclidean distance between two 2D points.

    Args:
        p1: (x1, y1)
        p2: (x2, y2)

    Returns:
        Distance in pixels.
    """
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def px_to_deg(px_offset: float, deg_per_pixel: float = 0.1) -> float:
    """
    Convert pixel offset to angular offset in degrees.

    Args:
        px_offset: Offset in pixels.
        deg_per_pixel: Conversion factor.

    Returns:
        Angular offset in degrees.
    """
    return px_offset * deg_per_pixel


def deg_to_px(deg_offset: float, deg_per_pixel: float = 0.1) -> float:
    """
    Convert angular offset to pixel offset.

    Args:
        deg_offset: Offset in degrees.
        deg_per_pixel: Conversion factor.

    Returns:
        Pixel offset.
    """
    return deg_offset / deg_per_pixel if deg_per_pixel != 0 else 0.0


def normalize_angle(angle: float) -> float:
    """Normalize angle to [-180, 180] range."""
    return ((angle + 180) % 360) - 180


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by factor t."""
    return a + (b - a) * t
