"""
ASTRATRACK — Experiment Report Exporter

Exports single experiment or multi-experiment comparisons to:
- Markdown
- JSON
- ReportLab PDF summary
"""

import os
import json
from typing import Optional, List

from experiments.record import ExperimentRecord
from experiments.comparator import ExperimentComparison, plot_experiment_comparison

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class ExperimentExporter:
    """Exports single and comparison experiment reports."""

    @staticmethod
    def export_comparison_markdown(comp: ExperimentComparison, filepath: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(comp.to_markdown())
        return filepath

    @staticmethod
    def export_comparison_pdf(comp: ExperimentComparison, filepath: str) -> Optional[str]:
        if not HAS_REPORTLAB:
            return None

        chart_path = os.path.join(os.path.dirname(filepath), "comparison_chart.png")
        plot_experiment_comparison(comp.experiments, chart_path)

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('Title', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#0F172A'))
        subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#475569'))
        section_style = ParagraphStyle('Sec', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#1E293B'), spaceBefore=8, spaceAfter=4)

        story = [
            Paragraph("ASTRATRACK — EXPERIMENT COMPARISON REPORT", title_style),
            Paragraph("Scientific Provenance & Empirical Benchmarking | Smart India Hackathon 2026", subtitle_style),
            Spacer(1, 12),
            Paragraph("1. Multi-Run Parameter & Metric Comparison", section_style)
        ]

        ids = [e.experiment_id[:16] for e in comp.experiments]
        table_data = [
            ["Metric / Run"] + ids + ["Units"]
        ]
        metrics_rows = [
            ("Scenario", [e.scenario_name for e in comp.experiments], ""),
            ("Detector", [e.detector_type for e in comp.experiments], ""),
            ("Controller", [e.controller_type for e in comp.experiments], ""),
            ("Seed", [str(e.random_seed) for e in comp.experiments], ""),
            ("Avg Error", [f"{e.average_error_px}" for e in comp.experiments], "px"),
            ("Max Error", [f"{e.maximum_error_px}" for e in comp.experiments], "px"),
            ("RMS Error", [f"{e.rms_error_px}" for e in comp.experiments], "px"),
            ("Lock Retention", [f"{e.lock_retention_pct}%" for e in comp.experiments], "%"),
            ("Latency", [f"{e.latency_ms}" for e in comp.experiments], "ms"),
        ]
        for name, vals, unit in metrics_rows:
            table_data.append([name] + vals + [unit])

        col_w = max(60, int(380 / max(1, len(ids))))
        tab = Table(table_data, colWidths=[110] + [col_w] * len(ids) + [50])
        tab.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(tab)
        story.append(Spacer(1, 14))

        if os.path.exists(chart_path):
            story.append(Paragraph("2. Empirical Trajectory & Error Visual Comparison", section_style))
            story.append(Image(chart_path, width=540, height=200))

        doc.build(story)
        return filepath
