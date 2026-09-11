"""
ASTRATRACK — Performance Evaluator

Audits measured metrics against quantitative mission criteria
to determine PASS, MARGINAL, or FAIL status.
"""

from typing import Dict, Any, List, Tuple
from metrics.report import EvaluationCriterion


class PerformanceEvaluator:
    """Evaluates simulation metrics against mission criteria."""

    def __init__(self,
                 max_rms_error_px: float = 15.0,
                 max_error_px: float = 40.0,
                 min_lock_retention_pct: float = 85.0,
                 max_acquisition_time_s: float = 2.5,
                 max_recovery_time_s: float = 2.0,
                 min_fps: float = 30.0,
                 max_latency_ms: float = 35.0):
        self.max_rms_error_px = max_rms_error_px
        self.max_error_px = max_error_px
        self.min_lock_retention_pct = min_lock_retention_pct
        self.max_acquisition_time_s = max_acquisition_time_s
        self.max_recovery_time_s = max_recovery_time_s
        self.min_fps = min_fps
        self.max_latency_ms = max_latency_ms

    def evaluate(self, metrics: Dict[str, Any]) -> Tuple[str, List[EvaluationCriterion]]:
        """
        Evaluate metrics against acceptance criteria.

        Returns:
            (status, criteria_checklist) where status is 'PASS', 'MARGINAL', or 'FAIL'.
        """
        checklist = []
        failed_count = 0

        # 1. Lock Retention
        actual_lock = metrics.get("lock_retention_rate_pct", 0.0)
        p_lock = actual_lock >= self.min_lock_retention_pct
        if not p_lock:
            failed_count += 1
        checklist.append(EvaluationCriterion(
            name="Lock Retention Rate",
            target=f">= {self.min_lock_retention_pct:.1f}%",
            actual=f"{actual_lock:.1f}%",
            passed=p_lock
        ))

        # 2. RMS Tracking Error
        actual_rms = metrics.get("rms_tracking_error_px", 0.0)
        p_rms = actual_rms <= self.max_rms_error_px
        if not p_rms:
            failed_count += 1
        checklist.append(EvaluationCriterion(
            name="RMS Tracking Error",
            target=f"<= {self.max_rms_error_px:.1f} px",
            actual=f"{actual_rms:.2f} px",
            passed=p_rms
        ))

        # 3. Maximum Peak Error
        actual_max = metrics.get("maximum_tracking_error_px", 0.0)
        p_max = actual_max <= self.max_error_px
        if not p_max:
            failed_count += 1
        checklist.append(EvaluationCriterion(
            name="Maximum Tracking Error",
            target=f"<= {self.max_error_px:.1f} px",
            actual=f"{actual_max:.2f} px",
            passed=p_max
        ))

        # 4. Processing Latency
        actual_lat = metrics.get("processing_latency_ms", 0.0)
        p_lat = actual_lat <= self.max_latency_ms
        if not p_lat:
            failed_count += 1
        checklist.append(EvaluationCriterion(
            name="Processing Pipeline Latency",
            target=f"<= {self.max_latency_ms:.1f} ms",
            actual=f"{actual_lat:.2f} ms",
            passed=p_lat
        ))

        # 5. Recovery Time
        actual_rec = metrics.get("recovery_time_s", 0.0)
        p_rec = (actual_rec <= self.max_recovery_time_s) or (actual_rec == 0.0)
        if not p_rec:
            failed_count += 1
        checklist.append(EvaluationCriterion(
            name="Mean Re-Acquisition Time",
            target=f"<= {self.max_recovery_time_s:.2f} s",
            actual=f"{actual_rec:.2f} s",
            passed=p_rec
        ))

        if failed_count == 0:
            status = "PASS"
        elif failed_count == 1:
            status = "MARGINAL"
        else:
            status = "FAIL"

        return status, checklist
