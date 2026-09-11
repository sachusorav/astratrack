"""
ASTRATRACK — Target Detection Interface & Data Structures

Defines the common detection contract, status codes, bounding boxes,
and detection results shared across classical and AI detection backends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple
import time
import numpy as np


class DetectionStatus(Enum):
    """Detection tracking status code."""
    DETECTED = "DETECTED"          # Target positively detected above threshold
    DEGRADED = "DEGRADED"          # Low confidence / high noise detection
    OCCLUDED = "OCCLUDED"          # Target partially or fully occluded
    LOST = "LOST"                  # No target detected in frame


@dataclass
class BoundingBox:
    """2D Bounding Box in image pixel coordinates."""
    x: float        # Top-left x
    y: float        # Top-left y
    w: float        # Box width
    h: float        # Box height

    @property
    def xmin(self) -> float:
        return self.x

    @property
    def ymin(self) -> float:
        return self.y

    @property
    def xmax(self) -> float:
        return self.x + self.w

    @property
    def ymax(self) -> float:
        return self.y + self.h

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.w * 0.5, self.y + self.h * 0.5)

    @property
    def area(self) -> float:
        return max(0.0, self.w * self.h)

    @property
    def aspect_ratio(self) -> float:
        return self.w / max(1e-6, self.h)

    def as_xyxy(self) -> Tuple[float, float, float, float]:
        """Return (xmin, ymin, xmax, ymax)."""
        return (self.xmin, self.ymin, self.xmax, self.ymax)

    def as_xywh(self) -> Tuple[float, float, float, float]:
        """Return (x, y, w, h)."""
        return (self.x, self.y, self.w, self.h)


@dataclass
class DetectionResult:
    """
    Complete result returned by any detector implementation.

    Provides backwards compatibility for code expecting:
        detection.x, detection.y, detection.radius, detection.confidence
    """
    bbox: Optional[BoundingBox] = None
    center: Optional[Tuple[float, float]] = None
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    status: DetectionStatus = DetectionStatus.LOST
    inference_time_ms: float = 0.0
    detector_name: str = "Unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Backwards Compatibility Accessors
    # ------------------------------------------------------------------ #

    @property
    def x(self) -> float:
        """Centroid X coordinate (legacy interface)."""
        if self.center is not None:
            return float(self.center[0])
        if self.bbox is not None:
            return float(self.bbox.center[0])
        return 0.0

    @property
    def y(self) -> float:
        """Centroid Y coordinate (legacy interface)."""
        if self.center is not None:
            return float(self.center[1])
        if self.bbox is not None:
            return float(self.bbox.center[1])
        return 0.0

    @property
    def radius(self) -> float:
        """Approximate bounding radius (legacy interface)."""
        if self.bbox is not None:
            return float(max(self.bbox.w, self.bbox.h) * 0.5)
        return float(self.metadata.get("radius", 0.0))

    @property
    def is_valid(self) -> bool:
        """Whether a valid target was detected."""
        return self.status in (DetectionStatus.DETECTED, DetectionStatus.DEGRADED) and self.center is not None


class IDetector(ABC):
    """
    Common Abstract Base Class for Optical Beacon Detectors.

    Enables seamless swapping between ClassicalDetector and AIDetector
    without altering perception, estimation, or control pipelines.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray,
               timestamp: Optional[float] = None) -> DetectionResult:
        """
        Process an input camera frame and return a DetectionResult.

        Args:
            frame: (H, W, 3) BGR image array.
            timestamp: Optional sensor capture timestamp.

        Returns:
            DetectionResult with bbox, center, confidence, status, and timing.
        """
        pass

    @property
    @abstractmethod
    def confidence_threshold(self) -> float:
        """Current confidence threshold (0.0 to 1.0)."""
        pass

    @confidence_threshold.setter
    @abstractmethod
    def confidence_threshold(self, value: float):
        """Set confidence threshold (0.0 to 1.0)."""
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        """Inference device in use (e.g. 'cpu', 'cuda', 'cuda:0')."""
        pass

    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Human-readable identifier of the detector implementation."""
        pass

    def warmup(self, frame_shape: Tuple[int, int] = (480, 640)):
        """Warm up inference engines / allocate buffers."""
        dummy = np.zeros((frame_shape[0], frame_shape[1], 3), dtype=np.uint8)
        self.detect(dummy)

    def reset(self):
        """Reset internal temporal states or tracking statistics."""
        pass
