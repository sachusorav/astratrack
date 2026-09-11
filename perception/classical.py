"""
ASTRATRACK — Classical Computer Vision Beacon Detector

High-performance classical CV baseline utilizing:
CLAHE contrast enhancement -> HSV thresholding -> Morphological filtering ->
Contour analysis (circularity, solidity, area) -> Sub-pixel centroid estimation.
"""

import time
import math
import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any

from perception.interface import (
    IDetector, DetectionResult, BoundingBox, DetectionStatus
)
from perception.preprocessing import preprocess


class ClassicalDetector(IDetector):
    """
    Classical Computer Vision baseline detector for optical beacons.

    Implements the IDetector interface.
    """

    def __init__(self,
                 hsv_low: Tuple[int, int, int] = (0, 150, 200),
                 hsv_high: Tuple[int, int, int] = (180, 255, 255),
                 confidence_threshold: float = 0.35,
                 min_area: float = 12.0,
                 max_area: float = 15000.0,
                 min_circularity: float = 0.25,
                 device: str = "cpu"):
        """
        Args:
            hsv_low: Lower HSV color threshold (H: 0-180, S: 0-255, V: 0-255).
            hsv_high: Upper HSV color threshold.
            confidence_threshold: Minimum confidence to report DETECTED.
            min_area: Minimum contour area in pixels.
            max_area: Maximum contour area in pixels.
            min_circularity: Minimum 4*pi*area / perimeter^2 circularity score.
            device: Computing device ('cpu').
        """
        self._hsv_low = np.array(hsv_low, dtype=np.uint8)
        self._hsv_high = np.array(hsv_high, dtype=np.uint8)
        self._confidence_threshold = float(confidence_threshold)
        self.min_area = float(min_area)
        self.max_area = float(max_area)
        self.min_circularity = float(min_circularity)
        self._device = "cpu"

        # Morphological structuring elements
        self._kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        # Debug store
        self.last_mask: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ #
    # IDetector Properties
    # ------------------------------------------------------------------ #

    @property
    def confidence_threshold(self) -> float:
        return self._confidence_threshold

    @confidence_threshold.setter
    def confidence_threshold(self, value: float):
        self._confidence_threshold = max(0.0, min(1.0, float(value)))

    @property
    def device(self) -> str:
        return self._device

    @property
    def detector_name(self) -> str:
        return "ClassicalCV-HSV"

    # ------------------------------------------------------------------ #
    # Detection Pipeline
    # ------------------------------------------------------------------ #

    def detect(self, frame: np.ndarray,
               timestamp: Optional[float] = None) -> DetectionResult:
        """
        Execute classical beacon detection pipeline on frame.
        """
        t_start = time.perf_counter()
        t_stamp = timestamp if timestamp is not None else time.time()

        if frame is None or frame.size == 0:
            return DetectionResult(
                status=DetectionStatus.LOST,
                timestamp=t_stamp,
                detector_name=self.detector_name,
                inference_time_ms=0.0
            )

        # 1. Preprocessing (Blur + CLAHE)
        processed = preprocess(frame)

        # 2. Color Segmentation (HSV)
        hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)

        # Handle wrap-around for red hues (H near 0 and H near 180)
        if self._hsv_low[0] > self._hsv_high[0]:
            # e.g. low=170, high=10 -> red range
            m1 = cv2.inRange(hsv, np.array([self._hsv_low[0], self._hsv_low[1], self._hsv_low[2]]),
                             np.array([180, self._hsv_high[1], self._hsv_high[2]]))
            m2 = cv2.inRange(hsv, np.array([0, self._hsv_low[1], self._hsv_low[2]]),
                             np.array([self._hsv_high[0], self._hsv_high[1], self._hsv_high[2]]))
            mask = cv2.bitwise_or(m1, m2)
        else:
            mask = cv2.inRange(hsv, self._hsv_low, self._hsv_high)

        # Fallback intensity threshold for bright optical spots (if saturation is low/overexposed)
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        _, bright_mask = cv2.threshold(gray, 235, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_or(mask, bright_mask)

        # 3. Morphological cleanup
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel_open)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel_close)
        self.last_mask = mask

        # 4. Contour extraction
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            t_elapsed = (time.perf_counter() - t_start) * 1000.0
            return DetectionResult(
                status=DetectionStatus.LOST,
                timestamp=t_stamp,
                detector_name=self.detector_name,
                inference_time_ms=t_elapsed
            )

        # 5. Filter & Score Candidate Contours
        best_contour = None
        best_score = -1.0
        best_bbox = None
        best_center = None
        best_circularity = 0.0

        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area or area > self.max_area:
                continue

            perimeter = cv2.arcLength(c, True)
            circularity = (4.0 * math.pi * area) / max(1e-5, (perimeter * perimeter))
            if circularity < self.min_circularity:
                continue

            # Sub-pixel centroid using intensity moments
            m = cv2.moments(c)
            if m["m00"] == 0:
                continue

            cx = float(m["m10"] / m["m00"])
            cy = float(m["m01"] / m["m00"])

            # Bounding box
            bx, by, bw, bh = cv2.boundingRect(c)
            bbox = BoundingBox(float(bx), float(by), float(bw), float(bh))

            # Peak intensity at centroid region
            icx, icy = max(0, min(frame.shape[1] - 1, int(cx))), max(0, min(frame.shape[0] - 1, int(cy)))
            patch = gray[max(0, icy - 3):min(frame.shape[0], icy + 4),
                         max(0, icx - 3):min(frame.shape[1], icx + 4)]
            peak_val = float(np.max(patch)) if patch.size > 0 else 0.0

            # Confidence composite: area consistency + circularity + peak brightness
            area_score = min(1.0, math.sqrt(area) / 18.0)
            circ_score = min(1.0, circularity)
            peak_score = peak_val / 255.0

            score = 0.45 * peak_score + 0.35 * circ_score + 0.20 * area_score

            if score > best_score:
                best_score = score
                best_contour = c
                best_bbox = bbox
                best_center = (cx, cy)
                best_circularity = circularity

        t_elapsed = (time.perf_counter() - t_start) * 1000.0

        if best_center is None or best_score < 0.1:
            return DetectionResult(
                status=DetectionStatus.LOST,
                timestamp=t_stamp,
                detector_name=self.detector_name,
                inference_time_ms=t_elapsed
            )

        # Status determination based on threshold
        confidence = float(np.clip(best_score, 0.0, 1.0))
        if confidence >= self._confidence_threshold:
            status = DetectionStatus.DETECTED
        elif confidence >= (self._confidence_threshold * 0.6):
            status = DetectionStatus.DEGRADED
        else:
            status = DetectionStatus.LOST

        return DetectionResult(
            bbox=best_bbox,
            center=best_center,
            confidence=confidence,
            timestamp=t_stamp,
            status=status,
            inference_time_ms=t_elapsed,
            detector_name=self.detector_name,
            metadata={
                "circularity": best_circularity,
                "area": float(cv2.contourArea(best_contour)),
                "raw_score": best_score,
            }
        )
