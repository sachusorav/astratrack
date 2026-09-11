"""
ASTRATRACK — Custom Scenario Builder

Allows engineers and evaluators to interactively construct, validate,
serialize, and deserialize custom aerospace tracking mission profiles.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional

from scenarios.definitions import ScenarioDefinition


class CustomScenarioBuilder:
    """Builder for custom ASTRATRACK scenarios."""

    def __init__(self, scenario_id: str = "CUSTOM-01", name: str = "Custom Scenario"):
        self.scenario_id = scenario_id
        self.name = name
        self.difficulty = "CUSTOM"
        self.description = "User-configured custom aerospace tracking mission."
        self.expected_challenge = "Custom evaluation criteria."

        # Defaults
        self.target_config: Dict[str, Any] = {
            "motion_model": "sinusoidal",
            "speed": 120.0,
            "radius": 12,
        }
        self.camera_config: Dict[str, Any] = {
            "fov_width": 640,
            "fov_height": 480,
            "max_slew_rate": 8.0,
            "inertia": 0.85,
        }
        self.disturbance_config: Dict[str, Any] = {
            "preset": "NORMAL",
            "channels": {},
        }
        self.evaluation_criteria: Dict[str, Any] = {
            "min_lock_retention_pct": 85.0,
            "max_rms_error_px": 12.0,
            "max_recovery_time_s": 2.0,
        }

    def set_target(self, motion_model: str = "sinusoidal", speed: float = 120.0, radius: int = 12):
        self.target_config["motion_model"] = motion_model
        self.target_config["speed"] = float(speed)
        self.target_config["radius"] = int(radius)
        return self

    def set_camera(self, fov_width: int = 640, fov_height: int = 480,
                   max_slew_rate: float = 8.0, inertia: float = 0.85):
        self.camera_config["fov_width"] = int(fov_width)
        self.camera_config["fov_height"] = int(fov_height)
        self.camera_config["max_slew_rate"] = float(max_slew_rate)
        self.camera_config["inertia"] = float(inertia)
        return self

    def set_disturbance_preset(self, preset_name: str):
        self.disturbance_config["preset"] = preset_name
        return self

    def configure_channel(self, channel_name: str, enabled: bool, intensity: float,
                          frequency: float = 1.0, duration: float = float("inf"),
                          start_delay: float = 0.0):
        if "channels" not in self.disturbance_config:
            self.disturbance_config["channels"] = {}
        self.disturbance_config["channels"][channel_name] = {
            "enabled": bool(enabled),
            "intensity": float(intensity),
            "frequency": float(frequency),
            "duration": float(duration),
            "start_delay": float(start_delay),
        }
        return self

    def set_evaluation_criteria(self, min_lock_retention_pct: float = 85.0,
                                max_rms_error_px: float = 12.0,
                                max_recovery_time_s: float = 2.0):
        self.evaluation_criteria["min_lock_retention_pct"] = float(min_lock_retention_pct)
        self.evaluation_criteria["max_rms_error_px"] = float(max_rms_error_px)
        self.evaluation_criteria["max_recovery_time_s"] = float(max_recovery_time_s)
        return self

    def build(self) -> ScenarioDefinition:
        """Validate and construct ScenarioDefinition."""
        return ScenarioDefinition(
            id=self.scenario_id,
            name=self.name,
            difficulty=self.difficulty,
            description=self.description,
            expected_challenge=self.expected_challenge,
            target_config=self.target_config.copy(),
            camera_config=self.camera_config.copy(),
            disturbance_config=self.disturbance_config.copy(),
            evaluation_criteria=self.evaluation_criteria.copy(),
        )

    def save_to_yaml(self, filepath: str) -> str:
        """Save custom scenario definition to YAML file."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        data = {
            "id": self.scenario_id,
            "name": self.name,
            "difficulty": self.difficulty,
            "description": self.description,
            "expected_challenge": self.expected_challenge,
            "target": self.target_config,
            "camera": self.camera_config,
            "disturbances": self.disturbance_config,
            "evaluation": self.evaluation_criteria,
        }
        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return filepath

    @classmethod
    def load_from_yaml(cls, filepath: str) -> ScenarioDefinition:
        """Load scenario from YAML file and construct ScenarioDefinition."""
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        builder = cls(scenario_id=str(data.get("id", "CUSTOM")), name=data.get("name", "Custom"))
        builder.difficulty = data.get("difficulty", "CUSTOM")
        builder.description = data.get("description", "")
        builder.expected_challenge = data.get("expected_challenge", "")
        builder.target_config = data.get("target", builder.target_config)
        builder.camera_config = data.get("camera", builder.camera_config)
        builder.disturbance_config = data.get("disturbances", builder.disturbance_config)
        builder.evaluation_criteria = data.get("evaluation", builder.evaluation_criteria)
        return builder.build()
