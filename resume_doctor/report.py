"""Markdown, JSON, and terminal reports."""

from __future__ import annotations

import json

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from resume_doctor.analyzer import Analysis

KIND_LABELS = {
    "section": "Section",
    "keyword": "Keyword",
    "metric": "Metric",
    "verb": "Verb",
    "clarity": "Clarity",
    "length": "Length",
}


def to_markdown(analysis: Analysis) -> str:
    lines = [
        "# Resume Doctor report",
        "",
        f"**ATS score: {analysis.score} / 100.** {analysis.band_label}",
        "",
        "## Breakdown",
        "",
        "| Check | Score | Notes |",
        "| --- | --- | --- |",
    ]
    for category in analysis.categories:
        notes = category.detail.replace("|", "/")
        lines.append(f"| {category.name} | {category.points}/{category.max_points} | {notes} |")

    missing = [item for item in analysis.keywords if not item.in_resume]
    lines.extend(["", "## Missing keywords", ""])
    if missing:
        for item in missing:
            lines.append(f"- {item.term} — asked {item.jd_count} times")
    else:
        lines.append("None. The resume covers the keywords this rubric extracted.")

    lines.extend(["", "## Line-by-line fixes", ""])
    if not analysis.fixes:
        lines.append("No line-level fixes. Read the breakdown before you send it.")
    for fix in analysis.fixes:
        label = KIND_LABELS.get(fix.kind, fix.kind)
        lines.append(f"### {label}")
        if fix.text:
            lines.append(f"> {fix.text}")
            lines.append("")
        lines.append(fix.suggestion)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_json(analysis: Analysis) -> str:
    return json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False) + "\n"


def to_pdf(analysis: Analysis) -> bytes:
    """A real PDF the browser can save as resume-doctor-report.pdf."""
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()
    width = pdf.epw

    red, green, blue = _pdf_tone(analysis.band_tone)
    pdf.set_fill_color(red, green, blue)
    pdf.set_text_color(246, 241, 231)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(width, 8, _pdf_text("Resume Doctor"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(width, 14, _pdf_text(f"{analysis.score} / 100"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(width, 7, _pdf_text(analysis.band_label), fill=True)
    guidance = analysis.to_dict()["stats"]["page_guidance"]
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(width, 6, _pdf_text(guidance), fill=True)
    pdf.ln(6)

    pdf.set_text_color(28, 25, 22)
    _pdf_heading(pdf, "Do these first")
    for index, step in enumerate(_pdf_steps(analysis), start=1):
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(width, 6, _pdf_text(f"{index}. {step}"))
        pdf.ln(1)

    _pdf_heading(pdf, "Breakdown")
    for category in analysis.categories:
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(width, 6, _pdf_text(f"{category.name}  {category.points}/{category.max_points}"))
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(width, 5, _pdf_text(category.detail))
        pdf.ln(1)

    missing = [item for item in analysis.keywords if not item.in_resume]
    present = [item for item in analysis.keywords if item.in_resume]
    _pdf_heading(pdf, "Missing keywords")
    pdf.set_font("Helvetica", size=11)
    if missing:
        pdf.multi_cell(width, 6, _pdf_text(", ".join(f"{item.term} ({item.jd_count})" for item in missing)))
    else:
        pdf.multi_cell(width, 6, "None.")

    _pdf_heading(pdf, "Already on the resume")
    pdf.set_font("Helvetica", size=11)
    if present:
        pdf.multi_cell(width, 6, _pdf_text(", ".join(item.term for item in present)))
    else:
        pdf.multi_cell(width, 6, "None yet.")

    _pdf_heading(pdf, "Line-by-line fixes")
    if not analysis.fixes:
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(width, 6, "No line-level fixes.")
    for fix in analysis.fixes:
        label = KIND_LABELS.get(fix.kind, fix.kind)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(width, 6, _pdf_text(label))
        pdf.set_font("Helvetica", size=11)
        if fix.text:
            pdf.multi_cell(width, 6, _pdf_text(fix.text))
        pdf.multi_cell(width, 6, _pdf_text(fix.suggestion))
        pdf.ln(2)

    return bytes(pdf.output())


def _pdf_tone(tone: str) -> tuple[int, int, int]:
    if tone == "good":
        return (15, 61, 54)
    if tone == "warn":
        return (58, 42, 20)
    if tone == "bad":
        return (61, 33, 27)
    return (18, 49, 46)


def _pdf_heading(pdf: object, title: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(pdf.epw, 8, title)
    pdf.ln(1)


def _pdf_steps(analysis: Analysis) -> list[str]:
    steps: list[str] = []
    section = next((fix for fix in analysis.fixes if fix.kind == "section"), None)
    if section:
        steps.append(section.suggestion)
    missing = [item for item in analysis.keywords if not item.in_resume]
    if missing:
        top = missing[0]
        times = "once" if top.jd_count == 1 else f"{top.jd_count} times"
        steps.append(f"Add {top.term}. The job says it {times}, and your resume does not.")
    line = next((fix for fix in analysis.fixes if fix.kind in {"verb", "metric"} and fix.text), None)
    if line:
        notes = [
            fix.suggestion
            for fix in analysis.fixes
            if fix.text == line.text and fix.kind in {"verb", "metric"}
        ]
        preview = " ".join(line.text.split())
        if len(preview) > 90:
            preview = preview[:89].rstrip() + "..."
        steps.append(f'Rewrite "{preview}". {" ".join(notes)}')
    return steps[:3]


def _pdf_text(text: str) -> str:
    cleaned = (
        text.replace("\u20b9", "Rs")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u2026", "...")
    )
    return cleaned.encode("latin-1", "replace").decode("latin-1")


def render_console(analysis: Analysis) -> None:
    console = Console()
    console.print(
        Panel(
            f"[bold]{analysis.score}[/bold] / 100   {escape(analysis.band_label)}",
            title="Resume Doctor",
            border_style="green" if analysis.score >= 70 else "yellow",
        )
    )
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Score", justify="right")
    table.add_column("Notes")
    for category in analysis.categories:
        table.add_row(category.name, f"{category.points}/{category.max_points}", category.detail)
    console.print(table)

    missing = [item for item in analysis.keywords if not item.in_resume]
    console.print()
    console.print("[bold]Missing keywords[/bold]")
    if missing:
        for item in missing:
            console.print(f"  {escape(item.term)}  ({item.jd_count})")
    else:
        console.print("  None")

    console.print()
    console.print("[bold]Line-by-line fixes[/bold]")
    if not analysis.fixes:
        console.print("  None")
        return
    for fix in analysis.fixes:
        label = KIND_LABELS.get(fix.kind, fix.kind)
        console.print()
        console.print(f"[dim]{label}[/dim]")
        if fix.text:
            console.print(f"  {escape(fix.text)}")
        console.print(f"  {escape(fix.suggestion)}")
