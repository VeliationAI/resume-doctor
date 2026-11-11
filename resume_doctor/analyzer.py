"""The 0–100 ATS rubric and the line-by-line fixes that come out of it."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from resume_doctor.keywords import Keyword, rank_keywords
from resume_doctor.parser import ParsedResume, parse_resume

# Points: sections 25, keywords 35, measurable impact 20, action verbs 10, length 10.
SECTION_POINTS = 5
KEYWORD_POINTS = 35
IMPACT_POINTS = 20
VERB_POINTS = 10
LENGTH_POINTS = 10

SECTION_FIXES = {
    "contact": "No contact info found — put an email and phone at the top. ATS parsers look for them.",
    "summary": "No summary found — add two or three lines under a Summary heading so the parser knows the target role.",
    "experience": "No experience section found — ATS parsers look for one.",
    "education": "No education section found — ATS parsers look for one.",
    "skills": "No Skills section found — ATS parsers look for one.",
}

# Longer phrases first so "was responsible for" wins over "responsible for".
WEAK_OPENERS = (
    ("was responsible for", "Owned"),
    ("responsible for", "Owned"),
    ("duties included", "Delivered"),
    ("tasked with", "Owned"),
    ("helped with", "Delivered"),
    ("helped to", "Delivered"),
    ("assisted with", "Supported"),
    ("assisted in", "Supported"),
    ("worked on", "Built"),
    ("involved in", "Led"),
    ("participated in", "Led"),
)

STRONG_VERBS = frozenset(
    """
    built led cut automated designed analyzed analysed shipped reduced increased
    launched owned migrated implemented created improved delivered optimized
    optimised mentored deployed drove scaled saved grew generated streamlined
    rebuilt introduced established partnered presented modeled modelled forecast
    forecasted visualized visualised queried cleaned transformed trained coached
    negotiated secured published standardized standardised accelerated
    consolidated eliminated simplified architected spearheaded managed directed
    produced quantified measured tracked developed engineered integrated
    refactored documented prioritized prioritised facilitated coordinated
    executed achieved exceeded won defined mapped audited validated monitored
    configured scripted extracted wrangled decreased lifted modernized
    modernised centralized centralised piloted authored constructed diagnosed
    identified investigated orchestrated overhauled pioneered redesigned
    replaced resolved restructured revamped slashed sourced systematized
    unified upgraded wrote reported
    """.split()
)

METRIC_RE = re.compile(
    r"\d|[$€£₹]|(?<![a-z])(?:million|billion|thousand|doubled|tripled|halved)(?![a-z])",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[A-Za-z']+")

METRIC_SUGGESTION = "Add a number: time saved, % improved, users reached, or ₹ value."
KEYWORD_FIX_LIMIT = 8
CLARITY_FIX_LIMIT = 6


@dataclass(frozen=True)
class Fix:
    kind: str
    text: str
    suggestion: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "text": self.text, "suggestion": self.suggestion}


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    points: int
    max_points: int
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "points": self.points,
            "max_points": self.max_points,
            "detail": self.detail,
        }


@dataclass
class Analysis:
    score: int
    band_label: str
    band_tone: str
    categories: list[Category] = field(default_factory=list)
    keywords: list[Keyword] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)
    word_count: int = 0
    sections: dict[str, bool] = field(default_factory=dict)
    experience_bullets: int = 0
    metric_bullets: int = 0
    strong_verb_bullets: int = 0
    long_lines: int = 0

    def to_dict(self) -> dict[str, object]:
        missing = [item for item in self.keywords if not item.in_resume]
        return {
            "score": self.score,
            "band_label": self.band_label,
            "band_tone": self.band_tone,
            "breakdown": [category.to_dict() for category in self.categories],
            "keywords": [
                {"term": item.term, "jd_count": item.jd_count, "in_resume": item.in_resume}
                for item in self.keywords
            ],
            "missing_keywords": [
                {"term": item.term, "jd_count": item.jd_count} for item in missing
            ],
            "fixes": [fix.to_dict() for fix in self.fixes],
            "stats": {
                "word_count": self.word_count,
                "sections": self.sections,
                "experience_bullets": self.experience_bullets,
                "metric_bullets": self.metric_bullets,
                "strong_verb_bullets": self.strong_verb_bullets,
                "long_lines": self.long_lines,
                "page_guidance": page_guidance(self.word_count),
            },
        }


def analyze(resume_text: str, job_text: str) -> Analysis:
    parsed = parse_resume(resume_text)
    keywords = rank_keywords(job_text, resume_text)
    categories = [
        _sections(parsed),
        _keywords(keywords),
        _impact(parsed),
        _verbs(parsed),
        _length(parsed),
    ]
    score = sum(category.points for category in categories)
    label, tone = band(score)
    return Analysis(
        score=score,
        band_label=label,
        band_tone=tone,
        categories=categories,
        keywords=keywords,
        fixes=_fixes(parsed, keywords),
        word_count=parsed.word_count,
        sections=dict(parsed.present),
        experience_bullets=len(parsed.experience_bullets),
        metric_bullets=sum(1 for bullet in parsed.experience_bullets if has_metric(bullet.text)),
        strong_verb_bullets=sum(1 for bullet in parsed.experience_bullets if is_strong(bullet.text)),
        long_lines=len(parsed.long_lines),
    )


def band(score: int) -> tuple[str, str]:
    if score >= 85:
        return "Ready to send.", "good"
    if score >= 70:
        return "Close. Fix the gaps below.", "ok"
    if score >= 50:
        return "The ATS will likely filter this.", "warn"
    return "Rewrite before you apply.", "bad"


def has_metric(text: str) -> bool:
    return METRIC_RE.search(text) is not None


def weak_opener(text: str) -> tuple[str, str] | None:
    lowered = text.lower().strip()
    for phrase, verb in WEAK_OPENERS:
        if lowered.startswith(phrase):
            return phrase, verb
    return None


def is_strong(text: str) -> bool:
    if weak_opener(text):
        return False
    words = WORD_RE.findall(text)
    return bool(words) and words[0].lower() in STRONG_VERBS


def length_points(word_count: int, long_lines: int) -> int:
    """10 points inside 400–900 words, less outside, minus a clarity penalty."""
    if 400 <= word_count <= 900:
        base = 10
    elif 300 <= word_count <= 399 or 901 <= word_count <= 1100:
        base = 6
    elif 200 <= word_count <= 299 or 1101 <= word_count <= 1400:
        base = 3
    else:
        base = 0
    # Each wall of text costs 2 points, and the category still caps at 10.
    penalty = min(4, 2 * long_lines)
    return max(0, base - penalty)


def page_guidance(word_count: int) -> str:
    if word_count < 400:
        return "This is short for a full resume — closer to half a page. Add scope and results."
    if word_count <= 650:
        return "About one page. A good length if you have under ten years of experience."
    if word_count <= 900:
        return "About one to two pages. Fine for a longer career if every bullet earns its place."
    return "This will run past two pages. Cut older roles and repeated tools."


def _sections(parsed: ParsedResume) -> Category:
    found = [name for name in ("contact", "summary", "experience", "education", "skills") if parsed.present[name]]
    missing = [name for name in ("contact", "summary", "experience", "education", "skills") if not parsed.present[name]]
    detail = "Found " + ", ".join(found) + "." if found else "No standard sections found."
    if missing:
        detail += " Missing " + ", ".join(missing) + "."
    return Category(
        key="sections",
        name="Sections",
        points=SECTION_POINTS * len(found),
        max_points=25,
        detail=detail,
    )


def _keywords(keywords: list[Keyword]) -> Category:
    total = len(keywords)
    covered = sum(1 for item in keywords if item.in_resume)
    if total == 0:
        points = 0
        detail = "No job-description keywords found. Paste the full posting."
    else:
        points = min(KEYWORD_POINTS, int(round(KEYWORD_POINTS * covered / total)))
        detail = f"{covered} of {total} job keywords appear in the resume."
    return Category(
        key="keywords",
        name="Keywords",
        points=points,
        max_points=KEYWORD_POINTS,
        detail=detail,
    )


def _impact(parsed: ParsedResume) -> Category:
    bullets = parsed.experience_bullets
    if not bullets:
        return Category(
            key="impact",
            name="Measurable impact",
            points=0,
            max_points=IMPACT_POINTS,
            detail="No experience bullets to score.",
        )
    hits = sum(1 for bullet in bullets if has_metric(bullet.text))
    return Category(
        key="impact",
        name="Measurable impact",
        points=min(IMPACT_POINTS, int(round(IMPACT_POINTS * hits / len(bullets)))),
        max_points=IMPACT_POINTS,
        detail=f"{hits} of {len(bullets)} experience bullets include a number, %, or currency.",
    )


def _verbs(parsed: ParsedResume) -> Category:
    bullets = parsed.experience_bullets
    if not bullets:
        return Category(
            key="verbs",
            name="Action verbs",
            points=0,
            max_points=VERB_POINTS,
            detail="No experience bullets to score.",
        )
    hits = sum(1 for bullet in bullets if is_strong(bullet.text))
    return Category(
        key="verbs",
        name="Action verbs",
        points=min(VERB_POINTS, int(round(VERB_POINTS * hits / len(bullets)))),
        max_points=VERB_POINTS,
        detail=f"{hits} of {len(bullets)} bullets open with a strong verb.",
    )


def _length(parsed: ParsedResume) -> Category:
    points = length_points(parsed.word_count, len(parsed.long_lines))
    detail = f"{parsed.word_count} words. {page_guidance(parsed.word_count)}"
    if parsed.long_lines:
        detail += f" {len(parsed.long_lines)} line(s) run past 25 words."
    return Category(
        key="length",
        name="Length and clarity",
        points=points,
        max_points=LENGTH_POINTS,
        detail=detail,
    )


def _fixes(parsed: ParsedResume, keywords: list[Keyword]) -> list[Fix]:
    fixes: list[Fix] = []
    for name in ("contact", "summary", "experience", "education", "skills"):
        if not parsed.present[name]:
            fixes.append(Fix(kind="section", text="", suggestion=SECTION_FIXES[name]))

    keyword_fixes = 0
    for item in keywords:
        if item.in_resume or keyword_fixes >= KEYWORD_FIX_LIMIT:
            continue
        times = "once" if item.jd_count == 1 else f"{item.jd_count} times"
        fixes.append(
            Fix(
                kind="keyword",
                text=item.term,
                suggestion=(
                    f"The job asks for {item.term} {times}; your resume never mentions it — "
                    "add it to Skills and one bullet."
                ),
            )
        )
        keyword_fixes += 1

    for bullet in parsed.experience_bullets:
        weak = weak_opener(bullet.text)
        if weak:
            phrase, verb = weak
            fixes.append(
                Fix(
                    kind="verb",
                    text=bullet.text,
                    suggestion=f'Start with "{verb}" instead of "{phrase}".',
                )
            )
        if not has_metric(bullet.text):
            fixes.append(Fix(kind="metric", text=bullet.text, suggestion=METRIC_SUGGESTION))

    for line in parsed.long_lines[:CLARITY_FIX_LIMIT]:
        words = len(line.split())
        fixes.append(
            Fix(
                kind="clarity",
                text=_clip(line),
                suggestion=(
                    f"This line is {words} words. Break it up — recruiters skip walls of text "
                    "over about 25 words."
                ),
            )
        )

    if not (400 <= parsed.word_count <= 900):
        if parsed.word_count < 400:
            suggestion = (
                f"This resume is {parsed.word_count} words. The readable range is 400–900 — "
                "add scope and results to the thin sections."
            )
        else:
            suggestion = (
                f"This resume is {parsed.word_count} words. The readable range is 400–900 — "
                "cut older roles and repeated tools so it stays within two pages."
            )
        fixes.append(Fix(kind="length", text="", suggestion=suggestion))
    return fixes


def _clip(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"
