"""
ASTRATRACK — Scintillation

Simulates atmospheric scintillation (intensity fluctuations / twinkling)
by applying random brightness modulation to the beacon region of the frame.
"""

import cv2
import numpy as np


def apply_scintillation(frame: np.ndarray, variance: float = 0.1,
                        beacon_mask: np.ndarray = None) -> np.ndarray:
    """
    Apply scintillation (random brightness fluctuation) to the frame.

    If a beacon mask is provided, only the beacon region is affected.
    Otherwise, applies a global multiplicative noise patch.

    Args:
        frame: Input BGR image.
        variance: Scintillation variance (0=off, 0.5=extreme).
        beacon_mask: Optional binary mask of the beacon region.

    Returns:
        Frame with scintillation applied.
    """
    if variance <= 0:
        return frame

    result = frame.astype(np.float32)

    # Generate random multiplicative factor (log-normal like)
    factor = 1.0 + np.random.normal(0, variance)
    factor = max(0.3, min(2.0, factor))  # Clamp to prevent blackout/blowout

    if beacon_mask is not None and beacon_mask.any():
        # Apply only to beacon region
        mask_3ch = np.stack([beacon_mask] * 3, axis=-1).astype(bool)
        result[mask_3ch] *= factor
    else:
        # Apply globally (less realistic but still visually effective)
        result *= factor

    result = np.clip(result, 0, 255).astype(np.uint8)
    return result
