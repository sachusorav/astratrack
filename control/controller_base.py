"""
ASTRATRACK — Controller Interface & Base Classes

Defines standard interface for camera and gimbal tracking controllers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ControllerTelemetry:
    """Telemetry data output by a tracking controller."""
    control_output: float
    error: float
    p_term: float = 0.0
    i_term: float = 0.0
    d_term: float = 0.0
    is_saturated: bool = False
    in_deadzone: bool = False


class IController(ABC):
    """Abstract base class for all tracking controllers."""

    @abstractmethod
    def compute(self, error: float, dt: float) -> float:
        """
        Compute control actuation for the given error.

        Args:
            error: Tracking error (setpoint - current).
            dt: Elapsed time step (seconds).

        Returns:
            Control command value (e.g. degrees/second or degrees/frame).
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset internal accumulator and memory state."""
        pass

    @abstractmethod
    def set_gains(self, **kwargs):
        """Update controller tuning gains at runtime."""
        pass

    @abstractmethod
    def get_telemetry(self) -> ControllerTelemetry:
        """Return the most recent control state and term breakdown."""
        pass
