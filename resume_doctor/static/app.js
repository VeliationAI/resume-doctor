const form = document.getElementById("check-form");
const resumeInput = document.getElementById("resume");
const jobInput = document.getElementById("job");
const fileInput = document.getElementById("resume-file");
const fileNote = document.getElementById("file-note");
const resumeSheet = document.getElementById("resume-sheet");
const statusEl = document.getElementById("status");
const checkBtn = document.getElementById("btn-check");
const btnLabel = document.getElementById("btn-label");
const scoreEl = document.getElementById("score");
const bandEl = document.getElementById("band");
const pageNote = document.getElementById("page-note");
const scorecard = document.getElementById("scorecard");
const barsEl = document.getElementById("bars");
const pillsEl = document.getElementById("pills");
const fixesEl = document.getElementById("fixes");
const toolsEl = document.getElementById("chart-tools");
const keywordLead = document.getElementById("keyword-lead");
const nextEl = document.getElementById("next");
const nextList = document.getElementById("next-list");
const resumeCount = document.getElementById("resume-count");
const resumeRange = document.getElementById("resume-range");
const resumeMeter = document.getElementById("resume-meter");
const jobCount = document.getElementById("job-count");

const KIND = {
  section: "Section",
  keyword: "Keyword",
  metric: "Metric",
  verb: "Verb",
  clarity: "Clarity",
  length: "Length",
};

let pdfFile = null;
let latestReport = null;
let scoreFrame = 0;

resumeInput.addEventListener("input", updateMeters);
jobInput.addEventListener("input", updateMeters);
document.getElementById("btn-sample").addEventListener("click", loadSample);
document.getElementById("btn-download").addEventListener("click", downloadReport);
document.getElementById("btn-reset").addEventListener("click", resetChart);
fileInput.addEventListener("change", onFile);
form.addEventListener("submit", onSubmit);
form.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    form.requestSubmit();
  }
});

