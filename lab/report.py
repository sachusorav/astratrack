"""
ASTRATRACK — Algorithm Comparison Report Generator

Generates structured Benchmark Reports (Markdown, JSON, PDF) from
AlgorithmComparisonLab results.
"""

import os
import json
from typing import Optional

from lab.runner import ComparisonReport

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class BenchmarkReportGenerator:
    """Generates benchmark documents from a ComparisonReport."""

    @staticmethod
    def to_markdown(report: ComparisonReport) -> str:
        """Render comparison table and improvement breakdown to Markdown."""
        lines = [
            f"# ASTRATRACK Algorithm Comparison Report",
            f"**Scenario:** `{report.scenario_name}` ({report.scenario_id}) | **Seed:** `{report.random_seed}` | **Frames:** `{report.duration_frames}`\n",
            "## 1. Multi-Mode Comparative Performance Table",
            "| Metric | Mode A (Classical+Direct) | Mode B (AI+PID) | Mode C (AI+Kalman+PID) | Mode D (Full Pipeline) | Units |",
            "|:---|:---:|:---:|:---:|:---:|:---:|",
        ]

        modes = list(report.mode_results.keys())
        keys_and_labels = [
            ("detection_success_pct", "Detection Success"),
            ("average_error_px", "Average Tracking Error"),
            ("maximum_error_px", "Maximum Tracking Error"),
            ("rms_error_px", "RMS Tracking Error"),
            ("acquisition_time_s", "Acquisition Time"),
            ("lock_retention_pct", "Lock Retention Rate"),
            ("recovery_time_s", "Recovery Time"),
            ("fps", "System Rate"),
            ("latency_ms", "Pipeline Latency"),
        ]
        units = ["%", "px", "px", "px", "s", "%", "s", "FPS", "ms"]

        for (prop, label), unit in zip(keys_and_labels, units):
            vals = [getattr(report.mode_results[m], prop) for m in modes]
            lines.append(f"| **{label}** | {vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} | {unit} |")

        lines.extend([
            "\n## 2. Engineering Improvement Summary (Mode D vs Mode A Baseline)",
            f"- **Average Error Reduction:** `{report.improvement_pct.get('average_error_reduction_pct', 0)}%`",
            f"- **RMS Error Reduction:** `{report.improvement_pct.get('rms_error_reduction_pct', 0)}%`",
            f"- **Lock Retention Gain:** `+{report.improvement_pct.get('lock_retention_gain_pct', 0)}%`\n",
            "> **Key Engineering Takeaway:** Adding PID regulation, Kalman estimation, forward prediction, and FSM re-acquisition "
            "transforms open-loop hunting into robust, noise-filtered, closed-loop aerospace target tracking."
        ])

        return "\n".join(lines)

    @staticmethod
    def save_markdown(report: ComparisonReport, filepath: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(BenchmarkReportGenerator.to_markdown(report))
        return filepath

    @staticmethod
    def save_json(report: ComparisonReport, filepath: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        data = {
            "scenario_id": report.scenario_id,
            "scenario_name": report.scenario_name,
            "random_seed": report.random_seed,
            "duration_frames": report.duration_frames,
            "improvements": report.improvement_pct,
            "modes": {
                m_name: {
                    "detection_success_pct": res.detection_success_pct,
                    "average_error_px": res.average_error_px,
                    "maximum_error_px": res.maximum_error_px,
                    "rms_error_px": res.rms_error_px,
                    "acquisition_time_s": res.acquisition_time_s,
                    "lock_retention_pct": res.lock_retention_pct,
                    "recovery_time_s": res.recovery_time_s,
                    "fps": res.fps,
                    "latency_ms": res.latency_ms,
                }
                for m_name, res in report.mode_results.items()
            }
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return filepath

    @staticmethod
    def export_pdf(report: ComparisonReport, chart_image_path: Optional[str], filepath: str) -> Optional[str]:
        if not HAS_REPORTLAB:
            return None

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('Title', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#0F172A'))
        subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#475569'))
        section_style = ParagraphStyle('Sec', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#1E293B'), spaceBefore=8, spaceAfter=4)

        story = [
            Paragraph("ASTRATRACK — ALGORITHM COMPARISON REPORT", title_style),
            Paragraph(f"Scenario: {report.scenario_name} | Seed: {report.random_seed} | Smart India Hackathon 2026", subtitle_style),
            Spacer(1, 10),
            Paragraph("1. Side-by-Side Measured Performance", section_style)
        ]

        modes = list(report.mode_results.keys())
        table_data = [
            ["Metric", "Mode A\nDirect", "Mode B\nAI+PID", "Mode C\nKalman", "Mode D\nFull PAT", "Units"]
        ]
        keys_and_labels = [
            ("detection_success_pct", "Detection Success", "%"),
            ("average_error_px", "Avg Error", "px"),
            ("maximum_error_px", "Max Error", "px"),
            ("rms_error_px", "RMS Error", "px"),
            ("lock_retention_pct", "Lock Retention", "%"),
            ("recovery_time_s", "Recovery Time", "s"),
            ("fps", "System FPS", "Hz"),
            ("latency_ms", "Latency", "ms"),
        ]
        for prop, label, unit in keys_and_labels:
            vals = [str(getattr(report.mode_results[m], prop)) for m in modes]
            table_data.append([label, vals[0], vals[1], vals[2], vals[3], unit])

        tab = Table(table_data, colWidths=[130, 80, 80, 80, 90, 60])
        tab.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(tab)
        story.append(Spacer(1, 10))

        if chart_image_path and os.path.exists(chart_image_path):
            story.append(Paragraph("2. Visual Performance Comparison Chart", section_style))
            story.append(Image(chart_image_path, width=540, height=320))

        doc.build(story)
        return filepath
