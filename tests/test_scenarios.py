"""
ASTRATRACK — Unit Tests for Scenario Lab & Builder

Tests:
- Registry lookup for all 10 standard scenarios (01 to 10)
- Structural integrity of scenario target, camera, disturbance, and evaluation parameters
- CustomScenarioBuilder configuration and YAML round-trip serialization
"""

import sys
import os
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from scenarios.registry import get_scenario, GLOBAL_REGISTRY
from scenarios.builder import CustomScenarioBuilder


class TestScenarios(unittest.TestCase):
    """Test suite for Scenario Lab."""

    def test_all_10_scenarios_exist(self):
        """Verify scenarios 01 through 10 are all present in registry."""
        expected_ids = [f"{i:02d}" for i in range(1, 11)]
        for sid in expected_ids:
            scen = get_scenario(sid)
            self.assertIsNotNone(scen, f"Scenario {sid} not found in registry")
            self.assertEqual(scen.id, sid)
            self.assertTrue(len(scen.name) > 0)
            self.assertIn(scen.difficulty, ["NOMINAL", "MEDIUM", "HARD", "SEVERE", "EXTREME"])
            self.assertIn("speed", scen.target_config)
            self.assertIn("fov_width", scen.camera_config)
            self.assertIn("preset", scen.disturbance_config)

    def test_custom_scenario_builder_and_yaml_roundtrip(self):
        """CustomScenarioBuilder produces valid definitions and serializes to YAML."""
        builder = CustomScenarioBuilder(scenario_id="TEST-99", name="High Wind Test")
        builder.set_target(motion_model="linear", speed=200.0, radius=14)
        builder.set_camera(fov_width=800, fov_height=600, max_slew_rate=12.0)
        builder.set_disturbance_preset("MODERATE DISTURBANCE")
        builder.configure_channel("platform_jitter", enabled=True, intensity=2.5)
        builder.set_evaluation_criteria(min_lock_retention_pct=88.0, max_rms_error_px=10.0)

        scen = builder.build()
        self.assertEqual(scen.id, "TEST-99")
        self.assertEqual(scen.target_config["speed"], 200.0)
        self.assertEqual(scen.camera_config["fov_width"], 800)

        # YAML round-trip
        yaml_path = os.path.join(WORKSPACE_ROOT, "outputs", "test_exports", "custom_test.yaml")
        builder.save_to_yaml(yaml_path)
        self.assertTrue(os.path.exists(yaml_path))

        loaded = CustomScenarioBuilder.load_from_yaml(yaml_path)
        self.assertEqual(loaded.id, "TEST-99")
        self.assertEqual(loaded.name, "High Wind Test")
        self.assertEqual(loaded.target_config["speed"], 200.0)
        self.assertEqual(loaded.evaluation_criteria["min_lock_retention_pct"], 88.0)

        # Cleanup
        if os.path.exists(yaml_path):
            os.remove(yaml_path)


if __name__ == "__main__":
    unittest.main()
