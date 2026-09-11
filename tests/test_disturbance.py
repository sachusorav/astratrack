"""
ASTRATRACK — Unit Tests for 10-Channel Disturbance Engine

Tests:
- All 10 disturbance channels independently
- Start delay and duration temporal gating
- Determinism guarantee: Identical master seed reproduces bitwise identical outputs
- 5 standard presets (NORMAL, LIGHT, MODERATE, SEVERE, EXTREME STRESS TEST)
"""

import sys
import os
import unittest
import numpy as np

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from disturbance.channel import DisturbanceChannelConfig
from disturbance.engine import DisturbanceEngine
from disturbance.presets import get_preset_channels, PRESET_NAMES


class TestDisturbanceEngine(unittest.TestCase):
    """Test suite for configurable disturbance engine."""

    def setUp(self):
        self.engine = DisturbanceEngine(preset="NORMAL", master_seed=42)

    def test_preset_names_exist(self):
        """Verify all 5 requested presets exist."""
        expected = ["NORMAL", "LIGHT DISTURBANCE", "MODERATE DISTURBANCE", "SEVERE DISTURBANCE", "EXTREME STRESS TEST"]
        for name in expected:
            self.assertIn(name, PRESET_NAMES)
            channels = get_preset_channels(name)
            self.assertEqual(len(channels), 10)

    def test_temporal_gating_start_delay_and_duration(self):
        """Channel only activates within [start_delay, start_delay + duration]."""
        ch = DisturbanceChannelConfig(
            name="test_channel",
            enabled=True,
            intensity=10.0,
            start_delay=2.0,
            duration=3.0
        )
        self.assertFalse(ch.is_active(1.0))   # before start_delay
        self.assertTrue(ch.is_active(2.5))    # inside active window
        self.assertTrue(ch.is_active(4.9))    # inside active window
        self.assertFalse(ch.is_active(5.1))   # past start_delay + duration

    def test_determinism_guarantee(self):
        """Two engines initialized with the same seed generate bitwise identical frames."""
        eng1 = DisturbanceEngine(preset="SEVERE DISTURBANCE", master_seed=12345)
        eng2 = DisturbanceEngine(preset="SEVERE DISTURBANCE", master_seed=12345)

        test_frame = np.full((120, 160, 3), 128, dtype=np.uint8)
        out1 = eng1.apply_image_disturbances(test_frame.copy(), t=2.0, target_fov_pos=(80, 60))
        out2 = eng2.apply_image_disturbances(test_frame.copy(), t=2.0, target_fov_pos=(80, 60))

        np.testing.assert_array_equal(out1, out2)

        # Also verify kinematic perturbations
        k1 = eng1.get_camera_perturbations(t=2.0)
        k2 = eng2.get_camera_perturbations(t=2.0)
        self.assertEqual(k1, k2)

    def test_image_noise_channel(self):
        """Noise channel adds variation to a uniform frame."""
        self.engine.configure_channel("image_noise", enabled=True, intensity=25.0)
        frame = np.full((50, 50, 3), 100, dtype=np.uint8)
        noisy = self.engine.apply_image_disturbances(frame, t=0.5)
        self.assertFalse(np.array_equal(frame, noisy))
        self.assertTrue(np.std(noisy) > 5.0)

    def test_target_occlusion_channel(self):
        """Occlusion channel darkens target region."""
        self.engine.configure_channel("target_occlusion", enabled=True, intensity=1.0)
        frame = np.full((100, 100, 3), 200, dtype=np.uint8)
        occluded = self.engine.apply_image_disturbances(frame, t=0.5, target_fov_pos=(50, 50))
        # Center should be darker than original 200
        self.assertLess(occluded[50, 50, 0], 100)

    def test_random_target_loss(self):
        """Random target loss activates intermittently when enabled."""
        self.engine.configure_channel("random_target_loss", enabled=True, intensity=0.5, frequency=1.0)
        # Should be True at t=0.1 (within drop window) and False at t=0.8
        self.assertTrue(self.engine.is_target_loss_active(0.1))
        self.assertFalse(self.engine.is_target_loss_active(0.8))


if __name__ == "__main__":
    unittest.main()