["dragenter", "dragover"].forEach((name) => {
  resumeSheet.addEventListener(name, (event) => {
    event.preventDefault();
    resumeSheet.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((name) => {
  resumeSheet.addEventListener(name, (event) => {
    event.preventDefault();
    resumeSheet.classList.remove("dragover");
  });
});
resumeSheet.addEventListener("drop", (event) => {
  const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
  if (file) acceptFile(file);
});

async function loadSample() {
  setStatus("Loading the sample…");
  try {
    const response = await fetch("/api/sample");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Sample unavailable.");
    clearFile();
    resumeInput.value = payload.resume;
    jobInput.value = payload.job;
    updateMeters();
    setStatus("Sample loaded. It is missing a Skills section on purpose.");
    resumeInput.focus();
  } catch (error) {
    setStatus(error.message || "Could not load the sample.", "bad");
  }
}

function onFile() {
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    clearFile();
    return;
  }
  acceptFile(file);
}

function acceptFile(file) {
  const name = file.name || "resume";
  const isPdf = /\.pdf$/i.test(name) || file.type === "application/pdf";
  if (!isPdf) {
    const reader = new FileReader();
    reader.onload = () => {
      resumeInput.value = String(reader.result || "");
      clearFile();
      updateMeters();
      setStatus(`Loaded ${name} into the resume box.`);
    };
    reader.onerror = () => setStatus("Could not read that file. Paste the text instead.", "bad");
    reader.readAsText(file);
    return;
  }
  pdfFile = file;
  fileNote.hidden = false;
  fileNote.textContent = "";
  fileNote.append(`${name} will be read on the server. The text box is ignored until you remove it. `);
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "text-btn";
  remove.textContent = "Remove PDF";
  remove.addEventListener("click", () => {
    clearFile();
    setStatus("PDF removed.");
  });
  fileNote.append(remove);
  resumeCount.textContent = "PDF attached";
  resumeRange.textContent = "Word count shows after the check";
  resumeMeter.dataset.tone = "warn";
  setStatus("");
}

function clearFile() {
  pdfFile = null;
  fileInput.value = "";
  fileNote.hidden = true;
  fileNote.textContent = "";
  updateMeters();
}

async function onSubmit(event) {
  event.preventDefault();
  const job = jobInput.value.trim();
  const resume = resumeInput.value.trim();
  if (!job) {
    setStatus("Paste the job description.", "bad");
    jobInput.focus();
    return;
  }
  if (!resume && !pdfFile) {
    setStatus("Paste a resume or upload a PDF.", "bad");
    resumeInput.focus();
    return;
  }

  checkBtn.disabled = true;
  btnLabel.textContent = "Checking…";
  setStatus("Scoring sections, keywords, bullets, and length.");

  const body = new FormData();
  body.set("job", jobInput.value);
  body.set("resume", pdfFile ? "" : resumeInput.value);
  if (pdfFile) body.set("resume_file", pdfFile);

  try {
    const response = await fetch("/api/check", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.detail;
      throw new Error(typeof detail === "string" ? detail : "The check failed.");
    }
    latestReport = payload.report;
    renderReport(payload.report);
    const steps = nextList.children.length;
    setStatus(`Score ${payload.report.score} out of 100. Start with the ${steps} steps under the score.`);
    document.getElementById("chart").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setStatus(error.message || "The check failed.", "bad");
  } finally {
    checkBtn.disabled = false;
    btnLabel.textContent = "Check resume";
  }
}

function renderReport(report) {
  scorecard.dataset.tone = report.band_tone || "idle";
  bandEl.textContent = report.band_label || "";
  const stats = report.stats || {};
  pageNote.textContent = stats.page_guidance || "";
  animateScore(report.score);
  renderBars(report.breakdown || []);
  renderNext(report);
  renderPills(report.keywords || []);
  renderFixes(report.fixes || []);
  toolsEl.hidden = false;
}

function firstSteps(report) {
  const steps = [];
  const fixes = report.fixes || [];
  const section = fixes.find((fix) => fix.kind === "section");
  if (section) steps.push(section.suggestion);
  const keyword = (report.missing_keywords || [])[0];
  if (keyword) {
    const times = keyword.jd_count === 1 ? "once" : `${keyword.jd_count} times`;
    steps.push(`Add ${keyword.term}. The job says it ${times}, and your resume does not.`);
  }
  const line = fixes.find((fix) => fix.kind === "verb") || fixes.find((fix) => fix.kind === "metric");
  if (line && line.text) {
    const weak = fixes.find((fix) => fix.kind === "verb" && fix.text === line.text);
    const metric = fixes.find((fix) => fix.kind === "metric" && fix.text === line.text);
    const advice = [weak && weak.suggestion, metric && metric.suggestion].filter(Boolean).join(" ");
    steps.push(`Rewrite “${clip(line.text, 90)}”. ${advice}`);
  }
  return steps.slice(0, 3);
}

function renderNext(report) {
  const steps = firstSteps(report);
  nextList.textContent = "";
  steps.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    nextList.append(item);
  });
  nextEl.hidden = steps.length === 0;
}

function animateScore(target) {
  cancelAnimationFrame(scoreFrame);
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) {
    scoreEl.textContent = String(target);
    return;
  }
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min(1, (now - start) / 700);
    const eased = 1 - (1 - t) ** 3;
    scoreEl.textContent = String(Math.round(target * eased));
    if (t < 1) scoreFrame = requestAnimationFrame(tick);
  };
  scoreFrame = requestAnimationFrame(tick);
}

function renderBars(categories) {
  barsEl.textContent = "";
  categories.forEach((category) => {
    const max = category.max_points || 1;
    const ratio = Math.max(0, Math.min(1, category.points / max));
    const li = document.createElement("li");
    const top = document.createElement("div");
    top.className = "bar-top";
    const name = document.createElement("span");
    name.textContent = category.name;
    const score = document.createElement("span");
    score.textContent = `${category.points}/${max}`;
    top.append(name, score);
    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("span");
    fill.className = "fill" + (ratio < 0.5 ? " bad" : ratio < 0.8 ? " warn" : "");
    track.append(fill);
    const detail = document.createElement("p");
    detail.className = "bar-detail";
    detail.textContent = category.detail || "";
    li.append(top, track, detail);
    barsEl.append(li);
    requestAnimationFrame(() => {
      fill.style.width = `${Math.round(ratio * 100)}%`;
    });
  });
}

