"""
ASTRATRACK — State Estimation & Prediction Visualizer

Renders distinct aerospace visual markers for:
1. RAW DETECTION (Red/Amber diamond marker)
2. ESTIMATED POSITION (Emerald green reticle with covariance error ellipse)
3. PREDICTED POSITION (Cyan forecast chevron & trajectory line)

Includes telemetry overlay and mode badge (DETECTION-ONLY / FILTERED / PREDICTIVE).
"""

import math
import cv2
import numpy as np
from typing import List, Tuple, Optional

from estimation.kalman import TrackState, TrackingMode


class VisualizerColors:
    """Distinct aerospace color palette for tracking layers (BGR format)."""
    # Raw Detection
    RAW_COLOR = (45, 80, 245)           # Scarlet Red / Coral
    RAW_ACCENT = (70, 110, 255)

    # Filtered Estimate
    EST_COLOR = (90, 230, 90)           # Emerald Green
    EST_ELLIPSE = (50, 180, 60)         # Covariance error ellipse
    EST_ACCENT = (140, 255, 140)

    # Predicted Position
    PRED_COLOR = (245, 200, 40)         # Cyan / Electric Blue
    PRED_TRAIL = (210, 160, 30)
    PRED_ACCENT = (255, 230, 80)

    # Text & Badges
    HUD_BG = (22, 18, 14)
    HUD_BORDER = (60, 50, 40)
    TEXT_PRIMARY = (240, 235, 230)
    TEXT_MUTED = (160, 150, 140)


