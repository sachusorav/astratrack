"""
ASTRATRACK — Aerospace Simulation Viewport Overlay

Renders professional aerospace tracking reticles onto the virtual camera frame:
- Corner-bracket target bounding box
- Target optical centroid marker
- Kalman predicted position with bead trajectory trail
- Precision boresight center crosshair with milliradian ticks
- Outer FOV boundary frame
- Color-coded aerospace status badge:
  LOCKED, ACQUIRING, TRACKING, TARGET LOST, REACQUIRING, ERROR, SEARCHING
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple


# BGR Color definitions for aerospace HUD
HUD_EMERALD = (118, 230, 0)      # LOCKED
HUD_GREEN = (3, 255, 118)        # TRACKING
HUD_CYAN = (255, 176, 0)         # ACQUIRING
HUD_AMBER = (0, 171, 255)        # REACQUIRING
HUD_CORAL = (82, 82, 255)        # TARGET LOST
HUD_RED = (0, 0, 213)            # ERROR
HUD_GOLD = (0, 214, 255)         # SEARCHING
HUD_DIM_GRAY = (70, 80, 95)      # Grid & Reticle
HUD_WHITE = (240, 245, 250)      # High-contrast text
HUD_MAGENTA = (255, 0, 255)      # Prediction trail


def draw_corner_brackets(img: np.ndarray, x: int, y: int, w: int, h: int,
                         color: Tuple[int, int, int], bracket_len: int = 8, thickness: int = 2):
    """Draw aerospace corner brackets [ ] around a target bounding box."""
    x1, y1 = x - w // 2, y - h // 2
    x2, y2 = x + w // 2, y + h // 2

    # Top-Left
    cv2.line(img, (x1, y1), (x1 + bracket_len, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y1), (x1, y1 + bracket_len), color, thickness, cv2.LINE_AA)
    # Top-Right
    cv2.line(img, (x2, y1), (x2 - bracket_len, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y1), (x2, y1 + bracket_len), color, thickness, cv2.LINE_AA)
    # Bottom-Left
    cv2.line(img, (x1, y2), (x1 + bracket_len, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y2), (x1, y2 - bracket_len), color, thickness, cv2.LINE_AA)
    # Bottom-Right
    cv2.line(img, (x2, y2), (x2 - bracket_len, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y2), (x2, y2 - bracket_len), color, thickness, cv2.LINE_AA)


def draw_aerospace_viewport(frame: np.ndarray,
                            fov_center: Tuple[int, int],
                            detection=None,
                            track_state=None,
                            predicted_points: Optional[List[Tuple[float, float]]] = None,
                            status_text: str = "TRACKING",
                            error_px: float = 0.0,
                            error_deg: float = 0.0,
                            confidence: float = 0.0,
                            latency_ms: float = 0.0) -> np.ndarray:
    """
    Render high-contrast aerospace HUD overlays on the camera frame.
    """
    h, w = frame.shape[:2]
    cx, cy = fov_center

    # 1. Outer FOV boundary frame & corner ticks
    cv2.rectangle(frame, (2, 2), (w - 3, h - 3), HUD_DIM_GRAY, 1)
    for corner in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]:
        cv2.circle(frame, corner, 3, HUD_DIM_GRAY, -1)

    # 2. Precision Center Boresight Crosshair with mrad ticks
    cv2.line(frame, (cx - 30, cy), (cx + 30, cy), HUD_DIM_GRAY, 1, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - 30), (cx, cy + 30), HUD_DIM_GRAY, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 4, HUD_DIM_GRAY, 1, cv2.LINE_AA)

    # Ticks along crosshair axes
    for d in [-20, -10, 10, 20]:
        cv2.line(frame, (cx + d, cy - 3), (cx + d, cy + 3), HUD_DIM_GRAY, 1, cv2.LINE_AA)
        cv2.line(frame, (cx - 3, cy + d), (cx + 3, cy + d), HUD_DIM_GRAY, 1, cv2.LINE_AA)

    # 3. Status color selection
    status_upper = status_text.upper()
    if "LOCKED" in status_upper:
        badge_color = HUD_EMERALD
    elif "TRACKING" in status_upper:
        badge_color = HUD_GREEN
    elif "ACQUIRING" in status_upper:
        badge_color = HUD_CYAN
    elif "REACQUIRING" in status_upper:
        badge_color = HUD_AMBER
    elif "LOST" in status_upper:
        badge_color = HUD_CORAL
    elif "ERROR" in status_upper:
        badge_color = HUD_RED
    else:
        badge_color = HUD_GOLD

    # 4. Status Badge Pill (Top-Left)
    badge_txt = f"[ {status_upper} ]"
    pill_w = 125
    cv2.rectangle(frame, (10, 10), (10 + pill_w, 32), (18, 22, 32), -1)
    cv2.rectangle(frame, (10, 10), (10 + pill_w, 32), badge_color, 1)
    cv2.circle(frame, (22, 21), 4, badge_color, -1)
    cv2.putText(frame, badge_txt, (32, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.42, badge_color, 1, cv2.LINE_AA)

    # 5. Target Bounding Box & Centroid
    if detection is not None:
        det_x = int(getattr(detection, "x", getattr(detection, "center", (cx, cy))[0]))
        det_y = int(getattr(detection, "y", getattr(detection, "center", (cx, cy))[1]))
        det_r = int(getattr(detection, "radius", 14))
        box_size = max(24, det_r * 2 + 8)

        # Corner brackets
        draw_corner_brackets(frame, det_x, det_y, box_size, box_size, badge_color, bracket_len=8, thickness=2)
        # Centroid dot
        cv2.circle(frame, (det_x, det_y), 2, badge_color, -1, cv2.LINE_AA)

        # Error vector line from boresight center to target
        cv2.line(frame, (cx, cy), (det_x, det_y), (60, 80, 120), 1, cv2.LINE_AA)

    # 6. Kalman Predicted Trajectory Trail
    if predicted_points and len(predicted_points) > 0:
        prev_pt = None
        for i, (px, py) in enumerate(predicted_points):
            pt = (int(px), int(py))
            if 0 <= pt[0] < w and 0 <= pt[1] < h:
                if prev_pt is not None and i % 2 == 0:
                    cv2.line(frame, prev_pt, pt, HUD_MAGENTA, 1, cv2.LINE_AA)
                cv2.circle(frame, pt, 2, HUD_MAGENTA, -1, cv2.LINE_AA)
                prev_pt = pt

        # Final predicted position chevron
        last_pt = (int(predicted_points[-1][0]), int(predicted_points[-1][1]))
        if 0 <= last_pt[0] < w and 0 <= last_pt[1] < h:
            cv2.drawMarker(frame, last_pt, HUD_MAGENTA, cv2.MARKER_TILTED_CROSS, 8, 1, cv2.LINE_AA)

    # 7. Bottom Telemetry HUD Strip
    hud_bg = frame.copy()
    cv2.rectangle(hud_bg, (0, h - 26), (w, h), (11, 14, 20), -1)
    cv2.addWeighted(hud_bg, 0.85, frame, 0.15, 0, frame)

    telem_str = (f"ERR: {error_px:04.1f}px ({error_deg:04.2f}deg) | "
                 f"CONF: {confidence:04.2f} | LATENCY: {latency_ms:04.1f}ms")
    cv2.putText(frame, telem_str, (12, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.38, HUD_WHITE, 1, cv2.LINE_AA)

    return frame


def draw_overlays(frame: np.ndarray, fov_center: tuple,
                  detection=None, track_state=None,
                  predicted_points: list = None) -> np.ndarray:
    """Backward-compatible entry point calling draw_aerospace_viewport."""
    err_px = track_state.error_px if track_state else 0.0
    err_deg = track_state.error_deg if track_state else 0.0
    is_locked = track_state.is_locked if track_state else False
    st = "LOCKED" if is_locked else ("COAST" if (track_state and track_state.coast_frames > 0) else "SEARCHING")
    conf = getattr(detection, "confidence", 0.9) if detection else 0.0

    return draw_aerospace_viewport(
        frame, fov_center, detection=detection,
        track_state=track_state, predicted_points=predicted_points,
        status_text=st, error_px=err_px, error_deg=err_deg,
        confidence=conf
    )
