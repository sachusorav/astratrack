"""
ASTRATRACK — Algorithm Comparison Lab Modes

Defines the 4 progressive engineering architectures:
MODE A: Classical detection (HSV) + Direct tracking (open-loop displacement)
MODE B: AI detection (YOLO) + PID closed-loop control
MODE C: AI detection + Kalman filter state estimation + PID control
MODE D: AI detection + Kalman filter + Anticipatory Prediction + PID + FSM Re-acquisition
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional

from core.config import AppConfig, BeaconConfig, CameraConfig, KalmanConfig, PIDConfig
from perception.factory import create_detector
from perception.classical import ClassicalDetector
from perception.ai_detector import AIDetector
from estimation.kalman import KalmanTracker
from estimation.predictor import MotionPredictor
from control.camera_controller import CameraController, ControllerMode
from tracking.fsm import TrackingFSM


class LabMode(Enum):
    MODE_A = "MODE A: Classical + Direct"
    MODE_B = "MODE B: AI + PID"
    MODE_C = "MODE C: AI + Kalman + PID"
    MODE_D = "MODE D: Full Pipeline (AI + Kalman + Pred + PID + Re-acq)"


@dataclass
class ModePipeline:
    """Assembled pipeline components for a specific comparison mode."""
    mode: LabMode
    detector: Any
    controller: CameraController
    kalman: Optional[KalmanTracker] = None
    predictor: Optional[MotionPredictor] = None
    fsm: Optional[TrackingFSM] = None


def build_mode_pipeline(mode: LabMode, config: AppConfig) -> ModePipeline:
    """Instantiate and configure the components for a given mode."""
    # 1. Detector
    if mode == LabMode.MODE_A:
        detector = create_detector(
            "classical",
            hsv_low=config.beacon.color_hsv_low,
            hsv_high=config.beacon.color_hsv_high,
            confidence_threshold=0.35
        )
    else:
        detector = create_detector("ai", confidence_threshold=0.45)

    # 2. Controller
    if mode == LabMode.MODE_A:
        controller = CameraController(
            mode=ControllerMode.DIRECT,
            kp=config.pid.kp,
            max_angular_velocity=config.camera.max_slew_rate,
            dead_zone=0.0,
            deg_per_pixel=config.camera.deg_per_pixel
        )
    else:
        controller = CameraController(
            mode=ControllerMode.PID_CONTROL,
            kp=config.pid.kp,
            ki=config.pid.ki,
            kd=config.pid.kd,
            max_angular_velocity=config.camera.max_slew_rate,
            dead_zone=config.pid.dead_zone,
            smoothing=0.15,
            deg_per_pixel=config.camera.deg_per_pixel
        )

    # 3. Kalman Filter
    kalman = None
    if mode in (LabMode.MODE_C, LabMode.MODE_D):
        kalman = KalmanTracker(
            config.kalman,
            fov_center=(config.camera.fov_width // 2, config.camera.fov_height // 2),
            deg_per_pixel=config.camera.deg_per_pixel
        )

    # 4. Predictor
    predictor = None
    if mode == LabMode.MODE_D:
        predictor = MotionPredictor(horizon=config.kalman.prediction_horizon, step=5)

    # 5. FSM
    fsm = None
    if mode == LabMode.MODE_D:
        fsm = TrackingFSM(
            confidence_threshold=0.45,
            confirm_frames=2,
            lock_error_threshold_px=25.0
        )

    return ModePipeline(
        mode=mode,
        detector=detector,
        controller=controller,
        kalman=kalman,
        predictor=predictor,
        fsm=fsm
    )
