"""
ASTRATRACK — Documentation Real Empirical Data Collector

Executes actual simulation benchmarks and multi-scenario experiments to collect
real, un-faked performance measurements for automatic documentation generation.
Strictly adheres to:
- Never generate fake results.
- All displayed results must come from actual simulation runs.
"""

import os
import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.config import AppConfig
from lab.runner import AlgorithmComparisonLab, ComparisonReport, ModeBenchmarkResult
from experiments.manager import ExperimentManager
from experiments.record import ExperimentRecord


@dataclass
class ScenarioEmpiricalData:
    """Real measured results for a single scenario."""
    scenario_id: str
    scenario_name: str
    fps: float
    avg_error_px: float
    max_error_px: float
    rms_error_px: float
    acquisition_time_s: float
    lock_retention_pct: float
    recovery_time_s: float
    latency_ms: float
    status: str


class EmpiricalDataCollector:
    """
    Executes actual simulation benchmarks to collect verified empirical performance data.
    Caches results to avoid redundant long-running re-simulations within the same run.
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.comparison_lab = AlgorithmComparisonLab(self.config)
        self.experiment_manager = ExperimentManager("experiments_store")
        self._cached_baseline_benchmark: Optional[ComparisonReport] = None
        self._cached_stress_benchmark: Optional[ComparisonReport] = None
        self._cached_scenario_matrix: Optional[List[ScenarioEmpiricalData]] = None
        self._cached_reproducibility: Optional[Dict[str, Any]] = None

    def get_baseline_comparison(self, frames: int = 120, seed: int = 42) -> ComparisonReport:
        """
        Executes Mode A, B, C, D on Scenario 01 (Baseline) with a fixed seed.
        Returns actual measured comparison results.
        """
        if self._cached_baseline_benchmark is None:
            self._cached_baseline_benchmark = self.comparison_lab.run_benchmark(
                scenario_id="01",
                frames=frames,
                seed=seed
            )
        return self._cached_baseline_benchmark

    def get_stress_comparison(self, frames: int = 120, seed: int = 42) -> ComparisonReport:
        """
        Executes Mode A, B, C, D on Scenario 09 (Combined Disturbance) with a fixed seed.
        Returns actual measured comparison results.
        """
        if self._cached_stress_benchmark is None:
            self._cached_stress_benchmark = self.comparison_lab.run_benchmark(
                scenario_id="09",
                frames=frames,
                seed=seed
            )
        return self._cached_stress_benchmark

    def get_scenario_matrix(self, frames_per_scenario: int = 100, seed: int = 42) -> List[ScenarioEmpiricalData]:
        """
        Runs Mode D (Full Pipeline) across multiple standard scenarios to build
        an empirical performance audit across diverse operational conditions.
        """
        if self._cached_scenario_matrix is not None:
            return self._cached_scenario_matrix

        target_scenarios = [
            ("01", "01 — Baseline Coarse Alignment"),
            ("02", "02 — High Speed Target"),
            ("04", "04 — Camera Vibration"),
            ("07", "07 — Temporary Occlusion"),
            ("09", "09 — Combined Disturbance"),
            ("10", "10 — Extreme Stress Test"),
        ]

        results: List[ScenarioEmpiricalData] = []
        for scen_id, scen_name in target_scenarios:
            rec = self.experiment_manager.run_experiment(
                scenario_id=scen_id,
                detector_type="classical",
                controller_type="PID",
                estimator_type="Kalman-CA",
                duration_frames=frames_per_scenario,
                random_seed=seed
            )
            status = "PASS" if rec.lock_retention_pct >= 75.0 and rec.rms_error_px <= 25.0 else (
                "MARGINAL" if rec.lock_retention_pct >= 50.0 else "FAIL"
            )
            results.append(ScenarioEmpiricalData(
                scenario_id=scen_id,
                scenario_name=scen_name,
                fps=rec.fps,
                avg_error_px=rec.average_error_px,
                max_error_px=rec.maximum_error_px,
                rms_error_px=rec.rms_error_px,
                acquisition_time_s=rec.acquisition_time_s,
                lock_retention_pct=rec.lock_retention_pct,
                recovery_time_s=rec.recovery_time_s,
                latency_ms=rec.latency_ms,
                status=status
            ))

        self._cached_scenario_matrix = results
        return results

    def get_reproducibility_verification(self, frames: int = 80, seed: int = 1337) -> Dict[str, Any]:
        """
        Verifies exact reproducibility by running Scenario 01 twice with identical seed.
        Proves delta is bit-exact zero.
        """
        if self._cached_reproducibility is not None:
            return self._cached_reproducibility

        rec1 = self.experiment_manager.run_experiment(
            scenario_id="01",
            duration_frames=frames,
            random_seed=seed,
            experiment_id_override="REPRO-TRIAL-1"
        )
        rec2 = self.experiment_manager.run_experiment(
            scenario_id="01",
            duration_frames=frames,
            random_seed=seed,
            experiment_id_override="REPRO-TRIAL-2"
        )

        delta_avg = abs(rec1.average_error_px - rec2.average_error_px)
        delta_max = abs(rec1.maximum_error_px - rec2.maximum_error_px)
        delta_rms = abs(rec1.rms_error_px - rec2.rms_error_px)
        delta_lock = abs(rec1.lock_retention_pct - rec2.lock_retention_pct)

        self._cached_reproducibility = {
            "trial_1": rec1,
            "trial_2": rec2,
            "delta_avg_error_px": delta_avg,
            "delta_max_error_px": delta_max,
            "delta_rms_error_px": delta_rms,
            "delta_lock_retention_pct": delta_lock,
            "is_bit_exact": (delta_avg == 0.0 and delta_max == 0.0 and delta_rms == 0.0 and delta_lock == 0.0)
        }
        return self._cached_reproducibility
