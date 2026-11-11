from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from resume_doctor.analyzer import (
    analyze,
    has_metric,
    is_strong,
    length_points,
    weak_opener,
)
from resume_doctor.cli import app
from resume_doctor.keywords import rank_keywords
from resume_doctor.parser import heading_of, parse_resume
from resume_doctor.server import create_app

ROOT = Path(__file__).resolve().parents[1]
RESUME = ROOT / "samples" / "sample-resume.txt"
JOB = ROOT / "samples" / "sample-job.txt"
runner = CliRunner()


def test_sections_score_five_points_each():
    text = """
    Ada Lovelace
    ada@example.com

    SUMMARY
    Analyst who writes reports.

    EXPERIENCE
    Analyst, Example Co
    - Responsible for weekly reporting
    - Built a pipeline that cut refresh time 40%

    EDUCATION
    BSc, Example University

    SKILLS
    Python, Excel
    """
    parsed = parse_resume(text)
    assert all(parsed.present[name] for name in ("contact", "summary", "experience", "education", "skills"))
    result = analyze(text, "Python and Excel for reporting.")
    sections = next(item for item in result.categories if item.key == "sections")
    assert sections.points == 25


def test_missing_section_fix_names_skills():
    text = "Ada Lovelace\nada@example.com\n\nSUMMARY\nAnalyst.\n\nEXPERIENCE\n- Built a report\n\nEDUCATION\nBSc\n"
    result = analyze(text, "Python developer who writes SQL.")
    skills = [fix for fix in result.fixes if "Skills section" in fix.suggestion]
    assert skills
    assert result.sections["skills"] is False


def test_keyword_gaps_follow_job_frequency():
    job = "gamma signal. " * 4 + "alpha widget. " * 3 + "beta canvas. " * 2
    resume = "I shipped a beta canvas and then another beta canvas."
    keywords = rank_keywords(job, resume)
    missing = [item for item in keywords if not item.in_resume]
    assert [item.key for item in missing[:2]] == ["gamma signal", "alpha widget"]
    counts = [item.jd_count for item in missing]
    assert counts == sorted(counts, reverse=True)


def test_power_bi_outranks_a_single_mention():
    job = "Power BI " * 6 + "SQL " * 4 + "We need Python once."
    resume = "I use Python for reports."
    keywords = rank_keywords(job, resume)
    assert keywords[0].term == "Power BI"
    assert keywords[0].jd_count == 6
    assert keywords[0].in_resume is False
    python = next(item for item in keywords if item.term == "Python")
    assert python.in_resume is True


def test_metric_and_weak_verb_fixes_are_specific():
    assert has_metric("Cut reporting time 40%")
    assert not has_metric("Improved reporting")
    assert weak_opener("Responsible for the weekly pack") == ("responsible for", "Owned")
    assert is_strong("Built a pipeline")
    assert not is_strong("Responsible for a pipeline")

    text = """
    SUMMARY
    Analyst.
    EXPERIENCE
    - Responsible for weekly reporting
    - Built a pipeline that cut refresh time 40%
    EDUCATION
    BSc
    SKILLS
    Python
    ada@example.com
    """
    result = analyze(text, "Python Python reporting reporting")
    verb = next(fix for fix in result.fixes if fix.kind == "verb")
    assert "Owned" in verb.suggestion
    assert "responsible for" in verb.suggestion
    metric_lines = [fix.text for fix in result.fixes if fix.kind == "metric"]
    assert any("Responsible for weekly reporting" in line for line in metric_lines)
    assert not any("40%" in line for line in metric_lines)


def test_length_band_and_long_line_penalty():
    assert length_points(500, 0) == 10
    assert length_points(500, 1) == 8
    assert length_points(100, 0) == 0
    assert length_points(1200, 0) == 3

    padding = "\n".join(" ".join(["notes"] * 10) for _ in range(45))
    text = (
        "CONTACT\nada@example.com\n\nSUMMARY\nAnalyst writing reports.\n\n"
        "EXPERIENCE\n- Built a report for the team\n\nEDUCATION\nBSc\n\nSKILLS\nPython\n"
        + padding
    )
    result = analyze(text, "Python Python reports reports")
    length = next(item for item in result.categories if item.key == "length")
    assert 400 <= result.word_count <= 900
    assert length.points == 10


def test_score_is_the_sum_of_the_breakdown():
    result = analyze(RESUME.read_text(encoding="utf-8"), JOB.read_text(encoding="utf-8"))
    assert result.score == sum(item.points for item in result.categories)
    assert 0 <= result.score <= 100
    for item in result.categories:
        assert 0 <= item.points <= item.max_points
    missing = [item.term for item in result.keywords if not item.in_resume]
    assert "Power BI" in missing
    assert "SQL" in missing
    assert result.sections["skills"] is False


def test_heading_detection():
    assert heading_of("## Work Experience") == "experience"
    assert heading_of("Skills:") == "skills"
    assert heading_of("Built a dashboard for the team last spring.") is None


def test_cli_json_and_markdown_output(tmp_path: Path):
    report = tmp_path / "report.md"
    result = runner.invoke(
        app,
        ["check", str(RESUME), "--job", str(JOB), "--output", str(report), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = report.read_text(encoding="utf-8")
    assert '"score"' in payload
    assert "Power BI" in result.output

    markdown = runner.invoke(
        app,
        ["check", str(RESUME), "--job", str(JOB), "--format", "markdown"],
    )
    assert markdown.exit_code == 0, markdown.output
    assert "ATS score:" in markdown.output


def test_web_check_and_health():
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200
    assert "Resume Doctor" in page.text

    response = client.post(
        "/api/check",
        json={
            "resume": RESUME.read_text(encoding="utf-8"),
            "job": JOB.read_text(encoding="utf-8"),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["score"] == body["report"]["score"]
    assert "Power BI" in body["markdown"]

    uploaded = client.post(
        "/api/check",
        data={"job": "Python Python SQL SQL", "resume": ""},
        files={"resume_file": ("resume.txt", b"Ada\nada@example.com\n\nSKILLS\nPython\n", "text/plain")},
    )
    assert uploaded.status_code == 200
    missing = [item["term"] for item in uploaded.json()["report"]["missing_keywords"]]
    assert "SQL" in missing

    empty = client.post("/api/check", json={"resume": "", "job": ""})
    assert empty.status_code == 400

    pdf = client.post(
        "/api/report.pdf",
        json={
            "resume": RESUME.read_text(encoding="utf-8"),
            "job": JOB.read_text(encoding="utf-8"),
        },
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "resume-doctor-report.pdf" in pdf.headers["content-disposition"]
