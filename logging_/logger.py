"""
ASTRATRACK — Performance Logger

Writes per-frame tracking metrics to a timestamped CSV file.
Automatically creates session folders for organized data collection.
"""

import csv
import os
import time
from typing import Optional
from logging_.session import SessionManager


class PerformanceLogger:
    """
    Logs per-frame tracking performance data to CSV.

    Columns:
        timestamp, gt_x, gt_y, det_x, det_y, est_x, est_y, pred_x, pred_y,
        err_track_px, err_gt_px, err_deg, fps, lock_status, coast_frames,
        pid_pan, pid_tilt, turb_level, vib_level, noise_level
    """

    HEADER = [
        "timestamp", "gt_x", "gt_y", "det_x", "det_y",
        "est_x", "est_y", "pred_x", "pred_y",
        "err_track_px", "err_gt_px", "err_deg",
        "fps", "lock_status", "coast_frames",
        "pid_pan", "pid_tilt",
        "turb_level", "vib_level", "noise_level",
    ]

    def __init__(self, session_manager: Optional[SessionManager] = None):
        """
        Initialize the logger.

        Args:
            session_manager: Optional SessionManager for organized sessions.
        """
        self.session = session_manager or SessionManager()
        self._file = None
        self._writer = None
        self._start_time = None
        self._frame_count = 0

    def start(self, config_dict: dict = None):
        """
        Start a new logging session.

        Args:
            config_dict: Optional config snapshot for session metadata.
        """
        self.session.start_session(config_dict)
        log_path = self.session.log_path

        self._file = open(log_path, 'w', newline='')
        self._writer = csv.writer(self._file)
        self._writer.writerow(self.HEADER)
        self._start_time = time.time()
        self._frame_count = 0

    def record(self, gt_pos: tuple, det_pos: tuple, est_pos: tuple,
               pred_pos: tuple, err_track_px: float, err_gt_px: float,
               err_deg: float, fps: float, is_locked: bool,
               coast_frames: int, pid_pan: float, pid_tilt: float,
               turb_level: float, vib_level: float, noise_level: float):
        """
        Record one frame's metrics.

        Args:
            gt_pos: Ground truth beacon position (x, y).
            det_pos: Detected position (x, y) or (-1, -1) if no detection.
            est_pos: Kalman estimated position (x, y).
            pred_pos: Predicted position (x, y).
            err_track_px: Tracking error in pixels (from FOV center).
            err_gt_px: Ground truth error in pixels.
            err_deg: Angular error in degrees.
            fps: Current frame rate.
            is_locked: Whether detection is present.
            coast_frames: Number of frames coasting.
            pid_pan: PID pan output.
            pid_tilt: PID tilt output.
            turb_level: Current turbulence level.
            vib_level: Current vibration level.
            noise_level: Current noise level.
        """
        if self._writer is None:
            return

        t = time.time() - self._start_time
        self._writer.writerow([
            f"{t:.4f}",
            f"{gt_pos[0]:.1f}", f"{gt_pos[1]:.1f}",
            f"{det_pos[0]:.1f}", f"{det_pos[1]:.1f}",
            f"{est_pos[0]:.1f}", f"{est_pos[1]:.1f}",
            f"{pred_pos[0]:.1f}", f"{pred_pos[1]:.1f}",
            f"{err_track_px:.2f}", f"{err_gt_px:.2f}", f"{err_deg:.3f}",
            f"{fps:.1f}", int(is_locked), coast_frames,
            f"{pid_pan:.3f}", f"{pid_tilt:.3f}",
            f"{turb_level:.1f}", f"{vib_level:.2f}", f"{noise_level:.1f}",
        ])
        self._frame_count += 1

        # Flush periodically
        if self._frame_count % 60 == 0 and self._file:
            self._file.flush()

    def stop(self):
        """Close the log file."""
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
            self._writer = None

    @property
    def is_active(self) -> bool:
        """True if logging is in progress."""
        return self._writer is not None
