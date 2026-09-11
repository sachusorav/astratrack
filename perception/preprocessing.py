"""
ASTRATRACK — Image Preprocessing

Pre-processing steps applied to the camera FOV frame before detection.
Improves robustness under noise and varying illumination.
"""

import cv2
import numpy as np


def preprocess(frame: np.ndarray, blur_kernel: int = 5,
               use_clahe: bool = True) -> np.ndarray:
    """
    Apply preprocessing to improve beacon detection under noise.

    Steps:
        1. Gaussian blur to reduce high-frequency noise.
        2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
           to normalize brightness.

    Args:
        frame: Input BGR image.
        blur_kernel: Gaussian blur kernel size (must be odd).
        use_clahe: Whether to apply CLAHE.

    Returns:
        Preprocessed BGR image.
    """
    # Gaussian blur
    if blur_kernel > 1:
        frame = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)

    # CLAHE on the L channel in LAB color space
    if use_clahe:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        lab = cv2.merge([l_channel, a_channel, b_channel])
        frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return frame