function renderPills(keywords) {
  pillsEl.textContent = "";
  if (!keywords.length) {
    const empty = document.createElement("p");
    empty.className = "placeholder";
    empty.textContent = "No keywords came out of that job description.";
    pillsEl.append(empty);
    keywordLead.textContent = "Paste more of the posting if this list is empty.";
    return;
  }
  const missing = keywords.filter((item) => !item.in_resume);
  const present = keywords.filter((item) => item.in_resume);
  keywordLead.textContent = missing.length
    ? `${missing.length} missing. The number is how often the job says it.`
    : "Every extracted keyword shows up in the resume.";
  pillsEl.append(pillGroup("Missing", missing, true));
  if (present.length) pillsEl.append(pillGroup("Already on the resume", present, false));
}

function pillGroup(label, items, isMissing) {
  const group = document.createElement("div");
  group.className = "pill-group";
  const title = document.createElement("p");
  title.className = "group-label" + (isMissing ? " missing" : " ok");
  title.textContent = label;
  const row = document.createElement("div");
  row.className = "pills";
  row.style.marginTop = "0";
  items.forEach((item) => {
    const pill = document.createElement("span");
    pill.className = "pill" + (item.in_resume ? "" : " missing");
    const term = document.createElement("span");
    term.textContent = item.term;
    const count = document.createElement("em");
    count.textContent = String(item.jd_count);
    pill.append(term, count);
    row.append(pill);
  });
  group.append(title, row);
  return group;
}

function renderFixes(fixes) {
  fixesEl.textContent = "";
  if (!fixes.length) {
    const empty = document.createElement("p");
    empty.className = "placeholder";
    empty.textContent = "No line-level fixes. Read the breakdown before you send it.";
    fixesEl.append(empty);
    return;
  }
  const loose = fixes.filter((fix) => fix.kind !== "verb" && fix.kind !== "metric");
  loose.forEach((fix) => fixesEl.append(fixCard(fix.kind, fix.text, [fix.suggestion])));
  const lines = mergeLines(fixes);
  if (!lines.length) return;
  const shown = lines.slice(0, 5);
  const rest = lines.slice(5);
  shown.forEach((line) => fixesEl.append(fixCard("verb", line.text, line.notes)));
  if (!rest.length) return;
  const more = document.createElement("button");
  more.type = "button";
  more.className = "text-btn more";
  more.textContent = `Show ${rest.length} more line${rest.length === 1 ? "" : "s"}`;
  more.addEventListener("click", () => {
    rest.forEach((line) => fixesEl.insertBefore(fixCard("verb", line.text, line.notes), more));
    more.remove();
  });
  fixesEl.append(more);
}

function mergeLines(fixes) {
  const order = [];
  const byText = new Map();
  fixes.forEach((fix) => {
    if (fix.kind !== "verb" && fix.kind !== "metric") return;
    const key = fix.text || fix.suggestion;
    if (!byText.has(key)) {
      byText.set(key, { text: fix.text, notes: [] });
      order.push(key);
    }
    byText.get(key).notes.push(fix.suggestion);
  });
  return order.map((key) => byText.get(key));
}

function fixCard(kind, text, notes) {
  const card = document.createElement("article");
  card.className = `fix ${kind || ""}`;
  const label = document.createElement("p");
  label.className = "fix-kind";
  label.textContent = kind === "verb" ? "Line" : (KIND[kind] || "Fix");
  card.append(label);
  if (text) {
    const quote = document.createElement("blockquote");
    quote.textContent = text;
    card.append(quote);
  }
  notes.forEach((note) => {
    const suggestion = document.createElement("p");
    suggestion.className = "fix-suggestion";
    suggestion.textContent = note;
    card.append(suggestion);
  });
  const actions = document.createElement("div");
  actions.className = "fix-actions";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "text-btn";
  copy.textContent = "Copy this fix";
  copy.addEventListener("click", async () => {
    const payload = [text, ...notes].filter(Boolean).join("\n");
    try {
      await navigator.clipboard.writeText(payload);
      copy.textContent = "Copied";
    } catch {
      copy.textContent = "Copy failed";
    }
    window.setTimeout(() => {
      copy.textContent = "Copy this fix";
    }, 1400);
  });
  actions.append(copy);
  card.append(actions);
  return card;
}

