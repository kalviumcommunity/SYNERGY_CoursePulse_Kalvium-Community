"""Reusable CSV, PDF, and interactive HTML report export functions."""

from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "output" / "reports"


def markdown_to_html(markdown_text: str) -> str:
    """Convert the small Markdown subset used by executive summaries to HTML."""
    lines = []
    for raw_line in markdown_text.splitlines():
        escaped = html.escape(raw_line)
        if escaped.startswith("### "):
            lines.append(f"<h3>{escaped[4:]}</h3>")
        elif escaped.startswith("## "):
            lines.append(f"<h2>{escaped[3:]}</h2>")
        elif escaped.startswith("# "):
            lines.append(f"<h1>{escaped[2:]}</h1>")
        elif escaped.startswith("- "):
            lines.append(f"<li>{escaped[2:]}</li>")
        elif escaped:
            lines.append(f"<p>{escaped}</p>")
    return "\n".join(lines)


def _pdf_text(markdown_text: str) -> list[str]:
    return [line.lstrip("#- ") for line in markdown_text.splitlines() if line.strip()]


def export_analysis(
    df: pd.DataFrame,
    summary_text: str,
    charts_dict: dict[str, Any],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    timestamp: str | None = None,
) -> Path:
    """Export cleaned data, PDF summary, HTML charts, and metadata together."""
    generated_at = datetime.now()
    folder_stamp = timestamp or generated_at.strftime("%Y-%m-%d_%H%M%S")
    report_dir = Path(output_dir) / f"{folder_stamp}_analysis"
    report_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(report_dir / "cleaned_data.csv", index=False)

    pdf_path = report_dir / "summary_report.pdf"
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=0.65 * inch, leftMargin=0.65 * inch)
    story = [Paragraph("CoursePulse Analysis Report", styles["Title"]), Spacer(1, 0.2 * inch)]
    for line in _pdf_text(summary_text):
        story.extend([Paragraph(html.escape(line), styles["BodyText"]), Spacer(1, 0.08 * inch)])
    document.build(story)

    chart_html = []
    for index, (chart_name, figure) in enumerate(charts_dict.items()):
        chart_html.append(
            f'<section class="chart-container"><h2>{html.escape(chart_name)}</h2>'
            f"{figure.to_html(include_plotlyjs='inline' if index == 0 else False, full_html=False)}</section>"
        )
    html_document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>CoursePulse Analysis Report</title>"
        "<style>body{font-family:Arial;max-width:1200px;margin:2rem auto;color:#222}"
        ".chart-container{margin:2rem 0}</style></head><body>"
        "<h1>CoursePulse Analysis Report</h1>"
        f"<div class='summary'>{markdown_to_html(summary_text)}</div>"
        f"{''.join(chart_html)}</body></html>"
    )
    (report_dir / "interactive_report.html").write_text(html_document, encoding="utf-8")

    metadata = {
        "Generated": generated_at.isoformat(timespec="seconds"),
        "Records": len(df),
        "Columns": list(df.columns),
        "Data Range": f"{df['order_date'].min()} to {df['order_date'].max()}" if "order_date" in df.columns else "N/A",
        "Charts": list(charts_dict),
    }
    (report_dir / "README.md").write_text(
        "# Analysis Report\n\n" + "\n".join(f"- **{key}:** {value}" for key, value in metadata.items()) + "\n",
        encoding="utf-8",
    )
    return report_dir


def verify_exports(report_dir: str | Path) -> dict[str, int]:
    """Verify required files exist, are non-empty, and CSV is readable."""
    report_path = Path(report_dir)
    required = ["cleaned_data.csv", "summary_report.pdf", "interactive_report.html", "README.md"]
    sizes = {}
    for filename in required:
        path = report_path / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty export: {path}")
        sizes[filename] = path.stat().st_size
    pd.read_csv(report_path / "cleaned_data.csv")
    return sizes


def build_default_report(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Build the repository's standard report from valid orders and Plotly charts."""
    from interactive_charts.plotly_dashboard import interactive_explorer, load_orders, metric_selector, revenue_trend, segment_performance

    orders = load_orders()
    charts = {
        "Daily Revenue Trend": revenue_trend(orders),
        "Revenue by Customer Segment": segment_performance(orders),
        "Metric Selector": metric_selector(orders),
        "Customer Explorer": interactive_explorer(orders),
    }
    summary = """## Executive Summary

The report contains valid CoursePulse orders and reusable interactive views.

### Findings

- Revenue and order activity are available by day and customer segment.
- Hover tooltips provide exact values while the HTML report supports zoom and filtering.

### Recommendation

Use the CSV for spreadsheet analysis, the PDF for meetings, and the HTML report for exploratory review.
"""
    return export_analysis(orders, summary, charts, output_dir)


if __name__ == "__main__":
    report = build_default_report()
    print(f"Exported report: {report}")
    print(verify_exports(report))