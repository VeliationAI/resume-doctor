"""Extract resume text and split it into sections and bullets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SECTION_ORDER = ("contact", "summary", "experience", "education", "skills")

HEADINGS: dict[str, frozenset[str]] = {
    "contact": frozenset(
        {"contact", "contact information", "personal details", "personal information"}
    ),
    "summary": frozenset(
        {
            "summary",
            "professional summary",
            "profile",
            "objective",
            "about",
            "about me",
            "career summary",
        }
    ),
    "experience": frozenset(
        {
            "experience",
            "work experience",
            "professional experience",
            "employment",
            "employment history",
            "work history",
        }
    ),
    "education": frozenset(
        {"education", "academic background", "academics", "education and certifications"}
    ),
    "skills": frozenset(
        {
            "skills",
            "technical skills",
            "core competencies",
            "competencies",
            "tools",
            "technologies",
            "technical competencies",
        }
    ),
}

BULLET_RE = re.compile(r"^\s*(?:[-*•▪‣–]|\d+[.)])\s+(.*\S)\s*$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LINKEDIN_RE = re.compile(r"linkedin\.com", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b"
    r"|(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"
)


@dataclass(frozen=True)
class Bullet:
    text: str
    section: str | None
    line_no: int


@dataclass(frozen=True)
class ParsedResume:
    text: str
    present: dict[str, bool]
    bullets: list[Bullet]
    experience_bullets: list[Bullet]
    long_lines: list[str]
    word_count: int


def extract_text(path: Path) -> str:
    """Read a resume or job description from .pdf, .txt, or .md."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path.read_bytes(), path.name)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported file type '{suffix}'. Use a .pdf, .txt, or .md file.")


def text_from_upload(filename: str, raw: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(raw, filename)
    if suffix in {".txt", ".md", ""}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")
    raise ValueError("Upload a PDF or paste the resume text.")


def _pdf_text(raw: bytes, name: str) -> str:
    import io

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            parts = [(page.extract_text() or "") for page in pdf.pages]
    except Exception as exc:  # noqa: BLE001 — surface a single readable error
        raise ValueError(f"Could not read {name}. Paste the resume text instead.") from exc
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError(
            "No text found in that PDF. Scanned resumes need to be pasted as text."
        )
    return text


def parse_resume(text: str) -> ParsedResume:
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    current: str | None = None
    bullets: list[Bullet] = []
    long_lines: list[str] = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        heading = heading_of(line)
        if heading:
            current = heading
            continue
        if current:
            sections[current].append(line)
        stripped = line.strip()
        if stripped and len(stripped.split()) > 25:
            long_lines.append(stripped)
        match = BULLET_RE.match(line)
        if match:
            bullets.append(Bullet(text=match.group(1).strip(), section=current, line_no=line_no))

    present = {name: bool("\n".join(lines).strip()) for name, lines in sections.items()}
    if not present["contact"] and has_contact(text):
        present["contact"] = True

    experience = [bullet for bullet in bullets if bullet.section == "experience"]
    if not experience and bullets and not present["experience"]:
        experience = list(bullets)

    return ParsedResume(
        text=text,
        present=present,
        bullets=bullets,
        experience_bullets=experience,
        long_lines=long_lines,
        word_count=len(text.split()),
    )


def heading_of(line: str) -> str | None:
    cleaned = re.sub(r"^#+\s*", "", line).strip().strip(":").strip("-").strip()
    if not cleaned or len(cleaned) > 48 or cleaned.endswith("."):
        return None
    key = re.sub(r"\s+", " ", cleaned.lower())
    for section, names in HEADINGS.items():
        if key in names:
            return section
    return None


def has_contact(text: str) -> bool:
    return bool(EMAIL_RE.search(text) or LINKEDIN_RE.search(text) or PHONE_RE.search(text))
