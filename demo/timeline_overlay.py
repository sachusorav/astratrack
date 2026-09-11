"""
ASTRATRACK — Judge Demo Timeline Overlay

Renders the interactive timeline breadcrumb ribbon onto the camera frame:
DETECT -> ACQUIRE -> TRACK -> DISTURBANCE -> TARGET LOST -> PREDICT -> REACQUIRE -> LOCKED
"""

import cv2
import numpy as np
from demo.director import DemoPhase


DISPLAY_STAGES = [
    DemoPhase.DETECT,
    DemoPhase.ACQUIRE,
    DemoPhase.TRACK,
    DemoPhase.DISTURBANCE,
    DemoPhase.TARGET_LOST,
    DemoPhase.PREDICT,
    DemoPhase.REACQUIRE,
    DemoPhase.LOCKED_REPORT,
]


def draw_demo_timeline(frame: np.ndarray,
                       current_phase: DemoPhase,
                       elapsed_s: float,
                       total_s: float = 90.0) -> np.ndarray:
    """
    Render aerospace timeline ribbon along top of camera frame.
    """
    h, w = frame.shape[:2]

    # Semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 54), (11, 14, 20), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    # Header label & timer
    timer_txt = f"JUDGE DEMO: {elapsed_s:04.1f}s / {total_s:04.1f}s"
    cv2.putText(frame, timer_txt, (14, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 230, 118), 1, cv2.LINE_AA)

    # Progress bar line
    bar_w = int((w - 28) * min(1.0, elapsed_s / total_s))
    cv2.line(frame, (14, 24), (14 + bar_w, 24), (0, 230, 118), 2, cv2.LINE_AA)

    # Stage pills
    curr_idx = 0
    for idx, p in enumerate(DISPLAY_STAGES):
        if p == current_phase or (current_phase == DemoPhase.HIGH_SPEED and p == DemoPhase.TRACK) or (current_phase == DemoPhase.COAST and p == DemoPhase.PREDICT):
            curr_idx = idx
            break

    n_stages = len(DISPLAY_STAGES)
    stage_w = (w - 28) / n_stages

    for i, phase in enumerate(DISPLAY_STAGES):
        x1 = int(14 + i * stage_w)
        x2 = int(x1 + stage_w - 4)
        y1, y2 = 30, 48

        # Color: Past = Emerald, Active = Glowing Cyan, Future = Muted Gray
        if i < curr_idx:
            bg_col = (20, 80, 40)
            txt_col = (120, 240, 160)
        elif i == curr_idx:
            bg_col = (100, 180, 0)  # Glowing Cyan/Green
            txt_col = (255, 255, 255)
        else:
            bg_col = (25, 30, 40)
            txt_col = (100, 115, 130)

        cv2.rectangle(frame, (x1, y1), (x2, y2), bg_col, -1)
        label = phase.value[:8]
        cv2.putText(frame, label, (x1 + 4, y1 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.30, txt_col, 1, cv2.LINE_AA)

    return frame
