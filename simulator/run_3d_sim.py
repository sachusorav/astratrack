"""
ASTRATRACK — 3D FSOC Tracking Simulator Interactive Runner

Run with:
    python simulator/run_3d_sim.py
    python simulator/run_3d_sim.py --scenario 3
    python simulator/run_3d_sim.py --deterministic --frames 300 --headless
"""

import sys
import os
import time
import argparse
import cv2
import numpy as np

# Ensure root workspace is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from simulator.simulation import Simulation3D
from simulator.scenarios import list_scenarios, get_scenario_by_id_or_key
from simulator.renderer import ViewMode


# Mouse interaction state
_mouse_dragging = False
_last_mouse_pos = (0, 0)


def mouse_callback(event, x, y, flags, param):
    """Handle mouse interactions for 3D orbit camera."""
    global _mouse_dragging, _last_mouse_pos
    sim: Simulation3D = param

    if event == cv2.EVENT_LBUTTONDOWN:
        _mouse_dragging = True
        _last_mouse_pos = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        _mouse_dragging = False
    elif event == cv2.EVENT_MOUSEMOVE and _mouse_dragging:
        dx = x - _last_mouse_pos[0]
        dy = y - _last_mouse_pos[1]
        _last_mouse_pos = (x, y)
        sim.renderer.rotate_orbit(delta_az=dx * 0.4, delta_el=-dy * 0.4)
    elif event == cv2.EVENT_MOUSEWHEEL:
        # cv2.EVENT_MOUSEWHEEL returns flags > 0 for forward, < 0 for backward
        if flags > 0:
            sim.renderer.zoom_orbit(-50.0)
        else:
            sim.renderer.zoom_orbit(50.0)


