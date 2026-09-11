"""
ASTRATRACK — Documentation Generator CLI Script

Usage:
    python scripts/generate_docs.py [options]

Options:
    --output-dir DIR      Directory to output generated documentation (default: docs)
    --skip-benchmark      Skip executing live benchmarks (use cached or placeholder)
    --no-pdf              Generate Markdown only, skip PDF compilation
    --all                 Generate all 4 documents with real empirical benchmarks (default)
"""

import sys
import os
import argparse

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from docs_generator.generator import DocumentationGenerator


def main():
    parser = argparse.ArgumentParser(description="ASTRATRACK Automatic Documentation Generator")
    parser.add_argument("--output-dir", default="docs", help="Target output directory for documents (default: docs)")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip running live benchmarks")
    parser.add_argument("--no-pdf", action="store_true", help="Do not generate PDF files")
    parser.add_argument("--all", action="store_true", help="Generate all reports with empirical benchmarks")
    args = parser.parse_args()

    run_benchmark = not args.skip_benchmark
    generate_pdf = not args.no_pdf

    print("================================================================================")
    print("ASTRATRACK — Automatic Documentation Generator")
    print(f"Output Directory: {os.path.abspath(args.output_dir)}")
    print(f"Run Empirical Benchmarks: {run_benchmark}")
    print(f"Generate PDFs: {generate_pdf}")
    print("================================================================================")

    gen = DocumentationGenerator()
    results = gen.generate_all(
        output_dir=args.output_dir,
        run_benchmark=run_benchmark,
        generate_pdf=generate_pdf,
        generate_md=True
    )

    print("\nGeneration Complete! Manifest of generated documents:")
    for doc_name, paths in results["documents"].items():
        print(f"\n[+] {doc_name.upper()}:")
        if paths.get("md_path"):
            print(f"    - Markdown: {paths['md_path']}")
        if paths.get("pdf_path"):
            print(f"    - PDF:      {paths['pdf_path']}")

    print("\nAll technical documentation successfully generated.")


if __name__ == "__main__":
    main()
