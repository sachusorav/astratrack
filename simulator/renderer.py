"""
ASTRATRACK — 3D Aerospace FSOC Renderer

High-fidelity 3D vector-graphics renderer for Free-Space Optical
Communication tracking simulation.

Renders directly to NumPy/OpenCV image buffers with aerospace-grade telemetry,
frustum projection, laser line-of-sight strobes, dynamic ground grids, and
a sensor boresight Picture-in-Picture (PiP).
"""

import math
import cv2
import numpy as np
from enum import Enum
from typing import Dict, List, Optional, Tuple

from simulator.math3d import (
    normalize, angle_between, look_at_matrix, perspective_proj,
    project_point, project_line, clamp_to_screen,
    rotation_x, rotation_y, rotation_z
)
from simulator.target3d import Target3D
from simulator.camera3d import TrackingCamera3D


class ViewMode(Enum):
    """Observer viewpoint modes."""
    ORBIT = "orbit"                 # Free 3D orbit around scene
    GROUND_STATION = "ground"       # View from behind ground station
    TARGET_CHASE = "chase"          # Chase camera following target
    SENSOR_FULL = "sensor"          # Direct full-screen camera sensor view


class AerospaceColors:
    """Color palette optimized for aerospace engineering visualizers (BGR format)."""
    # Backgrounds & canvas
    SPACE_BG = (18, 14, 10)              # Deep space navy-charcoal #0a0e12
    PANEL_BG = (28, 22, 16)              # Translucent panel background
    PANEL_BORDER = (60, 50, 40)          # Subtle panel border

    # Reference grid & environment
    GRID_MAJOR = (65, 55, 45)            # Major range rings & axes
    GRID_MINOR = (40, 35, 30)            # Subtle ground grid
    RADIAL_LINES = (50, 42, 35)          # Azimuth radials
    HORIZON_LINE = (75, 65, 55)          # Horizon ring
    STAR_COLOR = (180, 170, 160)         # Distant stars

    # Coordinate axes
    AXIS_X_EAST = (60, 60, 220)          # Red (X - East)
    AXIS_Y_ZENITH = (70, 210, 100)       # Green (Y - Zenith)
    AXIS_Z_NORTH = (220, 140, 50)        # Blue (Z - North)

    # Optical beacon & trajectory
    BEACON_CORE = (255, 255, 255)        # Pure white core
    BEACON_GLOW = (255, 220, 100)        # Warm amber/cyan optical glow
    BEACON_RETICLE = (255, 200, 50)      # Target acquisition box/crosshair
    TRAIL_START = (255, 180, 40)         # Recent flight path
    TRAIL_END = (90, 60, 20)             # Faded historical path
    VELOCITY_VECTOR = (60, 200, 255)     # Yellow-gold velocity arrow

    # Tracking states & FOV
    LOCK_LOCKED = (120, 230, 80)         # Emerald green (Locked)
    LOCK_ACQUIRING = (40, 180, 245)      # Amber gold (Acquiring / Marginal)
    LOCK_LOST = (60, 60, 230)            # Scarlet red (Lost / Out of FOV)

    # Line of Sight & Laser Link
    LOS_BEAM = (240, 240, 100)           # Cyan laser beam
    LOS_STROBE = (255, 255, 255)         # Pulse strobes along beam

    # Telemetry HUD
    HUD_TEXT_PRIMARY = (230, 225, 220)   # High-contrast off-white
    HUD_TEXT_MUTED = (140, 130, 120)     # Dim label gray
    HUD_ACCENT = (245, 175, 45)          # Aerospace cyan accent
    HUD_SUCCESS = (110, 220, 90)         # Status OK green
    HUD_WARN = (50, 170, 240)            # Status caution amber
    HUD_ALERT = (70, 70, 235)            # Status alert red


