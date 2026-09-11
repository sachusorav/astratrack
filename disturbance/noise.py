"""
ASTRATRACK — Image Noise

Adds sensor noise to the camera FOV frame.
Supports Gaussian noise and salt-and-pepper noise.
"""

import cv2
import numpy as np


def apply_gaussian_noise(frame: np.ndarray, sigma: float = 15.0) -> np.ndarray:
    """
    Add Gaussian noise to every pixel.

    Args:
        frame: Input BGR image.
        sigma: Standard deviation of noise (0 = no noise, 50 = heavy).

    Returns:
        Noisy BGR image.
    """
    if sigma <= 0:
        return frame

    noise = np.random.normal(0, sigma, frame.shape).astype(np.float32)
    noisy = frame.astype(np.float32) + noise
    noisy = np.clip(noisy, 0, 255).astype(np.uint8)
    return noisy


def apply_salt_pepper(frame: np.ndarray, density: float = 0.01) -> np.ndarray:
    """
    Add salt-and-pepper noise.

    Args:
        frame: Input BGR image.
        density: Fraction of pixels affected (0–0.05 typical).

    Returns:
        Noisy BGR image.
    """
    if density <= 0:
        return frame

    result = frame.copy()
    h, w = frame.shape[:2]
    num_pixels = int(h * w * density)

    # Salt (white)
    salt_coords = (
        np.random.randint(0, h, num_pixels),
        np.random.randint(0, w, num_pixels),
    )
    result[salt_coords] = 255

    # Pepper (black)
    pepper_coords = (
        np.random.randint(0, h, num_pixels),
        np.random.randint(0, w, num_pixels),
    )
    result[pepper_coords] = 0

    return result
