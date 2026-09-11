"""
ASTRATRACK — Unit Tests for Experiment Manager & Reproducibility Engine

Tests:
- Save and load fidelity of ExperimentRecord
- Experiment listing
- Multi-experiment comparison generation
- Deterministic reproducibility mechanism (re-running reproduces matching metrics)
"""

import sys
import os
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from experiments.manager import ExperimentManager
from experiments.comparator import compare_experiments
from experiments.exporter import ExperimentExporter


class TestExperimentManager(unittest.TestCase):
    """Test suite for Experiment Manager."""

    def setUp(self):
        self.test_store = os.path.join(WORKSPACE_ROOT, "outputs", "test_experiments_store")
        self.manager = ExperimentManager(base_dir=self.test_store)

    def test_run_and_save_experiment(self):
        """Execute a short experiment, verify save and load."""
        record = self.manager.run_experiment(
            scenario_id="01",
            duration_frames=30,
            random_seed=42,
            experiment_id_override="EXP_UNITTEST_01"
        )
        self.assertEqual(record.experiment_id, "EXP_UNITTEST_01")
        self.assertGreater(record.fps, 0.0)
        self.assertGreater(record.average_error_px, 0.0)

        # Load back
        loaded = self.manager.load_experiment("EXP_UNITTEST_01")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.experiment_id, "EXP_UNITTEST_01")
        self.assertEqual(loaded.average_error_px, record.average_error_px)

    def test_reproducibility_engine(self):
        """Reproduce experiment with exact seed and verify identical metrics."""
        rec1 = self.manager.run_experiment(
            scenario_id="01",
            duration_frames=30,
            random_seed=1234,
            experiment_id_override="EXP_ORIGINAL"
        )
        rec2 = self.manager.reproduce_experiment("EXP_ORIGINAL")

        # Must match identically due to deterministic PRNG
        self.assertAlmostEqual(rec1.average_error_px, rec2.average_error_px, places=3)
        self.assertAlmostEqual(rec1.rms_error_px, rec2.rms_error_px, places=3)
        self.assertAlmostEqual(rec1.maximum_error_px, rec2.maximum_error_px, places=3)

    def test_multi_experiment_comparison_and_export(self):
        """Compare two experiments and export PDF report."""
        rec1 = self.manager.run_experiment(scenario_id="01", controller_type="DIRECT", duration_frames=25, random_seed=42, experiment_id_override="EXP_DIR")
        rec2 = self.manager.run_experiment(scenario_id="01", controller_type="PID", duration_frames=25, random_seed=42, experiment_id_override="EXP_PID")

        comp = compare_experiments([rec1, rec2])
        self.assertEqual(len(comp.experiments), 2)
        md = comp.to_markdown()
        self.assertIn("EXP_DIR", md)
        self.assertIn("EXP_PID", md)

        pdf_path = os.path.join(WORKSPACE_ROOT, "outputs", "test_exports", "test_exp_comp.pdf")
        res_pdf = ExperimentExporter.export_comparison_pdf(comp, pdf_path)
        self.assertIsNotNone(res_pdf)
        self.assertTrue(os.path.exists(pdf_path))

        if os.path.exists(pdf_path):
            os.remove(pdf_path)


if __name__ == "__main__":
    unittest.main()
