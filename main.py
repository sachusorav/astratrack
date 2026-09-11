"""
ASTRATRACK — Main Entry Point

Launches the ASTRATRACK application.

Usage:
    python main.py                  # Run with defaults
    python main.py config.yaml      # Run with custom config
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import AppConfig, load_config
from ui.dashboard import Dashboard


def main():
    """Entry point for the ASTRATRACK application."""
    # Load configuration
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)

    print("=" * 60)
    print("  ASTRATRACK — AI Virtual Camera Tracking Simulator")
    print("  Smart India Hackathon 2026")
    print("=" * 60)
    print()
    print(f"  World:       {config.world.width} × {config.world.height} px")
    print(f"  Camera FOV:  {config.camera.fov_width} × {config.camera.fov_height} px")
    print(f"  PID Gains:   Kp={config.pid.kp}, Ki={config.pid.ki}, Kd={config.pid.kd}")
    print(f"  Beacon:      {config.beacon.motion_model} motion, speed={config.beacon.speed}")
    print()
    print("  Press START in the UI to begin tracking.")
    print("  Use sliders to adjust PID gains and disturbances live.")
    print()

    # Create and run the dashboard
    dashboard = Dashboard(config)
    dashboard.setup()
    dashboard.run()


if __name__ == "__main__":
    main()
