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

const KIND = {
  section: "Section",
  keyword: "Keyword",
  metric: "Metric",
  verb: "Verb",
  clarity: "Clarity",
  length: "Length",
};

let pdfFile = null;
let latestMarkdown = "";
let scoreFrame = 0;

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
  setStatus("");
}

function clearFile() {
  pdfFile = null;
  fileInput.value = "";
  fileNote.hidden = true;
  fileNote.textContent = "";
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
    latestMarkdown = payload.markdown || "";
    renderReport(payload.report);
    const fixes = (payload.report.fixes || []).length;
    setStatus(`Score ${payload.report.score} out of 100. ${fixes} fix${fixes === 1 ? "" : "es"}.`);
    if (window.matchMedia("(max-width: 860px)").matches) {
      document.getElementById("chart").scrollIntoView({ behavior: "smooth", block: "start" });
    }
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
  renderPills(report.keywords || []);
  renderFixes(report.fixes || []);
  toolsEl.hidden = false;
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
  [...missing, ...present].forEach((item) => {
    const pill = document.createElement("span");
    pill.className = "pill" + (item.in_resume ? "" : " missing");
    pill.title = item.in_resume ? "Found in the resume" : "Not in the resume";
    const term = document.createElement("span");
    term.textContent = item.term;
    const count = document.createElement("em");
    count.textContent = String(item.jd_count);
    pill.append(term, count);
    pillsEl.append(pill);
  });
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
  fixes.forEach((fix) => {
    const card = document.createElement("article");
    card.className = `fix ${fix.kind || ""}`;
    const kind = document.createElement("p");
    kind.className = "fix-kind";
    kind.textContent = KIND[fix.kind] || "Fix";
    card.append(kind);
    if (fix.text) {
      const quote = document.createElement("blockquote");
      quote.textContent = fix.text;
      card.append(quote);
    }
    const suggestion = document.createElement("p");
    suggestion.className = "fix-suggestion";
    suggestion.textContent = fix.suggestion;
    card.append(suggestion);
    fixesEl.append(card);
  });
}

function downloadReport() {
  if (!latestMarkdown) return;
  const blob = new Blob([latestMarkdown], { type: "text/markdown" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "resume-doctor-report.md";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function resetChart() {
  latestMarkdown = "";
  scoreEl.textContent = "—";
  bandEl.textContent = "Waiting for a resume";
  pageNote.textContent = "400–900 words is the readable range. One page if you are early in your career, two if you are not.";
  scorecard.dataset.tone = "idle";
  toolsEl.hidden = true;
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

function setStatus(message, tone) {
  statusEl.textContent = message;
  if (tone) statusEl.dataset.tone = tone;
  else delete statusEl.dataset.tone;
}
