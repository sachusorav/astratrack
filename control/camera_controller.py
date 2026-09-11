"""
ASTRATRACK — Dual-Axis Camera Controller

Coordinates pan (horizontal) and tilt (vertical) camera tracking by computing:
    target_position - camera_center
and routing the horizontal and vertical errors to the selected control architecture
(DIRECT, P, or PID).
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Dict, Optional, Any

from control.controller_base import IController, ControllerTelemetry
from control.pid import PController, PIDController, DirectController


class ControllerMode(Enum):
    """Supported tracking controller architectures."""
    DIRECT = "direct"
    P_CONTROL = "p_control"
    PID_CONTROL = "pid_control"


@dataclass
class DualAxisControlOutput:
    """Complete dual-axis control commands and real-time state telemetry."""
    pan_command: float         # Actuation command for pan axis (deg/frame or deg/s)
    tilt_command: float        # Actuation command for tilt axis (deg/frame or deg/s)
    pan_error_deg: float       # Horizontal tracking error in degrees
    tilt_error_deg: float      # Vertical tracking error in degrees
    pan_error_px: float        # Horizontal tracking error in pixels
    tilt_error_px: float       # Vertical tracking error in pixels
    pan_rate: float            # Estimated / command pan rate (deg/s)
    tilt_rate: float           # Estimated / command tilt rate (deg/s)
    mode: ControllerMode       # Active controller mode
    pan_telemetry: ControllerTelemetry
    tilt_telemetry: ControllerTelemetry


class CameraController:
    """
    Dual-axis camera pointing controller.

    Computes:
        horizontal_error = target_x - camera_center_x
        vertical_error   = target_y - camera_center_y
    and generates pan_command and tilt_command using the active controller.
    """

    def __init__(self,
                 mode: ControllerMode = ControllerMode.PID_CONTROL,
                 kp: float = 0.4,
                 ki: float = 0.01,
                 kd: float = 0.1,
                 max_angular_velocity: float = 10.0,
                 dead_zone: float = 2.0,
                 smoothing: float = 0.0,
                 deg_per_pixel: float = 0.1):
        """
        Initialize dual-axis controller.

        Args:
            mode: Initial ControllerMode (DIRECT, P_CONTROL, PID_CONTROL).
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            max_angular_velocity: Maximum output limit (deg/frame).
            dead_zone: Deadband threshold in pixels.
            smoothing: Smoothing / inertia factor [0, 0.99].
            deg_per_pixel: Scale conversion from pixels to angular degrees.
        """
        self.mode = mode
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_angular_velocity = max_angular_velocity
        self.dead_zone = dead_zone
        self.smoothing = smoothing
        self.deg_per_pixel = deg_per_pixel

        # Controllers for pan and tilt
        self.pan_controller: IController = None
        self.tilt_controller: IController = None
        self._init_controllers()

        # Measured rates
        self._prev_pan_cmd = 0.0
        self._prev_tilt_cmd = 0.0
        self._last_output: Optional[DualAxisControlOutput] = None

    def _init_controllers(self):
        """Instantiate controllers according to selected mode."""
        dead_zone_deg = self.dead_zone * self.deg_per_pixel

        if self.mode == ControllerMode.DIRECT:
            self.pan_controller = DirectController(
                gain=self.kp, output_limit=self.max_angular_velocity
            )
            self.tilt_controller = DirectController(
                gain=self.kp, output_limit=self.max_angular_velocity
            )
        elif self.mode == ControllerMode.P_CONTROL:
            self.pan_controller = PController(
                kp=self.kp,
                dead_zone=dead_zone_deg,
                output_limit=self.max_angular_velocity,
                smoothing=self.smoothing
            )
            self.tilt_controller = PController(
                kp=self.kp,
                dead_zone=dead_zone_deg,
                output_limit=self.max_angular_velocity,
                smoothing=self.smoothing
            )
        else:  # PID_CONTROL
            self.pan_controller = PIDController(
                kp=self.kp,
                ki=self.ki,
                kd=self.kd,
                dead_zone=dead_zone_deg,
                output_limit=self.max_angular_velocity,
                smoothing=self.smoothing
            )
            self.tilt_controller = PIDController(
                kp=self.kp,
                ki=self.ki,
                kd=self.kd,
                dead_zone=dead_zone_deg,
                output_limit=self.max_angular_velocity,
                smoothing=self.smoothing
            )

    def set_mode(self, mode: ControllerMode):
        """Switch controller mode (DIRECT, P_CONTROL, PID_CONTROL)."""
        if self.mode != mode:
            self.mode = mode
            self._init_controllers()

    def set_parameters(self,
                       kp: Optional[float] = None,
                       ki: Optional[float] = None,
                       kd: Optional[float] = None,
                       max_angular_velocity: Optional[float] = None,
                       dead_zone: Optional[float] = None,
                       smoothing: Optional[float] = None):
        """Update configurable parameters across both axes."""
        if kp is not None:
            self.kp = float(kp)
        if ki is not None:
            self.ki = float(ki)
        if kd is not None:
            self.kd = float(kd)
        if max_angular_velocity is not None:
            self.max_angular_velocity = float(max_angular_velocity)
        if dead_zone is not None:
            self.dead_zone = float(dead_zone)
        if smoothing is not None:
            self.smoothing = float(smoothing)

        # Update underlying controllers
        dead_zone_deg = self.dead_zone * self.deg_per_pixel
        kwargs = {
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "output_limit": self.max_angular_velocity,
            "dead_zone": dead_zone_deg,
            "smoothing": self.smoothing,
            "gain": self.kp,
        }
        self.pan_controller.set_gains(**kwargs)
        self.tilt_controller.set_gains(**kwargs)

    def compute(self,
                target_pos: Tuple[float, float],
                camera_center: Tuple[float, float],
                dt: float = 0.02) -> DualAxisControlOutput:
        """
        Compute pan and tilt tracking commands.

        Args:
            target_pos: (target_x, target_y) in FOV or world coordinates.
            camera_center: (center_x, center_y) of camera FOV.
            dt: Elapsed time step (seconds).

        Returns:
            DualAxisControlOutput with commands, errors, and rates.
        """
        # Horizontal and vertical pixel errors: target_position - camera_center
        error_x_px = target_pos[0] - camera_center[0]
        error_y_px = target_pos[1] - camera_center[1]

        # Convert to angular errors (degrees)
        error_pan_deg = error_x_px * self.deg_per_pixel
        error_tilt_deg = error_y_px * self.deg_per_pixel

        # Compute control commands
        pan_command = self.pan_controller.compute(error_pan_deg, dt)
        tilt_command = self.tilt_controller.compute(error_tilt_deg, dt)

        # Compute instantaneous rates (deg/s)
        pan_rate = pan_command / dt if dt > 0 else 0.0
        tilt_rate = tilt_command / dt if dt > 0 else 0.0

        self._prev_pan_cmd = pan_command
        self._prev_tilt_cmd = tilt_command

        output = DualAxisControlOutput(
            pan_command=pan_command,
            tilt_command=tilt_command,
            pan_error_deg=error_pan_deg,
            tilt_error_deg=error_tilt_deg,
            pan_error_px=error_x_px,
            tilt_error_px=error_y_px,
            pan_rate=pan_rate,
            tilt_rate=tilt_rate,
            mode=self.mode,
            pan_telemetry=self.pan_controller.get_telemetry(),
            tilt_telemetry=self.tilt_controller.get_telemetry()
        )
        self._last_output = output
        return output

    def reset(self):
        """Reset internal controllers and rates."""
        self.pan_controller.reset()
        self.tilt_controller.reset()
        self._prev_pan_cmd = 0.0
        self._prev_tilt_cmd = 0.0
        self._last_output = None

    @property
    def last_output(self) -> Optional[DualAxisControlOutput]:
        return self._last_output
