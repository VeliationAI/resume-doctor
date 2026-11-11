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
