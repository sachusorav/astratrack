"""
ASTRATRACK — Unit Tests for Performance Metrics & Reporting Engine

Tests:
- MetricsCollector streaming calculation of all 16 metrics
- Mathematical accuracy of online RMS and average tracking errors
- PerformanceEvaluator PASS/MARGINAL/FAIL decision criteria
- ReportExporter CSV, JSON, and ReportLab PDF outputs
"""

import sys
import os
import unittest
import numpy as np

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from metrics.collector import MetricsCollector
from metrics.evaluator import PerformanceEvaluator
from metrics.report import PerformanceReport
from metrics.exporters import ReportExporter


class TestPerformanceMetrics(unittest.TestCase):
    """Test suite for metrics calculation and reporting."""

    def test_online_rms_and_average_accuracy(self):
        """Streaming RMS and average error match numpy calculations exactly."""
        collector = MetricsCollector(deg_per_pixel=0.1)
        test_errors = [2.0, 4.0, 6.0, 8.0, 10.0]

        for i, err in enumerate(test_errors):
            collector.record_frame(
                sim_time=(i + 1) * 0.02,
                is_detected=True,
                confidence=0.9,
                inference_time_ms=8.5,
                processing_latency_ms=12.0,
                tracking_error_px=err,
                camera_angular_error_deg=err * 0.1,
                is_locked=True
            )

        self.assertAlmostEqual(collector.average_tracking_error_px, float(np.mean(test_errors)))
        self.assertAlmostEqual(collector.rms_tracking_error_px, float(np.sqrt(np.mean(np.array(test_errors)**2))))
        self.assertAlmostEqual(collector.max_tracking_error_px, 10.0)
        self.assertAlmostEqual(collector.lock_retention_rate_pct, 100.0)

    def test_all_16_metrics_present(self):
        """Dictionary returned contains all 16 metrics."""
        collector = MetricsCollector()
        collector.record_frame(
            sim_time=1.0, is_detected=True, confidence=0.85,
            inference_time_ms=9.0, processing_latency_ms=13.0,
            tracking_error_px=3.2, camera_angular_error_deg=0.32,
            is_locked=True, prediction_error_px=1.5
        )
        collector.on_target_loss()
        collector.on_target_recovered(0.45)

        m = collector.get_realtime_metrics_dict()
        expected_keys = [
            "simulation_duration_s", "fps", "detection_fps", "inference_time_ms",
            "processing_latency_ms", "acquisition_time_s", "average_tracking_error_px",
            "average_tracking_error_deg", "maximum_tracking_error_px", "maximum_tracking_error_deg",
            "rms_tracking_error_px", "rms_tracking_error_deg", "lock_retention_rate_pct",
            "target_loss_count", "successful_recovery_count", "recovery_time_s",
            "detection_confidence", "prediction_error_px", "camera_angular_error_deg"
        ]
        for k in expected_keys:
            self.assertIn(k, m)

    def test_evaluator_pass_fail(self):
        """Evaluator returns PASS when criteria are met, FAIL when violated."""
        evaluator = PerformanceEvaluator(
            max_rms_error_px=10.0,
            min_lock_retention_pct=90.0,
            max_latency_ms=30.0
        )
        passing_metrics = {
            "rms_tracking_error_px": 5.0,
            "maximum_tracking_error_px": 15.0,
            "lock_retention_rate_pct": 95.0,
            "processing_latency_ms": 12.0,
            "recovery_time_s": 0.5
        }
        status, checklist = evaluator.evaluate(passing_metrics)
        self.assertEqual(status, "PASS")
        self.assertTrue(all(c.passed for c in checklist))

        failing_metrics = {
            "rms_tracking_error_px": 25.0,
            "maximum_tracking_error_px": 80.0,
            "lock_retention_rate_pct": 40.0,
            "processing_latency_ms": 60.0,
            "recovery_time_s": 5.0
        }
        status, checklist = evaluator.evaluate(failing_metrics)
        self.assertEqual(status, "FAIL")

    def test_export_formats(self):
        """Test exporting CSV, JSON, and PDF summary."""
        collector = MetricsCollector()
        for i in range(10):
            collector.record_frame(
                sim_time=i * 0.02, is_detected=True, confidence=0.9,
                inference_time_ms=8.0, processing_latency_ms=11.0,
                tracking_error_px=2.5, camera_angular_error_deg=0.25,
                is_locked=True
            )

        test_dir = os.path.join(WORKSPACE_ROOT, "outputs", "test_exports")
        csv_path = os.path.join(test_dir, "test.csv")
        json_path = os.path.join(test_dir, "test.json")
        pdf_path = os.path.join(test_dir, "test.pdf")

        # 1. CSV
        ReportExporter.export_csv(collector, csv_path)
        self.assertTrue(os.path.exists(csv_path))

        # 2. JSON
        evaluator = PerformanceEvaluator()
        m = collector.get_realtime_metrics_dict()
        status, checklist = evaluator.evaluate(m)
        report = PerformanceReport(
            run_id="EXP-TEST-001",
            timestamp="2026-09-09T00:00:00Z",
            scenario="01_BASELINE",
            configuration={"fov_w": 640, "fov_h": 480},
            disturbance_settings={"preset": "NORMAL"},
            detector="ClassicalCV-HSV",
            controller="PID",
            filter_settings={"type": "Kalman-4D"},
            metrics=m,
            pass_fail_status=status,
            criteria_checklist=checklist
        )
        ReportExporter.export_json(report, json_path)
        self.assertTrue(os.path.exists(json_path))

        # 3. PDF
        res_pdf = ReportExporter.export_pdf(report, pdf_path)
        self.assertIsNotNone(res_pdf)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 1000)

        # Cleanup test files
        for p in [csv_path, json_path, pdf_path]:
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    unittest.main()
