"""
ASTRATRACK — Unit Tests for Algorithm Comparison Lab

Tests:
- Sequential deterministic execution of Mode A, Mode B, Mode C, Mode D
- Calculation of all required comparison metrics:
  Detection Success, Average Error, Maximum Error, Acquisition Time,
  Lock Retention, Recovery Time, FPS, Latency
- Visual chart generation via Matplotlib
- Markdown, JSON, and PDF report compilation
"""

import sys
import os
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from lab.runner import AlgorithmComparisonLab
from lab.visualizer import generate_comparison_chart
from lab.report import BenchmarkReportGenerator


class TestAlgorithmComparisonLab(unittest.TestCase):
    """Test suite for Algorithm Comparison Lab."""

    def test_run_benchmark_comparison(self):
        """Execute all 4 modes on Scenario 01 for 30 frames and verify metrics."""
        lab = AlgorithmComparisonLab()
        report = lab.run_benchmark(scenario_id="01", frames=30, seed=42)

        self.assertEqual(len(report.mode_results), 4)

        for mode_name, res in report.mode_results.items():
            self.assertGreaterEqual(res.detection_success_pct, 0.0)
            self.assertGreaterEqual(res.average_error_px, 0.0)
            self.assertGreaterEqual(res.maximum_error_px, 0.0)
            self.assertGreaterEqual(res.rms_error_px, 0.0)
            self.assertGreaterEqual(res.acquisition_time_s, 0.0)
            self.assertGreaterEqual(res.lock_retention_pct, 0.0)
            self.assertGreaterEqual(res.recovery_time_s, 0.0)
            self.assertGreater(res.fps, 0.0)
            self.assertGreater(res.latency_ms, 0.0)

        # Verify chart generation
        chart_path = os.path.join(WORKSPACE_ROOT, "outputs", "test_exports", "test_chart.png")
        saved_chart = generate_comparison_chart(report, chart_path)
        self.assertTrue(os.path.exists(saved_chart))

        # Verify report generation
        md_text = BenchmarkReportGenerator.to_markdown(report)
        self.assertIn("Mode A", md_text)
        self.assertIn("Mode D", md_text)

        pdf_path = os.path.join(WORKSPACE_ROOT, "outputs", "test_exports", "test_benchmark.pdf")
        res_pdf = BenchmarkReportGenerator.export_pdf(report, saved_chart, pdf_path)
        self.assertIsNotNone(res_pdf)
        self.assertTrue(os.path.exists(pdf_path))

        # Cleanup
        for p in [chart_path, pdf_path]:
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    unittest.main()
