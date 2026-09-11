"""
ASTRATRACK — System Architecture Documentation Builder

Generates the in-depth System Architecture Documentation including:
- Mermaid diagrams for component hierarchy, dataflow, and state transitions
- Coordinate frame transformations and projection mathematics
- Detailed mathematical formulations for Kalman filtering, PID control, and spiral re-acquisition
- Real-time threading, determinism, and data structures
"""

from typing import Optional


class ArchitectureDocBuilder:
    """Builds the comprehensive System Architecture Document."""

    def build_markdown(self) -> str:
        md = []

        md.append(
            "# ASTRATRACK: System Architecture & Design Specification\n"
            "**Document Classification:** Engineering Architecture Documentation  \n"
            "**Project:** Smart India Hackathon (SIH 2026) — Aerospace R&D Category  \n"
            "**System Architecture:** Multi-Tier Deterministic Closed-Loop Simulation & Tracking Engine  \n\n"
            "---\n"
        )

        md.append(
            "## 1. Architectural Principles\n\n"
            "ASTRATRACK is architected around five core principles essential for mission-critical aerospace simulation:\n\n"
            "1. **Strict Modularity & Decoupled Layers:** Physical simulation, perception, state estimation, control, and user presentation exist in isolated, interface-driven packages.\n"
            "2. **Bit-Exact Determinism:** Master-seed random number generation ensures that any simulation scenario can be recreated bit-for-bit, enabling scientific reproducibility.\n"
            "3. **Air-Gapped Self-Containment:** The simulation possesses zero dependencies on cloud APIs, internet connectivity, or proprietary runtime services.\n"
            "4. **Multi-Rate Operational Bandwidth:** The tracking control loop executes at up to 120 Hz, perception at 30–60 Hz, and telemetry visualization at 60 Hz.\n"
            "5. **Zero-Fake Data Guarantee:** All telemetry, metrics, and reports are directly derived from online mathematical evaluation of simulation states.\n"
        )

        md.append(
            "## 2. High-Level System Component Diagram\n\n"
            "The diagram below illustrates the major subsystems and their inter-relationships:\n\n"
            "```mermaid\n"
            "graph TD\n"
            "    subgraph SIMULATION_CORE [Simulation Core]\n"
            "        W[3D World & Target Kinematics] --> C[Virtual Camera Body]\n"
            "        C --> D[10-Channel Disturbance Engine]\n"
            "    end\n\n"
            "    subgraph PERCEPTION_TIER [Perception Tier]\n"
            "        D -->|Degraded Frame| P[Perception Engine: AI / Classical]\n"
            "    end\n\n"
            "    subgraph ESTIMATION_AND_TRACKING [Estimation & Tracking Tier]\n"
            "        P -->|Raw Centroid & Conf| FSM[Target-Loss & Re-Acquisition FSM]\n"
            "        P -->|Observations| KF[6-State Kalman Filter]\n"
            "        KF -->|State Est & Covariance| MP[Multi-Step Motion Predictor]\n"
            "        FSM -->|Search Waypoint / Mode| KF\n"
            "    end\n\n"
            "    subgraph CONTROL_TIER [Control Tier]\n"
            "        MP -->|Target Error| CC[Camera Controller: Dual-Axis PID]\n"
            "        CC -->|Pan/Tilt Rate Cmds| C\n"
            "    end\n\n"
            "    subgraph METRICS_AND_UI [Telemetry & Presentation Tier]\n"
            "        P --> MET[16-Metric Performance Collector]\n"
            "        KF --> MET\n"
            "        CC --> MET\n"
            "        MET --> UI[Aerospace Engineering Dashboard]\n"
            "    end\n"
            "```\n"
        )

        md.append(
            "## 3. Data Flow & Processing Pipeline\n\n"
            "The data flow pipeline executes sequentially on every simulation step $\\Delta t$:\n\n"
            "```mermaid\n"
            "sequenceDiagram\n"
            "    autonumber\n"
            "    participant W as World / Target\n"
            "    participant Cam as Virtual Camera\n"
            "    participant Dist as Disturbance Engine\n"
            "    participant Det as Perception (AI/CV)\n"
            "    participant FSM as Tracking FSM\n"
            "    participant Est as Kalman Estimator\n"
            "    participant Ctrl as PID Controller\n"
            "    participant Met as Metrics Collector\n\n"
            "    W->>Cam: Update 3D Beacon Position (X, Y, Z)\n"
            "    Cam->>Dist: Render Pristine Sensor Frame\n"
            "    Dist->>Det: Inject Active Disturbance Channels (Noise/Turb/Blur)\n"
            "    Det->>FSM: Extracted BBox, Centroid (u, v), Confidence\n"
            "    FSM->>Est: State Transition (Tracking / Coasting / Spiral Search)\n"
            "    Est->>Ctrl: Filtered State & Forward Predicted Coordinates\n"
            "    Ctrl->>Cam: Dual-Axis Angular Rate Commands (dPan, dTilt)\n"
            "    Cam->>Cam: Integrate Gimbal Kinematics & Update Actuators\n"
            "    Cam->>Met: Log Tracking Error, FPS, and Lock Status\n"
            "```\n"
        )

        md.append(
            "## 4. Finite State Machine (FSM) Transition Model\n\n"
            "The target loss and re-acquisition engine operates as a 7-state finite state machine:\n\n"
            "```mermaid\n"
            "stateDiagram-v2\n"
            "    [*] --> SEARCHING\n"
            "    SEARCHING --> ACQUIRING: Target Detected (Conf >= Threshold)\n"
            "    ACQUIRING --> LOCKED: Confirmed for N consecutive frames\n"
            "    ACQUIRING --> SEARCHING: Lost before confirmation\n"
            "    LOCKED --> TRACKING: Optical lock achieved\n"
            "    TRACKING --> TARGET_LOST: Conf < Threshold for N_loss frames\n"
            "    TARGET_LOST --> PREDICTING: Kalman forward extrapolation active\n"
            "    PREDICTING --> REACQUIRING: Execute Archimedean spiral search\n"
            "    REACQUIRING --> LOCKED: Beacon redetected within search zone\n"
            "    REACQUIRING --> SEARCHING: Search timeout exceeded (Full reset)\n"
            "```\n"
        )

        md.append(
            "## 5. Coordinate Systems & Spatial Transformations\n\n"
            "ASTRATRACK implements four distinct right-handed coordinate frames:\n\n"
            "### 5.1 World Frame $\\mathcal{F}_w$\n"
            "Origin at ground station optical terminal base. Coordinates $\\mathbf{p}_w = [X_w, Y_w, Z_w]^T$. "
            "Defines absolute spatial positions of optical beacon and ground station platform.\n\n"
            "### 5.2 Camera Body Frame $\\mathcal{F}_c$\n"
            "Origin at camera entrance pupil. $Z_c$ aligned with optical boresight, $X_c$ rightwards, $Y_c$ upwards. "
            "Transformed from world frame via camera position $\\mathbf{p}_{cam}$ and Euler rotation angles $(\\psi, \\theta)$ (Pan, Tilt):\n"
            "$$\\mathbf{p}_c = R_y(\\theta) R_z(\\psi) (\\mathbf{p}_w - \\mathbf{p}_{cam})$$\n\n"
            "### 5.3 Pixel Sensor Plane $\\mathcal{F}_p$\n"
            "2D discrete sensor array $(W \\times H)$ with origin at top-left pixel. "
            "Pinhole perspective projection with focal length $f_x, f_y$ and principal point $(c_x, c_y)$:\n"
            "$$u = f_x \\frac{X_c}{Z_c} + c_x, \\quad v = f_y \\frac{Y_c}{Z_c} + c_y$$\n\n"
            "### 5.4 Actuator Angular Rate Space $\\mathcal{F}_a$\n"
            "Translates pixel error into camera gimbal angular rate commands $(\\dot{\\psi}, \\dot{\\theta})$:\n"
            "$$\\dot{\\psi}_{cmd} = \\text{PID}_{pan}(u - c_x), \\quad \\dot{\\theta}_{cmd} = -\\text{PID}_{tilt}(v - c_y)$$\n"
        )

        md.append(
            "## 6. Mathematical Formulations\n\n"
            "### 6.1 Discrete Kalman Filter (Constant Acceleration CA Model)\n"
            "- **State Vector:** $\\mathbf{x} = [x, y, v_x, v_y, a_x, a_y]^T$\n"
            "- **Continuous White Noise Acceleration (CWNA) Covariance:**\n"
            "  $$Q = \\begin{bmatrix} Q_{1D} & 0 \\\\ 0 & Q_{1D} \\end{bmatrix}, \\quad Q_{1D} = q_c \\begin{bmatrix} \\frac{\\Delta t^5}{20} & \\frac{\\Delta t^4}{8} & \\frac{\\Delta t^3}{6} \\\\ \\frac{\\Delta t^4}{8} & \\frac{\\Delta t^3}{3} & \\frac{\\Delta t^2}{2} \\\\ \\frac{\\Delta t^3}{6} & \\frac{\\Delta t^2}{2} & \\Delta t \\end{bmatrix}$$\n"
            "- **Measurement Update with Innovation:**\n"
            "  $$\\mathbf{y}_k = \\mathbf{z}_k - H \\hat{\\mathbf{x}}_{k|k-1}$$\n"
            "  $$S_k = H P_{k|k-1} H^T + R$$\n"
            "  $$K_k = P_{k|k-1} H^T S_k^{-1}$$\n"
            "  $$\\hat{\\mathbf{x}}_{k|k} = \\hat{\\mathbf{x}}_{k|k-1} + K_k \\mathbf{y}_k$$\n"
            "  $$P_{k|k} = (I - K_k H) P_{k|k-1} (I - K_k H)^T + K_k R K_k^T \\quad \\text{(Joseph Stabilized Form)}$$\n\n"
            "### 6.2 Dual-Axis PID Control with Anti-Windup & Derivative Filter\n"
            "- **Integral Accumulation:**\n"
            "  $$I(k) = I(k-1) + e(k) \\Delta t$$\n"
            "  $$I(k) = \\text{clamp}\\left(I(k), -\\frac{u_{max}}{K_i}, \\frac{u_{max}}{K_i}\\right)$$\n"
            "- **Filtered Derivative:**\n"
            "  $$D(k) = \\alpha \\frac{e(k) - e(k-1)}{\\Delta t} + (1 - \\alpha) D(k-1)$$\n"
            "- **Total Output with Dead-Zone:**\n"
            "  $$u(k) = \\begin{cases} 0 & \\text{if } |e(k)| \\le e_{dead} \\\\ \\text{clamp}(K_p e(k) + K_i I(k) + K_d D(k), -u_{max}, u_{max}) & \\text{otherwise} \\end{cases}$$\n\n"
            "### 6.3 Archimedean Spiral Re-Acquisition Path\n"
            "When entering `REACQUIRING`, search coordinates are generated parameterized by angular displacement $\\theta(t) = \\omega t$:\n"
            "$$r(t) = r_0 + \\frac{v_{search}}{2\\pi} \\theta(t)$$\n"
            "$$x_{cmd}(t) = x_{last} + r(t) \\cos(\\theta(t)), \\quad y_{cmd}(t) = y_{last} + r(t) \\sin(\\theta(t))$$\n"
            "Guaranteeing uniform spatial scanning of the uncertainty ellipse without blind spots.\n"
        )

        md.append(
            "## 7. Threading, Timing, and Determinism\n\n"
            "- **Synchronous Simulation Stepping:** All submodules advance via a unified discrete time-step $\\Delta t = 1/FPS$.\n"
            "- **Master PRNG Architecture:** High-quality Mersenne Twister / PCG streams keyed by master seed, ensuring zero cross-run divergence.\n"
            "- **UI Decoupling:** The UI rendering loop is decoupled from simulation updates using double-buffered telemetry state snapshots, eliminating UI thread jitter on simulation dynamics.\n"
        )

        return "\n".join(md)
