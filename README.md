# ASTRATRACK

**AI-Based Virtual Camera Tracking and Coarse Alignment Simulator**

> Smart India Hackathon 2026

## Overview

ASTRATRACK simulates the coarse-alignment stage of a Free Space Optical Communication (FSOC) Pointing, Acquisition, and Tracking (PAT) system. A virtual camera with pan/tilt control automatically detects, tracks, and follows moving optical beacons in configurable environments — with realistic disturbance models for atmospheric turbulence, platform vibration, image noise, and scintillation.

The project ships two complementary simulation modes:

| Mode | Entry Point | Rendering | Pipeline |
|:---|:---|:---|:---|
| **2D Fast Simulator** | `python main.py` | Dear PyGui dashboard | Full perception pipeline |
| **3D Visualization** | `python run_3d_simulator.py` | OpenCV 3D scene | Direct gimbal (default) or full pipeline |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch 2D simulator (Dear PyGui dashboard)
python main.py

# 3. Launch 3D simulator (interactive OpenCV window)
python run_3d_simulator.py

# 3a. 3D simulator with full perception/Kalman/FSM/PID pipeline enabled
python run_3d_simulator.py --pipeline

# 3b. Select a specific scenario
python run_3d_simulator.py --scenario 3          # Orbital arc (LEO pass)

# 3c. Headless deterministic run (60 frames, no window)
python run_3d_simulator.py --deterministic --frames 60 --headless
```

---

## 3D Simulator Controls

| Key / Mouse | Action |
|:---|:---|
| `1`–`6` | Switch tracking scenario |
| `V` | Cycle view mode (Orbit / Ground / Chase / Sensor) |
| `Space` | Pause / Resume |
| `R` | Reset to start |
| `N` | Single-step (when paused) |
| `T` | Toggle trajectory trail |
| `F` | Toggle camera FOV frustum |
| `L` | Toggle laser LOS beam |
| `G` | Toggle ground reference grid |
| `H` | Toggle telemetry HUD |
| `P` | Toggle sensor picture-in-picture |
| `D` | Toggle deterministic mode |
| Left-drag | Rotate orbit camera |
| Scroll | Zoom orbit camera |
| `W/A/S/D` | Orbit camera rotation |
| `+` / `-` | Orbit camera zoom |
| `ESC` / `Q` | Quit |

---

## 3D Scenarios

| # | ID | Name | Difficulty |
|:---|:---|:---|:---|
| 1 | `stationary` | Stationary Beacon | Nominal |
| 2 | `linear` | Linear Flight Path | Low |
| 3 | `orbital` | Orbital Arc (LEO Pass) | Medium |
| 4 | `turbulence` | Atmospheric Turbulence Jitter | High |
| 5 | `high_speed` | High-Speed Crossing | Critical |
| 6 | `evasive` | Evasive / Erratic Trajectory | Severe |

---

## Pipeline Mode (`--pipeline`)

Without `--pipeline`, the 3D simulator uses a direct proportional gimbal tracker (`TrackingCamera3D`) that slews toward the known target position. This is fast and always tracks successfully.

With `--pipeline`, the full perception stack is engaged:

```
Rendered Sensor Frame
   → IDetector (classical HSV or AI)
   → KalmanTracker (4-state CV filter)
   → TrackingFSM (7-state acquisition/reacquisition machine)
   → CameraController (dual-axis PID)
   → TrackingCamera3D (gimbal)
```

The HUD gains a second "PERCEPTION PIPELINE" card showing FSM state, detection confidence, Kalman estimate, PID error, and reacquisition statistics.

Switch detector backend with `--detector ai` (requires model weights) or `--detector classical` (default, no extra dependencies).

---

## Architecture

```
AstraTrack/
├── main.py                    # 2D simulator launcher (Dear PyGui)
├── run_3d_simulator.py        # 3D simulator launcher (OpenCV)
│
├── simulator/                 # 3D engine (self-contained)
│   ├── simulation.py          # Simulation3D coordinator
│   ├── renderer.py            # 3D vector-graphics renderer (NumPy/OpenCV)
│   ├── camera3d.py            # Pan/tilt gimbal with slew limits & inertia
│   ├── target3d.py            # 3D beacon with 7 trajectory types
│   ├── math3d.py              # Pinhole projection & linear algebra
│   ├── scenarios.py           # 6 preconfigured scenarios
│   ├── pipeline3d.py          # Full pipeline adapter (new)
│   └── run_3d_sim.py          # CLI entry point
│
├── perception/                # Detector implementations
├── estimation/                # Kalman filter & predictor
├── control/                   # PID & camera controller
├── tracking/                  # Tracking FSM
├── disturbance/               # Turbulence / noise / vibration engine
├── sim/                       # 2D world & motion models
├── camera/                    # 2D virtual camera
├── ui/                        # Dear PyGui dashboard
├── logging_/                  # CSV session logging
├── metrics/                   # Performance evaluator
└── tests/                     # 75 automated tests (pytest)
```

---

## Technology Stack

| Component | Technology |
|:---|:---|
| Language | Python 3.10+ |
| 3D Rendering | Custom pinhole projection (NumPy + OpenCV) |
| Computer Vision | OpenCV |
| UI / Dashboard | Dear PyGui |
| Numerics | NumPy |
| Turbulence Model | Perlin Noise |
| Test Runner | pytest |

---

## Team

Smart India Hackathon 2026 — Team ASTRATRACK
# astratrack