async function downloadReport() {
  const job = jobInput.value.trim();
  const resume = resumeInput.value.trim();
  if (!job || (!resume && !pdfFile)) {
    setStatus("Run a check before downloading the PDF.", "bad");
    return;
  }
  const button = document.getElementById("btn-download");
  button.disabled = true;
  const previous = button.textContent;
  button.textContent = "Preparing PDF…";
  try {
    const body = new FormData();
    body.set("job", jobInput.value);
    body.set("resume", pdfFile ? "" : resumeInput.value);
    if (pdfFile) body.set("resume_file", pdfFile);
    const response = await fetch("/api/report.pdf", { method: "POST", body });
    if (!response.ok) {
      let detail = "Could not build the PDF.";
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") detail = payload.detail;
      } catch {
        /* The failure body is not always JSON. */
      }
      throw new Error(detail);
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "resume-doctor-report.pdf";
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    setStatus("Saved resume-doctor-report.pdf.");
  } catch (error) {
    setStatus(error.message || "Could not build the PDF.", "bad");
  } finally {
    button.disabled = false;
    button.textContent = previous;
  }
}

function resetChart() {
  latestReport = null;
  scoreEl.textContent = "—";
  bandEl.textContent = "Waiting for a resume";
  pageNote.textContent = "400–900 words is the readable range. One page if you are early in your career, two if you are not.";
  scorecard.dataset.tone = "idle";
  toolsEl.hidden = true;
  nextEl.hidden = true;
  nextList.textContent = "";
  keywordLead.textContent = "Missing ones are listed first, the ones the job repeats most often at the front.";
  barsEl.innerHTML = "";
  ["Sections|0/25", "Keywords|0/35", "Measurable impact|0/20", "Action verbs|0/10", "Length and clarity|0/10"].forEach((row) => {
    const [name, score] = row.split("|");
    const li = document.createElement("li");
    li.innerHTML = `<div class="bar-top"><span></span><span></span></div><div class="track"><span class="fill"></span></div>`;
    li.querySelectorAll("span")[0].textContent = name;
    li.querySelectorAll("span")[1].textContent = score;
    barsEl.append(li);
  });
  pillsEl.textContent = "";
  const placeholder = document.createElement("p");
  placeholder.className = "placeholder";
  placeholder.textContent = "They show up here after a check.";
  pillsEl.append(placeholder);
  fixesEl.textContent = "";
  const example = document.createElement("article");
  example.className = "fix example";
  example.innerHTML = "<p class=\"fix-kind\">What a fix looks like</p>";
  const quote = document.createElement("blockquote");
  quote.textContent = "Responsible for weekly reporting";
  const suggestion = document.createElement("p");
  suggestion.className = "fix-suggestion";
  suggestion.textContent = "Start with “Owned” instead of “responsible for”. Then add a number: time saved, % improved, users reached, or ₹ value.";
  example.append(quote, suggestion);
  fixesEl.append(example);
  setStatus("Score cleared.");
}

function updateMeters() {
  const resumeWords = wordCount(resumeInput.value);
  const jobWords = wordCount(jobInput.value);
  if (!pdfFile) {
    resumeCount.textContent = `${resumeWords} word${resumeWords === 1 ? "" : "s"}`;
    if (!resumeWords) {
      resumeRange.textContent = "Aim for 400–900";
      delete resumeMeter.dataset.tone;
    } else if (resumeWords < 400) {
      resumeRange.textContent = "Short of the 400–900 range";
      resumeMeter.dataset.tone = "warn";
    } else if (resumeWords > 900) {
      resumeRange.textContent = "Over the 400–900 range";
      resumeMeter.dataset.tone = "bad";
    } else {
      resumeRange.textContent = "In the 400–900 range";
      resumeMeter.dataset.tone = "good";
    }
  }
  jobCount.textContent = `${jobWords} word${jobWords === 1 ? "" : "s"}`;
}

function wordCount(text) {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

function clip(text, limit) {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= limit) return compact;
  return compact.slice(0, limit - 1).trimEnd() + "…";
}

function setStatus(message, tone) {
  statusEl.textContent = message;
  if (tone) statusEl.dataset.tone = tone;
  else delete statusEl.dataset.tone;
}