class Renderer3D:
    """
    3D FSOC Simulation Renderer.

    Handles 3D coordinate projection, aerospace visual features,
    telemetry rendering, and picture-in-picture sensor view.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

        # Observer Camera State (Orbit mode)
        self.view_mode: ViewMode = ViewMode.ORBIT
        self.orbit_azimuth_deg: float = 35.0     # Horizontal angle
        self.orbit_elevation_deg: float = 22.0   # Vertical angle above horizon
        self.orbit_distance: float = 950.0       # Distance from focal point
        self.orbit_target = np.array([0.0, 180.0, 300.0])  # Center of focus
        self.orbit_fov_deg: float = 55.0

        # Rendering toggles
        self.show_ground_grid: bool = True
        self.show_trajectory_trail: bool = True
        self.show_camera_fov: bool = True
        self.show_los_beam: bool = True
        self.show_coordinate_axes: bool = True
        self.show_telemetry_hud: bool = True
        self.show_pip_sensor: bool = True

        # Internal animation time
        self._strobe_phase: float = 0.0

        # Precompute celestial background stars (deterministic positions)
        rng = np.random.RandomState(1337)
        star_count = 140
        star_az = rng.uniform(0, 360, star_count)
        star_el = rng.uniform(5, 85, star_count)
        star_r = 5000.0
        self._stars: List[np.ndarray] = []
        for a, e in zip(star_az, star_el):
            ar, er = math.radians(a), math.radians(e)
            sx = star_r * math.cos(er) * math.sin(ar)
            sy = star_r * math.sin(er)
            sz = star_r * math.cos(er) * math.cos(ar)
            self._stars.append(np.array([sx, sy, sz]))

    # ------------------------------------------------------------------ #
    # Main Render Pipeline
    # ------------------------------------------------------------------ #

    def render(self, target: Target3D, camera: TrackingCamera3D,
               telemetry_data: Dict) -> np.ndarray:
        """
        Render a full 3D simulation frame.

        Args:
            target: Target beacon instance.
            camera: Ground station camera instance.
            telemetry_data: Live telemetry metrics dictionary.

        Returns:
            OpenCV image (H, W, 3) BGR uint8 buffer.
        """
        self._strobe_phase = (self._strobe_phase + 0.08) % 1.0

        # Special Mode: Full Sensor View
        if self.view_mode == ViewMode.SENSOR_FULL:
            frame = self._render_sensor_view(target, camera, self.width, self.height)
            if self.show_telemetry_hud:
                self._draw_hud_telemetry(frame, target, camera, telemetry_data, minimal=True)
            return frame

        # Create base canvas with dark aerospace sky
        frame = np.full((self.height, self.width, 3), AerospaceColors.SPACE_BG, dtype=np.uint8)

        # Compute Observer View & Projection matrices
        view_mat, proj_mat, eye_pos = self._compute_observer_matrices(target, camera)

        # 1. Background celestial stars
        self._draw_stars(frame, view_mat, proj_mat)

        # 2. Ground reference grid & concentric rings
        if self.show_ground_grid:
            self._draw_ground_reference(frame, view_mat, proj_mat)

        # 3. Coordinate axes
        if self.show_coordinate_axes:
            self._draw_coordinate_axes(frame, view_mat, proj_mat)

        # 4. Ground station & tracking gimbal pedestal
        self._draw_ground_station(frame, camera, view_mat, proj_mat)

        # 5. Target trajectory trail
        if self.show_trajectory_trail and len(target.trajectory_history) > 1:
            self._draw_trajectory(frame, target.trajectory_history, view_mat, proj_mat)

        # 6. Camera FOV frustum
        if self.show_camera_fov:
            self._draw_camera_fov(frame, camera, target.position, view_mat, proj_mat)

        # 7. Line of Sight (LOS) beam with laser pulse strobes
        if self.show_los_beam and target.visible:
            self._draw_line_of_sight(frame, camera, target.position, view_mat, proj_mat)

        # 8. Optical Beacon & Velocity Vector
        if target.visible:
            self._draw_target_beacon(frame, target, camera, view_mat, proj_mat)

        # 9. Picture-in-Picture Sensor View
        if self.show_pip_sensor and target.visible:
            self._draw_pip_sensor(frame, target, camera)

        # 10. Professional Aerospace Telemetry HUD
        if self.show_telemetry_hud:
            self._draw_hud_telemetry(frame, target, camera, telemetry_data)

        # 11. View mode badge & quick hotkey bar
        self._draw_status_bar(frame, telemetry_data)

        return frame

    # ------------------------------------------------------------------ #
    # Observer Matrix Computation
    # ------------------------------------------------------------------ #

    def _compute_observer_matrices(self, target: Target3D,
                                   camera: TrackingCamera3D
                                   ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute 4x4 View and Projection matrices for active view mode."""
        aspect = self.width / float(self.height)
        proj_mat = perspective_proj(self.orbit_fov_deg, aspect, near=1.0, far=15000.0)

        if self.view_mode == ViewMode.ORBIT:
            # Spherical orbit around orbit_target
            az_rad = math.radians(self.orbit_azimuth_deg)
            el_rad = math.radians(self.orbit_elevation_deg)
            r = self.orbit_distance

            ox = self.orbit_target[0] + r * math.cos(el_rad) * math.sin(az_rad)
            oy = self.orbit_target[1] + r * math.sin(el_rad)
            oz = self.orbit_target[2] + r * math.cos(el_rad) * math.cos(az_rad)
            eye = np.array([ox, oy, oz], dtype=np.float64)
            view_mat = look_at_matrix(eye, self.orbit_target)

        elif self.view_mode == ViewMode.GROUND_STATION:
            # Stand 25m behind and 8m above ground station looking toward target
            cam_dir = camera.direction
            eye = camera.position - cam_dir * 30.0 + np.array([0.0, 10.0, 0.0])
            look_point = camera.position + cam_dir * 150.0
            view_mat = look_at_matrix(eye, look_point)

        elif self.view_mode == ViewMode.TARGET_CHASE:
            # Chase target from behind velocity vector or along trajectory
            vel = target.velocity
            speed = np.linalg.norm(vel)
            heading = vel / (speed + 1e-6) if speed > 1.0 else np.array([0.0, 0.0, 1.0])
            eye = target.position - heading * 80.0 + np.array([0.0, 25.0, 0.0])
            view_mat = look_at_matrix(eye, target.position)

        else:
            eye = np.array([0.0, 100.0, 300.0])
            view_mat = look_at_matrix(eye, np.array([0.0, 100.0, 0.0]))

        return view_mat, proj_mat, eye

    # ------------------------------------------------------------------ #
    # 3D Environment Elements
    # ------------------------------------------------------------------ #

    def _draw_stars(self, frame: np.ndarray, view: np.ndarray, proj: np.ndarray):
        """Draw background celestial stars with subtle luminance."""
        for s in self._stars:
            pt = project_point(s, view, proj, self.width, self.height)
            if pt:
                x, y, _ = pt
                if 0 <= x < self.width and 0 <= y < self.height:
                    cv2.circle(frame, (x, y), 1, AerospaceColors.STAR_COLOR, -1)

    def _draw_ground_reference(self, frame: np.ndarray, view: np.ndarray, proj: np.ndarray):
        """Draw ground reference plane with range rings, radials, and elevation ticks."""
        origin = np.array([0.0, 0.0, 0.0])

        # Concentric range rings: 200m, 400m, 600m, 800m, 1000m
        ring_radii = [200.0, 400.0, 600.0, 800.0, 1000.0]
        segments = 48

        for r in ring_radii:
            ring_pts = []
            for i in range(segments + 1):
                theta = 2.0 * math.pi * i / segments
                px = r * math.sin(theta)
                pz = r * math.cos(theta)
                ring_pts.append(np.array([px, 0.0, pz]))

            color = AerospaceColors.GRID_MAJOR if r == 1000.0 else AerospaceColors.GRID_MINOR
            for i in range(segments):
                line = project_line(ring_pts[i], ring_pts[i + 1], view, proj, self.width, self.height)
                if line:
                    cv2.line(frame, line[0], line[1], color, 1, cv2.LINE_AA)

            # Range label at North edge
            lbl_pos = np.array([0.0, 0.0, r])
            pt = project_point(lbl_pos, view, proj, self.width, self.height)
            if pt:
                cv2.putText(frame, f"{int(r)}m", (pt[0] + 4, pt[1] - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, AerospaceColors.GRID_MAJOR, 1, cv2.LINE_AA)

        # Azimuth radial spokes every 30 degrees
        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            outer = np.array([1000.0 * math.sin(rad), 0.0, 1000.0 * math.cos(rad)])
            line = project_line(origin, outer, view, proj, self.width, self.height)
            if line:
                cv2.line(frame, line[0], line[1], AerospaceColors.RADIAL_LINES, 1, cv2.LINE_AA)

            # Cardinal labels (N, E, S, W)
            if deg % 90 == 0:
                cardinal = {0: "N (000)", 90: "E (090)", 180: "S (180)", 270: "W (270)"}[deg]
                lbl_3d = np.array([1060.0 * math.sin(rad), 0.0, 1060.0 * math.cos(rad)])
                pt = project_point(lbl_3d, view, proj, self.width, self.height)
                if pt:
                    cv2.putText(frame, cardinal, (pt[0] - 18, pt[1] + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.38, AerospaceColors.HUD_TEXT_MUTED, 1, cv2.LINE_AA)

    def _draw_coordinate_axes(self, frame: np.ndarray, view: np.ndarray, proj: np.ndarray):
        """Draw 3D coordinate triad (X: East, Y: Zenith, Z: North)."""
        origin = np.array([0.0, 0.0, 0.0])
        axis_len = 90.0

        axes = [
            (np.array([axis_len, 0.0, 0.0]), AerospaceColors.AXIS_X_EAST, "+X (E)"),
            (np.array([0.0, axis_len, 0.0]), AerospaceColors.AXIS_Y_ZENITH, "+Y (Z)"),
            (np.array([0.0, 0.0, axis_len]), AerospaceColors.AXIS_Z_NORTH, "+Z (N)"),
        ]

        for axis_end, color, label in axes:
            line = project_line(origin, axis_end, view, proj, self.width, self.height)
            if line:
                cv2.line(frame, line[0], line[1], color, 2, cv2.LINE_AA)
                cv2.putText(frame, label, (line[1][0] + 5, line[1][1] - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)

    def _draw_ground_station(self, frame: np.ndarray, camera: TrackingCamera3D,
                             view: np.ndarray, proj: np.ndarray):
        """Draw ground station pedestal and gimbal orientation."""
        base = np.array([camera.position[0], 0.0, camera.position[2]])
        top = camera.position

        # Pedestal column
        line = project_line(base, top, view, proj, self.width, self.height)
        if line:
            cv2.line(frame, line[0], line[1], (100, 90, 80), 3, cv2.LINE_AA)

        # Ground anchor pad
        pad_r = 15.0
        for i in range(8):
            th1 = 2.0 * math.pi * i / 8
            th2 = 2.0 * math.pi * (i + 1) / 8
            p1 = base + np.array([pad_r * math.sin(th1), 0.0, pad_r * math.cos(th1)])
            p2 = base + np.array([pad_r * math.sin(th2), 0.0, pad_r * math.cos(th2)])
            pad_line = project_line(p1, p2, view, proj, self.width, self.height)
            if pad_line:
                cv2.line(frame, pad_line[0], pad_line[1], (70, 60, 50), 1, cv2.LINE_AA)

        # Gimbal head indicator
        cam_pt = project_point(top, view, proj, self.width, self.height)
        if cam_pt:
            cv2.circle(frame, (cam_pt[0], cam_pt[1]), 5, (160, 150, 140), -1)
            cv2.putText(frame, "GS-01 [OPT-TERM]", (cam_pt[0] + 8, cam_pt[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, AerospaceColors.HUD_TEXT_MUTED, 1, cv2.LINE_AA)

        # Pointing boresight vector (30m vector)
        bore_end = top + camera.direction * 35.0
        bore_line = project_line(top, bore_end, view, proj, self.width, self.height)
        if bore_line:
            cv2.line(frame, bore_line[0], bore_line[1], AerospaceColors.HUD_ACCENT, 2, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    # Target & Trajectory
    # ------------------------------------------------------------------ #

    def _draw_trajectory(self, frame: np.ndarray, trail: List[np.ndarray],
                         view: np.ndarray, proj: np.ndarray):
        """Draw smooth multi-segment flight trajectory with historical gradient fading."""
        count = len(trail)
        step = max(1, count // 120)  # Downsample for high performance

        for i in range(0, count - step, step):
            p1 = trail[i]
            p2 = trail[i + step]
            line = project_line(p1, p2, view, proj, self.width, self.height)
            if line:
                # Alpha fade: older = darker
                progress = i / float(count)
                b = int(AerospaceColors.TRAIL_END[0] + progress * (AerospaceColors.TRAIL_START[0] - AerospaceColors.TRAIL_END[0]))
                g = int(AerospaceColors.TRAIL_END[1] + progress * (AerospaceColors.TRAIL_START[1] - AerospaceColors.TRAIL_END[1]))
                r = int(AerospaceColors.TRAIL_END[2] + progress * (AerospaceColors.TRAIL_START[2] - AerospaceColors.TRAIL_END[2]))
                cv2.line(frame, line[0], line[1], (b, g, r), 1, cv2.LINE_AA)

    def _draw_target_beacon(self, frame: np.ndarray, target: Target3D,
                            camera: TrackingCamera3D, view: np.ndarray, proj: np.ndarray):
        """Draw the moving optical beacon with glow, reticle, and velocity vector."""
        pt = project_point(target.position, view, proj, self.width, self.height)
        if not pt:
            return

        x, y, depth = pt

        # Velocity vector arrow
        vel_mag = np.linalg.norm(target.velocity)
        if vel_mag > 1.0:
            vel_dir = target.velocity / vel_mag
            v_end = target.position + vel_dir * min(60.0, vel_mag * 0.8)
            v_line = project_line(target.position, v_end, view, proj, self.width, self.height)
            if v_line:
                cv2.arrowedLine(frame, v_line[0], v_line[1],
                                AerospaceColors.VELOCITY_VECTOR, 1, tipLength=0.25)

        # Glow halo
        cv2.circle(frame, (x, y), 8, AerospaceColors.BEACON_GLOW, 1, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 4, (255, 240, 180), -1, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 2, AerospaceColors.BEACON_CORE, -1, cv2.LINE_AA)

        # Target acquisition reticle box
        lock_color = AerospaceColors.LOCK_LOCKED if camera.is_locked else (
            AerospaceColors.LOCK_ACQUIRING if camera.is_target_in_fov(target.position)
            else AerospaceColors.LOCK_LOST
        )
        s = 14
        cv2.rectangle(frame, (x - s, y - s), (x + s, y + s), lock_color, 1, cv2.LINE_AA)

        # Corner ticks
        c_len = 4
        cv2.line(frame, (x - s, y - s), (x - s + c_len, y - s), lock_color, 2)
        cv2.line(frame, (x - s, y - s), (x - s, y - s + c_len), lock_color, 2)
        cv2.line(frame, (x + s, y - s), (x + s - c_len, y - s), lock_color, 2)
        cv2.line(frame, (x + s, y - s), (x + s, y - s + c_len), lock_color, 2)
        cv2.line(frame, (x - s, y + s), (x - s + c_len, y + s), lock_color, 2)
        cv2.line(frame, (x - s, y + s), (x - s, y + s - c_len), lock_color, 2)
        cv2.line(frame, (x + s, y + s), (x + s - c_len, y + s), lock_color, 2)
        cv2.line(frame, (x + s, y + s), (x + s, y + s - c_len), lock_color, 2)

        # Slant range & Target label tag
        dist_m = np.linalg.norm(target.position - camera.position)
        tag = f"TGT-01 [{dist_m:.1f}m]"
        cv2.putText(frame, tag, (x + s + 5, y - s + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, AerospaceColors.HUD_TEXT_PRIMARY, 1, cv2.LINE_AA)

        # Ground projection shadow (altitude plumb line)
        ground_pt = np.array([target.position[0], 0.0, target.position[2]])
        plumb = project_line(target.position, ground_pt, view, proj, self.width, self.height)
        if plumb:
            cv2.line(frame, plumb[0], plumb[1], (60, 50, 45), 1, cv2.LINE_4)
            cv2.circle(frame, plumb[1], 3, (70, 60, 50), -1)

    # ------------------------------------------------------------------ #
    # Camera FOV Frustum & Line of Sight
    # ------------------------------------------------------------------ #

    def _draw_camera_fov(self, frame: np.ndarray, camera: TrackingCamera3D,
                         target_pos: np.ndarray, view: np.ndarray, proj: np.ndarray):
        """Draw 3D perspective FOV pyramid extending to target distance."""
        dist = float(np.linalg.norm(target_pos - camera.position))
        dist = max(100.0, min(dist, 1500.0))

        corners = camera.get_fov_corners(dist)
        origin = camera.position

        fov_color = AerospaceColors.LOCK_LOCKED if camera.is_locked else (
            AerospaceColors.LOCK_ACQUIRING if camera.is_target_in_fov(target_pos)
            else AerospaceColors.LOCK_LOST
        )

        # 4 Frustum ray edges from camera aperture to rectangle corners
        for corner in corners:
            line = project_line(origin, corner, view, proj, self.width, self.height)
            if line:
                cv2.line(frame, line[0], line[1], fov_color, 1, cv2.LINE_AA)

        # Rectangular cross section at distance
        for i in range(4):
            c1 = corners[i]
            c2 = corners[(i + 1) % 4]
            line = project_line(c1, c2, view, proj, self.width, self.height)
            if line:
                cv2.line(frame, line[0], line[1], fov_color, 1, cv2.LINE_AA)

    def _draw_line_of_sight(self, frame: np.ndarray, camera: TrackingCamera3D,
                            target_pos: np.ndarray, view: np.ndarray, proj: np.ndarray):
        """Draw laser Line-of-Sight (LOS) link with traveling pulse strobes."""
        beam_line = project_line(camera.position, target_pos, view, proj, self.width, self.height)
        if not beam_line:
            return

        p1, p2 = beam_line
        # Base link line
        color = AerospaceColors.LOS_BEAM if camera.is_locked else (80, 100, 100)
        cv2.line(frame, p1, p2, color, 1, cv2.LINE_AA)

        # Pulsing strobe photons along the link
        strobe_count = 5
        for i in range(strobe_count):
            t = (self._strobe_phase + (i / strobe_count)) % 1.0
            sx = int(p1[0] + t * (p2[0] - p1[0]))
            sy = int(p1[1] + t * (p2[1] - p1[1]))
            if 0 <= sx < self.width and 0 <= sy < self.height:
                cv2.circle(frame, (sx, sy), 2, AerospaceColors.LOS_STROBE, -1, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    # Sensor Boresight (PiP & Full View)
    # ------------------------------------------------------------------ #

    def _render_sensor_view(self, target: Target3D, camera: TrackingCamera3D,
                            w: int, h: int) -> np.ndarray:
        """Render what the tracking camera's focal plane sensor actually sees."""
        sensor = np.full((h, w, 3), (15, 12, 10), dtype=np.uint8)

        cx, cy = w // 2, h // 2

        # Reticle concentric rings
        cv2.circle(sensor, (cx, cy), int(h * 0.15), (45, 40, 35), 1, cv2.LINE_AA)
        cv2.circle(sensor, (cx, cy), int(h * 0.30), (35, 30, 25), 1, cv2.LINE_AA)
        cv2.line(sensor, (cx - 30, cy), (cx + 30, cy), (80, 70, 60), 1)
        cv2.line(sensor, (cx, cy - 30), (cx, cy + 30), (80, 70, 60), 1)

        # Compute target offset in camera angular frame
        to_target = target.position - camera.position
        dist = np.linalg.norm(to_target)
        if dist > 1e-3 and target.visible:
            cam_dir = camera.direction
            up = np.array([0.0, 1.0, 0.0])
            cam_right = normalize(np.cross(cam_dir, up))
            cam_up = normalize(np.cross(cam_right, cam_dir))

            # Angular deviation in radians
            to_norm = to_target / dist
            dx_rad = np.dot(to_norm, cam_right)
            dy_rad = np.dot(to_norm, cam_up)

            # Convert to pixels based on FOV
            half_fov_rad = math.radians(camera.config.fov_deg / 2.0)
            px = int(cx + (dx_rad / half_fov_rad) * (w / 2))
            py = int(cy - (dy_rad / half_fov_rad) * (h / 2))

            # Clamp spot position for sensor display
            gw = 18
            px = max(gw + 2, min(w - gw - 2, px))
            py = max(gw + 2, min(h - gw - 2, py))

            # Draw target optical spot
            spot_color = (255, 255, 255) if camera.is_locked else (200, 220, 255)
            cv2.circle(sensor, (px, py), 5, (0, 180, 255), 1, cv2.LINE_AA)
            cv2.circle(sensor, (px, py), 3, spot_color, -1, cv2.LINE_AA)

            # Tracking error vector
            lock_color = AerospaceColors.LOCK_LOCKED if camera.is_locked else (
                AerospaceColors.LOCK_ACQUIRING if camera.is_target_in_fov(target.position)
                else AerospaceColors.LOCK_LOST
            )
            cv2.line(sensor, (cx, cy), (px, py), lock_color, 1, cv2.LINE_AA)

            # Spot bounding gate
            cv2.rectangle(sensor, (px - gw, py - gw), (px + gw, py + gw), lock_color, 1)

        # Responsive label
        if w < 300:
            lbl = f"APERTURE [{camera.config.fov_deg:.1f}\u00b0 FOV]"
            cv2.putText(sensor, lbl, (8, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.34, AerospaceColors.HUD_ACCENT, 1, cv2.LINE_AA)
        else:
            lbl = f"OPTICAL RECEIVER APERTURE [{camera.config.fov_deg:.1f} deg FOV]"
            cv2.putText(sensor, lbl, (15, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, AerospaceColors.HUD_ACCENT, 1, cv2.LINE_AA)

        return sensor

    def _draw_pip_sensor(self, frame: np.ndarray, target: Target3D,
                         camera: TrackingCamera3D):
        """Draw small Picture-in-Picture sensor view in upper-right quadrant."""
        pip_w = 240
        pip_h = 160
        pip_x = self.width - pip_w - 20
        pip_y = 45

        pip_img = self._render_sensor_view(target, camera, pip_w, pip_h)

        # Border
        lock_color = AerospaceColors.LOCK_LOCKED if camera.is_locked else (
            AerospaceColors.LOCK_ACQUIRING if camera.is_target_in_fov(target.position)
            else AerospaceColors.LOCK_LOST
        )
        cv2.rectangle(pip_img, (0, 0), (pip_w - 1, pip_h - 1), lock_color, 1)

        # Embed into main frame
        frame[pip_y:pip_y + pip_h, pip_x:pip_x + pip_w] = pip_img

        # Label
        cv2.putText(frame, "TRACKER SENSOR PiP", (pip_x + 6, pip_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, AerospaceColors.HUD_TEXT_MUTED, 1, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    # Telemetry HUD
    # ------------------------------------------------------------------ #

    def _draw_hud_telemetry(self, frame: np.ndarray, target: Target3D,
                            camera: TrackingCamera3D, telem: Dict, minimal: bool = False):
        """Draw clean, high-density aerospace telemetry cards."""
        # Top banner
        title = "ASTRATRACK  |  FSOC 3D TRACKING SIMULATOR"
        cv2.putText(frame, title, (20, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, AerospaceColors.HUD_TEXT_PRIMARY, 2, cv2.LINE_AA)

        # Lock Status Badge
        lock_str = "TARGET LOCKED" if camera.is_locked else (
            "ACQUIRING" if camera.is_target_in_fov(target.position) else "SEARCH / UNLOCKED"
        )
        lock_color = AerospaceColors.LOCK_LOCKED if camera.is_locked else (
            AerospaceColors.LOCK_ACQUIRING if camera.is_target_in_fov(target.position)
            else AerospaceColors.LOCK_LOST
        )

        badge_x = 420
        badge_w = 160
        cv2.rectangle(frame, (badge_x, 12), (badge_x + badge_w, 34), (30, 24, 18), -1)
        cv2.rectangle(frame, (badge_x, 12), (badge_x + badge_w, 34), lock_color, 1)
        cv2.putText(frame, lock_str, (badge_x + 12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, lock_color, 1, cv2.LINE_AA)

        # Mode Indicator
        mode_str = f"MODE: {telem.get('mode', 'REAL-TIME').upper()}"
        cv2.putText(frame, mode_str, (600, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, AerospaceColors.HUD_ACCENT, 1, cv2.LINE_AA)

        # Time & FPS
        fps = telem.get("fps", 0.0)
        sim_time = telem.get("sim_time", 0.0)
        perf_str = f"T: {sim_time:06.2f}s  |  FPS: {fps:.1f}"
        cv2.putText(frame, perf_str, (780, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, AerospaceColors.HUD_TEXT_MUTED, 1, cv2.LINE_AA)

        if minimal:
            return

        # Left Telemetry Card: Target Kinematics & Pointing
        card_x = 20
        card_y = 55
        card_w = 260
        card_h = 295

        # Background overlay for readability
        overlay = frame.copy()
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h),
                      AerospaceColors.PANEL_BG, -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h),
                      AerospaceColors.PANEL_BORDER, 1)

        # Section Header
        cv2.putText(frame, "TELEMETRY & POINTING", (card_x + 10, card_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, AerospaceColors.HUD_ACCENT, 1, cv2.LINE_AA)
        cv2.line(frame, (card_x + 10, card_y + 26), (card_x + card_w - 10, card_y + 26),
                 AerospaceColors.PANEL_BORDER, 1)

        # Compute values
        delta = target.position - camera.position
        slant_range = np.linalg.norm(delta)
        speed = np.linalg.norm(target.velocity)
        pointing_err_mrad = math.radians(camera.angular_error_deg) * 1000.0

        rows = [
            ("Slant Range", f"{slant_range:.1f} m"),
            ("Target Velocity", f"{speed:.1f} m/s"),
            ("Tgt Pos [X,Y,Z]", f"[{target.position[0]:.0f}, {target.position[1]:.0f}, {target.position[2]:.0f}]"),
            ("Gimbal Azimuth", f"{camera.pan_deg:+06.1f} deg"),
            ("Gimbal Elevation", f"{camera.tilt_deg:+05.1f} deg"),
            ("Angular Error", f"{camera.angular_error_deg:.3f} deg ({pointing_err_mrad:.1f} mrad)"),
            ("Camera FOV", f"{camera.config.fov_deg:.1f} deg"),
            ("Lock Stability", f"{telem.get('lock_fraction', 0.0) * 100.0:.1f} %"),
            ("Link SNR (est.)", f"{telem.get('snr_db', 24.5):.1f} dB"),
            ("Scenario", f"{telem.get('scenario_name', 'Linear')}"),
        ]

        ty = card_y + 48
        for label, val in rows:
            cv2.putText(frame, label, (card_x + 12, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.34, AerospaceColors.HUD_TEXT_MUTED, 1, cv2.LINE_AA)
            cv2.putText(frame, val, (card_x + 130, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.34, AerospaceColors.HUD_TEXT_PRIMARY, 1, cv2.LINE_AA)
            ty += 24

    def _draw_status_bar(self, frame: np.ndarray, telem: Dict):
        """Draw bottom status & hotkeys strip."""
        bar_y = self.height - 28
        cv2.rectangle(frame, (0, bar_y), (self.width, self.height), (12, 10, 8), -1)
        cv2.line(frame, (0, bar_y), (self.width, bar_y), AerospaceColors.PANEL_BORDER, 1)

        status_txt = (
            f"VIEW: {self.view_mode.value.upper()} | "
            f"ORBIT: AZ {self.orbit_azimuth_deg:.0f}° EL {self.orbit_elevation_deg:.0f}° R {self.orbit_distance:.0f}m | "
            f"[1-6] Scenario  [V] View Mode  [SPACE] Pause  [R] Reset  [T] Trail  [F] FOV  [L] LOS  [H] HUD"
        )
        cv2.putText(frame, status_txt, (15, bar_y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, AerospaceColors.HUD_TEXT_MUTED, 1, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    # Observer Navigation Controls
    # ------------------------------------------------------------------ #

    def rotate_orbit(self, delta_az: float, delta_el: float):
        """Rotate orbit observer camera around center."""
        self.orbit_azimuth_deg = (self.orbit_azimuth_deg + delta_az) % 360.0
        self.orbit_elevation_deg = max(2.0, min(88.0, self.orbit_elevation_deg + delta_el))

    def zoom_orbit(self, delta_r: float):
        """Zoom orbit observer camera."""
        self.orbit_distance = max(100.0, min(3000.0, self.orbit_distance + delta_r))

    def cycle_view_mode(self):
        """Cycle observer perspective between ORBIT, GROUND_STATION, TARGET_CHASE, SENSOR_FULL."""
        modes = list(ViewMode)
        idx = (modes.index(self.view_mode) + 1) % len(modes)
        self.view_mode = modes[idx]