def main():
    parser = argparse.ArgumentParser(
        description="ASTRATRACK 3D FSOC Tracking Simulation Environment"
    )
    parser.add_argument(
        "--scenario", "-s", type=str, default="2",
        help="Scenario number (1-6) or ID (stationary, linear, orbital, turbulence, high_speed, evasive)"
    )
    parser.add_argument(
        "--deterministic", "-d", action="store_true",
        help="Run in deterministic mode with fixed random seed"
    )
    parser.add_argument(
        "--width", type=int, default=1280,
        help="Viewport width (pixels)"
    )
    parser.add_argument(
        "--height", type=int, default=720,
        help="Viewport height (pixels)"
    )
    parser.add_argument(
        "--record", type=str, default=None,
        help="Path to save output video (e.g. output.mp4)"
    )
    parser.add_argument(
        "--frames", type=int, default=0,
        help="Run for N frames then exit (0 = infinite)"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run without displaying GUI window (useful for automated tests/recording)"
    )
    parser.add_argument(
        "--save-screenshot", type=str, default=None,
        help="Save an initial screenshot to this path and continue"
    )

    args = parser.parse_args()

    # Load scenario
    scenario = get_scenario_by_id_or_key(args.scenario)
    if scenario is None:
        print(f"[ERROR] Unknown scenario '{args.scenario}'. Available scenarios:")
        for s in list_scenarios():
            print(f"  {s.id}: {s.name}")
        sys.exit(1)

    print(f"============================================================")
    print(f"  ASTRATRACK — 3D FSOC TRACKING SIMULATOR")
    print(f"============================================================")
    print(f"  Loaded Scenario: [{scenario.id}] {scenario.name}")
    print(f"  Category:        {scenario.category}")
    print(f"  Description:     {scenario.description}")
    print(f"  Mode:            {'DETERMINISTIC' if args.deterministic else 'REAL-TIME'}")
    print(f"  Resolution:      {args.width}x{args.height}")
    print(f"------------------------------------------------------------")
    print(f"  Controls:")
    print(f"    [1-6]      Switch Scenarios")
    print(f"    [V]        Cycle View (Orbit / Ground / Chase / Sensor)")
    print(f"    [Space]    Pause / Resume")
    print(f"    [R]        Reset to Start")
    print(f"    [N]        Single Step (when paused)")
    print(f"    [T]        Toggle Trajectory Trail")
    print(f"    [F]        Toggle Camera FOV")
    print(f"    [L]        Toggle Laser LOS Beam")
    print(f"    [G]        Toggle Ground Reference Grid")
    print(f"    [H]        Toggle Telemetry HUD")
    print(f"    [P]        Toggle Sensor PiP")
    print(f"    [D]        Toggle Deterministic Mode")
    print(f"    [Mouse]    Click & drag to rotate orbit / Wheel to zoom")
    print(f"    [W/A/S/D]  Orbit camera rotation")
    print(f"    [+/-]      Orbit camera zoom")
    print(f"    [ESC / Q]  Quit")
    print(f"============================================================")

    # Initialize simulation
    sim = Simulation3D(
        scenario=scenario,
        width=args.width,
        height=args.height,
        deterministic=args.deterministic
    )

    # Video writer setup if recording
    writer = None
    if args.record:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.record, fourcc, 30.0, (args.width, args.height))
        print(f"[*] Recording enabled: saving to '{args.record}'")

    window_name = "ASTRATRACK — 3D FSOC Tracking Simulator"
    if not args.headless:
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window_name, mouse_callback, sim)

    frame_idx = 0
    saved_screenshot = False

    try:
        while True:
            # Advance simulation step
            sim.step()

            # Render frame
            frame = sim.render()

            # Save initial screenshot if requested
            if args.save_screenshot and not saved_screenshot and frame_idx >= 5:
                os.makedirs(os.path.dirname(os.path.abspath(args.save_screenshot)), exist_ok=True)
                cv2.imwrite(args.save_screenshot, frame)
                print(f"[*] Saved screenshot to: {args.save_screenshot}")
                saved_screenshot = True

            # Write to video
            if writer is not None:
                writer.write(frame)

            # Display
            if not args.headless:
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF

                # Key handling
                if key in (27, ord('q'), ord('Q')):
                    break
                elif key == 32:  # Space
                    sim.toggle_pause()
                elif key in (ord('r'), ord('R')):
                    sim.reset()
                elif key in (ord('n'), ord('N')):
                    sim.step(0.02)
                elif key in (ord('v'), ord('V')):
                    sim.renderer.cycle_view_mode()
                elif key in (ord('t'), ord('T')):
                    sim.renderer.show_trajectory_trail = not sim.renderer.show_trajectory_trail
                elif key in (ord('f'), ord('F')):
                    sim.renderer.show_camera_fov = not sim.renderer.show_camera_fov
                elif key in (ord('l'), ord('L')):
                    sim.renderer.show_los_beam = not sim.renderer.show_los_beam
                elif key in (ord('g'), ord('G')):
                    sim.renderer.show_ground_grid = not sim.renderer.show_ground_grid
                elif key in (ord('h'), ord('H')):
                    sim.renderer.show_telemetry_hud = not sim.renderer.show_telemetry_hud
                elif key in (ord('p'), ord('P')):
                    sim.renderer.show_pip_sensor = not sim.renderer.show_pip_sensor
                elif key in (ord('d'), ord('D')):
                    sim.set_deterministic(not sim.deterministic)
                elif key in [ord(str(i)) for i in range(1, 7)]:
                    scenario_num = chr(key)
                    sim.load_scenario(scenario_num)
                    print(f"[*] Switched to Scenario {scenario_num}: {sim.scenario.name}")
                elif key in (ord('w'), ord('W')):
                    sim.renderer.rotate_orbit(delta_az=0.0, delta_el=3.0)
                elif key in (ord('s'), ord('S')):
                    sim.renderer.rotate_orbit(delta_az=0.0, delta_el=-3.0)
                elif key in (ord('a'), ord('A')):
                    sim.renderer.rotate_orbit(delta_az=-4.0, delta_el=0.0)
                elif key in (ord('d'), ord('D')) and flags_shift():
                    sim.renderer.rotate_orbit(delta_az=4.0, delta_el=0.0)
                elif key in (ord('+'), ord('=')):
                    sim.renderer.zoom_orbit(-40.0)
                elif key in (ord('-'), ord('_')):
                    sim.renderer.zoom_orbit(40.0)

            frame_idx += 1
            if args.frames > 0 and frame_idx >= args.frames:
                break

    except KeyboardInterrupt:
        print("\n[!] Simulation interrupted by user.")
    finally:
        if writer is not None:
            writer.release()
            print(f"[*] Recording finalized: {args.record}")
        if not args.headless:
            cv2.destroyAllWindows()
        print(f"[*] Simulation session ended after {frame_idx} frames. Final sim time: {sim.sim_time:.2f}s")


def flags_shift():
    return False


if __name__ == "__main__":
    main()
