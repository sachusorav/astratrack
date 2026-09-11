"""
ASTRATRACK — Atmospheric Turbulence Simulation

Simulates Kolmogorov-like atmospheric turbulence by applying a smooth
displacement field to warp the image geometrically (like atmospheric seeing).

Uses downsampled noise + bicubic upscale for performance (no per-pixel loops).
"""

import cv2
import numpy as np

# Try to import noise library for better quality; fall back gracefully
try:
    from noise import pnoise2
    HAS_PERLIN = True
except ImportError:
    HAS_PERLIN = False


def _generate_displacement_field(h: int, w: int, strength: float,
                                  scale: float, time: float) -> tuple:
    """
    Generate smooth displacement fields for turbulence warping.

    Uses a small random noise grid upsampled with bicubic interpolation
    for smooth, performant spatial distortion. Time-varying via seed.

    Args:
        h: Frame height.
        w: Frame width.
        strength: Warp magnitude in pixels.
        scale: Spatial frequency (higher = finer detail).
        time: Current time (for evolving the field).

    Returns:
        (dx_field, dy_field) — float32 arrays of shape (h, w).
    """
    # Downsampled grid size (small enough for speed, big enough for smooth result)
    grid_h = max(8, int(h * scale * 5))
    grid_w = max(8, int(w * scale * 5))

    # Time-varying seed for animation
    seed_x = int(time * 100) % (2**31 - 1)
    seed_y = int(time * 100 + 50000) % (2**31 - 1)

    rng_x = np.random.RandomState(seed_x)
    rng_y = np.random.RandomState(seed_y)

    # Generate small noise fields
    small_dx = rng_x.randn(grid_h, grid_w).astype(np.float32)
    small_dy = rng_y.randn(grid_h, grid_w).astype(np.float32)

    # Upscale with bicubic interpolation for smooth spatial variation
    dx_field = cv2.resize(small_dx, (w, h), interpolation=cv2.INTER_CUBIC) * strength
    dy_field = cv2.resize(small_dy, (w, h), interpolation=cv2.INTER_CUBIC) * strength

    return dx_field, dy_field


def apply_turbulence(frame: np.ndarray, strength: float = 3.0,
                     scale: float = 0.01, time: float = 0.0) -> np.ndarray:
    """
    Apply atmospheric turbulence distortion to an image.

    Uses a smooth displacement field to warp pixel positions,
    simulating wavefront distortion from Kolmogorov-like turbulence.

    Args:
        frame: Input BGR image.
        strength: Warp magnitude in pixels (0=off, 10=extreme).
        scale: Spatial frequency of the noise pattern.
        time: Current simulation time (evolves the noise field).

    Returns:
        Turbulence-distorted BGR image.
    """
    if strength <= 0:
        return frame

    h, w = frame.shape[:2]

    # Generate displacement fields
    dx_field, dy_field = _generate_displacement_field(h, w, strength, scale, time)

    # Create remap coordinates: base grid + displacement
    base_x = np.arange(w, dtype=np.float32)[np.newaxis, :].repeat(h, axis=0)
    base_y = np.arange(h, dtype=np.float32)[:, np.newaxis].repeat(w, axis=1)

    map_x = base_x + dx_field
    map_y = base_y + dy_field

    # Apply warping
    warped = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_REFLECT)

    return warped
