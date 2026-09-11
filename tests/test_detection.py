"""
ASTRATRACK — Unit Tests for Target Detection Module

Tests:
- Common IDetector interface compliance
- ClassicalDetector accuracy and status transitions
- AIDetector offline fallback handling and device selection
- Configurable confidence threshold gating
- Bounding box and sub-pixel centroid accuracy
- Backwards compatibility with legacy BeaconDetector
- Benchmark dataset generation and evaluation
"""

import math
import sys
import os
import unittest
import numpy as np
import cv2

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from perception.interface import (
    IDetector, DetectionResult, BoundingBox, DetectionStatus
)
from perception.classical import ClassicalDetector
from perception.ai_detector import AIDetector
from perception.detector import BeaconDetector
from perception.factory import create_detector
from perception.benchmark import (
    generate_benchmark_dataset, benchmark_detector
)


class TestTargetDetection(unittest.TestCase):
    """Test suite for target detection subsystem."""

    def setUp(self):
        """Create standard synthetic test frames."""
        self.width = 640
        self.height = 480
        self.cx = 320.0
        self.cy = 240.0
        self.radius = 10.0

        # Synthetic optical beacon frame (red/white glow on dark background)
        self.beacon_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.beacon_frame[:, :] = (15, 12, 10)  # Dark night sky
        cv2.circle(self.beacon_frame, (int(self.cx), int(self.cy)), int(self.radius * 2.5), (30, 50, 180), -1)
        cv2.circle(self.beacon_frame, (int(self.cx), int(self.cy)), int(self.radius * 1.2), (60, 100, 220), -1)
        cv2.circle(self.beacon_frame, (int(self.cx), int(self.cy)), int(self.radius * 0.6), (180, 200, 255), -1)
        cv2.circle(self.beacon_frame, (int(self.cx), int(self.cy)), 2, (255, 255, 255), -1)

        # Blank negative frame
        self.blank_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.blank_frame[:, :] = (15, 12, 10)

    # ------------------------------------------------------------------ #
    # 1. Interface Compliance Tests
    # ------------------------------------------------------------------ #

    def test_interface_inheritance(self):
        """Verify both detectors implement the common IDetector interface."""
        self.assertTrue(issubclass(ClassicalDetector, IDetector))
        self.assertTrue(issubclass(AIDetector, IDetector))

        classical = ClassicalDetector()
        ai = AIDetector()

        self.assertIsInstance(classical, IDetector)
        self.assertIsInstance(ai, IDetector)

    def test_detector_properties(self):
        """Verify required properties exist and return appropriate types."""
        detectors = [ClassicalDetector(), AIDetector()]
        for det in detectors:
            self.assertIsInstance(det.confidence_threshold, float)
            self.assertIsInstance(det.device, str)
            self.assertIsInstance(det.detector_name, str)
            self.assertIn(det.device, ("cpu", "cuda"))

    # ------------------------------------------------------------------ #
    # 2. Classical Detector Tests
    # ------------------------------------------------------------------ #

    def test_classical_detects_beacon(self):
        """Verify ClassicalDetector detects beacon and reports accurate coordinates."""
        detector = ClassicalDetector(confidence_threshold=0.3)
        res = detector.detect(self.beacon_frame)

        self.assertIsInstance(res, DetectionResult)
        self.assertEqual(res.status, DetectionStatus.DETECTED)
        self.assertTrue(res.is_valid)
        self.assertGreater(res.confidence, 0.3)
        self.assertIsNotNone(res.center)
        self.assertIsNotNone(res.bbox)

        # Centroid accuracy within 1.5 pixels
        self.assertAlmostEqual(res.center[0], self.cx, delta=1.5)
        self.assertAlmostEqual(res.center[1], self.cy, delta=1.5)

        # Legacy backward-compatibility accessors
        self.assertAlmostEqual(res.x, self.cx, delta=1.5)
        self.assertAlmostEqual(res.y, self.cy, delta=1.5)
        self.assertGreater(res.radius, 0.0)

        # Bounding box bounds
        self.assertLessEqual(res.bbox.xmin, self.cx)
        self.assertGreaterEqual(res.bbox.xmax, self.cx)
        self.assertLessEqual(res.bbox.ymin, self.cy)
        self.assertGreaterEqual(res.bbox.ymax, self.cy)
        self.assertGreater(res.bbox.area, 0.0)

    def test_classical_blank_frame_returns_lost(self):
        """Verify ClassicalDetector returns LOST on empty frames."""
        detector = ClassicalDetector()
        res = detector.detect(self.blank_frame)

        self.assertEqual(res.status, DetectionStatus.LOST)
        self.assertFalse(res.is_valid)

    # ------------------------------------------------------------------ #
    # 3. AI Detector & Offline Fallback Tests
    # ------------------------------------------------------------------ #

    def test_ai_detector_offline_fallback(self):
        """Verify AIDetector reports missing weights and runs offline fallback."""
        ai = AIDetector(model_path="nonexistent_weights.onnx", confidence_threshold=0.3)

        self.assertFalse(ai.weights_loaded)
        self.assertIn("nonexistent_weights.onnx", ai.status_message)
        self.assertIsNotNone(ai.fallback_detector)

        # Run inference on beacon frame
        res = ai.detect(self.beacon_frame)
        self.assertIsInstance(res, DetectionResult)
        self.assertEqual(res.status, DetectionStatus.DETECTED)
        self.assertTrue(res.is_valid)
        self.assertAlmostEqual(res.center[0], self.cx, delta=1.5)
        self.assertAlmostEqual(res.center[1], self.cy, delta=1.5)
        self.assertTrue(res.metadata.get("fallback", False))

    def test_ai_detector_device_config(self):
        """Verify AIDetector respects device selection without crashes."""
        ai_cpu = AIDetector(device="cpu")
        self.assertEqual(ai_cpu.device, "cpu")

        # Requesting CUDA in environments without CUDA should gracefully fall back
        ai_cuda = AIDetector(device="cuda")
        self.assertIn(ai_cuda.device, ("cpu", "cuda"))

    # ------------------------------------------------------------------ #
    # 4. Configurable Confidence Threshold Tests
    # ------------------------------------------------------------------ #

    def test_configurable_confidence_threshold(self):
        """Verify detection status updates when threshold is modified."""
        detector = ClassicalDetector(confidence_threshold=0.2)
        res_low = detector.detect(self.beacon_frame)
        self.assertEqual(res_low.status, DetectionStatus.DETECTED)

        # Set impossible threshold
        detector.confidence_threshold = 0.999
        self.assertEqual(detector.confidence_threshold, 0.999)
        res_high = detector.detect(self.beacon_frame)
        self.assertNotEqual(res_high.status, DetectionStatus.DETECTED)

    # ------------------------------------------------------------------ #
    # 5. Factory & Adapter Tests
    # ------------------------------------------------------------------ #

    def test_factory_creation(self):
        """Verify factory creates both detectors and rejects unknown types."""
        d_cv = create_detector("classical", confidence_threshold=0.4)
        self.assertIsInstance(d_cv, ClassicalDetector)
        self.assertEqual(d_cv.confidence_threshold, 0.4)

        d_ai = create_detector("ai", confidence_threshold=0.45)
        self.assertIsInstance(d_ai, AIDetector)
        self.assertEqual(d_ai.confidence_threshold, 0.45)

        with self.assertRaises(ValueError):
            create_detector("unknown_type")

    def test_beacon_detector_adapter(self):
        """Verify legacy BeaconDetector adapter backwards compatibility."""
        legacy = BeaconDetector()
        res = legacy.detect(self.beacon_frame)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res.x, self.cx, delta=1.5)
        self.assertAlmostEqual(res.y, self.cy, delta=1.5)

        # Blank frame returns None for legacy callers
        lost = legacy.detect(self.blank_frame)
        self.assertIsNone(lost)

    # ------------------------------------------------------------------ #
    # 6. Benchmark Suite Execution Test
    # ------------------------------------------------------------------ #

    def test_benchmark_suite(self):
        """Verify benchmark generator and runner execute cleanly."""
        dataset = generate_benchmark_dataset(num_samples=15, seed=99)
        self.assertEqual(len(dataset), 15)

        detector = ClassicalDetector()
        report = benchmark_detector(detector, dataset, warmup_frames=2)

        self.assertGreater(report.fps, 0.0)
        self.assertGreater(report.mean_inference_ms, 0.0)
        self.assertGreaterEqual(report.detection_rate_pct, 50.0)
        self.assertLess(report.localization_rmse_px, 15.0)


if __name__ == "__main__":
    unittest.main()
