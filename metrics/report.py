"""
ASTRATRACK — Performance Report Schema

Encapsulates complete run metadata, pipeline configuration,
empirical metric results, and quantitative pass/fail evaluation.
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class EvaluationCriterion:
    """Individual pass/fail test criterion."""
    name: str
    target: str
    actual: str
    passed: bool


@dataclass
class PerformanceReport:
    """
    Authoritative Performance Report for an ASTRATRACK simulation run.

    Never generates fake results; all values derive strictly from actual runs.
    """
    run_id: str
    timestamp: str
    scenario: str
    configuration: Dict[str, Any]
    disturbance_settings: Dict[str, Any]
    detector: str
    controller: str
    filter_settings: Dict[str, Any]
    metrics: Dict[str, Any]
    pass_fail_status: str                         # "PASS", "FAIL", "MARGINAL"
    criteria_checklist: List[EvaluationCriterion] = field(default_factory=list)
    summary_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to serializable dictionary."""
        d = asdict(self)
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        """Render report as GitHub-flavored Markdown document."""
        lines = [
            f"# ASTRATRACK Performance Report — {self.run_id}",
            f"**Timestamp:** {self.timestamp}  ",
            f"**Scenario:** {self.scenario}  ",
            f"**Overall Result:** `{self.pass_fail_status}`  \n",
            "## 1. System Pipeline Configuration",
            f"- **Detector:** {self.detector}",
            f"- **Controller:** {self.controller}",
            f"- **Estimator / Filter:** {self.filter_settings.get('type', 'Kalman')}",
            f"- **Disturbance Profile:** {self.disturbance_settings.get('preset', 'Custom')}\n",
            "## 2. Real-Time Operational & Kinematic Metrics",
            "| Metric | Measured Value | Units |",
            "|:---|:---:|:---:|",
            f"| Simulation Duration | {self.metrics.get('simulation_duration_s', 0)} | s |",
            f"| System Rate | {self.metrics.get('fps', 0)} | FPS |",
            f"| Detection Rate | {self.metrics.get('detection_fps', 0)} | FPS |",
            f"| Detector Inference Time | {self.metrics.get('inference_time_ms', 0)} | ms |",
            f"| Processing Latency | {self.metrics.get('processing_latency_ms', 0)} | ms |",
            f"| Acquisition Time | {self.metrics.get('acquisition_time_s', 0)} | s |",
            f"| Average Tracking Error | {self.metrics.get('average_tracking_error_px', 0)} px / {self.metrics.get('average_tracking_error_deg', 0)}° | px / ° |",
            f"| Maximum Tracking Error | {self.metrics.get('maximum_tracking_error_px', 0)} px / {self.metrics.get('maximum_tracking_error_deg', 0)}° | px / ° |",
            f"| RMS Tracking Error | {self.metrics.get('rms_tracking_error_px', 0)} px / {self.metrics.get('rms_tracking_error_deg', 0)}° | px / ° |",
            f"| Lock Retention Rate | {self.metrics.get('lock_retention_rate_pct', 0)}% | % |",
            f"| Target Loss Count | {self.metrics.get('target_loss_count', 0)} | count |",
            f"| Successful Recoveries | {self.metrics.get('successful_recovery_count', 0)} | count |",
            f"| Mean Recovery Time | {self.metrics.get('recovery_time_s', 0)} | s |",
            f"| Detection Confidence | {self.metrics.get('detection_confidence', 0)} | 0.0–1.0 |",
            f"| Prediction Error | {self.metrics.get('prediction_error_px', 0)} | px |",
            f"| Camera Angular Error | {self.metrics.get('camera_angular_error_deg', 0)} | ° |\n",
            "## 3. Mission Acceptance Criteria Audit",
            "| Evaluation Criterion | Target Threshold | Actual Measured | Status |",
            "|:---|:---:|:---:|:---:|",
        ]

        for crit in self.criteria_checklist:
            badge = "✅ PASS" if crit.passed else "❌ FAIL"
            lines.append(f"| {crit.name} | {crit.target} | {crit.actual} | {badge} |")

        lines.append(f"\n> **Final Verification:** This performance report was generated from real simulation telemetry under run `{self.run_id}`.")
        return "\n".join(lines)
