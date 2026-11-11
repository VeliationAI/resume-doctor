"""Markdown, JSON, and terminal reports."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from resume_doctor.analyzer import Analysis, Fix

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
    """A designed PDF that matches the on-screen report."""
    from fpdf import FPDF

    class _Sheet(FPDF):
        def header(self) -> None:
            self.set_fill_color(239, 230, 214)
            self.rect(0, 0, self.w, self.h, "F")

        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Noto", size=8)
            self.set_text_color(109, 101, 92)
            self.cell(0, 6, _pdf_text(f"Resume Doctor   {self.page_no()}"), align="C")

    pdf = _Sheet(format="A4")
    font_dir = Path(__file__).parent / "fonts"
    pdf.add_font("Noto", "", str(font_dir / "NotoSans-Regular.ttf"))
    pdf.add_font("Noto", "B", str(font_dir / "NotoSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    _pdf_scorecard(pdf, analysis)
    _pdf_heading(pdf, "Do these first")
    for index, step in enumerate(_pdf_steps(analysis), start=1):
        _pdf_step(pdf, index, step)
    _pdf_heading(pdf, "Keywords")
    missing = [item for item in analysis.keywords if not item.in_resume]
    present = [item for item in analysis.keywords if item.in_resume]
    _pdf_label(pdf, "Missing", (182, 64, 42))
    _pdf_chips(
        pdf,
        [f"{item.term}  {item.jd_count}" for item in missing] or ["None"],
        (248, 228, 220),
        (124, 45, 29),
    )
    _pdf_label(pdf, "Already on the resume", (15, 118, 110))
    _pdf_chips(
        pdf,
        [item.term for item in present] or ["None yet"],
        (216, 243, 234),
        (18, 49, 46),
    )
    _pdf_heading(pdf, "Line-by-line fixes")
    loose, lines = _pdf_groups(analysis)
    shown = [fix for fix in loose if fix.kind != "keyword"]
    if any(fix.kind == "keyword" for fix in loose):
        shown.append(
            Fix(
                kind="keyword",
                text="",
                suggestion=(
                    "Add the missing terms above to a Skills section. "
                    "Use the ones the job repeats most inside a bullet."
                ),
            )
        )
    if not shown and not lines:
        pdf.set_font("Noto", size=11)
        pdf.set_text_color(28, 25, 22)
        pdf.multi_cell(pdf.epw, 6, "No line-level fixes.", new_x="LMARGIN", new_y="NEXT")
    for fix in shown:
        _pdf_card(
            pdf,
            KIND_LABELS.get(fix.kind, fix.kind),
            fix.text,
            [fix.suggestion],
            (182, 64, 42) if fix.kind == "keyword" else (15, 118, 110),
        )
    for line in lines:
        _pdf_card(pdf, "Line", str(line["text"]), list(line["notes"]), (18, 49, 46))
    return bytes(pdf.output())


def _pdf_scorecard(pdf: object, analysis: Analysis) -> None:
    tone = analysis.band_tone
    if tone == "good":
        color = (15, 61, 54)
    elif tone == "warn":
        color = (58, 42, 20)
    elif tone == "bad":
        color = (61, 33, 27)
    else:
        color = (18, 49, 46)
    x, y, width, height = 14, 14, 182, 78
    pdf.set_fill_color(*color)
    pdf.rect(x, y, width, height, "F")
    pdf.set_text_color(213, 235, 228)
    pdf.set_font("Noto", "B", 8)
    pdf.set_xy(x + 6, y + 6)
    pdf.cell(50, 4, "ATS SCORE")
    pdf.set_text_color(246, 241, 231)
    pdf.set_font("Noto", "B", 32)
    pdf.set_xy(x + 6, y + 12)
    pdf.cell(52, 16, str(analysis.score))
    pdf.set_font("Noto", "B", 11)
    pdf.set_xy(x + 6, y + 30)
    pdf.multi_cell(52, 5, _pdf_text(analysis.band_label), new_x="LMARGIN", new_y="NEXT")
    guidance = analysis.to_dict()["stats"]["page_guidance"]
    pdf.set_font("Noto", size=8)
    pdf.set_text_color(217, 207, 192)
    pdf.set_xy(x + 6, y + 48)
    pdf.multi_cell(52, 4, _pdf_text(guidance), new_x="LMARGIN", new_y="NEXT")

    bar_x = x + 66
    bar_w = width - 74
    row_y = y + 8
    for category in analysis.categories:
        ratio = 0 if not category.max_points else category.points / category.max_points
        pdf.set_xy(bar_x, row_y)
        pdf.set_font("Noto", size=8)
        pdf.set_text_color(246, 241, 231)
        pdf.cell(bar_w - 18, 4, _pdf_text(category.name))
        pdf.cell(18, 4, f"{category.points}/{category.max_points}", align="R")
        track_y = row_y + 5
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(bar_x, track_y, bar_w, 2.2, "F")
        if ratio >= 0.8:
            fill = (143, 208, 196)
        elif ratio >= 0.5:
            fill = (228, 194, 122)
        else:
            fill = (231, 160, 144)
        if ratio > 0:
            pdf.set_fill_color(*fill)
            pdf.rect(bar_x, track_y, max(1.2, bar_w * ratio), 2.2, "F")
        row_y += 13
    pdf.set_xy(pdf.l_margin, y + height + 8)
    pdf.set_text_color(28, 25, 22)


def _pdf_heading(pdf: object, title: str) -> None:
    pdf.ln(1)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Noto", "B", 14)
    pdf.set_text_color(28, 25, 22)
    pdf.cell(0, 8, _pdf_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _pdf_label(pdf: object, title: str, color: tuple[int, int, int]) -> None:
    pdf.set_font("Noto", "B", 8)
    pdf.set_text_color(*color)
    pdf.cell(0, 5, _pdf_text(title.upper()), new_x="LMARGIN", new_y="NEXT")


def _pdf_step(pdf: object, number: int, text: str) -> None:
    pdf.set_fill_color(18, 49, 46)
    pdf.set_text_color(246, 241, 231)
    pdf.set_font("Noto", "B", 9)
    y = pdf.get_y()
    pdf.cell(6, 6, str(number), align="C", fill=True)
    pdf.set_xy(pdf.l_margin + 9, y)
    pdf.set_text_color(28, 25, 22)
    pdf.set_font("Noto", size=10)
    pdf.multi_cell(pdf.epw - 9, 5, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)


def _pdf_chips(
    pdf: object,
    labels: list[str],
    fill: tuple[int, int, int],
    ink: tuple[int, int, int],
) -> None:
    x = pdf.l_margin
    y = pdf.get_y()
    limit = pdf.w - pdf.r_margin
    pdf.set_font("Noto", "B", 8)
    for label in labels:
        safe = _pdf_text(label)
        chip_w = pdf.get_string_width(safe) + 6
        if x + chip_w > limit:
            x = pdf.l_margin
            y += 8
        if y > pdf.h - 20:
            pdf.add_page()
            x = pdf.l_margin
            y = pdf.t_margin
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*ink)
        pdf.set_xy(x, y)
        pdf.cell(chip_w, 6, safe, fill=True)
        x += chip_w + 2
    pdf.set_xy(pdf.l_margin, y + 9)
    pdf.set_text_color(28, 25, 22)


def _pdf_card(
    pdf: object,
    kind: str,
    quote: str,
    notes: list[str],
    accent: tuple[int, int, int],
) -> None:
    inner = pdf.epw - 8
    blocks: list[tuple[str, int, str]] = []
    if quote:
        blocks.append(("B", 11, quote))
    for note in notes:
        blocks.append(("", 10, note))
    height = 8
    for style, size, text in blocks:
        pdf.set_font("Noto", style, size)
        lines = pdf.multi_cell(
            inner,
            5,
            _pdf_text(text),
            dry_run=True,
            output="LINES",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        height += max(1, len(lines)) * 5
    height += 2
    if pdf.get_y() + height > pdf.h - 18:
        pdf.add_page()
    top = pdf.get_y()
    pdf.set_fill_color(250, 246, 239)
    pdf.rect(pdf.l_margin, top, pdf.epw, height, "F")
    pdf.set_fill_color(*accent)
    pdf.rect(pdf.l_margin, top, 1.5, height, "F")
    pdf.set_xy(pdf.l_margin + 4, top + 2)
    pdf.set_font("Noto", "B", 8)
    pdf.set_text_color(109, 101, 92)
    pdf.cell(inner, 4, _pdf_text(kind.upper()), new_x="LMARGIN", new_y="NEXT")
    for style, size, text in blocks:
        pdf.set_x(pdf.l_margin + 4)
        pdf.set_font("Noto", style, size)
        pdf.set_text_color(28, 25, 22)
        pdf.multi_cell(inner, 5, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(pdf.l_margin, top + height + 2.5)


def _pdf_groups(analysis: Analysis) -> tuple[list, list[dict[str, object]]]:
    loose = [fix for fix in analysis.fixes if fix.kind not in {"verb", "metric"}]
    lines: list[dict[str, object]] = []
    by_text: dict[str, dict[str, object]] = {}
    for fix in analysis.fixes:
        if fix.kind not in {"verb", "metric"}:
            continue
        key = fix.text or fix.suggestion
        if key not in by_text:
            by_text[key] = {"text": fix.text, "notes": []}
            lines.append(by_text[key])
        notes = by_text[key]["notes"]
        assert isinstance(notes, list)
        notes.append(fix.suggestion)
    return loose, lines


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
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
