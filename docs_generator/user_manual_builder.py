"""
ASTRATRACK — Aerospace User Manual Builder

Generates the comprehensive operational User Manual for engineers, operators, and evaluators.
Covers UI layout, controls, keyboard shortcuts, labs, experiments, judge demo, and export formats.
"""

from typing import Optional


class UserManualBuilder:
    """Builds the comprehensive ASTRATRACK User Manual."""

    def build_markdown(self) -> str:
        md = []

        md.append(
            "# ASTRATRACK: System Operation & User Manual\n"
            "**Document Classification:** Engineering User Manual & Operator Guide  \n"
            "**Project:** Smart India Hackathon (SIH 2026) — Aerospace R&D Category  \n"
            "**System:** Virtual Camera Tracking & Coarse Alignment Simulator for FSOC  \n\n"
            "---\n"
        )

        md.append(
            "## 1. System Overview\n\n"
            "ASTRATRACK is an aerospace-grade simulation and evaluation platform engineered to test and benchmark "
            "coarse pointing, acquisition, and tracking (PAT) algorithms for Free Space Optical Communication (FSOC). "
            "It couples a dynamic 3D optical beacon environment with a virtual camera, realistic actuator dynamics, "
            "a 10-channel disturbance engine, AI/classical perception pipelines, discrete-time Kalman filtering, "
            "and closed-loop PID control laws.\n\n"
            "The system runs entirely offline without internet dependencies, ensuring 100% deterministic reproducibility "
            "and security compliance for air-gapped aerospace ground stations.\n"
        )

        md.append(
            "## 2. Dashboard Layout (5 Primary Zones)\n\n"
            "The user interface is modeled after mission-critical satellite ground station consoles, utilizing high-contrast, "
            "dark aerospace styling organized into 5 dedicated zones:\n\n"
            "### Zone 1: TOP BAR\n"
            "- **ASTRATRACK Identity & Status Badge:** Displays current system operational status (`INITIALIZING`, `IDLE`, `TRACKING`, `BENCHMARKING`).\n"
            "- **FSM Tracking State:** Real-time state pill (`SEARCHING`, `ACQUIRING`, `LOCKED`, `TRACKING`, `TARGET_LOST`, `PREDICTING`, `REACQUIRING`).\n"
            "- **Real-time Telemetry:** Instantaneous simulation FPS, detection rate, and elapsed mission time.\n"
            "- **Global Actions:** Quick-access buttons for *Pause/Resume*, *Reset*, *Judge Demo*, and *Run Benchmark*.\n\n"
            "### Zone 2: MAIN VIEWPORT\n"
            "- **Optical Sensor Feed:** Real-time rendered video stream of the synthetic optical beacon.\n"
            "- **Optical Boresight Reticle:** High-precision crosshairs denoting camera center $(W/2, H/2)$.\n"
            "- **Target Reticle:** Aerospace corner-bracket bounding box tracking the beacon centroid.\n"
            "- **Kalman State Vectors:** Visual centroid dot and predicted trajectory vector.\n"
            "- **Forward Bead Prediction Trail:** Multi-step forward state predictions visualizing acceleration.\n"
            "- **Search Pattern Overlay:** Real-time rendering of Archimedean spiral re-acquisition search paths.\n\n"
            "### Zone 3: TELEMETRY PANEL\n"
            "- **Target Pixel Position:** Centroid coordinates $(X, Y)$ in sensor pixel plane.\n"
            "- **Angular Error:** Real-time boresight error in degrees (Pan Error, Tilt Error).\n"
            "- **Tracking Error Magnitude:** Euclidean error in pixels and micro-radians.\n"
            "- **Camera Gimbal State:** Current camera pan angle, tilt angle, and slew angular velocities.\n"
            "- **Detection Confidence:** Normalized detection probability $[0.0, 1.0]$.\n"
            "- **Latency Telemetry:** Optical inference latency (ms) and total closed-loop processing latency (ms).\n\n"
            "### Zone 4: CONTROL PANEL\n"
            "- **Scenario Selector:** Dropdown menu for scenarios 01 through 10.\n"
            "- **Perception Selector:** Toggle between Classical HSV Moments and Deep AI Neural Detector.\n"
            "- **Estimator Selector:** Discrete Kalman Filter Constant Velocity (CV-4) vs Constant Acceleration (CA-6).\n"
            "- **Prediction Engine:** Enable/disable forward lead prediction.\n"
            "- **Controller Law:** Toggle between Direct Proportional and Dual-Axis PID Control.\n"
            "- **PID Gain Sliders:** Interactive real-time tuning for $K_p$, $K_i$, $K_d$, and dead-zone threshold.\n"
            "- **Disturbance Presets:** Instant selection of `NORMAL`, `LIGHT`, `MODERATE`, `SEVERE`, and `EXTREME` presets.\n\n"
            "### Zone 5: PERFORMANCE PANEL\n"
            "- **Live Telemetry Strip Charts:** Real-time scrolling graphs for Tracking Error (px), Frame Rate (FPS), and Detection Confidence.\n"
            "- **Key Performance Indicators (KPIs):** Lock Retention Rate (%), Mean RMS Error (px), Acquisition Time (s), and Recovery Latency (s).\n"
            "- **Export Actions:** One-click generation of CSV telemetry logs, JSON reports, and ReportLab PDF executive summaries.\n"
        )

        md.append(
            "## 3. Keyboard Shortcuts & Operational Controls\n\n"
            "| Key | Action | Function |\n"
            "|---|---|---|\n"
            "| **Space** | Pause / Resume | Freezes simulation state and camera actuators for inspection. |\n"
            "| **R** | Reset Simulation | Resets camera angles, target positions, and telemetry buffers to initial state. |\n"
            "| **D** | Launch Judge Demo | Initiates the automated 10-phase scripted demonstration (<90s). |\n"
            "| **C** | Comparison Lab | Opens the multi-mode algorithm comparison laboratory dialog. |\n"
            "| **1 – 9** | Scenario Select | Directly switches operational scenario to Scenario 01 through 09. |\n"
            "| **0** | Extreme Stress | Directly loads Scenario 10 (Extreme Stress Test). |\n"
            "| **P** | Toggle Prediction | Enables or bypasses the multi-step forward motion predictor. |\n"
            "| **K** | Toggle Kalman | Toggles between raw optical detections and Kalman state filtering. |\n"
            "| **F** | Toggle Fullscreen | Maximizes the aerospace dashboard viewport. |\n"
        )

        md.append(
            "## 4. Scenario Lab\n\n"
            "The Scenario Lab allows operators to test tracking algorithms across standardized operational environments:\n\n"
            "1. **01 — Baseline Coarse Alignment:** Smooth low-velocity target with zero atmospheric disturbance.\n"
            "2. **02 — High Speed Target:** Rapid angular traversal requiring high gimbal slew rates.\n"
            "3. **03 — Target Acceleration:** Dynamic weaving and sudden acceleration steps testing derivative response.\n"
            "4. **04 — Camera Vibration:** High-frequency harmonic oscillation simulating reaction wheel resonance.\n"
            "5. **05 — Image Noise:** Low signal-to-noise ratio (SNR) sensor noise testing detection thresholds.\n"
            "6. **06 — Turbulence:** Spatial optical distortion simulating atmospheric refractive index fluctuations.\n"
            "7. **07 — Temporary Occlusion:** Solid cloud or barrier occlusion testing coasting and re-acquisition.\n"
            "8. **08 — Target Loss:** Complete signal interruption testing FSM loss transitions.\n"
            "9. **09 — Combined Disturbance:** Multi-channel stress combining noise, vibration, and turbulence.\n"
            "10. **10 — Extreme Stress Test:** 100% intensity across all 10 disturbance channels simultaneously.\n\n"
            "### Custom Scenario Builder\n"
            "Operators can construct custom scenarios by adjusting target trajectory parameters, camera properties, "
            "and individual disturbance channels. Scenarios can be exported and imported as standardized `.yaml` scenario manifests.\n"
        )

        md.append(
            "## 5. Algorithm Comparison Lab\n\n"
            "The Comparison Lab performs rigorous side-by-side benchmarking across four standardized algorithmic pipelines:\n\n"
            "- **Mode A (Classical + Direct):** HSV color thresholding with direct proportional camera drive.\n"
            "- **Mode B (AI + PID):** Deep neural detection with dual-axis PID control.\n"
            "- **Mode C (AI + Kalman + PID):** Neural detection fused with a 6-state Kalman filter and PID control.\n"
            "- **Mode D (Full Pipeline):** Complete architecture (AI + Kalman Filter + Motion Prediction + PID Control + FSM Re-acquisition).\n\n"
            "### Benchmark Execution Procedure\n"
            "1. Click **Run Benchmark** on the top toolbar or press `C`.\n"
            "2. Select the operational test scenario (e.g. *Scenario 01 Baseline* or *Scenario 09 Combined Disturbance*).\n"
            "3. Set test duration (default: 150 frames) and random seed (default: 42).\n"
            "4. Click **Execute Benchmark**. The lab will sequentially run Modes A through D, recording telemetry.\n"
            "5. The system renders a comparative metrics table and a 4-panel visual comparison chart.\n"
        )

        md.append(
            "## 6. Experiment Manager & Reproducibility\n\n"
            "The Experiment Manager provides a scientific audit trail for aerospace research:\n\n"
            "- **Save Experiment:** Captures complete system provenance (git commit, configuration parameters, controller gains, disturbance settings, master seed, and full time-series telemetry).\n"
            "- **Load Experiment:** Inspects historical experiment runs stored in `experiments_store/`.\n"
            "- **Compare Experiments:** Displays multi-run comparison tables and error distribution overlays.\n"
            "- **Reproduce Experiment:** Automatically loads an experiment manifest, configures the identical scenario, pipeline, and seed, and re-executes the simulation. The resulting metrics will match bit-exactly.\n"
        )

        md.append(
            "## 7. Dedicated Judge Demo Mode (<90 Seconds)\n\n"
            "The Judge Demo mode is an automated, self-guided operational demonstration designed for hackathon judges and evaluators. "
            "It runs in under 90 seconds without human intervention:\n\n"
            "1. **Phase 1: DETECT (t = 0.0s):** Spawns optical beacon in peripheral field of view; AI detector acquires beacon.\n"
            "2. **Phase 2: ACQUIRE (t = 6.0s):** Controller initiates camera slew; aligns optical boresight with target.\n"
            "3. **Phase 3: TRACK (t = 14.0s):** FSM confirms target lock; camera tracks beacon with sub-pixel steady-state error.\n"
            "4. **Phase 4: HIGH SPEED (t = 22.0s):** Beacon increases velocity; PID derivative control suppresses transient lag.\n"
            "5. **Phase 5: DISTURBANCE (t = 32.0s):** Injects camera vibration and atmospheric turbulence; Kalman filter suppresses jitter.\n"
            "6. **Phase 6: PREDICT (t = 42.0s):** Motion predictor projects 5-step forward trajectory; forward lead bead trail renders.\n"
            "7. **Phase 7: TARGET LOST (t = 50.0s):** Injects complete optical occlusion; FSM triggers `TARGET_LOST`.\n"
            "8. **Phase 8: COAST (t = 56.0s):** Camera coasts along predicted trajectory without erratic diverging motions.\n"
            "9. **Phase 9: REACQUIRE (t = 64.0s):** Occlusion clears; Archimedean spiral search detects beacon and restores `LOCKED`.\n"
            "10. **Phase 10: COMPLETE (t = 76.0s):** Freezes simulation and displays the official Judge Evaluation Scorecard.\n"
        )

        md.append(
            "## 8. Data Exporting & Verification\n\n"
            "- **CSV Telemetry:** Full per-frame time series saved to `outputs/telemetry_<run_id>.csv`.\n"
            "- **JSON Performance Report:** Machine-readable performance manifest with PASS/MARGINAL/FAIL evaluations saved to `outputs/report_<run_id>.json`.\n"
            "- **Executive PDF Report:** Publication-grade ReportLab document containing summary tables and metadata saved to `outputs/report_<run_id>.pdf`.\n"
        )

        return "\n".join(md)
