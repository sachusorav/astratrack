"""
ASTRATRACK — Unit Tests for State Estimation & Prediction Subsystem

Tests:
- 4-State (CV) and 6-State (CA) Kalman Filter kinematics
- Velocity and acceleration estimation accuracy
- Measurement dropout / coast mode and uncertainty inflation
- Configurable process noise (Q) and measurement noise (R)
- Spatial uncertainty error ellipse computation
- Prediction ON/OFF toggle and trajectory forecast
- TrackingMode selection (DETECTION_ONLY / FILTERED / PREDICTIVE)
- Aerospace visualization rendering
- Estimation benchmark suite execution
"""

import sys
import os
import math
import unittest
import numpy as np

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from core.config import KalmanConfig
from estimation.kalman import (
    KalmanTracker, TrackState, TrackingMode, ErrorEllipse
)
from estimation.predictor import MotionPredictor, PredictionPoint
from estimation.visualizer import render_tracking_frame


class MockDetection:
    """Mock detection object with x, y coordinates and confidence."""
    def __init__(self, x: float, y: float, confidence: float = 0.9):
        self.x = float(x)
        self.y = float(y)
        self.confidence = float(confidence)


class TestStateEstimationAndPrediction(unittest.TestCase):
    """Test suite for Kalman estimation, prediction, and visualizer."""

    def setUp(self):
        self.config = KalmanConfig(
            process_noise=0.1,
            measurement_noise=2.0,
            initial_covariance=5.0,
            coast_limit=30,
            prediction_horizon=10
        )

    # ------------------------------------------------------------------ #
    # 1. Kinematic State Vector Tests (4D CV & 6D CA)
    # ------------------------------------------------------------------ #

    def test_4state_cv_tracking(self):
        """Verify 4-state Constant Velocity tracking converges on position and velocity."""
        tracker = KalmanTracker(self.config, state_dim=4, prediction_enabled=True)
        self.assertEqual(tracker.state_dim, 4)
        self.assertEqual(tracker.x.shape, (4, 1))

        dt = 0.05
        true_vx, true_vy = 20.0, -10.0

        # Simulate 30 steps of constant velocity motion
        for i in range(30):
            mx = 100.0 + true_vx * (i * dt)
            my = 200.0 + true_vy * (i * dt)
            state = tracker.update(MockDetection(mx, my), dt=dt)

        self.assertAlmostEqual(state.estimated_pos[0], mx, delta=3.0)
        self.assertAlmostEqual(state.estimated_pos[1], my, delta=3.0)
        self.assertAlmostEqual(state.estimated_vel[0], true_vx, delta=3.5)
        self.assertAlmostEqual(state.estimated_vel[1], true_vy, delta=3.5)

    def test_6state_ca_tracking(self):
        """Verify 6-state Constant Acceleration model tracks acceleration components."""
        tracker = KalmanTracker(self.config, state_dim=6, prediction_enabled=True)
        self.assertEqual(tracker.state_dim, 6)
        self.assertEqual(tracker.x.shape, (6, 1))

        dt = 0.05
        ax, ay = 4.0, -2.0

        for i in range(40):
            t = i * dt
            mx = 50.0 + 0.5 * ax * (t ** 2)
            my = 80.0 + 0.5 * ay * (t ** 2)
            state = tracker.update(MockDetection(mx, my), dt=dt)

        self.assertAlmostEqual(state.estimated_pos[0], mx, delta=4.0)
        self.assertAlmostEqual(state.estimated_pos[1], my, delta=4.0)
        self.assertIsNotNone(state.estimated_acc)
        self.assertAlmostEqual(state.estimated_acc[0], ax, delta=2.5)

    # ------------------------------------------------------------------ #
    # 2. Missing Measurements & Coast Mode
    # ------------------------------------------------------------------ #

    def test_missing_measurement_coasting(self):
        """Verify tracker enters coast mode and inflates uncertainty when detections cease."""
        tracker = KalmanTracker(self.config)

        # Initialize with 5 measurements
        for i in range(5):
            tracker.update(MockDetection(100.0 + i * 2.0, 100.0))

        cov_before = tracker.update(MockDetection(110.0, 100.0)).covariance

        # Measurement drops out
        state_coast = tracker.update(None)
        self.assertTrue(tracker.is_coasting)
        self.assertEqual(tracker.coast_frames, 1)
        self.assertFalse(state_coast.is_locked)

        # Uncertainty must inflate without measurements
        self.assertGreater(state_coast.covariance, cov_before)

        # Coast past limit
        for _ in range(self.config.coast_limit + 5):
            tracker.update(None)
        self.assertTrue(tracker.coast_exceeded)

    # ------------------------------------------------------------------ #
    # 3. Uncertainty & Spatial Error Ellipse
    # ------------------------------------------------------------------ #

    def test_uncertainty_estimate_and_ellipse(self):
        """Verify 2D error ellipse parameters are correctly extracted from P."""
        tracker = KalmanTracker(self.config)
        state = tracker.update(MockDetection(200.0, 150.0))

        self.assertGreater(state.position_uncertainty, 0.0)
        self.assertIsNotNone(state.error_ellipse)
        self.assertIsInstance(state.error_ellipse, ErrorEllipse)
        self.assertGreater(state.error_ellipse.semi_major, 0.0)
        self.assertGreater(state.error_ellipse.semi_minor, 0.0)
        self.assertLessEqual(state.error_ellipse.semi_minor, state.error_ellipse.semi_major + 1e-4)

    # ------------------------------------------------------------------ #
    # 4. Configurable Process & Measurement Noise
    # ------------------------------------------------------------------ #

    def test_configurable_noise_properties(self):
        """Verify Q and R matrix scales can be adjusted dynamically."""
        tracker = KalmanTracker(self.config)

        # Process noise
        tracker.process_noise = 2.5
        self.assertEqual(tracker.process_noise, 2.5)
        self.assertAlmostEqual(tracker.Q[0, 0], (tracker._last_dt ** 3) * 2.5 / 3.0, delta=0.01)

        # Measurement noise
        tracker.measurement_noise = 12.0
        self.assertEqual(tracker.measurement_noise, 12.0)
        self.assertEqual(tracker.R[0, 0], 12.0)
        self.assertEqual(tracker.R[1, 1], 12.0)

    # ------------------------------------------------------------------ #
    # 5. Prediction Toggle (ON/OFF)
    # ------------------------------------------------------------------ #

    def test_prediction_toggle(self):
        """Verify toggle between predictive and filtered tracking."""
        tracker = KalmanTracker(self.config, prediction_enabled=True, prediction_horizon=10)

        # Establish velocity
        for i in range(10):
            tracker.update(MockDetection(100.0 + i * 10.0, 100.0 + i * 5.0), dt=0.05)

        # 1. Prediction ON: predicted position leads estimated position
        state_on = tracker.update(MockDetection(200.0, 150.0), dt=0.05)
        self.assertTrue(state_on.prediction_enabled)
        self.assertNotEqual(state_on.predicted_pos[0], state_on.estimated_pos[0])
        self.assertGreater(state_on.predicted_pos[0], state_on.estimated_pos[0])

        # 2. Prediction OFF: predicted position matches estimated position
        tracker.prediction_enabled = False
        state_off = tracker.update(MockDetection(210.0, 155.0), dt=0.05)
        self.assertFalse(state_off.prediction_enabled)
        self.assertEqual(state_off.predicted_pos, state_off.estimated_pos)
        self.assertEqual(state_off.tracking_mode, TrackingMode.FILTERED)

    # ------------------------------------------------------------------ #
    # 6. Motion Predictor
    # ------------------------------------------------------------------ #

    def test_motion_predictor(self):
        """Verify multi-step forward trajectory generation and toggle."""
        predictor = MotionPredictor(horizon=20, step=5, enabled=True)

        track_state = TrackState(
            estimated_pos=(100.0, 100.0),
            estimated_vel=(10.0, 20.0),
            predicted_pos=(120.0, 140.0),
            error_px=10.0,
            error_deg=1.0,
            covariance=2.0,
            is_locked=True,
            coast_frames=0,
            prediction_enabled=True,
            position_uncertainty=1.5
        )

        pts = predictor.predict_trajectory(track_state, dt=0.1)
        self.assertEqual(len(pts), 4)  # 5, 10, 15, 20
        self.assertGreater(pts[-1][0], track_state.estimated_pos[0])
        self.assertGreater(pts[-1][1], track_state.estimated_pos[1])

        # Uncertainty expansion
        unc_pts = predictor.predict_with_uncertainty(track_state)
        self.assertEqual(len(unc_pts), 4)
        self.assertGreater(unc_pts[-1].uncertainty_radius, unc_pts[0].uncertainty_radius)

        # Disabled predictor returns empty list
        predictor.enabled = False
        self.assertEqual(len(predictor.predict_trajectory(track_state)), 0)

    # ------------------------------------------------------------------ #
    # 7. Visualization Rendering
    # ------------------------------------------------------------------ #

    def test_visualizer_rendering(self):
        """Verify rendering markers onto a frame buffer."""
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        state = TrackState(
            estimated_pos=(320.0, 240.0),
            estimated_vel=(15.0, -10.0),
            predicted_pos=(350.0, 220.0),
            error_px=15.0,
            error_deg=1.5,
            covariance=3.5,
            is_locked=True,
            coast_frames=0,
            raw_pos=(318.0, 242.0),
            error_ellipse=ErrorEllipse(12.0, 8.0, 30.0),
            prediction_enabled=True
        )

        out = render_tracking_frame(canvas, state, [(330.0, 230.0), (340.0, 225.0)])
        self.assertEqual(out.shape, canvas.shape)
        # Should have non-zero pixels drawn
        self.assertGreater(np.count_nonzero(out), 0)


if __name__ == "__main__":
    unittest.main()
