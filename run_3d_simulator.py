"""
ASTRATRACK — 3D FSOC Tracking Simulation Environment Launcher

Usage:
    python run_3d_simulator.py
    python run_3d_simulator.py --scenario 3
    python run_3d_simulator.py --help
"""

import sys
import os

# Forward to the simulator package runner
from simulator.run_3d_sim import main

if __name__ == "__main__":
    main()
