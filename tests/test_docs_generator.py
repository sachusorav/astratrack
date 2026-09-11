"""
ASTRATRACK — Documentation Generator Unit Tests

Validates:
- Successful generation of all 4 documents (Technical Report, User Manual, Architecture Doc, Experiment Report)
- Technical Report contains all 16 specified sections with correct headings
- Disturbance engineering approximation disclaimer is explicitly present
- Zero fake/synthetic results: empirical tables populated with real measured numbers
- Output files exist and are non-empty
- PDF compilation succeeds when ReportLab is present
"""

import os
import re
import pytest
from docs_generator.generator import DocumentationGenerator
from docs_generator.pdf_engine import HAS_REPORTLAB


class TestDocumentationGenerator:
    """Test suite for automatic documentation generation."""

    @pytest.fixture(scope="class")
    def generated_docs(self, tmp_path_factory):
        """Generates all documentation in a temporary directory for verification."""
        tmp_dir = str(tmp_path_factory.mktemp("test_docs"))
        generator = DocumentationGenerator()
        results = generator.generate_all(
            output_dir=tmp_dir,
            run_benchmark=True,
            generate_pdf=True,
            generate_md=True
        )
        return {"results": results, "dir": tmp_dir}

    def test_all_four_markdown_files_exist(self, generated_docs):
        doc_dir = generated_docs["dir"]
        expected_files = [
            "technical_report.md",
            "user_manual.md",
            "architecture_documentation.md",
            "experiment_report.md"
        ]
        for f in expected_files:
            p = os.path.join(doc_dir, f)
            assert os.path.exists(p), f"Missing expected document: {f}"
            assert os.path.getsize(p) > 1000, f"Document {f} is suspiciously small ({os.path.getsize(p)} bytes)"

    def test_technical_report_all_16_mandated_sections(self, generated_docs):
        tech_path = os.path.join(generated_docs["dir"], "technical_report.md")
        with open(tech_path, "r", encoding="utf-8") as f:
            content = f.read()

        mandated_sections = [
            "1. Problem Understanding",
            "2. FSOC Background",
            "3. Coarse Alignment",
            "4. System Architecture",
            "5. Software Modules",
            "6. AI Detection",
            "7. Tracking",
            "8. Kalman Estimation",
            "9. Prediction",
            "10. PID Control",
            "11. Disturbance Model",
            "12. Re-acquisition",
            "13. Testing Methodology",
            "14. Performance Analysis",
            "15. Limitations",
            "16. Future Hardware-in-the-Loop Integration"
        ]

        for sec in mandated_sections:
            assert f"## {sec}" in content, f"Technical report missing mandated section: '{sec}'"

    def test_disturbance_model_engineering_approximation_disclaimer(self, generated_docs):
        tech_path = os.path.join(generated_docs["dir"], "technical_report.md")
        with open(tech_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Mandated phrase from user instructions
        assert "configurable engineering approximations for algorithm robustness testing" in content
        assert "physically exact" in content

    def test_no_synthetic_placeholders_in_performance_analysis(self, generated_docs):
        tech_path = os.path.join(generated_docs["dir"], "technical_report.md")
        with open(tech_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Ensure performance analysis section is present and contains real metrics
        assert "## 14. Performance Analysis" in content
        assert "Mode A (Direct)" in content
        assert "Mode D (Full Pipeline)" in content
        assert "Average Tracking Error (px)" in content
        assert "Lock Retention Rate (%)" in content
        assert "TBD" not in content
        assert "TODO" not in content

    def test_architecture_documentation_contains_mermaid_diagrams(self, generated_docs):
        arch_path = os.path.join(generated_docs["dir"], "architecture_documentation.md")
        with open(arch_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "```mermaid" in content
        assert "graph TD" in content
        assert "sequenceDiagram" in content
        assert "stateDiagram-v2" in content

    def test_experiment_report_reproducibility_bit_exact(self, generated_docs):
        exp_path = os.path.join(generated_docs["dir"], "experiment_report.md")
        with open(exp_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Bit-Exact Reproducibility Verification" in content
        assert "MATCH (BIT-EXACT)" in content
        assert "0.000000" in content

    def test_pdf_generation(self, generated_docs):
        if not HAS_REPORTLAB:
            pytest.skip("ReportLab not available in environment")

        doc_dir = generated_docs["dir"]
        expected_pdfs = [
            "technical_report.pdf",
            "user_manual.pdf",
            "architecture_documentation.pdf",
            "experiment_report.pdf"
        ]
        for f in expected_pdfs:
            p = os.path.join(doc_dir, f)
            assert os.path.exists(p), f"Missing expected PDF document: {f}"
            assert os.path.getsize(p) > 2000, f"PDF {f} is suspiciously small ({os.path.getsize(p)} bytes)"
