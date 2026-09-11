"""
ASTRATRACK — Aerospace PDF Document Engine

Compiles technical documentation into publication-ready, aerospace-grade PDF documents
utilizing ReportLab Platypus flowables, running headers, footers, and custom styles.
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
    )
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y' on aerospace footer."""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_aerospace_chrome(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_aerospace_chrome(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(colors.HexColor("#64748b"))

        # Top Running Header
        self.drawString(54, 11 * 72 - 36, "ASTRATRACK — FSOC COARSE ALIGNMENT & POINTING SIMULATOR")
        self.drawRightString(8.5 * 72 - 54, 11 * 72 - 36, "SIH 2026 // AEROSPACE R&D LAB")

        # Top Hairline
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 11 * 72 - 42, 8.5 * 72 - 54, 11 * 72 - 42)

        # Bottom Hairline
        self.line(54, 45, 8.5 * 72 - 54, 45)

        # Bottom Running Footer
        self.setFont("Helvetica", 7)
        self.drawString(54, 32, "OFFICIAL TECHNICAL DOCUMENTATION — REPRODUCIBLE SCIENTIFIC BENCHMARK")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * 72 - 54, 32, page_str)

        self.restoreState()


class AerospacePDFEngine:
    """Renders structured documentation content into aerospace-grade PDFs."""

    def __init__(self):
        if not HAS_REPORTLAB:
            return

        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            'DocTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=6
        ))
        self.styles.add(ParagraphStyle(
            'DocSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#0369a1'),
            spaceAfter=14
        ))
        self.styles.add(ParagraphStyle(
            'MetaBox',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#334155')
        ))
        self.styles.add(ParagraphStyle(
            'SecH1',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            textColor=colors.HexColor('#0f172a'),
            spaceBefore=12,
            spaceAfter=5,
            keepWithNext=True
        ))
        self.styles.add(ParagraphStyle(
            'SecH2',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#1e293b'),
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True
        ))
        self.styles.add(ParagraphStyle(
            'SecBody',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=6
        ))
        self.styles.add(ParagraphStyle(
            'SecBullet',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            leftIndent=14,
            textColor=colors.HexColor('#334155'),
            spaceAfter=3
        ))
        self.styles.add(ParagraphStyle(
            'CalloutBox',
            parent=self.styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#0c4a6e'),
            spaceBefore=4,
            spaceAfter=6
        ))
        self.styles.add(ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#0f172a'),
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            'TableCellLeft',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#0f172a'),
            alignment=0
        ))

    def build_pdf_from_markdown(self, markdown_text: str, output_path: str, title: str, subtitle: str) -> bool:
        """Parses markdown text into styled ReportLab flowables and compiles the PDF."""
        if not HAS_REPORTLAB:
            return False

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        story = []

        # Title & Subtitle banner
        story.append(Paragraph(title, self.styles['DocTitle']))
        story.append(Paragraph(subtitle, self.styles['DocSubtitle']))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=12))

        lines = markdown_text.split("\n")
        i = 0
        in_code_block = False
        code_lines: List[str] = []
        table_lines: List[str] = []

        while i < len(lines):
            line = lines[i]

            # Code block check
            if line.strip().startswith("```"):
                if in_code_block:
                    # Flush code block as styled table
                    code_text = "<br/>".join([c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for c in code_lines])
                    t_data = [[Paragraph(f"<font face='Courier' size='7'>{code_text}</font>", self.styles['SecBody'])]]
                    t = Table(t_data, colWidths=[504])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 6))
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                    code_lines = []
                i += 1
                continue

            if in_code_block:
                code_lines.append(line)
                i += 1
                continue

            # Markdown Table check
            if line.strip().startswith("|") and line.strip().endswith("|"):
                table_lines.append(line.strip())
                i += 1
                # Check if next line is also a table line
                while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                # Parse markdown table
                self._render_markdown_table(table_lines, story)
                table_lines = []
                continue

            # Headers
            if line.startswith("# "):
                # Skip document title if duplicate
                clean_title = line[2:].strip()
                if clean_title.lower() != title.lower():
                    story.append(Spacer(1, 10))
                    story.append(Paragraph(clean_title, self.styles['SecH1']))
                    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#e2e8f0'), spaceAfter=6))
            elif line.startswith("## "):
                clean_h2 = line[3:].strip()
                story.append(Spacer(1, 6))
                story.append(Paragraph(clean_h2, self.styles['SecH1']))
            elif line.startswith("### "):
                clean_h3 = line[4:].strip()
                story.append(Paragraph(clean_h3, self.styles['SecH2']))
            elif line.startswith("#### "):
                clean_h4 = line[5:].strip()
                story.append(Paragraph(f"<b>{clean_h4}</b>", self.styles['SecH2']))
            elif line.strip().startswith("> "):
                # Callout box
                callout_text = line.strip()[2:].strip()
                t_call = [[Paragraph(f"<b>NOTE:</b> {callout_text}", self.styles['CalloutBox'])]]
                t = Table(t_call, colWidths=[504])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f9ff')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#7dd3fc')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 4))
            elif line.strip().startswith("- ") or line.strip().startswith("* "):
                bullet_content = self._format_inline_markdown(line.strip()[2:].strip())
                story.append(Paragraph(f"&bull; {bullet_content}", self.styles['SecBullet']))
            elif line.strip() == "---":
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceBefore=6, spaceAfter=6))
            elif line.strip():
                p_text = self._format_inline_markdown(line.strip())
                story.append(Paragraph(p_text, self.styles['SecBody']))

            i += 1

        try:
            doc.build(story, canvasmaker=NumberedCanvas)
            return True
        except Exception as e:
            print(f"Error compiling PDF {output_path}: {e}")
            return False

    def _format_inline_markdown(self, text: str) -> str:
        """Converts bold, italic, and code markdown spans to HTML tags for ReportLab."""
        # Escape raw ampersands (except existing entities)
        text = re.sub(r'&(?!(amp|lt|gt|quot|apos|bull);)', '&amp;', text)
        # Bold **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Italic *text*
        text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
        # Code `text`
        text = re.sub(r'`([^`]+?)`', r"<font face='Courier' color='#0369a1'><b>\1</b></font>", text)
        return text

    def _render_markdown_table(self, table_lines: List[str], story: List[Any]):
        """Parses markdown table lines and adds a styled ReportLab Table to the story."""
        if len(table_lines) < 2:
            return

        rows: List[List[str]] = []
        for row_str in table_lines:
            if re.match(r'^[|\s\-:]+$', row_str):
                # Separator line like |---|---|
                continue
            cells = [c.strip() for c in row_str.strip('|').split('|')]
            rows.append(cells)

        if not rows:
            return

        col_count = len(rows[0])
        # Total printable width is 504 pt (letter width 612 - 108 margin)
        col_width = 504.0 / col_count

        table_data = []
        for row_idx, row in enumerate(rows):
            formatted_row = []
            for col_idx, cell in enumerate(row):
                fmt_text = self._format_inline_markdown(cell)
                if row_idx == 0:
                    formatted_row.append(Paragraph(f"<b>{fmt_text}</b>", self.styles['TableHeader']))
                else:
                    style = self.styles['TableCellLeft'] if col_idx == 0 else self.styles['TableCell']
                    formatted_row.append(Paragraph(fmt_text, style))
            table_data.append(formatted_row)

        t = Table(table_data, colWidths=[col_width] * col_count)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]
        # Alternating row background
        for r in range(1, len(table_data)):
            bg = colors.HexColor('#ffffff') if r % 2 == 1 else colors.HexColor('#f8fafc')
            t_style.append(('BACKGROUND', (0, r), (-1, r), bg))

        t.setStyle(TableStyle(t_style))
        story.append(Spacer(1, 4))
        story.append(t)
        story.append(Spacer(1, 6))
