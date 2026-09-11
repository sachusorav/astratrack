"""
ASTRATRACK — 3D FSOC Simulation Engine

Coordinates the target kinematics, tracking camera gimbal control loop,
disturbance perturbations, and metrics calculation in 3D space.

Supports:
- Deterministic mode (fixed seed & fixed time step)
- Real-time interactive mode
- Multi-scenario switching
- Full telemetry logging
"""

import time
import math
import numpy as np
from typing import Dict, List, Optional

from simulator.target3d import Target3D, TargetConfig
from simulator.camera3d import TrackingCamera3D, CameraConfig3D
from simulator.scenarios import Scenario, get_scenario_stationary, get_scenario_by_id_or_key
from simulator.renderer import Renderer3D


class Simulation3D:
    """
    Main 3D simulation coordinator for ASTRATRACK.

    Integrates:
    - Target trajectory kinematics
    - Pan/tilt tracking camera
    - Disturbance injection
    - Lock detection and metrics
    - Visual rendering pipeline
    """

    def __init__(self, scenario: Optional[Scenario] = None,
                 width: int = 1280, height: int = 720,
                 deterministic: bool = False,
                 fixed_dt: float = 0.02):
        self.width = width
        self.height = height
        self.deterministic = deterministic
        self.fixed_dt = fixed_dt

        # Active scenario
        self.scenario: Scenario = scenario or get_scenario_stationary()

        # Components
        self.target: Target3D = None
        self.camera: TrackingCamera3D = None
        self.renderer: Renderer3D = Renderer3D(width=width, height=height)

        # Simulation state
        self.is_paused: bool = False
        self.sim_time: float = 0.0
        self.step_count: int = 0
        self.fps: float = 0.0

        # Metrics accumulators
        self._locked_steps: int = 0
        self._error_history: List[float] = []
        self._last_wall_time: float = time.perf_counter()

        # Initialize scenario
        self.reset()

    # ------------------------------------------------------------------ #
    # Lifecycle & Scenario Control
    # ------------------------------------------------------------------ #

    def load_scenario(self, scenario_or_key):
        """Switch active scenario by Scenario instance or key ('1'-'6')."""
        if isinstance(scenario_or_key, Scenario):
            self.scenario = scenario_or_key
        else:
            scen = get_scenario_by_id_or_key(str(scenario_or_key))
            if scen:
                self.scenario = scen
            else:
                return False
        self.reset()
        return True

    def reset(self):
        """Reset the simulation back to t=0 with the active scenario."""
        target_cfg = self.scenario.target_config
        cam_cfg = self.scenario.camera_config

        # Deterministic seed override if requested
        if self.deterministic and target_cfg.random_seed is None:
            target_cfg.random_seed = 42

        self.target = Target3D(target_cfg)
        self.camera = TrackingCamera3D(cam_cfg)

        self.sim_time = 0.0
        self.step_count = 0
        self._locked_steps = 0
        self._error_history.clear()
        self._last_wall_time = time.perf_counter()

    def set_deterministic(self, enable: bool, seed: Optional[int] = 42):
        """Toggle deterministic simulation mode."""
        self.deterministic = enable
        if enable:
            self.scenario.target_config.random_seed = seed
        else:
            self.scenario.target_config.random_seed = None
        self.reset()

    def toggle_pause(self):
        """Toggle simulation pause state."""
        self.is_paused = not self.is_paused

    # ------------------------------------------------------------------ #
    # Stepping & Physics
    # ------------------------------------------------------------------ #

    def step(self, dt: Optional[float] = None):
        """
        Advance the simulation state by one time-step.

        Args:
            dt: Optional time delta. If None, uses fixed_dt or wall time.
        """
        if self.is_paused:
            return

        now = time.perf_counter()
        if dt is None:
            if self.deterministic:
                dt = self.fixed_dt
            else:
                wall_dt = now - self._last_wall_time
                dt = min(0.1, max(0.001, wall_dt))  # Clamp dt

        # FPS calculation
        if now > self._last_wall_time:
            instant_fps = 1.0 / max(1e-5, (now - self._last_wall_time))
            self.fps = 0.9 * self.fps + 0.1 * instant_fps
        self._last_wall_time = now

        # 1. Update Target Kinematics
        self.target.update(dt)

        # 2. Update Ground Tracking Camera
        self.camera.update(dt, self.target.position, target_visible=self.target.visible)

        # 3. Accumulate tracking metrics
        self.sim_time += dt
        self.step_count += 1
        if self.camera.is_locked:
            self._locked_steps += 1
        self._error_history.append(self.camera.angular_error_deg)
        if len(self._error_history) > 1000:
            self._error_history.pop(0)

    # ------------------------------------------------------------------ #
    # Rendering & Telemetry
    # ------------------------------------------------------------------ #

    def render(self) -> np.ndarray:
        """Render the current simulation state to an image frame."""
        telem = self.get_telemetry()
        return self.renderer.render(self.target, self.camera, telem)

    def get_telemetry(self) -> Dict:
        """Return real-time telemetry and tracking metrics."""
        lock_fraction = (self._locked_steps / max(1, self.step_count))
        mean_err = float(np.mean(self._error_history)) if self._error_history else 0.0
        slant_range = float(np.linalg.norm(self.target.position - self.camera.position))

        # Optical link budget estimation (Friis-like optical attenuation)
        # Higher distance = lower SNR, turbulence noise increases jitter
        base_snr = 30.0 - 5.0 * math.log10(max(1.0, slant_range / 300.0))
        if not self.target.visible:
            base_snr = 0.0

        return {
            "sim_time": self.sim_time,
            "step_count": self.step_count,
            "fps": self.fps,
            "mode": "Deterministic" if self.deterministic else "Real-Time",
            "scenario_id": self.scenario.id,
            "scenario_name": self.scenario.name,
            "target_pos": self.target.position.copy(),
            "target_vel": self.target.velocity.copy(),
            "camera_pan": self.camera.pan_deg,
            "camera_tilt": self.camera.tilt_deg,
            "angular_error_deg": self.camera.angular_error_deg,
            "mean_error_deg": mean_err,
            "is_locked": self.camera.is_locked,
            "lock_fraction": lock_fraction,
            "slant_range_m": slant_range,
            "snr_db": max(0.0, base_snr),
            "is_paused": self.is_paused,
        }
