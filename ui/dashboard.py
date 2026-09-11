"""
ASTRATRACK — Professional Aerospace Engineering Dashboard

Organized into 5 distinct operational zones:
1. TOP BAR: Branding, System Status Badge, FPS/Latency, Mission Clock, Quick Triggers
2. MAIN VIEW: Virtual camera viewport with high-contrast aerospace HUD overlays
3. TELEMETRY PANEL: Real-time sensor readout (Position, Velocity, Rates, Errors)
4. CONTROL PANEL: Scenario selector, Target speed, Disturbance preset, Pipeline toggles
5. PERFORMANCE PANEL: Real-time rolling plots (FPS, Error, Confidence) & KPI Scorecard
"""

import os
import sys
import time
import math
from typing import Optional
import cv2
import numpy as np
import dearpygui.dearpygui as dpg

from core.config import AppConfig
from core.constants import DEFAULT_DT
from core.math_utils import euclidean_dist

from sim.world import World
from camera.virtual_camera import VirtualCamera
from perception.factory import create_detector
from estimation.kalman import KalmanTracker
from estimation.predictor import MotionPredictor
from control.camera_controller import CameraController, ControllerMode
from disturbance.engine import DisturbanceEngine
from tracking.fsm import TrackingFSM, FSMState
from metrics.collector import MetricsCollector
from metrics.evaluator import PerformanceEvaluator
from metrics.report import PerformanceReport
from metrics.exporters import ReportExporter
from scenarios.registry import get_scenario, GLOBAL_REGISTRY
from demo.director import JudgeDemoDirector, DemoPhase
from demo.timeline_overlay import draw_demo_timeline
from ui.viewport import draw_aerospace_viewport


