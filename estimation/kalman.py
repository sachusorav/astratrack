"""
ASTRATRACK — Advanced State Estimation & Kalman Filter

Provides continuous target state estimation and uncertainty tracking for
optical beacons. Supports:
- 4-State Constant Velocity (CV): [x, y, vx, vy]^T
- 6-State Constant Acceleration (CA): [x, y, vx, vy, ax, ay]^T
- Dynamic time-step (dt) adaptation
- Configurable process noise (Q) and measurement noise (R)
- Measurement dropout handling (coast mode / dead-reckoning)
- Covariance estimation and 2D spatial uncertainty error ellipse
- Prediction ON/OFF toggle and TrackingMode selection
"""

import math
import cv2
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any

from core.config import KalmanConfig


class TrackingMode(Enum):
    """Active target tracking paradigm."""
    DETECTION_ONLY = "detection_only"   # Raw measurements only (unfiltered)
    FILTERED = "filtered"               # Kalman filtered state (prediction OFF)
    PREDICTIVE = "predictive"           # Kalman filtered state + anticipatory prediction (prediction ON)


@dataclass
class ErrorEllipse:
    """2D spatial uncertainty error ellipse derived from covariance submatrix."""
    semi_major: float      # 1-sigma semi-major axis (pixels)
    semi_minor: float      # 1-sigma semi-minor axis (pixels)
    angle_deg: float       # Orientation angle in degrees


@dataclass
class TrackState:
    """
    Complete state estimation output from the Kalman tracker.

    100% backwards compatible with legacy callers while adding 6D acceleration,
    raw measurement storage, error ellipses, and tracking mode metadata.
    """
    estimated_pos: Tuple[float, float]               # (x, y) filtered position in pixels
    estimated_vel: Tuple[float, float]               # (vx, vy) filtered velocity in px/s or px/frame
    predicted_pos: Tuple[float, float]               # (x, y) predicted position N steps ahead
    error_px: float                                  # Distance from FOV boresight center in pixels
    error_deg: float                                 # Angular error from center in degrees
    covariance: float                                # Trace of covariance matrix P
    is_locked: bool                                  # True if valid measurement received this frame
    coast_frames: int                                # Consecutive frames coasted without measurement

    # Advanced metadata
    estimated_acc: Tuple[float, float] = (0.0, 0.0)  # (ax, ay) estimated acceleration
    raw_pos: Optional[Tuple[float, float]] = None    # Raw measurement (x, y) if received
    position_uncertainty: float = 0.0                # sqrt(P_xx + P_yy) in pixels
    error_ellipse: Optional[ErrorEllipse] = None     # 2D uncertainty ellipse
    tracking_mode: TrackingMode = TrackingMode.PREDICTIVE
    prediction_enabled: bool = True
    state_vector: Optional[np.ndarray] = None        # Full state vector
    covariance_matrix: Optional[np.ndarray] = None   # Full P matrix


