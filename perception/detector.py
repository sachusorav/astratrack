"""
ASTRATRACK — Target Detection Facade & Legacy BeaconDetector Adapter

Exposes the unified IDetector interface, ClassicalDetector, AIDetector,
and provides backwards-compatible BeaconDetector adapter for legacy callers.
"""

import cv2
import numpy as np
from typing import Optional, Union

from perception.interface import (
    IDetector, DetectionResult, BoundingBox, DetectionStatus
)
from perception.classical import ClassicalDetector
from perception.ai_detector import AIDetector
from perception.factory import create_detector

# Legacy alias
Detection = DetectionResult


class BeaconDetector(ClassicalDetector):
    """
    Backwards-compatible adapter for legacy BeaconDetector callers.

    Accepts BeaconConfig from core.config and implements IDetector.
    """

    def __init__(self, config=None, min_area: int = 50, **kwargs):
        if config is not None and hasattr(config, "color_hsv_low") and hasattr(config, "color_hsv_high"):
            super().__init__(
                hsv_low=tuple(config.color_hsv_low),
                hsv_high=tuple(config.color_hsv_high),
                min_area=min_area,
                **kwargs
            )
        else:
            super().__init__(min_area=min_area, **kwargs)

    def detect(self, frame: np.ndarray, do_preprocess: bool = True,
               timestamp: Optional[float] = None) -> Optional[DetectionResult]:
        """
        Detect beacon in frame. Returns DetectionResult if found, None if lost (for legacy callers).
        """
        result = super().detect(frame, timestamp=timestamp)
        if result.status == DetectionStatus.LOST or result.center is None:
            return None
        return result


__all__ = [
    "IDetector",
    "DetectionResult",
    "Detection",
    "BoundingBox",
    "DetectionStatus",
    "ClassicalDetector",
    "AIDetector",
    "BeaconDetector",
    "create_detector",
]
