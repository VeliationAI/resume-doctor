"""Command line: check a resume, or open the web UI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal, Optional

import typer

from resume_doctor import __version__
from resume_doctor.analyzer import analyze
from resume_doctor.parser import extract_text
from resume_doctor.report import render_console, to_json, to_markdown

app = typer.Typer(
    help="Score a resume against a job description and print line-by-line ATS fixes.",
    no_args_is_help=True,
    add_completion=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """Resume Doctor."""


@app.command()
def check(
    resume: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="Resume .pdf, .txt, or .md"),
    ],
    job: Annotated[
        Path,
        typer.Option("--job", "-j", exists=True, dir_okay=False, readable=True, help="Job description file"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write the report to this file"),
    ] = None,
    fmt: Annotated[
        Literal["text", "markdown", "json"],
        typer.Option("--format", "-f", help="text (terminal), markdown, or json"),
    ] = "text",
) -> None:
    """Print an ATS score, missing keywords, and line-by-line fixes."""
    try:
        resume_text = extract_text(resume)
        job_text = extract_text(job)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    analysis = analyze(resume_text, job_text)
    markdown = to_markdown(analysis)
    payload = to_json(analysis) if fmt == "json" else markdown

    if output:
        output.write_text(payload if fmt == "json" else markdown, encoding="utf-8")

    if fmt == "json":
        _emit(payload)
    elif fmt == "markdown":
        _emit(markdown)
    else:
        render_console(analysis)
        if output:
            typer.echo(f"Wrote {output}")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port")] = 8000,
) -> None:
    """Open the web UI. On Render, the start command binds 0.0.0.0:$PORT directly."""
    import uvicorn

    env_port = os.environ.get("PORT")
    if env_port:
        host = "0.0.0.0"
        port = int(env_port)
    uvicorn.run("resume_doctor.server:create_app", factory=True, host=host, port=port)


def _emit(text: str) -> None:
    try:
        typer.echo(text, nl=False)
    except UnicodeEncodeError:
        typer.echo(text.encode("ascii", "backslashreplace").decode("ascii"), nl=False)