def draw_raw_detection_marker(frame: np.ndarray, x: float, y: float,
                             radius: float = 12.0):
    """Draw a distinct diamond marker with crosshair for RAW DETECTION."""
    ix, iy = int(round(x)), int(round(y))
    r = int(max(6, radius))

    # Diamond vertices
    pts = np.array([
        [ix, iy - r],
        [ix + r, iy],
        [ix, iy + r],
        [ix - r, iy]
    ], dtype=np.int32)

    cv2.polylines(frame, [pts], isClosed=True, color=VisualizerColors.RAW_COLOR, thickness=2, lineType=cv2.LINE_AA)
    # Open cross ticks
    cv2.line(frame, (ix - r - 4, iy), (ix - r + 2, iy), VisualizerColors.RAW_COLOR, 1, cv2.LINE_AA)
    cv2.line(frame, (ix + r - 2, iy), (ix + r + 4, iy), VisualizerColors.RAW_COLOR, 1, cv2.LINE_AA)
    cv2.line(frame, (ix, iy - r - 4), (ix, iy - r + 2), VisualizerColors.RAW_COLOR, 1, cv2.LINE_AA)
    cv2.line(frame, (ix, iy + r - 2), (ix, iy + r + 4), VisualizerColors.RAW_COLOR, 1, cv2.LINE_AA)

    # Label
    cv2.putText(frame, "RAW", (ix + r + 6, iy + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, VisualizerColors.RAW_COLOR, 1, cv2.LINE_AA)


def draw_estimated_marker(frame: np.ndarray, x: float, y: float,
                          track_state: TrackState, radius: float = 10.0):
    """Draw circular reticle, crosshair, and covariance error ellipse for ESTIMATED POSITION."""
    ix, iy = int(round(x)), int(round(y))
    r = int(max(5, radius))

    # Covariance error ellipse (2-sigma spatial uncertainty)
    if track_state.error_ellipse is not None:
        ell = track_state.error_ellipse
        major = int(max(4, min(120, ell.semi_major * 2.0)))
        minor = int(max(3, min(120, ell.semi_minor * 2.0)))
        angle = ell.angle_deg
        cv2.ellipse(frame, (ix, iy), (major, minor), angle, 0, 360,
                    VisualizerColors.EST_ELLIPSE, 1, cv2.LINE_AA)

    # Centroid circle & crosshair
    cv2.circle(frame, (ix, iy), r, VisualizerColors.EST_COLOR, 2, cv2.LINE_AA)
    cv2.circle(frame, (ix, iy), 2, VisualizerColors.EST_ACCENT, -1, cv2.LINE_AA)
    cv2.line(frame, (ix - r - 5, iy), (ix + r + 5, iy), VisualizerColors.EST_COLOR, 1, cv2.LINE_AA)
    cv2.line(frame, (ix, iy - r - 5), (ix, iy + r + 5), VisualizerColors.EST_COLOR, 1, cv2.LINE_AA)

    # Label
    vel_str = f"EST [{track_state.estimated_vel[0]:+.1f}, {track_state.estimated_vel[1]:+.1f}]"
    cv2.putText(frame, vel_str, (ix + r + 6, iy - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, VisualizerColors.EST_COLOR, 1, cv2.LINE_AA)


def draw_predicted_marker(frame: np.ndarray, est_x: float, est_y: float,
                          pred_x: float, pred_y: float,
                          trajectory_points: Optional[List[Tuple[float, float]]] = None):
    """Draw trajectory line, waypoint dots, and chevron target for PREDICTED POSITION."""
    iex, iey = int(round(est_x)), int(round(est_y))
    ipx, ipy = int(round(pred_x)), int(round(pred_y))

    # Dotted or solid trajectory forecast line
    if trajectory_points and len(trajectory_points) > 1:
        pts = [(iex, iey)] + [(int(round(p[0])), int(round(p[1]))) for p in trajectory_points]
        for i in range(len(pts) - 1):
            cv2.line(frame, pts[i], pts[i + 1], VisualizerColors.PRED_TRAIL, 1, cv2.LINE_AA)
            cv2.circle(frame, pts[i + 1], 2, VisualizerColors.PRED_ACCENT, -1, cv2.LINE_AA)
    else:
        cv2.line(frame, (iex, iey), (ipx, ipy), VisualizerColors.PRED_TRAIL, 1, cv2.LINE_AA)

    # Predicted position chevron / reticle
    pr = 8
    # Square reticle with cut corners
    cv2.rectangle(frame, (ipx - pr, ipy - pr), (ipx + pr, ipy + pr),
                  VisualizerColors.PRED_COLOR, 2, cv2.LINE_AA)
    cv2.circle(frame, (ipx, ipy), 2, VisualizerColors.PRED_ACCENT, -1, cv2.LINE_AA)

    # Label
    cv2.putText(frame, "PRED (+N)", (ipx + pr + 6, ipy + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, VisualizerColors.PRED_COLOR, 1, cv2.LINE_AA)


def draw_estimation_telemetry(frame: np.ndarray, track_state: TrackState,
                              fps: float = 60.0):
    """Draw top-left aerospace telemetry card comparing raw, estimated, and predicted states."""
    card_x, card_y = 15, 15
    card_w, card_h = 290, 160

    # Background panel
    sub = frame[card_y:card_y + card_h, card_x:card_x + card_w]
    if sub.shape[0] == card_h and sub.shape[1] == card_w:
        overlay = np.full_like(sub, VisualizerColors.HUD_BG)
        cv2.addWeighted(overlay, 0.85, sub, 0.15, 0, sub)
        cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h),
                      VisualizerColors.HUD_BORDER, 1)

    # Mode Badge
    mode_text = {
        TrackingMode.DETECTION_ONLY: "MODE: DETECTION-ONLY",
        TrackingMode.FILTERED: "MODE: FILTERED (PRED OFF)",
        TrackingMode.PREDICTIVE: "MODE: PREDICTIVE TRACKING"
    }.get(track_state.tracking_mode, "MODE: PREDICTIVE")

    badge_color = {
        TrackingMode.DETECTION_ONLY: VisualizerColors.RAW_COLOR,
        TrackingMode.FILTERED: VisualizerColors.EST_COLOR,
        TrackingMode.PREDICTIVE: VisualizerColors.PRED_COLOR
    }.get(track_state.tracking_mode, VisualizerColors.PRED_COLOR)

    cv2.putText(frame, mode_text, (card_x + 12, card_y + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, badge_color, 1, cv2.LINE_AA)

    # State values
    raw_str = f"[{track_state.raw_pos[0]:.1f}, {track_state.raw_pos[1]:.1f}]" if track_state.raw_pos else "LOST / OCCLUDED"
    est_str = f"[{track_state.estimated_pos[0]:.1f}, {track_state.estimated_pos[1]:.1f}]"
    vel_str = f"[{track_state.estimated_vel[0]:+.1f}, {track_state.estimated_vel[1]:+.1f}] px/s"
    pred_str = f"[{track_state.predicted_pos[0]:.1f}, {track_state.predicted_pos[1]:.1f}]" if track_state.prediction_enabled else "OFF"
    unc_str = f"{track_state.position_uncertainty:.2f} px (trace P: {track_state.covariance:.1f})"

    rows = [
        ("Raw Detection:", raw_str, VisualizerColors.RAW_COLOR),
        ("Filtered Est:", est_str, VisualizerColors.EST_COLOR),
        ("Est Velocity:", vel_str, VisualizerColors.TEXT_PRIMARY),
        ("Predicted Pos:", pred_str, VisualizerColors.PRED_COLOR if track_state.prediction_enabled else VisualizerColors.TEXT_MUTED),
        ("Uncertainty \u03c3:", unc_str, VisualizerColors.TEXT_MUTED),
    ]

    ty = card_y + 46
    for lbl, val, val_col in rows:
        cv2.putText(frame, lbl, (card_x + 12, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, VisualizerColors.TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, val, (card_x + 115, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, val_col, 1, cv2.LINE_AA)
        ty += 22


def render_tracking_frame(frame: np.ndarray,
                          track_state: TrackState,
                          predicted_trajectory: Optional[List[Tuple[float, float]]] = None,
                          show_raw: bool = True,
                          show_est: bool = True,
                          show_pred: bool = True,
                          show_telemetry: bool = True) -> np.ndarray:
    """
    Composite all estimation visual markers onto a frame buffer.

    Args:
        frame: Base BGR image (e.g. camera view).
        track_state: Current TrackState from KalmanTracker.
        predicted_trajectory: Optional list of trajectory waypoints.
        show_raw: Draw RAW DETECTION marker if available.
        show_est: Draw ESTIMATED POSITION reticle & uncertainty ellipse.
        show_pred: Draw PREDICTED POSITION marker & forecast trajectory.
        show_telemetry: Draw overlay metrics card.

    Returns:
        Rendered OpenCV frame.
    """
    out = frame.copy()

    # 1. Raw Detection (Red Diamond)
    if show_raw and track_state.raw_pos is not None:
        draw_raw_detection_marker(out, track_state.raw_pos[0], track_state.raw_pos[1])

    # 2. Filtered Estimate (Emerald Reticle + Covariance Ellipse)
    if show_est:
        draw_estimated_marker(out, track_state.estimated_pos[0], track_state.estimated_pos[1], track_state)

    # 3. Predicted Position (Cyan Chevron & Vector)
    if show_pred and track_state.prediction_enabled:
        draw_predicted_marker(
            out,
            track_state.estimated_pos[0], track_state.estimated_pos[1],
            track_state.predicted_pos[0], track_state.predicted_pos[1],
            trajectory_points=predicted_trajectory
        )

    # 4. Telemetry Overlay Card
    if show_telemetry:
        draw_estimation_telemetry(out, track_state)

    return out
