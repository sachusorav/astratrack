"""
ASTRATRACK — Multi-Step Motion Predictor & Trajectory Extrapolator

Projects Kalman filter kinematic states into future time frames to support:
- Visual trajectory forecast
- Anticipatory gimbal slew & lead-angle compensation
- Uncertainty cone propagation
- Prediction ON/OFF toggle
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from estimation.kalman import TrackState, ErrorEllipse


@dataclass
class PredictionPoint:
    """A single forecasted trajectory waypoint with uncertainty."""
    step: int
    pos: Tuple[float, float]
    uncertainty_radius: float


class MotionPredictor:
    """
    Generates multi-step future positions and uncertainty envelopes.

    Supports:
    - Linear (CV) and Quadratic (CA) extrapolation
    - Dynamic prediction horizon and step size
    - Prediction enable/disable toggle
    """

    def __init__(self,
                 horizon: int = 30,
                 step: int = 5,
                 enabled: bool = True):
        """
        Args:
            horizon: Number of frames into future to predict.
            step: Step interval between prediction points.
            enabled: Master enable/disable toggle for trajectory prediction.
        """
        self.horizon = int(horizon)
        self.step = max(1, int(step))
        self.enabled = bool(enabled)

    def predict_trajectory(self, track_state: TrackState,
                           dt: float = 0.01667) -> List[Tuple[float, float]]:
        """
        Generate a list of predicted future positions (x, y).

        If prediction is disabled, returns an empty list.

        Args:
            track_state: Current Kalman track state.
            dt: Frame duration in seconds (default: 1/60s).

        Returns:
            List of (x, y) coordinates along predicted trajectory.
        """
        if not self.enabled or not track_state.prediction_enabled:
            return []

        points: List[Tuple[float, float]] = []
        ex, ey = track_state.estimated_pos
        vx, vy = track_state.estimated_vel
        ax, ay = track_state.estimated_acc

        use_accel = (abs(ax) > 1e-4 or abs(ay) > 1e-4)

        for n in range(self.step, self.horizon + 1, self.step):
            dt_lead = float(n) * dt
            if use_accel:
                px = ex + vx * dt_lead + 0.5 * ax * (dt_lead ** 2)
                py = ey + vy * dt_lead + 0.5 * ay * (dt_lead ** 2)
            else:
                px = ex + vx * dt_lead
                py = ey + vy * dt_lead
            points.append((px, py))

        return points

    def predict_with_uncertainty(self, track_state: TrackState
                                  ) -> List[PredictionPoint]:
        """
        Generate trajectory points with expanding spatial uncertainty radii.
        """
        if not self.enabled or not track_state.prediction_enabled:
            return []

        points: List[PredictionPoint] = []
        ex, ey = track_state.estimated_pos
        vx, vy = track_state.estimated_vel
        ax, ay = track_state.estimated_acc
        base_unc = track_state.position_uncertainty

        for n in range(self.step, self.horizon + 1, self.step):
            fn = float(n)
            px = ex + vx * fn + 0.5 * ax * (fn ** 2)
            py = ey + vy * fn + 0.5 * ay * (fn ** 2)

            # Uncertainty expands with sqrt of prediction horizon
            expanded_unc = base_unc * (1.0 + 0.12 * np.sqrt(fn))

            points.append(PredictionPoint(
                step=n,
                pos=(px, py),
                uncertainty_radius=expanded_unc
            ))

        return points
