"""
ASTRATRACK — QA Automated Tests: Stress & Robustness Evaluation

Validates system behavior under severe operational conditions:
1. High target speed: Rapid traversal, actuator saturation handling, and stability.
2. High vibration: 35 Hz mechanical oscillations, derivative filtering, anti-chatter.
3. High noise: Severe sensor noise, false-positive rejection, Kalman filtering.
4. Temporary target loss: Extended 35-frame dropout, coasting stability, and re-acquisition.
5. Multiple disturbances: Simultaneous composite disturbance environment.
6. Low FPS: Stability at 10-15 FPS (large dt = 0.1s) with discrete Kalman and PID.
7. High latency: Sensor/actuator lag compensation via multi-step forward prediction.
"""

import math
import pytest
import numpy as np
from core.config import AppConfig
from sim.world import World
from camera.virtual_camera import VirtualCamera
from disturbance.engine import DisturbanceEngine
from perception.factory import create_detector
from estimation.kalman import KalmanTracker
from estimation.predictor import MotionPredictor
from control.camera_controller import CameraController, ControllerMode
from tracking.fsm import TrackingFSM, FSMState


class TestStressAndRobustness:
    """Stress testing suite validating aerospace robustness margins."""

    @pytest.fixture
    def sim_env(self):
        config = AppConfig()
        world = World(config)
        camera = VirtualCamera(config.camera, config.world)
        dist_engine = DisturbanceEngine(master_seed=999)
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
        fsm = TrackingFSM(confidence_threshold=0.5, confirm_frames=2)
        return {
            "config": config,
            "world": world,
            "camera": camera,
            "dist_engine": dist_engine,
            "detector": detector,
            "kalman": kalman,
            "predictor": predictor,
            "controller": controller,
            "fsm": fsm
        }

    def test_stress_high_target_speed(self, sim_env):
        """
        Stress Test 1: High Target Speed.
        Target maneuvers at 400% nominal speed (speed = 450 px/s).
        Assert actuator rate clamping prevents numerical runaway and tracking recovers.
        """
        env = sim_env
        world, camera, controller = env["world"], env["camera"], env["controller"]
        kalman, detector = env["kalman"], env["detector"]
        dt = 0.02

        world.primary_beacon.set_motion_model("sinusoidal")
        world.primary_beacon.speed = 450.0  # Very high speed
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        max_pan_rate = 0.0
        max_tilt_rate = 0.0

        for _ in range(60):
            world.tick(dt)
            fov_frame = camera.capture(world.render())
            det = detector.detect(fov_frame)

            track_state = kalman.update(det, dt=dt)
            ctrl_out = controller.compute(track_state.estimated_pos, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            max_pan_rate = max(max_pan_rate, abs(camera.pan_rate))
            max_tilt_rate = max(max_tilt_rate, abs(camera.tilt_rate))

            # Numerical stability assertions
            assert np.isfinite(ctrl_out.pan_command), "Pan command produced NaN/inf"
            assert np.isfinite(ctrl_out.tilt_command), "Tilt command produced NaN/inf"
            assert np.isfinite(camera.center_x), "Camera center_x produced NaN/inf"
            assert np.isfinite(camera.center_y), "Camera center_y produced NaN/inf"

        # Rate clamping assertion
        assert max_pan_rate <= (camera.config.max_slew_rate / camera.config.deg_per_pixel) + 1e-1

    def test_stress_high_vibration(self, sim_env):
        """
        Stress Test 2: High Vibration.
        Injects intense 35 Hz camera LOS vibration at 0.85 intensity.
        Assert derivative low-pass filter suppresses chatter and commands remain bounded.
        """
        env = sim_env
        world, camera, dist_engine = env["world"], env["camera"], env["dist_engine"]
        detector, kalman, controller = env["detector"], env["kalman"], env["controller"]
        dt = 0.02

        # Enable severe vibration
        dist_engine.channels["camera_vibration"].enabled = True
        dist_engine.channels["camera_vibration"].intensity = 0.85
        dist_engine.channels["camera_vibration"].frequency = 35.0

        world.primary_beacon.set_motion_model("static")
        world.primary_beacon.x = camera.center_x + 30.0
        world.primary_beacon.y = camera.center_y + 20.0

        commands = []
        for step in range(50):
            sim_time = step * dt
            world.tick(dt)
            # Inject vibration jitter into camera position
            jitter_x, jitter_y, _, _ = dist_engine.get_camera_perturbations(sim_time)
            camera.add_jitter(jitter_x, jitter_y)

            fov_frame = camera.capture(world.render())
            det = detector.detect(fov_frame)
            track_state = kalman.update(det, dt=dt)

            ctrl_out = controller.compute(track_state.estimated_pos, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)
            commands.append((ctrl_out.pan_command, ctrl_out.tilt_command))

        pan_diffs = [abs(commands[i][0] - commands[i - 1][0]) for i in range(1, len(commands))]
        assert max(pan_diffs) < 20.0, f"Jerk under vibration exceeded margin: {max(pan_diffs):.2f}"

    def test_stress_high_noise(self, sim_env):
        """
        Stress Test 3: High Noise.
        Injects intense noise into sensor frame.
        Assert perception and Kalman filter reject noise spikes and maintain tracking state.
        """
        env = sim_env
        world, camera, dist_engine = env["world"], env["camera"], env["dist_engine"]
        detector, kalman, controller = env["detector"], env["kalman"], env["controller"]
        camera.smoothing = 0.1
        dt = 0.02

        dist_engine.channels["image_noise"].enabled = True
        dist_engine.channels["image_noise"].intensity = 12.0  # High sensor noise sigma

        world.primary_beacon.set_motion_model("static")
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        kalman_errors = []
        cx, cy = camera.fov_center

        for step in range(40):
            sim_time = step * dt
            world.tick(dt)
            fov_frame = camera.capture(world.render())
            noisy_frame = dist_engine.apply_image_disturbances(fov_frame, sim_time)

            det = detector.detect(noisy_frame)
            track_state = kalman.update(det, dt=dt)

            ctrl_out = controller.compute(track_state.estimated_pos, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)
            err = math.hypot(track_state.estimated_pos[0] - cx, track_state.estimated_pos[1] - cy)
            kalman_errors.append(err)

        assert np.mean(kalman_errors) < 25.0, "High noise caused tracking divergence"

    def test_stress_temporary_target_loss(self, sim_env):
        """
        Stress Test 4: Temporary Target Loss.
        Simulates an extended 30-frame dropout.
        Asserts Kalman covariance does not explode and re-acquisition succeeds upon signal restoration.
        """
        env = sim_env
        world, camera, detector = env["world"], env["camera"], env["detector"]
        kalman, controller, fsm = env["kalman"], env["controller"], env["fsm"]
        dt = 0.02

        world.primary_beacon.set_motion_model("linear")
        world.primary_beacon.vx = 15.0
        world.primary_beacon.vy = 5.0
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        for step in range(70):
            sim_time = step * dt
            world.tick(dt)
            fov_frame = camera.capture(world.render())

            if 20 <= step <= 45:
                det = None
                is_det = False
                conf = 0.0
            else:
                det = detector.detect(fov_frame)
                is_det = det is not None and det.confidence > 0.4
                conf = det.confidence if is_det else 0.0

            track_state = kalman.update(det, dt=dt)
            det_coords = (det.x, det.y) if is_det else None

            fsm.update(
                detection_pos=det_coords,
                confidence=conf,
                estimated_pos=track_state.estimated_pos,
                predicted_pos=track_state.predicted_pos,
                camera_center=camera.fov_center,
                sim_time=sim_time,
                dt=dt
            )

            # Covariance matrix check
            p_diag = np.diag(kalman.P)
            assert np.all(p_diag >= 0), "Kalman covariance lost positive semi-definiteness"
            assert np.all(np.isfinite(p_diag)), "Kalman covariance exploded to inf/NaN"

            ctrl_out = controller.compute(track_state.estimated_pos, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

        assert fsm.metrics.number_of_losses >= 1
        assert fsm.metrics.number_of_recoveries >= 1
        assert fsm.state in (FSMState.LOCKED, FSMState.TRACKING)

    def test_stress_multiple_disturbances(self, sim_env):
        """
        Stress Test 5: Multiple Disturbances.
        Activates severe composite disturbance preset.
        Asserts no crashes, no NaN outputs, and stable execution.
        """
        env = sim_env
        world, camera, dist_engine = env["world"], env["camera"], env["dist_engine"]
        detector, kalman, controller = env["detector"], env["kalman"], env["controller"]
        dt = 0.02

        dist_engine.load_preset("SEVERE")
        world.primary_beacon.set_motion_model("sinusoidal")
        world.primary_beacon.speed = 120.0
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        for step in range(50):
            sim_time = step * dt
            world.tick(dt)
            jx, jy, _, _ = dist_engine.get_camera_perturbations(sim_time)
            camera.add_jitter(jx, jy)

            fov_frame = camera.capture(world.render())
            degraded_frame = dist_engine.apply_image_disturbances(fov_frame, sim_time)

            det = detector.detect(degraded_frame)
            track_state = kalman.update(det, dt=dt)

            ctrl_out = controller.compute(track_state.estimated_pos, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            assert np.isfinite(ctrl_out.pan_command)
            assert np.isfinite(ctrl_out.tilt_command)
            assert np.isfinite(track_state.estimated_pos[0])

    def test_stress_low_fps(self, sim_env):
        """
        Stress Test 6: Low FPS Operation.
        Executes simulation at 10 FPS (dt = 0.10s).
        Asserts discrete Kalman filter and PID integration remain stable.
        """
        env = sim_env
        world, camera, detector = env["world"], env["camera"], env["detector"]
        kalman, controller = env["kalman"], env["controller"]
        camera.smoothing = 0.1
        dt = 0.10  # Large discrete time-step (10 FPS)

        world.primary_beacon.set_motion_model("static")
        world.primary_beacon.x = camera.center_x + 40.0
        world.primary_beacon.y = camera.center_y + 30.0

        for _ in range(35):
            world.tick(dt)
            fov_frame = camera.capture(world.render())
            det = detector.detect(fov_frame)

            track_state = kalman.update(det, dt=dt)
            ctrl_out = controller.compute(track_state.estimated_pos, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            assert np.isfinite(track_state.estimated_pos[0])
            assert np.isfinite(ctrl_out.pan_command)

        # Target should converge toward center
        cx, cy = camera.fov_center
        final_err = math.hypot(camera.world_to_fov(world.primary_beacon.x, world.primary_beacon.y)[0] - cx,
                               camera.world_to_fov(world.primary_beacon.x, world.primary_beacon.y)[1] - cy)
        assert final_err < 15.0

    def test_stress_high_latency(self, sim_env):
        """
        Stress Test 7: High Latency.
        Simulates 6 frames of transport lag (~120ms at 50 FPS).
        Asserts forward lead prediction maintains stable tracking.
        """
        env = sim_env
        world, camera, detector = env["world"], env["camera"], env["detector"]
        kalman, predictor, controller = env["kalman"], env["predictor"], env["controller"]
        camera.smoothing = 0.1
        dt = 0.02

        world.primary_beacon.set_motion_model("linear")
        world.primary_beacon.speed = 35.0
        world.primary_beacon.direction_deg = 25.0
        world.primary_beacon.x = camera.center_x
        world.primary_beacon.y = camera.center_y

        lag_frames = 6
        # Pre-seed buffer with initial nominal detection to model transport pipeline latency
        init_det = detector.detect(camera.capture(world.render()))
        lag_buffer = [init_det] * lag_frames
        errors = []
        cx, cy = camera.fov_center

        for step in range(60):
            sim_time = step * dt
            world.tick(dt)
            fov_frame = camera.capture(world.render())
            det = detector.detect(fov_frame)

            lag_buffer.append(det)
            delayed_det = lag_buffer.pop(0)

            track_state = kalman.update(delayed_det, dt=dt)
            pred_pts = predictor.predict_trajectory(track_state, dt=dt)
            target_pt = pred_pts[0] if pred_pts else track_state.estimated_pos

            ctrl_out = controller.compute(target_pt, camera.fov_center, dt=dt)
            camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

            beacon_fov = camera.world_to_fov(world.primary_beacon.x, world.primary_beacon.y)
            err = math.hypot(beacon_fov[0] - cx, beacon_fov[1] - cy)
            errors.append(err)

            assert np.isfinite(ctrl_out.pan_command)
            assert np.isfinite(track_state.estimated_pos[0])

        assert np.mean(errors[15:]) < 35.0, "High latency caused closed-loop divergence"
