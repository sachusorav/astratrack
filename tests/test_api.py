"""
ASTRATRACK — QA Automated Tests: Public API & Interfaces

Validates:
- Perception API contract, factory instantiation, and error handling
- Controller API contract, mode switching, and telemetry schema
- Scenario Registry API (catalog querying, invalid lookups)
- Experiment Manager API (serialization, persistence, retrieval)
- Comparison Lab API (pipeline construction, mode enum coverage)
- Tracking FSM API (state inspection, reset contract)
- Disturbance Engine API (channel toggling, preset configuration)
"""

import os
import pytest
import numpy as np
from core.config import AppConfig
from perception.factory import create_detector
from perception.interface import IDetector, DetectionResult, BoundingBox, DetectionStatus
from control.camera_controller import CameraController, ControllerMode
from control.pid import PIDController, PController, DirectController
from scenarios.registry import get_scenario, list_scenarios, GLOBAL_REGISTRY
from experiments.manager import ExperimentManager
from experiments.record import ExperimentRecord
from lab.modes import LabMode, build_mode_pipeline
from tracking.fsm import TrackingFSM, FSMState, ReacquisitionMetrics
from disturbance.engine import DisturbanceEngine
from disturbance.presets import get_preset_channels


class TestPublicAPI:
    """Comprehensive API contract verification suite."""

    # 1. Perception API
    def test_perception_factory_and_invalid_type(self):
        # Classical detector creation
        classical = create_detector("classical", hsv_low=(0, 0, 200), hsv_high=(180, 50, 255))
        assert isinstance(classical, IDetector)
        assert "Classical" in classical.detector_name

        # AI detector creation
        ai = create_detector("ai")
        assert isinstance(ai, IDetector)
        assert "AI" in ai.detector_name

        # Invalid detector type should raise ValueError
        with pytest.raises(ValueError, match="Unknown detector_type"):
            create_detector("quantum_spectral_detector")

    def test_detection_result_contract(self):
        # Verify DetectionResult format and properties
        bbox = BoundingBox(x=10.0, y=20.0, w=30.0, h=40.0)
        det = DetectionResult(
            bbox=bbox,
            center=(25.0, 40.0),
            confidence=0.95,
            status=DetectionStatus.DETECTED,
            inference_time_ms=2.5,
            detector_name="test_detector"
        )
        assert det.bbox == bbox
        assert det.center == (25.0, 40.0)
        assert 0.0 <= det.confidence <= 1.0
        assert det.status == DetectionStatus.DETECTED
        assert det.inference_time_ms >= 0.0

    # 2. Controller API
    def test_controller_api_and_mode_switching(self):
        cam_ctrl = CameraController(mode=ControllerMode.PID_CONTROL, kp=0.4, ki=0.01, kd=0.1)

        # Test initial mode
        assert cam_ctrl.mode == ControllerMode.PID_CONTROL

        # Test mode switching API
        cam_ctrl.set_mode(ControllerMode.DIRECT)
        assert cam_ctrl.mode == ControllerMode.DIRECT
        assert isinstance(cam_ctrl.pan_controller, DirectController)

        cam_ctrl.set_mode(ControllerMode.P_CONTROL)
        assert cam_ctrl.mode == ControllerMode.P_CONTROL
        assert isinstance(cam_ctrl.pan_controller, PController)

        cam_ctrl.set_mode(ControllerMode.PID_CONTROL)
        assert cam_ctrl.mode == ControllerMode.PID_CONTROL
        assert isinstance(cam_ctrl.pan_controller, PIDController)

        # Test parameter updating API
        cam_ctrl.set_parameters(kp=1.5, ki=0.2, kd=0.08)
        assert cam_ctrl.kp == 1.5
        assert cam_ctrl.ki == 0.2
        assert cam_ctrl.kd == 0.08

        # Test compute API returning DualAxisControlOutput
        output = cam_ctrl.compute(
            target_pos=(340.0, 230.0),
            camera_center=(320.0, 240.0),
            dt=0.016
        )
        assert hasattr(output, "pan_command")
        assert hasattr(output, "tilt_command")
        assert hasattr(output, "pan_error_px")
        assert hasattr(output, "tilt_error_px")
        assert output.pan_error_px == 20.0
        assert output.tilt_error_px == -10.0

    # 3. Scenario Registry API
    def test_scenario_registry_api(self):
        scenarios = list_scenarios()
        assert len(scenarios) >= 10

        # Query valid scenario
        s1 = get_scenario("01")
        assert s1 is not None
        assert s1.id == "01"
        assert "BASELINE" in s1.name.upper()

        # Query with full ID
        s1_full = get_scenario("01_baseline")
        assert s1_full is not None
        assert s1_full.id == "01"

        # Query invalid scenario
        s_invalid = get_scenario("999_non_existent")
        assert s_invalid is None

    # 4. Experiment Manager API
    def test_experiment_manager_api(self, tmp_path):
        exp_dir = str(tmp_path / "exp_api_test")
        mgr = ExperimentManager(base_dir=exp_dir)

        # List initially empty
        assert len(mgr.list_experiments()) == 0

        # Save record
        record = ExperimentRecord(
            experiment_id="EXP-API-001",
            created_at="2026-09-09T00:00:00Z",
            scenario_id="01",
            scenario_name="Baseline Test",
            detector_type="classical",
            tracker_type="FSM",
            estimator_type="Kalman-CA",
            controller_type="PID",
            controller_gains={"kp": 1.0, "ki": 0.1, "kd": 0.05},
            disturbance_preset="NORMAL",
            disturbance_params={},
            random_seed=42,
            duration_seconds=5.0,
            frame_count=100,
            fps=60.0,
            average_error_px=1.5,
            maximum_error_px=3.2,
            rms_error_px=1.8,
            acquisition_time_s=0.25,
            lock_retention_pct=98.5,
            recovery_time_s=0.0,
            latency_ms=1.2,
            error_series=[1.0, 1.2, 1.5]
        )

        saved_path = mgr.save_experiment(record)
        assert os.path.exists(saved_path)

        # Load record
        loaded = mgr.load_experiment("EXP-API-001")
        assert loaded is not None
        assert loaded.experiment_id == "EXP-API-001"
        assert loaded.rms_error_px == 1.8
        assert loaded.controller_gains["kp"] == 1.0

        # Non-existent record
        assert mgr.load_experiment("EXP-UNKNOWN") is None

    # 5. Algorithm Comparison Lab API
    def test_comparison_lab_pipeline_api(self):
        config = AppConfig()
        
        # Test pipeline builder for all modes
        for mode in LabMode:
            pipeline = build_mode_pipeline(mode, config)
            assert pipeline.mode == mode
            assert pipeline.detector is not None
            assert pipeline.controller is not None

        # Mode D must have full pipeline
        pipe_d = build_mode_pipeline(LabMode.MODE_D, config)
        assert pipe_d.kalman is not None
        assert pipe_d.predictor is not None
        assert pipe_d.fsm is not None

        # Mode A must not have Kalman or Predictor
        pipe_a = build_mode_pipeline(LabMode.MODE_A, config)
        assert pipe_a.kalman is None
        assert pipe_a.predictor is None

    # 6. FSM State API
    def test_fsm_state_api(self):
        fsm = TrackingFSM(confidence_threshold=0.6, confirm_frames=3)
        assert fsm.state == FSMState.SEARCHING
        assert fsm.state not in (FSMState.LOCKED, FSMState.TRACKING)

        # Reset contract
        fsm.reset()
        assert fsm.state == FSMState.SEARCHING
        assert fsm.metrics.number_of_losses == 0
        assert fsm.metrics.number_of_recoveries == 0

    # 7. Disturbance Engine API
    def test_disturbance_engine_api(self):
        engine = DisturbanceEngine(master_seed=123)
        assert len(engine.channels) == 10

        # Query preset API
        preset = get_preset_channels("SEVERE")
        assert preset is not None
        assert "image_noise" in preset
        assert preset["image_noise"].enabled is True

        # Apply preset API
        engine.load_preset("MODERATE")
        assert engine.channels["image_noise"].intensity > 0.0

        # Reset API
        engine.reset()
        assert len(engine.channels) == 10
