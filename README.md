# Resume Doctor

An offline ATS check. Paste a resume next to a job description and get a score out of 100, the keywords the posting keeps repeating, and a fix for every weak line.

Most resumes die in an applicant tracking system before a person reads them. Resume Doctor runs a deterministic rubric — no account, no model — so the same resume and the same job always produce the same score.

## Web

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
resume-doctor serve
```

Open http://127.0.0.1:8000. Upload a PDF or paste the text. **Try a flawed sample** loads a data-analyst resume that is missing a Skills section on purpose.

## CLI

```bash
resume-doctor check samples/sample-resume.txt --job samples/sample-job.txt
resume-doctor check samples/sample-resume.txt --job samples/sample-job.txt --output report.md
resume-doctor check samples/sample-resume.txt --job samples/sample-job.txt --format json
```

`check` accepts `.pdf`, `.txt`, and `.md`.

## What the score measures

| Check | Points | What it looks at |
| --- | --- | --- |
| Sections | 25 | Contact, summary, experience, education, skills |
| Keywords | 35 | How many of the job's top keywords appear in the resume |
| Measurable impact | 20 | Share of experience bullets with a number, %, or currency |
| Action verbs | 10 | Share of bullets that open with a strong verb |
| Length and clarity | 10 | 400–900 words, and lines that run past about 25 words |

## Before / after

The sample resume says:

> Responsible for weekly sales reporting for the regional team

Resume Doctor does not rewrite the line. It tells you what is wrong with it:

> Start with "Owned" instead of "responsible for".
> Add a number: time saved, % improved, users reached, or ₹ value.

A human version of that same work:

> Owned weekly sales reporting for 40 stores and cut the Monday pack from 3 hours to 45 minutes.

The sample job asks for Power BI over and over. The sample resume never says it, so the keyword list leads with that gap. On this pair the score is **49 / 100** — rewrite before you apply.

## Deploy

[`render.yaml`](render.yaml) is a Render Blueprint for one free Python web service. The process binds `0.0.0.0:$PORT`. Free services sleep after a stretch of no traffic, so the first open of the day can take a few seconds.

## License

MIT © Veliation AI