class Dashboard:
    """Aerospace Mission Control Ground Station Dashboard for ASTRATRACK."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.running = False
        self.paused = False
        self.in_judge_demo = False

        # --- Subsystems ---
        self.world = World(self.config)
        self.camera = VirtualCamera(self.config.camera, self.config.world)
        self.detector = create_detector("classical",
                                        hsv_low=self.config.beacon.color_hsv_low,
                                        hsv_high=self.config.beacon.color_hsv_high)
        self.detector_type_str = "Classical CV (HSV)"

        self.controller = CameraController(
            mode=ControllerMode.PID_CONTROL,
            kp=self.config.pid.kp,
            ki=self.config.pid.ki,
            kd=self.config.pid.kd,
            max_angular_velocity=self.config.camera.max_slew_rate,
            dead_zone=self.config.pid.dead_zone,
            smoothing=0.15,
            deg_per_pixel=self.config.camera.deg_per_pixel
        )

        self.kalman = KalmanTracker(
            self.config.kalman,
            fov_center=self.camera.fov_center,
            deg_per_pixel=self.config.camera.deg_per_pixel,
        )
        self.kalman_enabled = True

        self.predictor = MotionPredictor(
            horizon=self.config.kalman.prediction_horizon,
            step=5,
        )
        self.prediction_enabled = True

        self.fsm = TrackingFSM(confidence_threshold=0.35)
        self.disturbance = DisturbanceEngine(preset="NORMAL")
        self.metrics_collector = MetricsCollector(deg_per_pixel=self.config.camera.deg_per_pixel)
        self.judge_demo = JudgeDemoDirector()

        # --- Performance and Plot Histories ---
        self._fps = 60.0
        self._frame_count = 0
        self._start_time = time.time()
        self._last_time = time.time()
        self._max_history = 200

        self._time_hist = []
        self._error_hist = []
        self._conf_hist = []
        self._fps_hist = []

        # Current frame state
        self._current_detection = None
        self._current_track_state = None
        self._current_predicted_pts = []
        self._current_fov_frame = None
        self._sim_time = 0.0

    def setup(self):
        """Build Dear PyGui context, theme, windows, and 5 operational zones."""
        dpg.create_context()

        # --- Aerospace Dark Theme ---
        with dpg.theme() as dark_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (11, 14, 20, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (17, 22, 32, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (15, 20, 30, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (26, 36, 56, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (22, 28, 42, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (32, 42, 64, 255))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (0, 176, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (24, 38, 62, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (36, 58, 96, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 176, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (230, 235, 245, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (35, 45, 65, 255))
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)

        dpg.bind_theme(dark_theme)

        # Viewport Texture
        blank = np.zeros((self.config.camera.fov_height, self.config.camera.fov_width, 4), dtype=np.float32)
        with dpg.texture_registry():
            dpg.add_raw_texture(
                width=self.config.camera.fov_width,
                height=self.config.camera.fov_height,
                default_value=blank.flatten(),
                format=dpg.mvFormat_Float_rgba,
                tag="viewport_texture",
            )

        # Keyboard shortcuts
        with dpg.handler_registry():
            dpg.add_key_press_handler(dpg.mvKey_Spacebar, callback=lambda: self.toggle_pause())
            dpg.add_key_press_handler(dpg.mvKey_R, callback=lambda: self.reset_simulation())
            dpg.add_key_press_handler(dpg.mvKey_K, callback=lambda: self._on_toggle_kalman())
            dpg.add_key_press_handler(dpg.mvKey_P, callback=lambda: self._on_toggle_prediction())
            dpg.add_key_press_handler(dpg.mvKey_D, callback=lambda: self._on_toggle_detector())
            dpg.add_key_press_handler(dpg.mvKey_F5, callback=lambda: self._start_judge_demo())

        # Main Window holding the 5 zones
        with dpg.window(tag="main_window", no_title_bar=True, no_resize=True, no_move=True):
            # ZONE 1: TOP BAR
            self._create_top_bar()

            # ZONES 2, 3, 4 (Middle Horizontal Split)
            with dpg.group(horizontal=True):
                # ZONE 2: MAIN VIEW
                self._create_main_view()
                # ZONE 3: TELEMETRY PANEL
                self._create_telemetry_panel()
                # ZONE 4: CONTROL PANEL
                self._create_control_panel()

            dpg.add_spacer(height=4)

            # ZONE 5: PERFORMANCE PANEL
            self._create_performance_panel()

        # DPG viewport
        dpg.create_viewport(title="ASTRATRACK — Aerospace Tracking Dashboard (SIH 2026)",
                            width=1440, height=920, min_width=1280, min_height=800)
        dpg.setup_dearpygui()
        dpg.set_primary_window("main_window", True)
        dpg.show_viewport()

    # ------------------------------------------------------------------ #
    # ZONE 1: TOP BAR
    # ------------------------------------------------------------------ #
    def _create_top_bar(self):
        with dpg.child_window(height=52, border=True):
            with dpg.group(horizontal=True):
                dpg.add_text("★ ASTRATRACK", color=(0, 230, 118))
                dpg.add_text("| Aerospace FSOC Tracking Simulator | SIH 2026", color=(140, 150, 170))

                dpg.add_spacer(width=20)
                dpg.add_text("STATUS:")
                dpg.add_button(label="[ SEARCHING ]", tag="top_status_badge", small=True)

                dpg.add_spacer(width=20)
                dpg.add_text("RATE:")
                dpg.add_text("60.0 FPS", tag="top_fps_text", color=(0, 230, 118))

                dpg.add_spacer(width=15)
                dpg.add_text("LATENCY:")
                dpg.add_text("09.2 ms", tag="top_latency_text", color=(0, 176, 255))

                dpg.add_spacer(width=15)
                dpg.add_text("MISSION CLOCK:")
                dpg.add_text("T+00:00.0", tag="top_clock_text", color=(255, 214, 0))

                dpg.add_spacer(width=30)
                dpg.add_button(label="★ START JUDGE DEMO (90s)", callback=self._start_judge_demo, tag="btn_judge_demo")
                dpg.add_button(label="Export Audit PDF", callback=self._export_pdf_report)
                dpg.add_button(label="Pause (Space)", callback=self.toggle_pause)
                dpg.add_button(label="Reset (R)", callback=self.reset_simulation)

    # ------------------------------------------------------------------ #
    # ZONE 2: MAIN VIEW
    # ------------------------------------------------------------------ #
    def _create_main_view(self):
        with dpg.child_window(width=660, height=500, border=True):
            dpg.add_text("ZONE 2: OPTICAL SENSOR VIEWPORT", color=(0, 176, 255))
            dpg.add_image("viewport_texture", width=self.config.camera.fov_width, height=self.config.camera.fov_height)

    # ------------------------------------------------------------------ #
    # ZONE 3: TELEMETRY PANEL
    # ------------------------------------------------------------------ #
    def _create_telemetry_panel(self):
        with dpg.child_window(width=360, height=500, border=True):
            dpg.add_text("ZONE 3: REAL-TIME TELEMETRY", color=(0, 176, 255))
            dpg.add_separator()

            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=160)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=180)

                with dpg.table_row():
                    dpg.add_text("Target Position (FOV):")
                    dpg.add_text("(320.0, 240.0) px", tag="telem_pos_fov", color=(220, 230, 245))

                with dpg.table_row():
                    dpg.add_text("Target Velocity:")
                    dpg.add_text("+00.0, +00.0 px/s", tag="telem_vel", color=(220, 230, 245))

                with dpg.table_row():
                    dpg.add_text("Detection Confidence:")
                    dpg.add_text("0.95 (HIGH)", tag="telem_conf", color=(0, 230, 118))

                with dpg.table_row():
                    dpg.add_text("Gimbal Pan / Rate:")
                    dpg.add_text("+00.0° (+00.0°/s)", tag="telem_pan", color=(220, 230, 245))

                with dpg.table_row():
                    dpg.add_text("Gimbal Tilt / Rate:")
                    dpg.add_text("+00.0° (+00.0°/s)", tag="telem_tilt", color=(220, 230, 245))

                with dpg.table_row():
                    dpg.add_text("Boresight Error:")
                    dpg.add_text("0.0 px (0.00°)", tag="telem_err", color=(255, 82, 82))

                with dpg.table_row():
                    dpg.add_text("Control Output:")
                    dpg.add_text("Pan: 0.0, Tilt: 0.0", tag="telem_ctrl", color=(0, 176, 255))

                with dpg.table_row():
                    dpg.add_text("Pipeline Latency:")
                    dpg.add_text("10.2 ms", tag="telem_lat", color=(0, 176, 255))

            dpg.add_spacer(height=8)
            dpg.add_text("RE-ACQUISITION PERFORMANCE", color=(255, 171, 0))
            dpg.add_separator()
            dpg.add_text("Losses: 0  |  Recoveries: 0 (100%)", tag="telem_losses")
            dpg.add_text("Last Recovery: 0.00 s  |  Mean: 0.00 s", tag="telem_rec_time")

    # ------------------------------------------------------------------ #
    # ZONE 4: CONTROL PANEL
    # ------------------------------------------------------------------ #
    def _create_control_panel(self):
        with dpg.child_window(width=380, height=500, border=True):
            dpg.add_text("ZONE 4: MISSION CONTROL PANEL", color=(0, 176, 255))
            dpg.add_separator()

            # Scenario selection
            scenarios = [f"{s.id} — {s.name}" for s in GLOBAL_REGISTRY.list_all()]
            dpg.add_text("Scenario Preset:")
            dpg.add_combo(scenarios, default_value=scenarios[0], callback=self._on_scenario_select, tag="combo_scenario")

            # Target speed
            dpg.add_text("Target Speed (px/s):")
            dpg.add_slider_float(min_value=20.0, max_value=350.0, default_value=120.0,
                                 callback=self._on_speed_change, tag="slider_target_speed")

            # Disturbance preset
            dpg.add_text("Disturbance Intensity:")
            dpg.add_combo(["NORMAL", "LIGHT DISTURBANCE", "MODERATE DISTURBANCE", "SEVERE DISTURBANCE", "EXTREME STRESS TEST"],
                          default_value="NORMAL", callback=self._on_disturbance_preset_change, tag="combo_disturbance")

            dpg.add_spacer(height=6)
            dpg.add_text("PIPELINE TOGGLES (SIH DEMO SWITCHES):", color=(0, 230, 118))
            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_button(label="Detector: Classical (D)", callback=self._on_toggle_detector, tag="btn_toggle_det")
                dpg.add_button(label="Kalman: ON (K)", callback=self._on_toggle_kalman, tag="btn_toggle_kalman")

            with dpg.group(horizontal=True):
                dpg.add_button(label="Prediction: ON (P)", callback=self._on_toggle_prediction, tag="btn_toggle_pred")
                dpg.add_button(label="Control: PID (C)", callback=self._on_toggle_control_mode, tag="btn_toggle_ctrl")

            dpg.add_spacer(height=6)
            dpg.add_text("PID GAIN TUNING:")
            dpg.add_slider_float(label="Kp", min_value=0.05, max_value=1.5, default_value=0.45,
                                 callback=self._on_pid_change, tag="slider_kp")
            dpg.add_slider_float(label="Ki", min_value=0.00, max_value=0.1, default_value=0.01,
                                 callback=self._on_pid_change, tag="slider_ki")
            dpg.add_slider_float(label="Kd", min_value=0.00, max_value=0.5, default_value=0.10,
                                 callback=self._on_pid_change, tag="slider_kd")

    # ------------------------------------------------------------------ #
    # ZONE 5: PERFORMANCE PANEL
    # ------------------------------------------------------------------ #
    def _create_performance_panel(self):
        with dpg.child_window(height=260, border=True):
            with dpg.group(horizontal=True):
                dpg.add_text("ZONE 5: PERFORMANCE ANALYTICS & LIVE PLOTS", color=(0, 176, 255))
                dpg.add_spacer(width=20)
                dpg.add_text("Acq Time:", color=(140, 150, 170))
                dpg.add_text("0.42 s", tag="perf_acq_time", color=(0, 230, 118))
                dpg.add_spacer(width=15)
                dpg.add_text("Lock Retention:", color=(140, 150, 170))
                dpg.add_text("95.2%", tag="perf_lock_ret", color=(0, 230, 118))
                dpg.add_spacer(width=15)
                dpg.add_text("RMS Error:", color=(140, 150, 170))
                dpg.add_text("2.15 px", tag="perf_rms_err", color=(0, 230, 118))

            with dpg.group(horizontal=True):
                # Plot 1: Tracking Error
                with dpg.plot(label="Boresight Tracking Error (px)", height=200, width=460):
                    dpg.add_plot_legend()
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frame", no_tick_labels=True)
                    with dpg.plot_axis(dpg.mvYAxis, label="Pixels"):
                        dpg.add_line_series([], [], label="Error", tag="plot_err_series")

                # Plot 2: Detection Confidence
                with dpg.plot(label="Detector Confidence", height=200, width=440):
                    dpg.add_plot_legend()
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frame", no_tick_labels=True)
                    with dpg.plot_axis(dpg.mvYAxis, label="Score [0-1]"):
                        dpg.add_line_series([], [], label="Confidence", tag="plot_conf_series")

                # Plot 3: Frame Rate
                with dpg.plot(label="System Frame Rate (FPS)", height=200, width=460):
                    dpg.add_plot_legend()
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frame", no_tick_labels=True)
                    with dpg.plot_axis(dpg.mvYAxis, label="FPS"):
                        dpg.add_line_series([], [], label="Rate", tag="plot_fps_series")

    # ------------------------------------------------------------------ #
    # Event Handlers & Callbacks
    # ------------------------------------------------------------------ #
    def toggle_pause(self):
        self.paused = not self.paused

    def reset_simulation(self):
        self.world = World(self.config)
        self.camera = VirtualCamera(self.config.camera, self.config.world)
        self.kalman.reset()
        self.controller.reset()
        self.fsm.reset()
        self.metrics_collector.reset()
        self._frame_count = 0
        self._sim_time = 0.0
        self._time_hist.clear()
        self._error_hist.clear()
        self._conf_hist.clear()
        self._fps_hist.clear()
        self.in_judge_demo = False

    def _start_judge_demo(self):
        self.in_judge_demo = True
        self.judge_demo.reset()

    def _on_scenario_select(self, sender, app_data):
        scen_id = app_data.split("—")[0].strip()
        scen = get_scenario(scen_id)
        if scen:
            self.world.primary_beacon.set_motion_model(scen.target_config.get("motion_model", "sinusoidal"))
            self.world.primary_beacon.speed = scen.target_config.get("speed", 120.0)
            dpg.set_value("slider_target_speed", scen.target_config.get("speed", 120.0))
            preset = scen.disturbance_config.get("preset", "NORMAL")
            self.disturbance.load_preset(preset)
            dpg.set_value("combo_disturbance", preset)

    def _on_speed_change(self, sender, app_data):
        self.world.primary_beacon.speed = float(app_data)

    def _on_disturbance_preset_change(self, sender, app_data):
        self.disturbance.load_preset(app_data)

    def _on_toggle_detector(self):
        if "Classical" in self.detector_type_str:
            self.detector = create_detector("ai", confidence_threshold=0.45)
            self.detector_type_str = "AI Detector (YOLO)"
            dpg.set_item_label("btn_toggle_det", "Detector: AI YOLO (D)")
        else:
            self.detector = create_detector("classical",
                                            hsv_low=self.config.beacon.color_hsv_low,
                                            hsv_high=self.config.beacon.color_hsv_high)
            self.detector_type_str = "Classical CV (HSV)"
            dpg.set_item_label("btn_toggle_det", "Detector: Classical (D)")

    def _on_toggle_kalman(self):
        self.kalman_enabled = not self.kalman_enabled
        label = f"Kalman: {'ON' if self.kalman_enabled else 'OFF'} (K)"
        dpg.set_item_label("btn_toggle_kalman", label)

    def _on_toggle_prediction(self):
        self.prediction_enabled = not self.prediction_enabled
        label = f"Prediction: {'ON' if self.prediction_enabled else 'OFF'} (P)"
        dpg.set_item_label("btn_toggle_pred", label)

    def _on_toggle_control_mode(self):
        if self.controller.mode == ControllerMode.PID_CONTROL:
            self.controller.set_mode(ControllerMode.P_CONTROL)
            dpg.set_item_label("btn_toggle_ctrl", "Control: P (C)")
        elif self.controller.mode == ControllerMode.P_CONTROL:
            self.controller.set_mode(ControllerMode.DIRECT)
            dpg.set_item_label("btn_toggle_ctrl", "Control: Direct (C)")
        else:
            self.controller.set_mode(ControllerMode.PID_CONTROL)
            dpg.set_item_label("btn_toggle_ctrl", "Control: PID (C)")

    def _on_pid_change(self, sender=None, app_data=None):
        kp = dpg.get_value("slider_kp")
        ki = dpg.get_value("slider_ki")
        kd = dpg.get_value("slider_kd")
        self.controller.set_parameters(kp=kp, ki=ki, kd=kd)

    def _export_pdf_report(self):
        evaluator = PerformanceEvaluator()
        m = self.metrics_collector.get_realtime_metrics_dict()
        status, checklist = evaluator.evaluate(m)
        report = PerformanceReport(
            run_id=f"RUN_{int(time.time())}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            scenario=dpg.get_value("combo_scenario"),
            configuration={"fov_w": self.config.camera.fov_width, "fov_h": self.config.camera.fov_height},
            disturbance_settings={"preset": self.disturbance.active_preset_name},
            detector=self.detector_type_str,
            controller=self.controller.mode.name,
            filter_settings={"enabled": self.kalman_enabled, "prediction": self.prediction_enabled},
            metrics=m,
            pass_fail_status=status,
            criteria_checklist=checklist
        )
        pdf_path = f"outputs/reports/Performance_Audit_{report.run_id}.pdf"
        ReportExporter.export_pdf(report, pdf_path)
        print(f"[INFO] Performance Audit PDF exported to: {pdf_path}")

    # ------------------------------------------------------------------ #
    # Main Simulation Step Loop
    # ------------------------------------------------------------------ #
    def _tick(self):
        """Execute one simulation frame across all subsystems."""
        if self.paused:
            return

        dt = DEFAULT_DT
        t0 = time.perf_counter()

        # Judge Demo override if active
        if self.in_judge_demo:
            phase, is_done = self.judge_demo.step(dt)
            degraded_frame = self.judge_demo.camera.capture(self.judge_demo.world.render())
            degraded_frame = draw_demo_timeline(degraded_frame, phase, self.judge_demo.sim_time, 90.0)

            # Update status badge
            dpg.set_item_label("top_status_badge", f"[ {phase.value} ]")
            dpg.set_value("top_clock_text", f"T+{self.judge_demo.sim_time:04.1f}s")

            # Texture update
            rgba = cv2.cvtColor(degraded_frame, cv2.COLOR_BGR2RGBA).astype(np.float32) / 255.0
            dpg.set_value("viewport_texture", rgba.flatten())
            return

        self._sim_time += dt
        self._frame_count += 1

        # 1. Physics & Camera Jitter
        self.world.tick(dt)
        jx, jy, _, _ = self.disturbance.get_camera_perturbations(self._sim_time)
        self.camera.add_jitter(jx, jy)

        # 2. Camera FOV Capture & Disturbance Injection
        world_frame = self.world.render()
        fov_frame = self.camera.capture(world_frame)
        beacon_fov = self.camera.world_to_fov(self.world.primary_beacon.x, self.world.primary_beacon.y)
        degraded_frame = self.disturbance.apply_image_disturbances(fov_frame, self._sim_time, beacon_fov)

        # 3. Detection
        t_det_0 = time.perf_counter()
        detection = self.detector.detect(degraded_frame)
        inf_time = (time.perf_counter() - t_det_0) * 1000.0
        is_det = detection is not None and (getattr(detection, "confidence", 0.0) > 0.3)
        conf = getattr(detection, "confidence", 0.9) if is_det else 0.0

        # 4. Estimation & Prediction
        est_pos = self.camera.fov_center
        pred_pos = est_pos
        predicted_points = []

        if self.kalman_enabled:
            track_state = self.kalman.update(detection, dt=dt)
            est_pos = track_state.estimated_pos
            if self.prediction_enabled:
                predicted_points = self.predictor.predict_trajectory(track_state, dt=dt)
                pred_pos = predicted_points[-1] if predicted_points else est_pos
        elif detection:
            est_pos = (detection.x, detection.y)
            pred_pos = est_pos

        # 5. Tracking FSM
        det_coords = (detection.x, detection.y) if is_det else None
        fsm_state = self.fsm.update(
            detection_pos=det_coords,
            confidence=conf,
            estimated_pos=est_pos,
            predicted_pos=pred_pos,
            camera_center=self.camera.fov_center,
            sim_time=self._sim_time,
            dt=dt
        )
        setpoint = self.fsm.get_tracking_setpoint(self.camera.fov_center)

        # 6. Actuation Command
        ctrl_out = self.controller.compute(setpoint, self.camera.fov_center, dt=dt)
        self.camera.actuate(ctrl_out.pan_command, ctrl_out.tilt_command, dt=dt)

        total_lat = (time.perf_counter() - t0) * 1000.0

        # 7. Metrics Collection
        err_px = ctrl_out.pan_error_px
        err_py = ctrl_out.tilt_error_px
        total_err_px = math.hypot(err_px, err_py)

        self.metrics_collector.record_frame(
            sim_time=self._sim_time,
            is_detected=is_det,
            confidence=conf,
            inference_time_ms=inf_time,
            processing_latency_ms=total_lat,
            tracking_error_px=total_err_px,
            camera_angular_error_deg=total_err_px * self.config.camera.deg_per_pixel,
            is_locked=fsm_state in (FSMState.LOCKED, FSMState.TRACKING)
        )

        # 8. Render Aerospace Viewport Overlays
        display_frame = draw_aerospace_viewport(
            degraded_frame,
            self.camera.fov_center,
            detection=detection,
            predicted_points=predicted_points,
            status_text=fsm_state.value,
            error_px=total_err_px,
            error_deg=total_err_px * self.config.camera.deg_per_pixel,
            confidence=conf,
            latency_ms=total_lat
        )

        # Update viewport texture
        rgba = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGBA).astype(np.float32) / 255.0
        dpg.set_value("viewport_texture", rgba.flatten())

        # 9. Update Real-Time Telemetry Displays
        self._update_telemetry_ui(ctrl_out, conf, total_lat, fsm_state)

    def _update_telemetry_ui(self, ctrl_out, conf: float, latency_ms: float, fsm_state: FSMState):
        """Update text readouts and rolling plots."""
        # Top bar
        dpg.set_item_label("top_status_badge", f"[ {fsm_state.value} ]")
        dpg.set_value("top_fps_text", f"{self.metrics_collector.fps:04.1f} FPS")
        dpg.set_value("top_latency_text", f"{latency_ms:04.1f} ms")
        mins = int(self._sim_time // 60)
        secs = self._sim_time % 60
        dpg.set_value("top_clock_text", f"T+{mins:02d}:{secs:04.1f}")

        # Zone 3: Telemetry
        dpg.set_value("telem_pos_fov", f"({ctrl_out.pan_error_px + self.camera.fov_center[0]:.1f}, {ctrl_out.tilt_error_px + self.camera.fov_center[1]:.1f}) px")
        dpg.set_value("telem_vel", f"+{self.camera.pan_rate:.1f}, +{self.camera.tilt_rate:.1f} °/s")
        dpg.set_value("telem_conf", f"{conf:.2f}")
        dpg.set_value("telem_pan", f"{self.camera.pan:+.1f}° ({self.camera.pan_rate:+.1f}°/s)")
        dpg.set_value("telem_tilt", f"{self.camera.tilt:+.1f}° ({self.camera.tilt_rate:+.1f}°/s)")
        err_mag = math.hypot(ctrl_out.pan_error_px, ctrl_out.tilt_error_px)
        dpg.set_value("telem_err", f"{err_mag:.1f} px ({err_mag * self.config.camera.deg_per_pixel:.2f}°)")
        dpg.set_value("telem_ctrl", f"P: {ctrl_out.pan_command:+.2f}, T: {ctrl_out.tilt_command:+.2f}")
        dpg.set_value("telem_lat", f"{latency_ms:.1f} ms")

        dpg.set_value("telem_losses", f"Losses: {self.fsm.metrics.number_of_losses}  |  Recoveries: {self.fsm.metrics.number_of_recoveries}")
        dpg.set_value("telem_rec_time", f"Last: {self.fsm.metrics.last_recovery_time:.2f} s  |  Mean: {self.fsm.metrics.mean_recovery_time:.2f} s")

        # Zone 5: Performance Scorecard
        dpg.set_value("perf_acq_time", f"{self.metrics_collector.acquisition_time_s:.2f} s")
        dpg.set_value("perf_lock_ret", f"{self.metrics_collector.lock_retention_rate_pct:.1f}%")
        dpg.set_value("perf_rms_err", f"{self.metrics_collector.rms_tracking_error_px:.2f} px")

        # Rolling plots update
        self._time_hist.append(self._frame_count)
        self._error_hist.append(err_mag)
        self._conf_hist.append(conf)
        self._fps_hist.append(self.metrics_collector.fps)

        if len(self._time_hist) > self._max_history:
            self._time_hist.pop(0)
            self._error_hist.pop(0)
            self._conf_hist.pop(0)
            self._fps_hist.pop(0)

        if self._frame_count % 3 == 0:
            dpg.set_value("plot_err_series", [self._time_hist, self._error_hist])
            dpg.set_value("plot_conf_series", [self._time_hist, self._conf_hist])
            dpg.set_value("plot_fps_series", [self._time_hist, self._fps_hist])

    def run(self):
        """Start the interactive GUI rendering loop."""
        self.running = True
        while dpg.is_dearpygui_running():
            self._tick()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()
