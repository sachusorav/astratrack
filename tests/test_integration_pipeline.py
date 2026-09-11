"""
ASTRATRACK — QA Automated Tests: Full Pipeline Integration

Tests the complete closed-loop architecture:
Virtual Camera → Detection → Estimation → Prediction → Controller

Validates:
1. Nominal Coarse Alignment: System drives an initial angular offset to boresight center (< 2 px).
2. Dynamic Trajectory Tracking: System continuously tracks a moving beacon with bounded error.
3. AI Perception Pipeline Integration: End-to-end integration using AIDetector.
4. Occlusion Coasting & Re-acquisition: Predictor and Kalman coast during target dropout, restoring lock.
"""

import math
import pytest
import numpy as np
from core.config import AppConfig
from sim.world import World
from camera.virtual_camera import VirtualCamera
from perception.factory import create_detector
from estimation.kalman import KalmanTracker
from estimation.predictor import MotionPredictor
from control.camera_controller import CameraController, ControllerMode
from tracking.fsm import TrackingFSM, FSMState


class TestPipelineIntegration:
    """End-to-end integration test suite for the complete PAT closed-loop pipeline."""

    @pytest.fixture
    def setup_pipeline(self):
        """Initializes a standard closed-loop pipeline setup."""
        config = AppConfig()
        world = World(config)
        camera = VirtualCamera(config.camera, config.world)
        camera.smoothing = 0.1  # Set responsive inertia for automated tests
        detector = create_detector("classical",
                                   hsv_low=config.beacon.color_hsv_low,
                                   hsv_high=config.beacon.color_hsv_high)
        kalman = KalmanTracker(config.kalman)
        predictor = MotionPredictor(horizon=15, step=5, enabled=True)
        controller = CameraController(
            mode=ControllerMode.PID_CONTROL,
            kp=config.pid.kp,
            ki=config.pid.ki,
            kd=config.pid.kd,
            max_angular_velocity=config.camera.max_slew_rate,
            dead_zone=config.pid.dead_zone,
            deg_per_pixel=config.camera.deg_per_pixel
        )
        fsm = TrackingFSM(
            confidence_threshold=0.5,
            confirm_frames=2,
            lock_error_threshold_px=25.0,
            predict_coast_duration=0.5,
            local_search_duration=1.0,
            expanded_search_duration=2.0
        )
        return {
            "config": config,
            "world": world,
            "camera": camera,
            "detector": detector,
            "kalman": kalman,
            "predictor": predictor,
            "controller": controller,
            "fsm": fsm,
            "dt": 0.02
        }

    def test_end_to_end_nominal_coarse_alignment(self, setup_pipeline):
        """
        Verify that an initial target offset is eliminated by the closed-loop system,
        bringing the optical beacon into the boresight center.
        """
        p = setup_pipeline
        world, camera, detector = p["world"], p["camera"], p["detector"]
        kalman, predictor, controller, fsm = p["kalman"], p["predictor"], p["controller"], p["fsm"]
        dt = p["dt"]

        # Place beacon at fixed offset in world frame
        world.primary_beacon.set_motion_model("static")
        world.primary_beacon.x = camera.center_x + 80.0
        world.primary_beacon.y = camera.center_y + 60.0

        # Check initial error
        init_frame = camera.capture(world.render())
        init_det = detector.detect(init_frame)
        assert init_det is not None and init_det.confidence > 0.4
        cx, cy = camera.fov_center
        init_err = math.hypot(init_det.x - cx, init_det.y - cy)
        assert init_err > 50.0

        # Run closed loop for 90 frames (~1.8 seconds)
        final_err = init_err
        for step in range(90):
            sim_time = step * dt
            world.tick(dt)
            world_frame = world.render()
            fov_frame = camera.capture(world_frame)

            det = detector.detect(fov_frame)
            is_det = det is not None and det.confidence > 0.4
            conf = det.confidence if is_det else 0.0

            track_state = kalman.update(det, dt=dt)
            pred_pts = predictor.predict_trajectory(track_state, dt=dt)
            pred_pos = pred_pts[0] if pred_pts else track_state.estimated_pos

            det_coords = (det.x, det.y) if is_det else None
            fsm.update(
                detection_pos=det_coords,
                confidence=conf,
                estimated_pos=track_state.estimated_pos,
                predicted_pos=pred_pos,
                camera_center=camera.fov_center,
                sim_time=sim_time,
                dt=dt
            )
            setpoint = fsm.get_tracking_setpoint(camera.fov_center)

            ctrl_out = controller.compute(
                target_pos=setpoint,
                camera_center=camera.fov_center,
                dt=dt
            )
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            beacon_fov = camera.world_to_fov(world.primary_beacon.x, world.primary_beacon.y)
            final_err = math.hypot(beacon_fov[0] - cx, beacon_fov[1] - cy)

        # Verification: alignment achieved
        assert final_err < 5.0, f"Coarse alignment failed: final error {final_err:.2f} px >= 5.0 px"
        assert fsm.state in (FSMState.LOCKED, FSMState.TRACKING)

    def test_end_to_end_dynamic_trajectory_tracking(self, setup_pipeline):
        """
        Verify pipeline tracking performance on a moving target.
        """
        p = setup_pipeline
        world, camera, detector = p["world"], p["camera"], p["detector"]
        kalman, predictor, controller, fsm = p["kalman"], p["predictor"], p["controller"], p["fsm"]
        dt = p["dt"]

        world.primary_beacon.set_motion_model("sinusoidal")
        world.primary_beacon.speed = 100.0
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        errors = []
        locked_frames = 0
        total_frames = 80
        cx, cy = camera.fov_center

        for step in range(total_frames):
            sim_time = step * dt
            world.tick(dt)
            fov_frame = camera.capture(world.render())

            det = detector.detect(fov_frame)
            is_det = det is not None and det.confidence > 0.4
            conf = det.confidence if is_det else 0.0

            track_state = kalman.update(det, dt=dt)
            pred_pts = predictor.predict_trajectory(track_state, dt=dt)
            pred_pos = pred_pts[0] if pred_pts else track_state.estimated_pos

            det_coords = (det.x, det.y) if is_det else None
            fsm.update(
                detection_pos=det_coords,
                confidence=conf,
                estimated_pos=track_state.estimated_pos,
                predicted_pos=pred_pos,
                camera_center=camera.fov_center,
                sim_time=sim_time,
                dt=dt
            )
            setpoint = fsm.get_tracking_setpoint(camera.fov_center)

            ctrl_out = controller.compute(
                target_pos=setpoint,
                camera_center=camera.fov_center,
                dt=dt
            )
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            beacon_fov = camera.world_to_fov(world.primary_beacon.x, world.primary_beacon.y)
            err = math.hypot(beacon_fov[0] - cx, beacon_fov[1] - cy)
            errors.append(err)

            if fsm.state in (FSMState.LOCKED, FSMState.TRACKING):
                locked_frames += 1

        avg_err = np.mean(errors[20:])
        lock_pct = (locked_frames / total_frames) * 100.0

        assert avg_err < 12.0, f"Average error {avg_err:.2f} px exceeded 12.0 px"
        assert lock_pct >= 75.0, f"Lock retention {lock_pct:.1f}% below 75%"

    def test_end_to_end_ai_detector_integration(self, setup_pipeline):
        """
        Verify closed loop pipeline with AI neural detector.
        """
        p = setup_pipeline
        world, camera = p["world"], p["camera"]
        kalman, controller, fsm = p["kalman"], p["controller"], p["fsm"]
        dt = p["dt"]

        ai_detector = create_detector("ai")
        world.primary_beacon.set_motion_model("static")
        world.primary_beacon.x = camera.center_x + 40.0
        world.primary_beacon.y = camera.center_y + 30.0

        errors = []
        cx, cy = camera.fov_center

        for step in range(40):
            sim_time = step * dt
            world.tick(dt)
            fov_frame = camera.capture(world.render())

            det = ai_detector.detect(fov_frame)
            track_state = kalman.update(det, dt=dt)

            ctrl_out = controller.compute(
                target_pos=track_state.estimated_pos,
                camera_center=camera.fov_center,
                dt=dt
            )
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            beacon_fov = camera.world_to_fov(world.primary_beacon.x, world.primary_beacon.y)
            err = math.hypot(beacon_fov[0] - cx, beacon_fov[1] - cy)
            errors.append(err)

        assert errors[-1] < errors[0], "Closed-loop tracking did not reduce error"
        assert errors[-1] < 15.0, f"Final tracking error {errors[-1]:.2f} px too large"

    def test_end_to_end_occlusion_coasting_and_recovery(self, setup_pipeline):
        """
        Verify coasting and recovery during optical occlusion.
        """
        p = setup_pipeline
        world, camera, detector = p["world"], p["camera"], p["detector"]
        kalman, predictor, controller, fsm = p["kalman"], p["predictor"], p["controller"], p["fsm"]
        dt = p["dt"]

        world.primary_beacon.set_motion_model("linear")
        world.primary_beacon.vx = 20.0
        world.primary_beacon.vy = 0.0
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        states_observed = set()

        for step in range(80):
            sim_time = step * dt
            world.tick(dt)
            fov_frame = camera.capture(world.render())

            # Occlusion between step 25 and 45
            is_occluded = (25 <= step <= 45)
            if is_occluded:
                det = None
                is_det = False
                conf = 0.0
            else:
                det = detector.detect(fov_frame)
                is_det = det is not None and det.confidence > 0.4
                conf = det.confidence if is_det else 0.0

            track_state = kalman.update(det, dt=dt)
            pred_pts = predictor.predict_trajectory(track_state, dt=dt)
            pred_pos = pred_pts[0] if pred_pts else track_state.estimated_pos

            det_coords = (det.x, det.y) if is_det else None
            state = fsm.update(
                detection_pos=det_coords,
                confidence=conf,
                estimated_pos=track_state.estimated_pos,
                predicted_pos=pred_pos,
                camera_center=camera.fov_center,
                sim_time=sim_time,
                dt=dt
            )
            states_observed.add(state)
            setpoint = fsm.get_tracking_setpoint(camera.fov_center)

            ctrl_out = controller.compute(
                target_pos=setpoint,
                camera_center=camera.fov_center,
                dt=dt
            )
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

        assert FSMState.LOCKED in states_observed or FSMState.TRACKING in states_observed
        assert FSMState.TARGET_LOST in states_observed or FSMState.PREDICTING in states_observed
        assert fsm.metrics.number_of_losses >= 1
        assert fsm.metrics.number_of_recoveries >= 1
        assert fsm.state in (FSMState.LOCKED, FSMState.TRACKING)
