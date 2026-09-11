"""
ASTRATRACK — Real-Time Performance Metrics Collector

Calculates all 16 real-time operational and kinematic metrics in online streaming fashion:
1. Simulation duration
2. FPS
3. Detection FPS
4. Inference time
5. Processing latency
6. Acquisition time
7. Average tracking error
8. Maximum tracking error
9. RMS tracking error
10. Lock retention rate
11. Target loss count
12. Successful recovery count
13. Recovery time
14. Detection confidence
15. Prediction error
16. Camera angular error
"""

import time
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np


@dataclass
class FrameTelemetrySample:
    """Individual frame telemetry record."""
    timestamp: float
    fps: float
    detection_fps: float
    inference_time_ms: float
    processing_latency_ms: float
    tracking_error_px: float
    tracking_error_deg: float
    camera_angular_error_deg: float
    is_locked: bool
    detection_confidence: float
    prediction_error_px: float


class MetricsCollector:
    """
    Streaming real-time metrics accumulator.
    Computes summary metrics without retaining heavy data in memory.
    """

    def __init__(self, deg_per_pixel: float = 0.1):
        self.deg_per_pixel = deg_per_pixel
        self.reset()

    def reset(self):
        """Reset all accumulator variables."""
        self.start_wall_time = time.time()
        self.sim_duration = 0.0
        self.frame_count = 0
        self.detection_count = 0

        # Timing & Latency
        self._last_frame_time = time.time()
        self.fps = 0.0
        self.detection_fps = 0.0
        self.last_inference_time_ms = 0.0
        self.last_processing_latency_ms = 0.0
        self._inference_times_ms: List[float] = []
        self._latencies_ms: List[float] = []

        # Acquisition & Lock
        self.first_lock_time: Optional[float] = None
        self.acquisition_time_s: float = 0.0
        self.locked_frames_count = 0

        # Errors (px & deg)
        self.last_tracking_error_px = 0.0
        self.last_tracking_error_deg = 0.0
        self.last_camera_angular_error_deg = 0.0
        self.max_tracking_error_px = 0.0
        self.max_tracking_error_deg = 0.0

        # Online running statistics (for exact Mean and RMS)
        self._error_sum_px = 0.0
        self._error_sum_sq_px = 0.0
        self._error_sum_deg = 0.0
        self._error_sum_sq_deg = 0.0

        # Re-acquisition
        self.target_loss_count = 0
        self.successful_recovery_count = 0
        self.recovery_times: List[float] = []
        self.last_recovery_time_s = 0.0

        # Confidence & Prediction
        self.last_detection_confidence = 0.0
        self._confidences: List[float] = []
        self.last_prediction_error_px = 0.0
        self._prediction_errors_px: List[float] = []

        # Time series history (for CSV export and plotting)
        self.samples: List[FrameTelemetrySample] = []
        self._max_stored_samples = 5000

    def record_frame(self,
                     sim_time: float,
                     is_detected: bool,
                     confidence: float,
                     inference_time_ms: float,
                     processing_latency_ms: float,
                     tracking_error_px: float,
                     camera_angular_error_deg: float,
                     is_locked: bool,
                     prediction_error_px: float = 0.0):
        """
        Ingest real-time frame telemetry.

        Args:
            sim_time: Current simulation timestamp.
            is_detected: Whether optical detector produced a candidate.
            confidence: Detector confidence score [0, 1].
            inference_time_ms: Inference runtime of detector.
            processing_latency_ms: End-to-end processing pipeline latency.
            tracking_error_px: Boresight tracking error in pixels.
            camera_angular_error_deg: Pointing error in degrees.
            is_locked: Whether target lock is confirmed.
            prediction_error_px: Discrepancy between prediction and reality.
        """
        now = time.time()
        dt_wall = now - self._last_frame_time
        self._last_frame_time = now

        self.frame_count += 1
        self.sim_duration = sim_time

        # 1. FPS & Detection FPS
        instant_fps = (1.0 / dt_wall) if dt_wall > 0 else 60.0
        self.fps = 0.9 * self.fps + 0.1 * instant_fps if self.fps > 0 else instant_fps

        if is_detected:
            self.detection_count += 1
        self.detection_fps = self.detection_count / max(0.001, self.sim_duration)

        # 2. Latencies
        self.last_inference_time_ms = inference_time_ms
        self.last_processing_latency_ms = processing_latency_ms
        self._inference_times_ms.append(inference_time_ms)
        self._latencies_ms.append(processing_latency_ms)

        # 3. Acquisition Time
        if is_locked and self.first_lock_time is None:
            self.first_lock_time = sim_time
            self.acquisition_time_s = sim_time

        if is_locked:
            self.locked_frames_count += 1

        # 4. Tracking Errors
        self.last_tracking_error_px = tracking_error_px
        tracking_error_deg = tracking_error_px * self.deg_per_pixel
        self.last_tracking_error_deg = tracking_error_deg
        self.last_camera_angular_error_deg = camera_angular_error_deg

        if tracking_error_px > self.max_tracking_error_px:
            self.max_tracking_error_px = tracking_error_px
            self.max_tracking_error_deg = tracking_error_deg

        self._error_sum_px += tracking_error_px
        self._error_sum_sq_px += (tracking_error_px ** 2)
        self._error_sum_deg += tracking_error_deg
        self._error_sum_sq_deg += (tracking_error_deg ** 2)

        # 5. Confidence & Prediction
        self.last_detection_confidence = confidence
        self._confidences.append(confidence)
        self.last_prediction_error_px = prediction_error_px
        self._prediction_errors_px.append(prediction_error_px)

        # Store sample for CSV export / history
        if len(self.samples) < self._max_stored_samples:
            self.samples.append(FrameTelemetrySample(
                timestamp=sim_time,
                fps=self.fps,
                detection_fps=self.detection_fps,
                inference_time_ms=inference_time_ms,
                processing_latency_ms=processing_latency_ms,
                tracking_error_px=tracking_error_px,
                tracking_error_deg=tracking_error_deg,
                camera_angular_error_deg=camera_angular_error_deg,
                is_locked=is_locked,
                detection_confidence=confidence,
                prediction_error_px=prediction_error_px
            ))

    def on_target_loss(self):
        """Lifecycle hook: target lost event."""
        self.target_loss_count += 1

    def on_target_recovered(self, recovery_time_s: float):
        """Lifecycle hook: target recovered event."""
        self.successful_recovery_count += 1
        self.last_recovery_time_s = recovery_time_s
        self.recovery_times.append(recovery_time_s)

    # ------------------------------------------------------------------ #
    # Computed Real-Time KPIs
    # ------------------------------------------------------------------ #

    @property
    def average_tracking_error_px(self) -> float:
        return (self._error_sum_px / self.frame_count) if self.frame_count > 0 else 0.0

    @property
    def average_tracking_error_deg(self) -> float:
        return (self._error_sum_deg / self.frame_count) if self.frame_count > 0 else 0.0

    @property
    def rms_tracking_error_px(self) -> float:
        return math.sqrt(self._error_sum_sq_px / self.frame_count) if self.frame_count > 0 else 0.0

    @property
    def rms_tracking_error_deg(self) -> float:
        return math.sqrt(self._error_sum_sq_deg / self.frame_count) if self.frame_count > 0 else 0.0

    @property
    def lock_retention_rate_pct(self) -> float:
        return (self.locked_frames_count / max(1, self.frame_count)) * 100.0

    @property
    def mean_recovery_time_s(self) -> float:
        if not self.recovery_times:
            return 0.0
        return float(sum(self.recovery_times) / len(self.recovery_times))

    @property
    def average_confidence(self) -> float:
        if not self._confidences:
            return 0.0
        return float(sum(self._confidences) / len(self._confidences))

    @property
    def average_latency_ms(self) -> float:
        if not self._latencies_ms:
            return 0.0
        return float(sum(self._latencies_ms) / len(self._latencies_ms))

    @property
    def average_inference_time_ms(self) -> float:
        if not self._inference_times_ms:
            return 0.0
        return float(sum(self._inference_times_ms) / len(self._inference_times_ms))

    @property
    def average_prediction_error_px(self) -> float:
        if not self._prediction_errors_px:
            return 0.0
        return float(sum(self._prediction_errors_px) / len(self._prediction_errors_px))

    def get_realtime_metrics_dict(self) -> Dict[str, Any]:
        """Return all 16 metrics in a clean dictionary."""
        return {
            "simulation_duration_s": round(self.sim_duration, 2),
            "fps": round(self.fps, 1),
            "detection_fps": round(self.detection_fps, 1),
            "inference_time_ms": round(self.average_inference_time_ms, 2),
            "processing_latency_ms": round(self.average_latency_ms, 2),
            "acquisition_time_s": round(self.acquisition_time_s, 2),
            "average_tracking_error_px": round(self.average_tracking_error_px, 2),
            "average_tracking_error_deg": round(self.average_tracking_error_deg, 3),
            "maximum_tracking_error_px": round(self.max_tracking_error_px, 2),
            "maximum_tracking_error_deg": round(self.max_tracking_error_deg, 3),
            "rms_tracking_error_px": round(self.rms_tracking_error_px, 2),
            "rms_tracking_error_deg": round(self.rms_tracking_error_deg, 3),
            "lock_retention_rate_pct": round(self.lock_retention_rate_pct, 1),
            "target_loss_count": self.target_loss_count,
            "successful_recovery_count": self.successful_recovery_count,
            "recovery_time_s": round(self.mean_recovery_time_s, 2),
            "detection_confidence": round(self.average_confidence, 3),
            "prediction_error_px": round(self.average_prediction_error_px, 2),
            "camera_angular_error_deg": round(self.last_camera_angular_error_deg, 3),
        }
