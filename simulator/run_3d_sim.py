"""
ASTRATRACK — 3D FSOC Tracking Simulator Interactive Runner

Run with:
    python simulator/run_3d_sim.py
    python simulator/run_3d_sim.py --scenario 3
    python simulator/run_3d_sim.py --scenario isl_crosslink
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
from simulator.scenarios import list_scenarios, get_scenario_by_id_or_key, MODE_GROUPS
from simulator.renderer import ViewMode


# Mouse interaction state
_mouse_dragging = False
_last_mouse_pos = (0, 0)


def mouse_callback(event, x, y, flags, param):
    """Handle mouse interactions for 3D orbit camera and on-screen control panel."""
    global _mouse_dragging, _last_mouse_pos
    sim: Simulation3D = param

    if event == cv2.EVENT_LBUTTONDOWN:
        # Check control panel click regions first
        if _check_ctrl_click(sim, x, y):
            return
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
        # flags > 0 = scroll forward (zoom in), < 0 = scroll backward (zoom out)
        if flags > 0:
            sim.renderer.zoom_orbit(-50.0)
        else:
            sim.renderer.zoom_orbit(50.0)


def _check_ctrl_click(sim: Simulation3D, x: int, y: int) -> bool:
    """
    Hit-test x,y against the on-screen control panel clickable regions.

    Returns True if a region was matched and an action was dispatched.
    """
    for region in sim.renderer._ctrl_regions:
        x1, y1, x2, y2 = region["rect"]
        if x1 <= x <= x2 and y1 <= y <= y2:
            action = region["action"]
            _dispatch_action(sim, action)
            return True
    return False


def _dispatch_action(sim: Simulation3D, action: str):
    """Dispatch a named control action (from keyboard shortcut or panel click)."""
    if action in ("pause", "resume"):
        sim.toggle_pause()
    elif action == "reset":
        sim.reset()
    elif action == "step":
        if sim.is_paused:
            sim.step(0.02)
    elif action == "toggle_mode":
        _toggle_mode(sim)
    elif action.startswith("set_scenario:"):
        scen_id = action.split("set_scenario:", 1)[1]
        # Find which mode owns this scenario
        target_mode = None
        for mode, ids in MODE_GROUPS.items():
            if scen_id in ids:
                target_mode = mode
                break
        if target_mode:
            ok = sim.switch_scene(target_mode, scen_id)
            if not ok:
                print(f"[!] Could not switch to scenario '{scen_id}'")
        else:
            print(f"[!] Scenario '{scen_id}' not found in any mode group")


def _toggle_mode(sim: Simulation3D):
    """Cycle to the next communication mode and load its first scenario."""
    modes = list(MODE_GROUPS.keys())
    cur_idx = modes.index(sim.active_mode) if sim.active_mode in modes else 0
    next_mode = modes[(cur_idx + 1) % len(modes)]
    first_scen = MODE_GROUPS[next_mode][0]
    ok = sim.switch_scene(next_mode, first_scen)
    if ok:
        print(f"[*] Mode toggled → {next_mode}  |  scenario: {first_scen}")


def main():
    parser = argparse.ArgumentParser(
        description="ASTRATRACK 3D FSOC Tracking Simulation Environment"
    )
    parser.add_argument(
        "--scenario", "-s", type=str, default="2",
        help=(
            "Scenario number (1-9) or ID. "
            "Ground→Sat [1-6]: stationary/linear/orbital/turbulence/high_speed/evasive. "
            "Sat↔Sat    [7-9]: sat_to_ground/isl_same_plane/isl_crosslink."
        )
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
    parser.add_argument(
        "--pipeline", action="store_true",
        help="Enable full perception pipeline (IDetector → Kalman → FSM → PID) instead of direct gimbal"
    )
    parser.add_argument(
        "--detector", type=str, default="classical",
        help="Detector backend when --pipeline is active: 'classical' (default) or 'ai'"
    )

    args = parser.parse_args()

    # Load scenario
    scenario = get_scenario_by_id_or_key(args.scenario)
    if scenario is None:
        print(f"[ERROR] Unknown scenario '{args.scenario}'. Available scenarios:")
        for s in list_scenarios():
            print(f"  {s.id:20s}  {s.name}  ({s.category})")
        sys.exit(1)

    print(f"============================================================")
    print(f"  ASTRATRACK — 3D FSOC TRACKING SIMULATOR")
    print(f"============================================================")
    print(f"  Loaded Scenario: [{scenario.id}] {scenario.name}")
    print(f"  Category:        {scenario.category}")
    print(f"  Description:     {scenario.description}")
    print(f"  Sim Mode:        {'DETERMINISTIC' if args.deterministic else 'REAL-TIME'}")
    print(f"  Resolution:      {args.width}x{args.height}")
    print(f"  Pipeline:        {'ENABLED [' + args.detector.upper() + ' detector]' if args.pipeline else 'DISABLED (direct gimbal)'}")
    print(f"------------------------------------------------------------")
    print(f"  Controls:")
    print(f"    ── Ground → Satellite Scenarios ──────────────────────")
    print(f"    [1]  Stationary Beacon    [2]  Linear Flight Path")
    print(f"    [3]  Orbital Arc (LEO)    [4]  Atmospheric Turbulence")
    print(f"    [5]  High-Speed Crossing  [6]  Evasive / Erratic")
    print(f"    ── Satellite ↔ Satellite Scenarios ───────────────────")
    print(f"    [7]  Sat→Ground Uplink    [8]  ISL Same-Plane")
    print(f"    [9]  ISL Crosslink (Cross-Plane)")
    print(f"    ── Mode & Simulation Controls ────────────────────────")
    print(f"    [M]        Toggle Communication Mode")
    print(f"    [Space]    Pause / Resume")
    print(f"    [R]        Reset to Start")
    print(f"    [N]        Single Step (when paused)")
    print(f"    [D]        Toggle Deterministic Mode")
    print(f"    ── View & Render Toggles ─────────────────────────────")
    print(f"    [V]  Cycle View  [T] Trail  [F] FOV   [L] LOS")
    print(f"    [G]  Grid        [H] HUD    [P] PiP   [C] Control Panel")
    print(f"    ── Orbit Camera ──────────────────────────────────────")
    print(f"    [Mouse] Click & drag / Wheel to zoom")
    print(f"    [W/S]   Tilt orbit up/down   [A/E] Rotate left/right")
    print(f"    [+/-]   Zoom in/out")
    print(f"    [ESC/Q] Quit")
    print(f"============================================================")

    # Initialize simulation
    sim = Simulation3D(
        scenario=scenario,
        width=args.width,
        height=args.height,
        deterministic=args.deterministic,
        use_pipeline=args.pipeline,
        detector_type=args.detector,
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

                # ── Quit ──
                if key in (27, ord('q'), ord('Q')):
                    break

                # ── Simulation controls ──
                elif key == 32:  # Space
                    sim.toggle_pause()
                elif key in (ord('r'), ord('R')):
                    sim.reset()
                elif key in (ord('n'), ord('N')):
                    if sim.is_paused:
                        sim.step(0.02)
                elif key in (ord('d'), ord('D')):
                    sim.set_deterministic(not sim.deterministic)

                # ── Communication mode toggle ──
                elif key in (ord('m'), ord('M')):
                    _toggle_mode(sim)

                # ── Ground → Satellite scenarios [1–6] ──
                elif key in [ord(str(i)) for i in range(1, 7)]:
                    scen_num = chr(key)
                    ok = sim.switch_scene("ground_to_sat", scen_num)
                    if not ok:
                        sim.load_scenario(scen_num)  # backward-compat fallback
                    print(f"[*] Switched to: {sim.scenario.name}")

                # ── Satellite ↔ Satellite scenarios [7–9] ──
                elif key == ord('7'):
                    sim.switch_scene("sat_to_sat", "sat_to_ground")
                    print(f"[*] Switched to: {sim.scenario.name}")
                elif key == ord('8'):
                    sim.switch_scene("sat_to_sat", "isl_same_plane")
                    print(f"[*] Switched to: {sim.scenario.name}")
                elif key == ord('9'):
                    sim.switch_scene("sat_to_sat", "isl_crosslink")
                    print(f"[*] Switched to: {sim.scenario.name}")

                # ── View mode cycle ──
                elif key in (ord('v'), ord('V')):
                    sim.renderer.cycle_view_mode()

                # ── Render toggles ──
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
                elif key in (ord('c'), ord('C')):
                    sim.renderer.show_control_panel = not sim.renderer.show_control_panel

                # ── Orbit camera controls ──
                elif key in (ord('w'), ord('W')):
                    sim.renderer.rotate_orbit(delta_az=0.0, delta_el=3.0)
                elif key in (ord('s'), ord('S')):
                    sim.renderer.rotate_orbit(delta_az=0.0, delta_el=-3.0)
                elif key in (ord('a'), ord('A')):
                    sim.renderer.rotate_orbit(delta_az=-4.0, delta_el=0.0)
                elif key in (ord('e'), ord('E')):
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


if __name__ == "__main__":
    main()
