"""Pull the job-description keywords that matter and see which the resume uses."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[a-z][a-z0-9+#.]{1,}")

STOPWORDS = frozenset(
    """
    a an the and or of to for in on with without within across into over per via
    from by as at be is are was were been being will can could should would may
    might must shall do does did doing have has had having this that these those
    it its their they them we our you your i my me he she his her they
    not but if about who whom which what when where how all any each more most
    some both between through during before after above below up down out off
    again further once here there why so too very just own same than then also
    such other plus etc eg ie am pm
    need needs needed required requirement requirements prefer preferred
    qualification qualifications responsibility responsibilities candidate
    candidates position company team teams role roles work working job jobs
    experience experienced year years yr yrs strong ability skill skills
    knowledge understanding environment looking seeking join opportunity well
    high based related various multiple please apply application resume
    description ideal successful success     help helps make makes take new good
    great best like want wanted currently current following follow provide
    provides support supports ensure including include used use using able
    build write explain sit define publish partner maintain transform
    reconcile describe show shows live lives mention screen miss change changed
    day days week weeks month months today tomorrow
    will who whose whom because while where onto upon
    """.split()
)

# Tools and methods that count even when the posting names them once.
KNOWN_SINGLE = frozenset(
    """
    python sql excel tableau pandas numpy spark hadoop snowflake looker dax
    java scala azure aws gcp docker git jira figma react salesforce sap
    alteryx qlik airflow dbt kafka redshift bigquery databricks tensorflow
    pytorch keras nlp statistics javascript typescript html css matlab spss
    sas stata vba powerbi pandas
    etl api bi kpi ui ux qa dax
    """.split()
)

SHORT_SKILLS = frozenset(
    {"sql", "bi", "aws", "gcp", "api", "etl", "kpi", "nlp", "ai", "ml", "ui", "ux", "dax", "sap", "qa"}
)

KNOWN_PHRASES = (
    "power bi",
    "power query",
    "power pivot",
    "machine learning",
    "deep learning",
    "data visualization",
    "data analysis",
    "data analytics",
    "business intelligence",
    "google analytics",
    "google sheets",
    "looker studio",
    "apache spark",
    "scikit learn",
    "natural language",
    "rest api",
    "time series",
    "linear regression",
    "microsoft excel",
)

DISPLAY = {
    "power bi": "Power BI",
    "power query": "Power Query",
    "power pivot": "Power Pivot",
    "machine learning": "Machine learning",
    "deep learning": "Deep learning",
    "data visualization": "Data visualization",
    "data analysis": "Data analysis",
    "data analytics": "Data analytics",
    "business intelligence": "Business intelligence",
    "google analytics": "Google Analytics",
    "google sheets": "Google Sheets",
    "looker studio": "Looker Studio",
    "apache spark": "Apache Spark",
    "scikit learn": "scikit-learn",
    "natural language": "Natural language",
    "rest api": "REST API",
    "time series": "Time series",
    "linear regression": "Linear regression",
    "sql": "SQL",
    "python": "Python",
    "excel": "Excel",
    "tableau": "Tableau",
    "etl": "ETL",
    "api": "API",
    "aws": "AWS",
    "gcp": "GCP",
    "nlp": "NLP",
    "kpi": "KPI",
    "bi": "BI",
    "dax": "DAX",
    "ui": "UI",
    "ux": "UX",
    "qa": "QA",
    "ai": "AI",
    "ml": "ML",
    "sap": "SAP",
    "html": "HTML",
    "css": "CSS",
    "vba": "VBA",
    "spss": "SPSS",
    "sas": "SAS",
    "pandas": "pandas",
    "numpy": "NumPy",
    "bigquery": "BigQuery",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
}


@dataclass(frozen=True)
class Keyword:
    term: str
    key: str
    jd_count: int
    in_resume: bool


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("power-bi", "power bi").replace("powerbi", "power bi")
    text = text.replace("scikit-learn", "scikit learn")
    text = re.sub(r"[^a-z0-9+#.\s]", " ", text)
    text = re.sub(r"\.(?![a-z0-9])", " ", text)
    text = re.sub(r"(?<![a-z0-9])\.", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bmicrosoft excel\b", "excel", text)
    text = re.sub(r"\bms excel\b", "excel", text)
    return text


def pretty(term: str) -> str:
    if term in DISPLAY:
        return DISPLAY[term]
    if term in SHORT_SKILLS:
        return term.upper()
    return " ".join(part.capitalize() for part in term.split())


def rank_keywords(job_text: str, resume_text: str, limit: int = 20) -> list[Keyword]:
    """Return the top job keywords, most frequent first, tagged if the resume has them."""
    job = normalize(job_text)
    resume = normalize(resume_text)
    counts: dict[str, int] = {}

    for phrase in KNOWN_PHRASES:
        found = _count(job, phrase)
        if found:
            counts[phrase] = found

    known = {key: count for key, count in counts.items() if " " in key}
    for phrase, found in _bigrams(job).items():
        if found >= 2 and not _shadowed_by_known(phrase, known):
            counts[phrase] = max(counts.get(phrase, 0), found)

    phrase_keys = [key for key in counts if " " in key]
    for token, found in _unigrams(job).items():
        if _covered_by_phrase(token, found, phrase_keys, counts):
            continue
        if _keep_unigram(token, found):
            counts[token] = max(counts.get(token, 0), found)

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [
        Keyword(
            term=pretty(key),
            key=key,
            jd_count=count,
            in_resume=_in_text(resume, key),
        )
        for key, count in ranked
    ]


def _in_text(text: str, term: str) -> bool:
    if _count(text, term):
        return True
    # "dashboards" in the job still counts when the resume says "dashboard".
    if " " in term or term in KNOWN_SINGLE or not term.endswith("s") or term.endswith("ss"):
        return False
    return _count(text, term[:-1]) > 0


def _count(text: str, term: str) -> int:
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))


def _unigrams(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for token in TOKEN_RE.findall(text):
        if token in STOPWORDS:
            continue
        if len(token) <= 2 and token not in SHORT_SKILLS:
            continue
        counts[token] += 1
    return counts


def _bigrams(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    previous: str | None = None
    for token in TOKEN_RE.findall(text):
        if token in STOPWORDS or (len(token) <= 2 and token not in SHORT_SKILLS):
            previous = None
            continue
        if previous and previous != token:
            counts[f"{previous} {token}"] += 1
        previous = token
    return counts


def _shadowed_by_known(bigram: str, known: dict[str, int]) -> bool:
    """Drop 'bi power' once 'power bi' is already a keyword."""
    if bigram in known:
        return False
    words = set(bigram.split())
    locked = words & SHORT_SKILLS
    for phrase in known:
        overlap = words & set(phrase.split())
        if overlap and (locked or overlap == words):
            return True
    return False


def _keep_unigram(token: str, count: int) -> bool:
    if len(token) <= 2:
        return token in SHORT_SKILLS and count >= 1
    if count >= 2:
        return True
    return token in KNOWN_SINGLE


def _covered_by_phrase(token: str, count: int, phrases: list[str], counts: dict[str, int]) -> bool:
    for phrase in phrases:
        if token in phrase.split() and count <= counts[phrase] + 1:
            return True
    return False
