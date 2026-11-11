"""FastAPI web UI for Resume Doctor."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from resume_doctor import __version__
from resume_doctor.analyzer import analyze
from resume_doctor.parser import text_from_upload
from resume_doctor.report import to_markdown

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
MAX_BYTES = 5_000_000
MAX_CHARS = 100_000


def create_app() -> FastAPI:
    app = FastAPI(title="Resume Doctor", version=__version__)
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "index.html", {"version": __version__})

    @app.get("/api/sample")
    def sample() -> dict[str, str]:
        folder = _samples_dir()
        return {
            "resume": (folder / "sample-resume.txt").read_text(encoding="utf-8"),
            "job": (folder / "sample-job.txt").read_text(encoding="utf-8"),
        }

    @app.post("/api/check")
    async def check(request: Request) -> dict[str, object]:
        resume_text, job_text = await _read_check(request)
        analysis = analyze(resume_text, job_text)
        return {"report": analysis.to_dict(), "markdown": to_markdown(analysis)}

    return app


async def _read_check(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Expected a JSON object.")
        resume_text = str(payload.get("resume") or "")
        job_text = str(payload.get("job") or "")
    else:
        form = await request.form()
        job_text = str(form.get("job") or "")
        resume_text = str(form.get("resume") or "")
        upload = form.get("resume_file")
        if upload is not None and hasattr(upload, "read"):
            raw = await upload.read()
            if len(raw) > MAX_BYTES:
                raise HTTPException(status_code=413, detail="That file is over 5 MB.")
            filename = getattr(upload, "filename", None) or "resume"
            try:
                resume_text = text_from_upload(filename, raw)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(resume_text) > MAX_CHARS or len(job_text) > MAX_CHARS:
        raise HTTPException(status_code=413, detail="That text is too long to score.")
    if not job_text.strip():
        raise HTTPException(status_code=400, detail="Paste the job description.")
    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Paste a resume or upload a PDF.")
    return resume_text, job_text


def _samples_dir() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[1] / "samples", Path.cwd() / "samples"]
    for folder in candidates:
        if (folder / "sample-resume.txt").exists() and (folder / "sample-job.txt").exists():
            return folder
    raise HTTPException(status_code=404, detail="Sample files are missing.")


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    import os

    import uvicorn

    env_port = os.environ.get("PORT")
    if env_port:
        host = "0.0.0.0"
        port = int(env_port)
    uvicorn.run(create_app(), host=host, port=port)
