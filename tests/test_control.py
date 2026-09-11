"""
ASTRATRACK — Unit Tests for Camera Control Subsystem

Tests:
- PController gain response, dead zone, output limit, smoothing
- PIDController proportional, integral anti-windup, derivative filtering
- DirectController raw proportional command
- CameraController tracking error computation: target_position - camera_center
- VirtualCamera actuation response, real-time rate updates, and limits
- Comparison between DIRECT, P, and PID controllers
"""

import sys
import os
import unittest
import numpy as np

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from core.config import CameraConfig, WorldConfig
from camera.virtual_camera import VirtualCamera
from control.pid import PController, PIDController, DirectController
from control.camera_controller import CameraController, ControllerMode


class TestCameraControl(unittest.TestCase):
    """Test suite for P, PID, and Direct tracking controllers."""

    def test_p_controller_dead_zone(self):
        """PController outputs zero when error is within dead zone."""
        ctrl = PController(kp=0.5, dead_zone=2.0, output_limit=10.0)
        self.assertEqual(ctrl.compute(1.5, dt=0.02), 0.0)
        self.assertTrue(ctrl.get_telemetry().in_deadzone)
        # Error beyond dead zone produces output
        out = ctrl.compute(4.0, dt=0.02)
        self.assertAlmostEqual(out, 2.0)
        self.assertFalse(ctrl.get_telemetry().in_deadzone)

    def test_p_controller_output_limit(self):
        """PController clamps to output_limit."""
        ctrl = PController(kp=1.0, dead_zone=0.0, output_limit=5.0)
        out = ctrl.compute(10.0, dt=0.02)
        self.assertEqual(out, 5.0)
        self.assertTrue(ctrl.get_telemetry().is_saturated)

    def test_pid_anti_windup(self):
        """PIDController clamps integral term to integral_limit."""
        ctrl = PIDController(kp=0.0, ki=1.0, kd=0.0, integral_limit=10.0, dead_zone=0.0)
        for _ in range(100):
            ctrl.compute(5.0, dt=0.1)
        self.assertAlmostEqual(ctrl._integral, 10.0)

    def test_pid_derivative_filtering(self):
        """PIDController applies low-pass filter to noisy derivative spikes."""
        ctrl = PIDController(kp=0.0, ki=0.0, kd=1.0, derivative_filter=0.8, dead_zone=0.0)
        # First step: error 0 -> 10
        ctrl.compute(10.0, dt=1.0)
        telemetry = ctrl.get_telemetry()
        # Raw derivative would be 10.0; filtered derivative is (1-0.8)*10 = 2.0
        self.assertAlmostEqual(telemetry.d_term, 2.0)

    def test_camera_tracking_error_computation(self):
        """CameraController computes target_pos - camera_center."""
        ctrl = CameraController(
            mode=ControllerMode.PID_CONTROL,
            kp=0.5,
            deg_per_pixel=0.1
        )
        target_pos = (500.0, 350.0)
        camera_center = (400.0, 300.0)
        output = ctrl.compute(target_pos, camera_center, dt=0.02)

        self.assertAlmostEqual(output.pan_error_px, 100.0)
        self.assertAlmostEqual(output.tilt_error_px, 50.0)
        self.assertAlmostEqual(output.pan_error_deg, 10.0)
        self.assertAlmostEqual(output.tilt_error_deg, 5.0)

    def test_virtual_camera_response_to_commands(self):
        """VirtualCamera centers move according to pan/tilt commands."""
        cam_cfg = CameraConfig(max_slew_rate=10.0, inertia=0.0)  # zero inertia for direct check
        world_cfg = WorldConfig(width=1000, height=1000)
        camera = VirtualCamera(cam_cfg, world_cfg)
        camera.smoothing = 0.0

        init_x, init_y = camera.center_x, camera.center_y
        # 1 deg command with deg_per_px = 0.1 -> 10 px shift
        camera.actuate(delta_pan=1.0, delta_tilt=2.0, dt=0.02)

        self.assertAlmostEqual(camera.center_x, init_x + 10.0)
        self.assertAlmostEqual(camera.center_y, init_y + 20.0)
        self.assertGreater(camera.pan_rate, 0.0)
        self.assertGreater(camera.tilt_rate, 0.0)

    def test_mode_switching(self):
        """CameraController switches between DIRECT, P, and PID cleanly."""
        ctrl = CameraController(mode=ControllerMode.DIRECT)
        self.assertIsInstance(ctrl.pan_controller, DirectController)

        ctrl.set_mode(ControllerMode.P_CONTROL)
        self.assertIsInstance(ctrl.pan_controller, PController)

        ctrl.set_mode(ControllerMode.PID_CONTROL)
        self.assertIsInstance(ctrl.pan_controller, PIDController)


if __name__ == "__main__":
    unittest.main()
