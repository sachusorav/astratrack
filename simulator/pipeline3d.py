"""
ASTRATRACK — 3D Perception + Estimation + Control Pipeline Adapter

Wires the existing IDetector → KalmanTracker → TrackingFSM → CameraController
pipeline into the 3D simulator WITHOUT modifying any of those modules.

The boundary adapter maps between coordinate systems:
  - 3D world-space (metres)         ← target3d.py / camera3d.py live here
  - 2D sensor-frame pixels          ← perception / estimation / control live here

Projection:
  renderer._render_sensor_view() renders a (H, W, 3) BGR image showing exactly
  what the tracking camera 'sees'. The beacon appears at pixel (px, py) in that
  frame.  IDetector.detect() finds that spot and returns a DetectionResult with
  .x and .y in that pixel space.

  The Kalman tracker works in the same pixel space (fov_center = frame centre).
  CameraController.compute() produces (pan_cmd_deg, tilt_cmd_deg) per frame.
  Those angular commands are fed back to TrackingCamera3D.pan_deg / tilt_deg.

This module is intentionally a THIN ADAPTER — all control logic stays in the
existing tested modules.  The only new logic here is the coordinate bridge.
"""

import math
import numpy as np
from typing import Optional, Tuple, Dict, Any

# Existing tested modules — zero modifications
from perception.factory import create_detector
from perception.interface import IDetector, DetectionResult, DetectionStatus
from estimation.kalman import KalmanTracker, TrackState
from control.camera_controller import CameraController, ControllerMode, DualAxisControlOutput
from tracking.fsm import TrackingFSM, FSMState

# 3D simulator modules
from simulator.camera3d import TrackingCamera3D
from simulator.target3d import Target3D
from simulator.renderer import Renderer3D


# Default sensor resolution for the pipeline frame
SENSOR_W = 640
SENSOR_H = 480


