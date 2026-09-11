"""
ASTRATRACK — Tracking Controllers

Implements:
1. PController — Proportional control with dead zone, rate limiting, and smoothing.
2. PIDController — Full PID with anti-windup, derivative filtering, dead zone, and smoothing.
3. DirectController — Unfiltered direct open-loop displacement for benchmark comparison.
"""

from typing import Optional, Dict, Any
from core.math_utils import clamp
from control.controller_base import IController, ControllerTelemetry


class PController(IController):
    """
    Proportional Controller with:
    - Configurable Kp
    - Dead zone suppression
    - Maximum angular velocity clamping
    - Output smoothing filter
    """

    def __init__(self, kp: float = 0.4, dead_zone: float = 2.0,
                 output_limit: float = 10.0, smoothing: float = 0.0):
        """
        Args:
            kp: Proportional gain.
            dead_zone: Error threshold below which control output is zero.
            output_limit: Maximum command magnitude (rate clamping).
            smoothing: Exponential smoothing factor (0.0=instant, 0.9=heavy lag).
        """
        self.kp = float(kp)
        self.dead_zone = float(dead_zone)
        self.output_limit = float(output_limit)
        self.smoothing = float(clamp(smoothing, 0.0, 0.99))

        self._prev_output = 0.0
        self._last_error = 0.0
        self._last_telemetry = ControllerTelemetry(control_output=0.0, error=0.0)

    def compute(self, error: float, dt: float = 1.0) -> float:
        self._last_error = error

        # 1. Dead zone check
        if abs(error) < self.dead_zone:
            self._last_telemetry = ControllerTelemetry(
                control_output=0.0, error=error, p_term=0.0, in_deadzone=True
            )
            self._prev_output = 0.0
            return 0.0

        # 2. Proportional computation
        p_term = self.kp * error

        # 3. Output clamping
        raw_output = clamp(p_term, -self.output_limit, self.output_limit)
        is_saturated = abs(p_term) > self.output_limit

        # 4. Smoothing filter: output = alpha * prev + (1 - alpha) * raw
        if self.smoothing > 0.0:
            smoothed = self.smoothing * self._prev_output + (1.0 - self.smoothing) * raw_output
        else:
            smoothed = raw_output

        self._prev_output = smoothed
        self._last_telemetry = ControllerTelemetry(
            control_output=smoothed,
            error=error,
            p_term=p_term,
            is_saturated=is_saturated,
            in_deadzone=False
        )
        return smoothed

    def reset(self):
        self._prev_output = 0.0
        self._last_error = 0.0
        self._last_telemetry = ControllerTelemetry(control_output=0.0, error=0.0)

    def set_gains(self, kp: Optional[float] = None, dead_zone: Optional[float] = None,
                  output_limit: Optional[float] = None, smoothing: Optional[float] = None, **kwargs):
        if kp is not None:
            self.kp = float(kp)
        if dead_zone is not None:
            self.dead_zone = float(dead_zone)
        if output_limit is not None:
            self.output_limit = float(output_limit)
        if smoothing is not None:
            self.smoothing = float(clamp(smoothing, 0.0, 0.99))

    def get_telemetry(self) -> ControllerTelemetry:
        return self._last_telemetry


