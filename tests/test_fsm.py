"""
ASTRATRACK — Unit Tests for Target-Loss Detection and Re-Acquisition FSM

Tests:
- Normal acquisition sequence: SEARCHING -> ACQUIRING -> LOCKED -> TRACKING
- Target loss and recovery sequence: TRACKING -> TARGET_LOST -> PREDICTING -> REACQUIRING -> LOCKED
- Metrics tracking: number_of_losses, number_of_recoveries, recovery_time
- Search expansion: Local spiral to expanded search upon local timeout
- Search exhaustion: Expanded search timeout increments failed_recoveries and resets to SEARCHING
"""

import sys
import os
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from tracking.fsm import TrackingFSM, FSMState


class TestTrackingFSM(unittest.TestCase):
    """Test suite for Tracking FSM."""

    def setUp(self):
        self.fsm = TrackingFSM(
            confidence_threshold=0.5,
            confirm_frames=2,
            lock_error_threshold_px=20.0,
            predict_coast_duration=0.5,
            local_search_duration=1.0,
            expanded_search_duration=2.0
        )
        self.cam_center = (320.0, 240.0)

    def test_normal_acquisition_flow(self):
        """SEARCHING -> ACQUIRING -> LOCKED -> TRACKING."""
        # 1. Initial state is SEARCHING
        self.assertEqual(self.fsm.state, FSMState.SEARCHING)

        # 2. First detection triggers ACQUIRING
        st = self.fsm.update(
            detection_pos=(325.0, 245.0), confidence=0.8,
            estimated_pos=(325.0, 245.0), predicted_pos=(325.0, 245.0),
            camera_center=self.cam_center, sim_time=0.1, dt=0.02
        )
        self.assertEqual(st, FSMState.ACQUIRING)

        # 3. Second confirmed detection triggers LOCKED
        st = self.fsm.update(
            detection_pos=(322.0, 242.0), confidence=0.85,
            estimated_pos=(322.0, 242.0), predicted_pos=(322.0, 242.0),
            camera_center=self.cam_center, sim_time=0.12, dt=0.02
        )
        self.assertEqual(st, FSMState.LOCKED)

        # 4. Small boresight error (<20px) triggers TRACKING
        st = self.fsm.update(
            detection_pos=(321.0, 241.0), confidence=0.9,
            estimated_pos=(321.0, 241.0), predicted_pos=(321.0, 241.0),
            camera_center=self.cam_center, sim_time=0.14, dt=0.02
        )
        self.assertEqual(st, FSMState.TRACKING)

    def test_target_loss_and_recovery_flow(self):
        """TRACKING -> TARGET_LOST -> PREDICTING -> REACQUIRING -> LOCKED."""
        # Fast-forward into TRACKING
        self.test_normal_acquisition_flow()
        self.assertEqual(self.fsm.state, FSMState.TRACKING)

        # Signal lost (confidence 0.0) -> TARGET_LOST
        st = self.fsm.update(
            detection_pos=None, confidence=0.0,
            estimated_pos=(321.0, 241.0), predicted_pos=(325.0, 241.0),
            camera_center=self.cam_center, sim_time=0.20, dt=0.02
        )
        self.assertEqual(st, FSMState.TARGET_LOST)
        self.assertEqual(self.fsm.metrics.number_of_losses, 1)

        # Next frame transitions immediately to PREDICTING (coast mode)
        st = self.fsm.update(
            detection_pos=None, confidence=0.0,
            estimated_pos=(325.0, 241.0), predicted_pos=(330.0, 241.0),
            camera_center=self.cam_center, sim_time=0.22, dt=0.02
        )
        self.assertEqual(st, FSMState.PREDICTING)

        # Coast for 0.6s (exceeds predict_coast_duration=0.5s) -> REACQUIRING
        for step in range(30):
            st = self.fsm.update(
                detection_pos=None, confidence=0.0,
                estimated_pos=(330.0, 241.0), predicted_pos=(335.0, 241.0),
                camera_center=self.cam_center, sim_time=0.24 + step * 0.02, dt=0.02
            )
        self.assertEqual(st, FSMState.REACQUIRING)

        # Target re-appears during REACQUIRING -> LOCKED
        st = self.fsm.update(
            detection_pos=(340.0, 240.0), confidence=0.88,
            estimated_pos=(340.0, 240.0), predicted_pos=(342.0, 240.0),
            camera_center=self.cam_center, sim_time=1.0, dt=0.02
        )
        self.assertEqual(st, FSMState.LOCKED)
        self.assertEqual(self.fsm.metrics.number_of_recoveries, 1)
        self.assertGreater(self.fsm.metrics.last_recovery_time, 0.5)

    def test_search_expansion_and_failure(self):
        """Local search timeout -> Expanded search -> Failure -> SEARCHING."""
        # Start in REACQUIRING
        self.fsm.state = FSMState.REACQUIRING
        self.fsm._search_start_time = 0.0
        self.fsm._loss_start_time = 0.0

        # Run through local search duration (1.0s)
        for step in range(60):
            t = step * 0.02
            st = self.fsm.update(
                detection_pos=None, confidence=0.0,
                estimated_pos=self.cam_center, predicted_pos=self.cam_center,
                camera_center=self.cam_center, sim_time=t, dt=0.02
            )
        self.assertTrue(self.fsm._is_search_expanded)
        self.assertEqual(st, FSMState.REACQUIRING)

        # Run past expanded search duration (1.0 + 2.0 = 3.0s)
        for step in range(60, 160):
            t = step * 0.02
            st = self.fsm.update(
                detection_pos=None, confidence=0.0,
                estimated_pos=self.cam_center, predicted_pos=self.cam_center,
                camera_center=self.cam_center, sim_time=t, dt=0.02
            )
        self.assertEqual(st, FSMState.SEARCHING)
        self.assertEqual(self.fsm.metrics.failed_recoveries, 1)


if __name__ == "__main__":
    unittest.main()
