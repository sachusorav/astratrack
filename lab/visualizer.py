"""
ASTRATRACK — Algorithm Comparison Chart Visualizer

Renders a 4-panel visual comparison chart using Matplotlib:
1. Tracking Error vs Time (Overlay of all 4 modes)
2. Average & Maximum Error Bar Chart
3. Lock Retention Rate Bar Chart
4. Latency vs FPS Tradeoff Chart
"""

import os
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional

from lab.runner import ComparisonReport


def generate_comparison_chart(report: ComparisonReport,
                              output_path: str = "outputs/benchmark_comparison_chart.png") -> str:
    """
    Generate high-resolution visual performance comparison chart.

    Args:
        report: ComparisonReport containing real measured results for Modes A-D.
        output_path: Target PNG filepath.

    Returns:
        Absolute filepath to saved image.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Set dark aerospace styling
    plt.style.use("dark_background")
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 9), dpi=150)
    fig.patch.set_facecolor("#0B0E14")

    modes = list(report.mode_results.keys())
    short_labels = ["Mode A\n(Direct)", "Mode B\n(AI+PID)", "Mode C\n(Kalman)", "Mode D\n(Full PAT)"]
    palette = ["#E53E3E", "#DD6B20", "#3182CE", "#38A169"]

    # ------------------------------------------------------------------ #
    # 1. Error vs Time Series Overlay
    # ------------------------------------------------------------------ #
    ax1.set_facecolor("#151B26")
    for i, mode_name in enumerate(modes):
        series = report.mode_results[mode_name].error_time_series
        steps = range(len(series))
        ax1.plot(steps, series, label=short_labels[i].replace('\n', ' '),
                 color=palette[i], linewidth=1.8, alpha=0.85)

    ax1.set_title("Tracking Error vs Frame Time (px)", color="#E2E8F0", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Simulation Frame", color="#A0AEC0", fontsize=9)
    ax1.set_ylabel("Boresight Error (px)", color="#A0AEC0", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.25, color="#718096")
    ax1.legend(loc="upper right", framealpha=0.6, fontsize=8)

    # ------------------------------------------------------------------ #
    # 2. Average & Maximum Error Bar Chart
    # ------------------------------------------------------------------ #
    ax2.set_facecolor("#151B26")
    x = np.arange(len(modes))
    width = 0.35

    avg_errs = [report.mode_results[m].average_error_px for m in modes]
    max_errs = [report.mode_results[m].maximum_error_px for m in modes]

    bars1 = ax2.bar(x - width/2, avg_errs, width, label="Avg Error (px)", color="#4FD1C5", alpha=0.85)
    bars2 = ax2.bar(x + width/2, max_errs, width, label="Max Error (px)", color="#F6AD55", alpha=0.85)

    ax2.set_title("Error Comparison (Lower is Better)", color="#E2E8F0", fontsize=11, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(short_labels, color="#CBD5E0", fontsize=9)
    ax2.set_ylabel("Pixels", color="#A0AEC0", fontsize=9)
    ax2.grid(True, linestyle="--", alpha=0.25, color="#718096")
    ax2.legend(loc="upper right", framealpha=0.6, fontsize=8)

    # ------------------------------------------------------------------ #
    # 3. Lock Retention Rate Bar Chart
    # ------------------------------------------------------------------ #
    ax3.set_facecolor("#151B26")
    lock_rates = [report.mode_results[m].lock_retention_pct for m in modes]
    bars3 = ax3.bar(short_labels, lock_rates, color=palette, width=0.5, alpha=0.85)

    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f"{yval:.1f}%",
                 ha="center", va="bottom", color="#FFFFFF", fontsize=9, fontweight="bold")

    ax3.set_title("Lock Retention Rate % (Higher is Better)", color="#E2E8F0", fontsize=11, fontweight="bold")
    ax3.set_ylabel("Retention (%)", color="#A0AEC0", fontsize=9)
    ax3.set_ylim(0, 115)
    ax3.grid(True, linestyle="--", alpha=0.25, color="#718096")

    # ------------------------------------------------------------------ #
    # 4. Latency vs FPS Tradeoff
    # ------------------------------------------------------------------ #
    ax4.set_facecolor("#151B26")
    fps_vals = [report.mode_results[m].fps for m in modes]
    lat_vals = [report.mode_results[m].latency_ms for m in modes]

    ax4.scatter(lat_vals, fps_vals, color=palette, s=160, edgecolors="#FFFFFF", linewidth=1.5, zorder=5)
    for i, txt in enumerate(short_labels):
        ax4.annotate(txt.replace('\n', ' '), (lat_vals[i] + 0.3, fps_vals[i] + 1.0),
                     color="#E2E8F0", fontsize=8.5, fontweight="bold")

    ax4.set_title("System Rate vs Latency Tradeoff", color="#E2E8F0", fontsize=11, fontweight="bold")
    ax4.set_xlabel("Processing Latency (ms)", color="#A0AEC0", fontsize=9)
    ax4.set_ylabel("Frame Rate (FPS)", color="#A0AEC0", fontsize=9)
    ax4.grid(True, linestyle="--", alpha=0.25, color="#718096")

    fig.suptitle(f"ASTRATRACK Algorithm Comparison Lab — Scenario: {report.scenario_name}",
                 color="#FFFFFF", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)

    return os.path.abspath(output_path)
