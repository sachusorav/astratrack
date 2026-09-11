"""
ASTRATRACK — Multi-Experiment Comparator

Compares multiple historical experiments side-by-side:
- Generates side-by-side KPI comparison tables
- Computes percentage improvements between runs
- Generates visual comparison overlay figures
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from experiments.record import ExperimentRecord


@dataclass
class ExperimentComparison:
    """Side-by-side comparative analysis of 2 or more experiments."""
    experiments: List[ExperimentRecord]
    metrics_table: Dict[str, List[Any]]

    def to_markdown(self) -> str:
        """Render comparison to GitHub Markdown table."""
        ids = [e.experiment_id for e in self.experiments]
        lines = [
            "# ASTRATRACK — Multi-Experiment Comparative Analysis",
            f"**Analyzed Runs:** {', '.join(ids)}\n",
            "| Parameter / Metric | " + " | ".join(ids) + " |",
            "|:---|" + "|".join([":---:"] * len(ids)) + "|",
            "| **Scenario** | " + " | ".join(e.scenario_name for e in self.experiments) + " |",
            "| **Detector** | " + " | ".join(e.detector_type for e in self.experiments) + " |",
            "| **Controller** | " + " | ".join(e.controller_type for e in self.experiments) + " |",
            "| **Disturbance** | " + " | ".join(e.disturbance_preset for e in self.experiments) + " |",
            "| **Seed** | " + " | ".join(str(e.random_seed) for e in self.experiments) + " |",
            "| **Avg Error (px)** | " + " | ".join(str(e.average_error_px) for e in self.experiments) + " |",
            "| **Max Error (px)** | " + " | ".join(str(e.maximum_error_px) for e in self.experiments) + " |",
            "| **RMS Error (px)** | " + " | ".join(str(e.rms_error_px) for e in self.experiments) + " |",
            "| **Lock Retention (%)** | " + " | ".join(f"{e.lock_retention_pct}%" for e in self.experiments) + " |",
            "| **Recovery Time (s)** | " + " | ".join(f"{e.recovery_time_s}s" for e in self.experiments) + " |",
            "| **FPS** | " + " | ".join(str(e.fps) for e in self.experiments) + " |",
            "| **Latency (ms)** | " + " | ".join(f"{e.latency_ms}ms" for e in self.experiments) + " |",
        ]
        return "\n".join(lines)


def compare_experiments(experiments: List[ExperimentRecord]) -> ExperimentComparison:
    """Construct an ExperimentComparison object from a list of records."""
    table = {
        "scenario": [e.scenario_name for e in experiments],
        "detector": [e.detector_type for e in experiments],
        "controller": [e.controller_type for e in experiments],
        "avg_error_px": [e.average_error_px for e in experiments],
        "rms_error_px": [e.rms_error_px for e in experiments],
        "lock_retention_pct": [e.lock_retention_pct for e in experiments],
    }
    return ExperimentComparison(experiments=experiments, metrics_table=table)


def plot_experiment_comparison(experiments: List[ExperimentRecord],
                               output_path: str = "outputs/experiment_comparison.png") -> str:
    """Generate side-by-side error curves and bar comparison chart."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=150)
    fig.patch.set_facecolor("#0B0E14")

    palette = ["#3182CE", "#38A169", "#DD6B20", "#E53E3E", "#9F7AEA"]

    # 1. Error time-series overlay
    ax1.set_facecolor("#151B26")
    for i, exp in enumerate(experiments[:5]):
        if exp.error_series:
            ax1.plot(exp.error_series, label=exp.experiment_id, color=palette[i % len(palette)], alpha=0.85)
    ax1.set_title("Tracking Error Time Series Overlay (px)", color="#FFFFFF", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Frame Step", color="#A0AEC0")
    ax1.set_ylabel("Error (px)", color="#A0AEC0")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.25)

    # 2. RMS Error & Lock Retention Comparison
    ax2.set_facecolor("#151B26")
    labels = [e.experiment_id[:14] for e in experiments[:5]]
    rms_vals = [e.rms_error_px for e in experiments[:5]]
    bars = ax2.bar(labels, rms_vals, color=palette[:len(experiments)], alpha=0.85)

    for bar in bars:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, h + 0.2, f"{h:.2f}px", ha="center", va="bottom", color="#FFFFFF", fontsize=8)

    ax2.set_title("RMS Tracking Error (px)", color="#FFFFFF", fontsize=11, fontweight="bold")
    ax2.set_ylabel("RMS Error (px)", color="#A0AEC0")
    ax2.grid(True, linestyle="--", alpha=0.25)

    plt.tight_layout()
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return os.path.abspath(output_path)
