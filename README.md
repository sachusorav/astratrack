# ASTRATRACK

**AI-Based Virtual Camera Tracking and Coarse Alignment Simulator**

> Smart India Hackathon 2026

## Overview

ASTRATRACK simulates the coarse-alignment stage of a Free Space Optical Communication (FSOC) Pointing, Acquisition, and Tracking (PAT) system. A virtual camera with pan/tilt control automatically detects, tracks, and follows moving optical beacons in a configurable 2D environment — with realistic disturbance models for atmospheric turbulence, platform vibration, image noise, and scintillation.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch
python main.py
```

## Architecture

- **Simulation Engine** — Virtual world with configurable moving beacons
- **Virtual Camera** — Pan/tilt actuator model with bounded FOV
- **CV Detection Pipeline** — HSV thresholding + contour centroid extraction
- **Kalman Filter** — State estimation with coast/predict capability
- **PID Controller** — Dual-axis camera control with anti-windup
- **Disturbance Engine** — Turbulence, vibration, noise, scintillation
- **Dashboard UI** — Real-time metrics, plots, and interactive controls (Dear PyGui)
- **Performance Logger** — Automatic CSV session logging

## Technology Stack

| Component | Technology |
|:----------|:----------|
| Language | Python 3.10+ |
| Computer Vision | OpenCV |
| UI / Dashboard | Dear PyGui |
| Numerics | NumPy |
| Turbulence Model | Perlin Noise |

## Team

Smart India Hackathon 2026 — Team ASTRATRACK
