"""
ASTRATRACK — Master Documentation Generator

Coordinates generation of all 4 official project documents:
1. Technical Report (16 mandated sections)
2. User Manual
3. Architecture Documentation
4. Experiment Report

Compiles both Markdown and aerospace-grade PDF outputs using ReportLab.
"""

import os
from typing import Dict, Any, Optional

from docs_generator.data_collector import EmpiricalDataCollector
from docs_generator.pdf_engine import AerospacePDFEngine, HAS_REPORTLAB
from docs_generator.technical_report_builder import TechnicalReportBuilder
from docs_generator.user_manual_builder import UserManualBuilder
from docs_generator.architecture_builder import ArchitectureDocBuilder
from docs_generator.experiment_report_builder import ExperimentReportBuilder


class DocumentationGenerator:
    """Coordinates generation of Markdown and PDF technical documents."""

    def __init__(self, data_collector: Optional[EmpiricalDataCollector] = None):
        self.collector = data_collector or EmpiricalDataCollector()
        self.pdf_engine = AerospacePDFEngine()
        self.tech_builder = TechnicalReportBuilder(self.collector)
        self.manual_builder = UserManualBuilder()
        self.arch_builder = ArchitectureDocBuilder()
        self.exp_builder = ExperimentReportBuilder(self.collector)

    def generate_all(self,
                     output_dir: str = "docs",
                     run_benchmark: bool = True,
                     generate_pdf: bool = True,
                     generate_md: bool = True) -> Dict[str, Any]:
        """
        Generates all 4 documentation deliverables in markdown and PDF formats.

        Returns:
            Dict containing file paths, status, and metadata.
        """
        abs_output_dir = os.path.abspath(output_dir)
        os.makedirs(abs_output_dir, exist_ok=True)

        results = {
            "output_dir": abs_output_dir,
            "has_reportlab": HAS_REPORTLAB,
            "documents": {}
        }

        # 1. Technical Report
        tech_md = self.tech_builder.build_markdown(run_benchmark=run_benchmark)
        tech_md_path = os.path.join(abs_output_dir, "technical_report.md")
        tech_pdf_path = os.path.join(abs_output_dir, "technical_report.pdf")
        if generate_md:
            with open(tech_md_path, "w", encoding="utf-8") as f:
                f.write(tech_md)
        pdf_ok = False
        if generate_pdf and HAS_REPORTLAB:
            pdf_ok = self.pdf_engine.build_pdf_from_markdown(
                tech_md, tech_pdf_path,
                title="ASTRATRACK — Technical Report",
                subtitle="FSOC Coarse Alignment & Pointing Simulation Engine"
            )
        results["documents"]["technical_report"] = {
            "md_path": tech_md_path if generate_md else None,
            "pdf_path": tech_pdf_path if pdf_ok else None,
            "sections_count": 16
        }

        # 2. User Manual
        manual_md = self.manual_builder.build_markdown()
        manual_md_path = os.path.join(abs_output_dir, "user_manual.md")
        manual_pdf_path = os.path.join(abs_output_dir, "user_manual.pdf")
        if generate_md:
            with open(manual_md_path, "w", encoding="utf-8") as f:
                f.write(manual_md)
        pdf_ok = False
        if generate_pdf and HAS_REPORTLAB:
            pdf_ok = self.pdf_engine.build_pdf_from_markdown(
                manual_md, manual_pdf_path,
                title="ASTRATRACK — User Manual & Operator Guide",
                subtitle="Aerospace Dashboard & Interactive PAT Evaluation Guide"
            )
        results["documents"]["user_manual"] = {
            "md_path": manual_md_path if generate_md else None,
            "pdf_path": manual_pdf_path if pdf_ok else None
        }

        # 3. Architecture Documentation
        arch_md = self.arch_builder.build_markdown()
        arch_md_path = os.path.join(abs_output_dir, "architecture_documentation.md")
        arch_pdf_path = os.path.join(abs_output_dir, "architecture_documentation.pdf")
        if generate_md:
            with open(arch_md_path, "w", encoding="utf-8") as f:
                f.write(arch_md)
        pdf_ok = False
        if generate_pdf and HAS_REPORTLAB:
            pdf_ok = self.pdf_engine.build_pdf_from_markdown(
                arch_md, arch_pdf_path,
                title="ASTRATRACK — System Architecture",
                subtitle="Engineering Specification, Flow Diagrams & Kinematics"
            )
        results["documents"]["architecture_documentation"] = {
            "md_path": arch_md_path if generate_md else None,
            "pdf_path": arch_pdf_path if pdf_ok else None
        }

        # 4. Experiment Report
        exp_md = self.exp_builder.build_markdown(run_trials=run_benchmark)
        exp_md_path = os.path.join(abs_output_dir, "experiment_report.md")
        exp_pdf_path = os.path.join(abs_output_dir, "experiment_report.pdf")
        if generate_md:
            with open(exp_md_path, "w", encoding="utf-8") as f:
                f.write(exp_md)
        pdf_ok = False
        if generate_pdf and HAS_REPORTLAB:
            pdf_ok = self.pdf_engine.build_pdf_from_markdown(
                exp_md, exp_pdf_path,
                title="ASTRATRACK — Empirical Experiment Report",
                subtitle="Multi-Scenario Evaluation & Reproducibility Verification"
            )
        results["documents"]["experiment_report"] = {
            "md_path": exp_md_path if generate_md else None,
            "pdf_path": exp_pdf_path if pdf_ok else None
        }

        return results