class KalmanTracker:
    """
    Adaptive Kalman filter for optical beacon state estimation and prediction.

    Supports 4-state [x, y, vx, vy] and 6-state [x, y, vx, vy, ax, ay] formulations.
    """

    def __init__(self,
                 config: Optional[KalmanConfig] = None,
                 fov_center: Tuple[float, float] = (320.0, 240.0),
                 deg_per_pixel: float = 0.1,
                 state_dim: int = 4,
                 prediction_enabled: bool = True,
                 prediction_horizon: int = 15):
        """
        Args:
            config: Kalman configuration object.
            fov_center: (cx, cy) boresight center in pixels.
            deg_per_pixel: Conversion factor from pixels to degrees.
            state_dim: 4 (CV model: x, y, vx, vy) or 6 (CA model: x, y, vx, vy, ax, ay).
            prediction_enabled: Master toggle for prediction extrapolation.
            prediction_horizon: Number of frames / steps to project into the future.
        """
        self.config = config or KalmanConfig()
        self.fov_center = fov_center
        self.deg_per_pixel = deg_per_pixel
        self.state_dim = 6 if state_dim == 6 else 4

        # Toggles & Configuration
        self._prediction_enabled = bool(prediction_enabled)
        self.prediction_horizon = int(prediction_horizon or self.config.prediction_horizon)
        self._process_noise = float(self.config.process_noise)
        self._measurement_noise = float(self.config.measurement_noise)
        self.tracking_mode = TrackingMode.PREDICTIVE if self._prediction_enabled else TrackingMode.FILTERED

        # Measurement dimension: always observing [x, y]
        self.meas_dim = 2

        # State tracking
        self.coast_frames = 0
        self.is_initialized = False
        self._last_detection = None
        self._last_dt = 1.0 / 60.0

        # Build filter matrices
        self._init_matrices(dt=self._last_dt)

    # ------------------------------------------------------------------ #
    # Filter Initialization & Matrices
    # ------------------------------------------------------------------ #

    def _init_matrices(self, dt: float = 0.01667):
        """Construct state transition (F), measurement (H), Q, R, and P matrices."""
        n = self.state_dim
        m = self.meas_dim
        self._last_dt = dt

        # State vector x: (n, 1)
        self.x = np.zeros((n, 1), dtype=np.float64)

        # Transition matrix F
        self.F = self._build_transition_matrix(dt)

        # Measurement matrix H: maps state to [x, y]
        self.H = np.zeros((m, n), dtype=np.float64)
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0

        # Process noise covariance Q
        self.Q = self._build_process_noise_matrix(dt, self._process_noise)

        # Measurement noise covariance R
        self.R = np.eye(m, dtype=np.float64) * self._measurement_noise

        # State error covariance P
        p0 = float(self.config.initial_covariance)
        self.P = np.eye(n, dtype=np.float64) * p0

    def _build_transition_matrix(self, dt: float) -> np.ndarray:
        """Build state transition matrix F for time-step dt."""
        n = self.state_dim
        F = np.eye(n, dtype=np.float64)
        if n == 4:
            # Constant Velocity (CV)
            F[0, 2] = dt
            F[1, 3] = dt
        elif n == 6:
            # Constant Acceleration (CA)
            F[0, 2] = dt
            F[1, 3] = dt
            F[0, 4] = 0.5 * dt * dt
            F[1, 5] = 0.5 * dt * dt
            F[2, 4] = dt
            F[3, 5] = dt
        return F

    def _build_process_noise_matrix(self, dt: float, q: float) -> np.ndarray:
        """
        Build continuous-white-noise process covariance matrix Q.
        Discretized using piecewise continuous acceleration model.
        """
        n = self.state_dim
        Q = np.eye(n, dtype=np.float64)
        if n == 4:
            # Position-velocity blocks
            dt3 = (dt ** 3) / 3.0
            dt2 = (dt ** 2) / 2.0
            Q_block = np.array([
                [dt3, dt2],
                [dt2, dt]
            ], dtype=np.float64) * q

            Q[0:2, 0:2] = Q_block * 0.5
            Q[0, 0] = dt3 * q
            Q[0, 2] = dt2 * q
            Q[2, 0] = dt2 * q
            Q[2, 2] = dt * q * 4.0

            Q[1, 1] = dt3 * q
            Q[1, 3] = dt2 * q
            Q[3, 1] = dt2 * q
            Q[3, 3] = dt * q * 4.0
        elif n == 6:
            # 6D: position, velocity, acceleration blocks
            dt5 = (dt ** 5) / 20.0
            dt4 = (dt ** 4) / 8.0
            dt3 = (dt ** 3) / 6.0
            dt2 = (dt ** 2) / 2.0

            # X block
            Q[0, 0] = dt5 * q; Q[0, 2] = dt4 * q; Q[0, 4] = dt3 * q
            Q[2, 0] = dt4 * q; Q[2, 2] = dt3 * q * 2.0; Q[2, 4] = dt2 * q
            Q[4, 0] = dt3 * q; Q[4, 2] = dt2 * q; Q[4, 4] = dt * q * 4.0

            # Y block
            Q[1, 1] = dt5 * q; Q[1, 3] = dt4 * q; Q[1, 5] = dt3 * q
            Q[3, 1] = dt4 * q; Q[3, 3] = dt3 * q * 2.0; Q[3, 5] = dt2 * q
            Q[5, 1] = dt3 * q; Q[5, 3] = dt2 * q; Q[5, 5] = dt * q * 4.0

        return Q

    # ------------------------------------------------------------------ #
    # Configurable Noise & Toggles
    # ------------------------------------------------------------------ #

    @property
    def process_noise(self) -> float:
        return self._process_noise

    @process_noise.setter
    def process_noise(self, value: float):
        """Set process noise covariance scale Q."""
        self._process_noise = max(1e-6, float(value))
        self.Q = self._build_process_noise_matrix(self._last_dt, self._process_noise)

    @property
    def measurement_noise(self) -> float:
        return self._measurement_noise

    @measurement_noise.setter
    def measurement_noise(self, value: float):
        """Set measurement noise covariance scale R."""
        self._measurement_noise = max(1e-6, float(value))
        self.R = np.eye(self.meas_dim, dtype=np.float64) * self._measurement_noise

    @property
    def prediction_enabled(self) -> bool:
        return self._prediction_enabled

    @prediction_enabled.setter
    def prediction_enabled(self, value: bool):
        """Toggle prediction ON/OFF."""
        self._prediction_enabled = bool(value)
        if self._prediction_enabled:
            self.tracking_mode = TrackingMode.PREDICTIVE
        else:
            self.tracking_mode = TrackingMode.FILTERED

    def set_tracking_mode(self, mode: TrackingMode):
        """Explicitly set tracking paradigm."""
        self.tracking_mode = mode
        if mode == TrackingMode.PREDICTIVE:
            self._prediction_enabled = True
        else:
            self._prediction_enabled = False

    # ------------------------------------------------------------------ #
    # Predict & Correct Cycle
    # ------------------------------------------------------------------ #

    def update(self, detection: Optional[object],
               dt: Optional[float] = None) -> TrackState:
        """
        Run one predict and update cycle.

        Args:
            detection: Object with .x and .y attributes, or None if measurement missing.
            dt: Optional time-step duration (seconds).

        Returns:
            TrackState with estimated pos, velocity, predicted pos, and uncertainty.
        """
        # Adapt transition matrices if dt changed
        if dt is not None and abs(dt - self._last_dt) > 1e-4 and dt > 0:
            self.F = self._build_transition_matrix(dt)
            self.Q = self._build_process_noise_matrix(dt, self._process_noise)
            self._last_dt = dt

        # ----------------- 1. Predict Step ----------------- #
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        raw_measurement: Optional[Tuple[float, float]] = None

        # ----------------- 2. Correct Step ----------------- #
        if detection is not None:
            # Extract measurement coords
            meas_x = float(getattr(detection, "x", 0.0))
            meas_y = float(getattr(detection, "y", 0.0))
            raw_measurement = (meas_x, meas_y)
            z = np.array([[meas_x], [meas_y]], dtype=np.float64)

            if not self.is_initialized:
                # Direct initialization on first positive detection
                self.x = np.zeros((self.state_dim, 1), dtype=np.float64)
                self.x[0, 0] = meas_x
                self.x[1, 0] = meas_y
                self.P = np.eye(self.state_dim, dtype=np.float64) * float(self.config.initial_covariance)
                self.is_initialized = True
            else:
                # Innovation / Residual: y = z - H * x
                y = z - (self.H @ self.x)

                # Dynamic measurement noise scaling based on confidence if available
                meas_r = self.R
                if hasattr(detection, "confidence") and detection.confidence > 0.01:
                    conf = float(detection.confidence)
                    # Lower confidence increases measurement uncertainty
                    meas_r = self.R / max(0.2, conf)

                # Innovation covariance: S = H * P * H^T + R
                S = self.H @ self.P @ self.H.T + meas_r

                # Kalman Gain: K = P * H^T * S^-1
                K = self.P @ self.H.T @ np.linalg.inv(S)

                # State update: x = x + K * y
                self.x = self.x + K @ y

                # Covariance update (Joseph form for numerical stability):
                # P = (I - K*H) * P * (I - K*H)^T + K*R*K^T
                I_KH = np.eye(self.state_dim, dtype=np.float64) - (K @ self.H)
                self.P = I_KH @ self.P @ I_KH.T + K @ meas_r @ K.T

            self.coast_frames = 0
            self._last_detection = detection
        else:
            # Coasting / Dead-reckoning: covariance naturally inflates with Q
            self.coast_frames += 1

        # ----------------- 3. Extract State Estimates ----------------- #
        est_x = float(self.x[0, 0])
        est_y = float(self.x[1, 0])
        est_vx = float(self.x[2, 0])
        est_vy = float(self.x[3, 0])
        est_ax = float(self.x[4, 0]) if self.state_dim == 6 else 0.0
        est_ay = float(self.x[5, 0]) if self.state_dim == 6 else 0.0

        # Tracking Mode Override (Detection Only)
        if self.tracking_mode == TrackingMode.DETECTION_ONLY and raw_measurement is not None:
            est_x, est_y = raw_measurement

        # Compute Boresight Error
        dx = est_x - self.fov_center[0]
        dy = est_y - self.fov_center[1]
        error_px = math.sqrt(dx * dx + dy * dy)
        error_deg = error_px * self.deg_per_pixel

        # ----------------- 4. Forward Prediction ----------------- #
        if self._prediction_enabled:
            # Advance forward in physical time (seconds)
            dt_lead = float(self.prediction_horizon) * max(1e-4, self._last_dt)
            if self.state_dim == 6:
                # Constant Acceleration projection
                pred_x = est_x + est_vx * dt_lead + 0.5 * est_ax * (dt_lead ** 2)
                pred_y = est_y + est_vy * dt_lead + 0.5 * est_ay * (dt_lead ** 2)
            else:
                # Constant Velocity projection
                pred_x = est_x + est_vx * dt_lead
                pred_y = est_y + est_vy * dt_lead
        else:
            # Prediction OFF: predicted position matches filtered estimate
            pred_x = est_x
            pred_y = est_y

        # ----------------- 5. Uncertainty & Error Ellipse ----------------- #
        # Position covariance submatrix (2x2)
        P_pos = self.P[0:2, 0:2]
        var_x = max(0.0, float(P_pos[0, 0]))
        var_y = max(0.0, float(P_pos[1, 1]))
        cov_xy = float(P_pos[0, 1])

        position_unc = math.sqrt(var_x + var_y)
        trace_p = float(np.trace(self.P))

        # Eigenvalues and orientation for spatial error ellipse
        eigenvalues, eigenvectors = np.linalg.eigh(P_pos)
        order = eigenvalues.argsort()[::-1]
        eigenvalues = np.maximum(1e-6, eigenvalues[order])
        eigenvectors = eigenvectors[:, order]

        semi_major = float(math.sqrt(eigenvalues[0]))
        semi_minor = float(math.sqrt(eigenvalues[1]))
        angle_rad = math.atan2(eigenvectors[1, 0], eigenvectors[0, 0])
        angle_deg = float(math.degrees(angle_rad))

        ellipse = ErrorEllipse(
            semi_major=semi_major,
            semi_minor=semi_minor,
            angle_deg=angle_deg
        )

        return TrackState(
            estimated_pos=(est_x, est_y),
            estimated_vel=(est_vx, est_vy),
            predicted_pos=(pred_x, pred_y),
            error_px=error_px,
            error_deg=error_deg,
            covariance=trace_p,
            is_locked=(detection is not None),
            coast_frames=self.coast_frames,
            estimated_acc=(est_ax, est_ay),
            raw_pos=raw_measurement,
            position_uncertainty=position_unc,
            error_ellipse=ellipse,
            tracking_mode=self.tracking_mode,
            prediction_enabled=self._prediction_enabled,
            state_vector=self.x.copy(),
            covariance_matrix=self.P.copy()
        )

    def reset(self):
        """Reset filter state to uninitialized."""
        self._init_matrices(dt=self._last_dt)
        self.coast_frames = 0
        self.is_initialized = False
        self._last_detection = None

    @property
    def is_coasting(self) -> bool:
        """True if currently propagating without measurements."""
        return self.coast_frames > 0

    @property
    def coast_exceeded(self) -> bool:
        """True if consecutive lost frames exceed configured coast threshold."""
        return self.coast_frames > self.config.coast_limit
