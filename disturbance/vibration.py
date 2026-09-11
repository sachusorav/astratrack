"""
ASTRATRACK — Platform Vibration

Simulates platform vibration (ship/UAV sway) by injecting sinusoidal +
random jitter into the camera's pan/tilt angles.
"""

import math
import random


def compute_vibration(time: float, amplitude_deg: float = 0.5,
                      frequency: float = 5.0) -> tuple:
    """
    Compute vibration-induced camera jitter for the current frame.

    Combines deterministic sinusoidal vibration with random band-limited noise.

    Args:
        time: Current simulation time (seconds).
        amplitude_deg: Peak vibration amplitude in degrees.
        frequency: Primary vibration frequency in Hz.

    Returns:
        (jitter_x, jitter_y) in pixels (pre-converted from degrees).
    """
    if amplitude_deg <= 0:
        return (0.0, 0.0)

    # Deterministic sinusoidal component (multi-frequency)
    sin_x = (
        amplitude_deg * 0.6 * math.sin(2 * math.pi * frequency * time) +
        amplitude_deg * 0.3 * math.sin(2 * math.pi * frequency * 1.7 * time + 0.5) +
        amplitude_deg * 0.1 * math.sin(2 * math.pi * frequency * 3.1 * time + 1.2)
    )
    sin_y = (
        amplitude_deg * 0.5 * math.sin(2 * math.pi * frequency * 0.8 * time + 0.3) +
        amplitude_deg * 0.35 * math.sin(2 * math.pi * frequency * 2.3 * time + 0.8) +
        amplitude_deg * 0.15 * math.sin(2 * math.pi * frequency * 4.0 * time + 2.0)
    )

    # Random component (band-limited white noise)
    rand_x = random.gauss(0, amplitude_deg * 0.3)
    rand_y = random.gauss(0, amplitude_deg * 0.3)

    # Convert degrees to pixels (using default 0.1 deg/px → 10 px/deg)
    scale = 10.0  # pixels per degree
    jitter_x = (sin_x + rand_x) * scale
    jitter_y = (sin_y + rand_y) * scale

    return (jitter_x, jitter_y)
