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

## Interactive Controls

Start the simulator once and drive the entire demo live — no restarts required.

### Communication Mode Selection

| Key / Button | Action |
|:---|:---|
| `M` | Toggle between **Ground → Satellite** and **Satellite ↔ Satellite** modes |
| On-screen `[M]` button | Same as above (click in the LIVE CONTROLS panel) |

### Ground → Satellite Scenarios (Keys 1–6)

| Key | ID | Name | Difficulty |
|:---|:---|:---|:---|
| `1` | `stationary` | Stationary Beacon | Nominal |
| `2` | `linear` | Linear Flight Path | Low |
| `3` | `orbital` | Orbital Arc (LEO Pass) | Medium |
| `4` | `turbulence` | Atmospheric Turbulence Jitter | High |
| `5` | `high_speed` | High-Speed Crossing | Critical |
| `6` | `evasive` | Evasive / Erratic Trajectory | Severe |

### Satellite ↔ Satellite Scenarios (Keys 7–9)

| Key | ID | Name | Difficulty |
|:---|:---|:---|:---|
| `7` | `sat_to_ground` | Sat → Ground Uplink (one-directional) | Medium |
| `8` | `isl_same_plane` | ISL Same-Plane (bilateral, co-planar LEO) | Medium |
| `9` | `isl_crosslink` | ISL Crosslink (bilateral, cross-plane) | High |

### Simulation Controls

| Key / Control | Action |
|:---|:---|
| `Space` / `[SPC] PAUSE` button | Pause / Resume |
| `R` / `[R] RESET` button | Reset current scenario to t = 0 |
| `N` / `[N] STEP` button | Single-step (only when paused) |
| `D` | Toggle deterministic mode (fixed seed) |

### View Controls

| Key | Action |
|:---|:---|
| `V` | Cycle viewpoint (Orbit / Ground / Chase / Sensor) |
| `T` | Toggle trajectory trail |
| `F` | Toggle camera FOV frustum |
| `L` | Toggle laser LOS beam |
| `G` | Toggle ground reference grid |
| `H` | Toggle telemetry HUD |
| `P` | Toggle sensor picture-in-picture |
| `C` | Toggle on-screen LIVE CONTROLS panel |
| Left-drag | Rotate orbit camera |
| Scroll wheel | Zoom orbit camera |
| `W` / `S` | Tilt orbit up / down |
| `A` / `E` | Rotate orbit left / right |
| `+` / `-` | Zoom in / out |
| `ESC` / `Q` | Quit |

### Demo Walkthrough (Live Mode Switching)

```
# Step 1 — Start on the default Linear Flight Path scenario
python run_3d_simulator.py --scenario stationary

# Step 2 — Press [Space] to pause the simulation
# Step 3 — Click the on-screen mode badge [M] button
#           OR press [M] to switch to Satellite ↔ Satellite mode
# Step 4 — Press [9] to load ISL Crosslink
#           OR click "[9]  ISL Crosslink" in the LIVE CONTROLS panel
#           → Amber banner "⟶ Satellite ↔ Satellite  |  ISL Crosslink" flashes for ~1.5 s
# Step 5 — Press [Space] to resume — simulation restarts cleanly in the new scenario
```

### Known Limitations

- **One-frame visual glitch** — switching mid-active-reacquisition may show a single-frame positional jump as the new target position resolves. Documented; not fixed.
- **Unity bidirectional WebSocket** — not implemented (Unity client absent from this repo). The telemetry server is structured to accept JSON commands when a client is added.


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
│   ├── scenarios.py           # 9 preconfigured scenarios (3D) + mode hierarchy
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