class PIDController(IController):
    """
    Discrete PID Controller with:
    - Anti-windup (integral clamping)
    - Derivative low-pass filtering to attenuate sensor noise
    - Dead zone with graceful integral bleeding
    - Configurable maximum angular velocity clamping
    - Actuation smoothing filter
    """

    def __init__(self, kp: float = 0.4, ki: float = 0.01, kd: float = 0.1,
                 integral_limit: float = 100.0, dead_zone: float = 2.0,
                 output_limit: float = 10.0, derivative_filter: float = 0.7,
                 smoothing: float = 0.0):
        """
        Args:
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            integral_limit: Maximum magnitude of integral accumulator (anti-windup).
            dead_zone: Error threshold below which control output is zero.
            output_limit: Maximum absolute command value.
            derivative_filter: Low-pass filter coefficient for derivative term (0-1).
            smoothing: Actuator output smoothing factor (0-0.99).
        """
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.integral_limit = float(integral_limit)
        self.dead_zone = float(dead_zone)
        self.output_limit = float(output_limit)
        self.derivative_filter = float(clamp(derivative_filter, 0.0, 0.99))
        self.smoothing = float(clamp(smoothing, 0.0, 0.99))

        # Internal state
        self._integral = 0.0
        self._prev_error = 0.0
        self._filtered_derivative = 0.0
        self._prev_output = 0.0
        self._last_telemetry = ControllerTelemetry(control_output=0.0, error=0.0)

    def compute(self, error: float, dt: float = 1.0) -> float:
        # Dead zone
        if abs(error) < self.dead_zone:
            # Gracefully decay integral to prevent buildup
            self._integral *= 0.95
            self._prev_error = error
            self._last_telemetry = ControllerTelemetry(
                control_output=0.0, error=error, in_deadzone=True
            )
            self._prev_output = 0.0
            return 0.0

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup clamping
        effective_dt = dt if dt > 0 else 0.02
        self._integral += error * effective_dt
        self._integral = clamp(self._integral, -self.integral_limit, self.integral_limit)
        i_term = self.ki * self._integral

        # Derivative term with low-pass noise filter
        raw_derivative = (error - self._prev_error) / effective_dt if effective_dt > 0 else 0.0
        self._filtered_derivative = (
            self.derivative_filter * self._filtered_derivative +
            (1.0 - self.derivative_filter) * raw_derivative
        )
        d_term = self.kd * self._filtered_derivative
        self._prev_error = error

        # Raw output and saturation check
        raw_output = p_term + i_term + d_term
        clamped_output = clamp(raw_output, -self.output_limit, self.output_limit)
        is_saturated = abs(raw_output) > self.output_limit

        # Actuation smoothing
        if self.smoothing > 0.0:
            smoothed = self.smoothing * self._prev_output + (1.0 - self.smoothing) * clamped_output
        else:
            smoothed = clamped_output

        self._prev_output = smoothed
        self._last_telemetry = ControllerTelemetry(
            control_output=smoothed,
            error=error,
            p_term=p_term,
            i_term=i_term,
            d_term=d_term,
            is_saturated=is_saturated,
            in_deadzone=False
        )
        return smoothed

    def reset(self):
        """Reset internal accumulator, previous error, and derivative."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._filtered_derivative = 0.0
        self._prev_output = 0.0
        self._last_telemetry = ControllerTelemetry(control_output=0.0, error=0.0)

    def set_gains(self, kp: Optional[float] = None, ki: Optional[float] = None,
                  kd: Optional[float] = None, dead_zone: Optional[float] = None,
                  output_limit: Optional[float] = None, smoothing: Optional[float] = None,
                  integral_limit: Optional[float] = None, **kwargs):
        """Update gains at runtime."""
        if kp is not None:
            self.kp = float(kp)
        if ki is not None:
            self.ki = float(ki)
        if kd is not None:
            self.kd = float(kd)
        if dead_zone is not None:
            self.dead_zone = float(dead_zone)
        if output_limit is not None:
            self.output_limit = float(output_limit)
        if smoothing is not None:
            self.smoothing = float(clamp(smoothing, 0.0, 0.99))
        if integral_limit is not None:
            self.integral_limit = float(integral_limit)

    def get_telemetry(self) -> ControllerTelemetry:
        return self._last_telemetry


class DirectController(IController):
    """
    Direct / Open-Loop Tracking:
    Directly maps error to displacement command without integral accumulation,
    derivative damping, or smoothing. Demonstrates hunting and oscillation.
    """

    def __init__(self, gain: float = 1.0, output_limit: float = 30.0):
        self.gain = float(gain)
        self.output_limit = float(output_limit)
        self._last_telemetry = ControllerTelemetry(control_output=0.0, error=0.0)

    def compute(self, error: float, dt: float = 1.0) -> float:
        raw_output = self.gain * error
        clamped_output = clamp(raw_output, -self.output_limit, self.output_limit)
        self._last_telemetry = ControllerTelemetry(
            control_output=clamped_output,
            error=error,
            p_term=raw_output,
            is_saturated=abs(raw_output) > self.output_limit,
            in_deadzone=False
        )
        return clamped_output

    def reset(self):
        self._last_telemetry = ControllerTelemetry(control_output=0.0, error=0.0)

    def set_gains(self, gain: Optional[float] = None, output_limit: Optional[float] = None, **kwargs):
        if gain is not None:
            self.gain = float(gain)
        if output_limit is not None:
            self.output_limit = float(output_limit)

    def get_telemetry(self) -> ControllerTelemetry:
        return self._last_telemetry