class Pipeline3D:
    """
    Full perception/estimation/control pipeline for the 3D FSOC simulator.

    Usage inside Simulation3D (when use_pipeline=True):
        Instead of calling camera.update(dt, target.position) directly,
        the simulation does:
            self.pipeline.step(dt, target, camera, renderer)
        This renders a sensor frame, detects the beacon, filters via Kalman,
        updates the FSM, and commands the gimbal.
    """

    def __init__(self,
                 sensor_w: int = SENSOR_W,
                 sensor_h: int = SENSOR_H,
                 detector_type: str = "classical",
                 controller_mode: ControllerMode = ControllerMode.PID_CONTROL,
                 kp: float = 0.35,
                 ki: float = 0.008,
                 kd: float = 0.08,
                 max_angular_velocity: float = 12.0,
                 dead_zone_px: float = 4.0,
                 deg_per_pixel: float = None):
        """
        Args:
            sensor_w / sensor_h : Resolution of the rendered sensor frame.
            detector_type       : 'classical' (OpenCV HSV) or 'ai'.
            controller_mode     : PID_CONTROL, P_CONTROL, or DIRECT.
            kp / ki / kd        : PID gains.
            max_angular_velocity: Max gimbal slew command (deg/frame).
            dead_zone_px        : Pixel deadband for control.
            deg_per_pixel       : Angular scale — computed from camera FOV if None.
        """
        self.sensor_w = sensor_w
        self.sensor_h = sensor_h
        self._deg_per_pixel_override = deg_per_pixel

        # ---- Perception ------------------------------------------------- #
        self.detector: IDetector = create_detector(
            detector_type=detector_type,
            confidence_threshold=0.30
        )

        # ---- Estimation ------------------------------------------------- #
        self.fov_center = (sensor_w / 2.0, sensor_h / 2.0)
        self.kalman = KalmanTracker(
            fov_center=self.fov_center,
            deg_per_pixel=0.1,          # Placeholder; updated per frame
            state_dim=4,
            prediction_enabled=True,
            prediction_horizon=12,
        )

        # ---- Control ---------------------------------------------------- #
        self.controller = CameraController(
            mode=controller_mode,
            kp=kp,
            ki=ki,
            kd=kd,
            max_angular_velocity=max_angular_velocity,
            dead_zone=dead_zone_px,
            smoothing=0.0,
            deg_per_pixel=0.1,          # Placeholder; updated per frame
        )

        # ---- Tracking FSM ----------------------------------------------- #
        self.fsm = TrackingFSM(
            confidence_threshold=0.30,
            confirm_frames=2,
            lock_error_threshold_px=30.0,
            predict_coast_duration=0.6,
            local_search_duration=2.5,
            expanded_search_duration=5.0,
        )

        # ---- Internal state --------------------------------------------- #
        self._last_detection: Optional[DetectionResult] = None
        self._last_track_state: Optional[TrackState] = None
        self._last_control: Optional[DualAxisControlOutput] = None
        self._last_fsm_state: FSMState = FSMState.SEARCHING
        self._last_sensor_frame: Optional[np.ndarray] = None
        self._frame_count: int = 0

    # ---------------------------------------------------------------------- #
    # Main Step
    # ---------------------------------------------------------------------- #

    def step(self, dt: float,
             target: Target3D,
             camera: TrackingCamera3D,
             renderer: Renderer3D) -> Dict[str, Any]:
        """
        Run one full pipeline cycle.

        Steps:
          1. Render sensor view (what the camera currently sees)
          2. Detect beacon in that frame
          3. Kalman filter update
          4. FSM state update
          5. Compute control commands (angular delta deg/frame)
          6. Apply commands to camera gimbal state

        Args:
            dt      : Simulation time step (seconds).
            target  : Current Target3D instance.
            camera  : Current TrackingCamera3D instance — MUTATED in-place.
            renderer: Renderer3D (used to generate sensor frame).

        Returns:
            Dictionary of pipeline telemetry for HUD display.
        """
        self._frame_count += 1

        # ------------------------------------------------------------------ #
        # 1. Render Sensor Frame
        # ------------------------------------------------------------------ #
        sensor_frame = renderer._render_sensor_view(target, camera,
                                                    self.sensor_w, self.sensor_h)
        self._last_sensor_frame = sensor_frame

        # ------------------------------------------------------------------ #
        # 2. Detect Beacon
        # ------------------------------------------------------------------ #
        detection = self.detector.detect(sensor_frame)
        self._last_detection = detection
        has_detection = detection.is_valid

        # ------------------------------------------------------------------ #
        # 3. Update deg_per_pixel from camera FOV (may drift if scenario changes)
        # ------------------------------------------------------------------ #
        fov_deg = camera.config.fov_deg
        # Pixels per radian → deg_per_pixel = fov_deg / sensor_w
        # (Horizontal FOV maps to full sensor width)
        deg_per_pixel = fov_deg / self.sensor_w if self._deg_per_pixel_override is None \
                        else self._deg_per_pixel_override
        self.kalman.deg_per_pixel = deg_per_pixel
        self.controller.deg_per_pixel = deg_per_pixel

        # ------------------------------------------------------------------ #
        # 4. Kalman Filter Update
        # ------------------------------------------------------------------ #
        kalman_detection = detection if has_detection else None
        track_state = self.kalman.update(kalman_detection, dt=dt)
        self._last_track_state = track_state

        # ------------------------------------------------------------------ #
        # 5. FSM Update
        # ------------------------------------------------------------------ #
        cx, cy = self.fov_center
        det_pos = (detection.x, detection.y) if has_detection else None
        fsm_state = self.fsm.update(
            detection_pos=det_pos,
            confidence=detection.confidence if has_detection else 0.0,
            estimated_pos=track_state.estimated_pos,
            predicted_pos=track_state.predicted_pos,
            camera_center=(cx, cy),
            sim_time=self._frame_count * dt,
            dt=dt,
        )
        self._last_fsm_state = fsm_state

        # ------------------------------------------------------------------ #
        # 6. Determine control setpoint from FSM
        # ------------------------------------------------------------------ #
        setpoint = self.fsm.get_tracking_setpoint(camera_center=(cx, cy))

        # ------------------------------------------------------------------ #
        # 7. CameraController — computes angular delta
        # ------------------------------------------------------------------ #
        control_out = self.controller.compute(
            target_pos=setpoint,
            camera_center=(cx, cy),
            dt=dt,
        )
        self._last_control = control_out

        # ------------------------------------------------------------------ #
        # 8. Apply angular commands to the 3D gimbal
        #    Convention: pan_command and tilt_command are in degrees/frame
        #    (already scaled by deg_per_pixel × error_px).
        #    We add them to the current gimbal angles.
        # ------------------------------------------------------------------ #
        if fsm_state not in (FSMState.SEARCHING,):
            # Apply PID-derived increment
            camera.pan_deg += control_out.pan_command
            camera.tilt_deg -= control_out.tilt_command   # y-axis flipped: +y pixel → lower elevation

            # Enforce gimbal limits
            camera.pan_deg = float(np.clip(
                camera.pan_deg,
                -camera.config.pan_limit_deg,
                camera.config.pan_limit_deg
            ))
            camera.tilt_deg = float(np.clip(
                camera.tilt_deg,
                camera.config.tilt_min_deg,
                camera.config.tilt_limit_deg
            ))

            # Mark pipeline as in-command (disable internal tracking so camera
            # doesn't also run its own proportional tracker this frame)
            camera._pan_rate = 0.0
            camera._tilt_rate = 0.0
        else:
            # SEARCHING — let the camera's own acquisition routine run
            # (proportional slew toward horizon centre)
            camera.update(dt, target.position, target_visible=False)

        # ------------------------------------------------------------------ #
        # 9. Return telemetry
        # ------------------------------------------------------------------ #
        return self._build_telemetry(detection, track_state, control_out, fsm_state)

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    def _build_telemetry(self,
                         detection: DetectionResult,
                         track: TrackState,
                         control: DualAxisControlOutput,
                         fsm: FSMState) -> Dict[str, Any]:
        """Build a telemetry dict that Simulation3D can merge into its own."""
        return {
            # Detection
            "pipeline_active": True,
            "detection_status": detection.status.value,
            "detection_confidence": round(detection.confidence, 3),
            "detection_pos": (round(detection.x, 1), round(detection.y, 1)) if detection.is_valid else None,
            # Estimation
            "kalman_pos": (round(track.estimated_pos[0], 1), round(track.estimated_pos[1], 1)),
            "kalman_vel": (round(track.estimated_vel[0], 1), round(track.estimated_vel[1], 1)),
            "kalman_covariance": round(track.covariance, 2),
            "kalman_coast_frames": track.coast_frames,
            # FSM
            "fsm_state": fsm.value,
            "fsm_losses": self.fsm.metrics.number_of_losses,
            "fsm_recoveries": self.fsm.metrics.number_of_recoveries,
            "fsm_mean_recovery_s": round(self.fsm.metrics.mean_recovery_time, 2),
            # Control
            "pid_pan_cmd": round(control.pan_command, 3),
            "pid_tilt_cmd": round(control.tilt_command, 3),
            "pid_error_px": round(math.hypot(control.pan_error_px, control.tilt_error_px), 1),
        }

    def reset(self):
        """Reset all pipeline components to initial state."""
        self.kalman.reset()
        self.controller.reset()
        self.fsm.reset()
        self.detector.reset()
        self._last_detection = None
        self._last_track_state = None
        self._last_control = None
        self._last_fsm_state = FSMState.SEARCHING
        self._last_sensor_frame = None
        self._frame_count = 0

    @property
    def last_sensor_frame(self) -> Optional[np.ndarray]:
        """Last rendered sensor frame (for debug display)."""
        return self._last_sensor_frame

    @property
    def fsm_state(self) -> FSMState:
        return self._last_fsm_state
