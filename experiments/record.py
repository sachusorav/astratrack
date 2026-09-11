"""
ASTRATRACK — Experiment Record Schema

Encapsulates complete experiment provenance, pipeline configuration,
and measured empirical results for scientific reproducibility.
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class ExperimentRecord:
    """Complete provenance and measured results for an experiment."""
    experiment_id: str
    created_at: str
    scenario_id: str
    scenario_name: str
    detector_type: str
    tracker_type: str
    estimator_type: str
    controller_type: str
    controller_gains: Dict[str, float]
    disturbance_preset: str
    disturbance_params: Dict[str, Any]
    random_seed: int
    duration_seconds: float
    frame_count: int

    # Results (strictly measured from actual simulation runs)
    fps: float
    average_error_px: float
    maximum_error_px: float
    rms_error_px: float
    acquisition_time_s: float
    lock_retention_pct: float
    recovery_time_s: float
    latency_ms: float

    # Optional time-series data for detailed comparison plots
    error_series: List[float] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExperimentRecord":
        return cls(**d)

    @classmethod
    def from_json(cls, json_str: str) -> "ExperimentRecord":
        return cls.from_dict(json.loads(json_str))
