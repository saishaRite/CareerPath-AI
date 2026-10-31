const $ = (id) => document.getElementById(id);
let latestAnalysis = null;
let resumeText = "";
const questions = [
  "Explain the difference between an array and a linked list. When would you choose one over the other?",
  "Describe a technical project you built. What trade-offs did you make and what would you improve?",
  "How would you debug an API endpoint that suddenly became slow?",
  "Explain how a hash map works and discuss a situation where collisions matter.",
  "Tell me about a time you had to learn a new technology quickly. How did you approach it?"
];
let questionIndex = 0;

function toast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2600);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed. Please try again.");
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function go(view) {
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  document.querySelectorAll(".nav-link").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  const titles = {
    overview: "Your career overview", analyzer: "Career analyzer", roadmap: "Learning roadmap",
    projects: "Project studio", interview: "Mock interview", applications: "Application tracker"
  };
  if ($("page-title")) $("page-title").textContent = titles[view] || "CareerPath AI";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll("[data-view]").forEach(b => b.addEventListener("click", () => go(b.dataset.view)));
document.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => go(b.dataset.go)));
if ($("today")) {
  $("today").textContent = new Date().toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

async function init() {
  try {
    const health = await api("/api/health");
    if ($("mode-label")) {
      $("mode-label").textContent = health.ai_mode || "Backend connected";
      $("mode-label").title = health.ai_configured
        ? `Gemini key detected. Model: ${health.model || "configured model"}.`
        : "Gemini key not detected. Local fallback is active.";
    }
    if (!health.ai_configured) {
      toast("Gemini is not configured. The app is using local fallback responses.");
    }
  } catch (err) {
    if ($("mode-label")) $("mode-label").textContent = "Backend unavailable";
    toast("Cannot connect to the backend. Check that Uvicorn is running.");
  }
  await refreshDashboard();
  await loadApplications();
}

if ($("resume-file")) {
  $("resume-file").addEventListener("change", async e => {
    const file = e.target.files[0];
    if (!file) return;
    if ($("file-label")) $("file-label").textContent = "Reading PDF…";
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api("/api/resume/parse", { method: "POST", body: form });
      resumeText = result.text;
      if ($("file-label")) $("file-label").textContent = `${result.filename} · text extracted successfully`;
      toast("Resume text extracted.");
    } catch (err) {
      resumeText = "";
      if ($("file-label")) $("file-label").textContent = err.message;
      toast(err.message);
    }
  });
}

if ($("analyze-btn")) {
  $("analyze-btn").addEventListener("click", async () => {
    const target_role = $("target-role").value.trim();
    const job_description = $("job-description").value.trim();
    if (target_role.length < 2) return toast("Enter a target role.");
    if (job_description.length < 30) return toast("Paste a real job description (at least 30 characters).");
    const manual_skills = $("manual-skills").value.split(",").map(x => x.trim()).filter(Boolean);
    const btn = $("analyze-btn");
    btn.disabled = true;
    btn.textContent = "Analyzing profile…";
    try {
      latestAnalysis = await api("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: $("student-name").value.trim() || "Student",
          target_role,
          job_description,
          resume_text: resumeText,
          manual_skills
        })
      });
      renderAnalysis(latestAnalysis);
      if ($("profile-name")) $("profile-name").firstChild.textContent = $("student-name").value.trim() || "Student";
      if ($("avatar")) $("avatar").textContent = ($("student-name").value.trim() || "S")[0].toUpperCase();
      toast("Career analysis complete.");
      await refreshDashboard();
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Analyze my career fit <span>→</span>';
    }
  });
}

function renderAnalysis(a) {
  const box = $("analysis-results");
  if (!box) return;
  box.classList.remove("hidden");
  const chips = (items, cls = "") => (items || []).map(x => `<span class="skill ${cls}">${escapeHtml(x)}</span>`).join("");
  box.innerHTML = `
    <div class="result-hero">
      <div>
        <div class="eyebrow light">${escapeHtml(a.mode || "Career analysis")} · ROLE MATCH</div>
        <h3>${escapeHtml(a.target_role)}</h3><p>${escapeHtml(a.summary)}</p>
      </div>
      <div class="score-ring" style="--score:${Number(a.score) || 0}%"><strong>${Number(a.score) || 0}</strong></div>
    </div>
    <div class="result-columns">
      <div class="result-box"><h4>Detected strengths</h4><div class="skill-row">${chips(a.matched_skills)}</div><p>${(a.strengths || []).map(escapeHtml).join(" · ") || "Add more verified skills to your profile."}</p></div>
      <div class="result-box"><h4>Priority skill gaps</h4><div class="skill-row">${chips(a.missing_skills, "gap")}</div><p>Gaps are based on detected terms in the supplied job description. Review them before making decisions.</p></div>
    </div>
    <div class="result-box" style="margin-top:13px"><h4>Recommended next actions</h4><ul>${(a.recommendations || []).map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul><button class="btn btn-primary" id="result-roadmap">Build my learning roadmap →</button></div>`;
  $("result-roadmap").addEventListener("click", () => { go("roadmap"); generateRoadmap(); });
}

if ($("generate-roadmap")) $("generate-roadmap").addEventListener("click", generateRoadmap);

async function generateRoadmap() {
  try {
    const data = await api("/api/roadmap/generate", { method: "POST" });
    renderTasks(data.tasks || []);
    toast("Learning roadmap generated.");
    await refreshDashboard();
  } catch (err) {
    toast(err.message);
  }
}

async function loadRoadmap() {
  try { renderTasks(await api("/api/roadmap")); } catch (err) { console.error(err); }
}

function renderTasks(tasks) {
  const box = $("roadmap-content");
  if (!box) return;
  if (!tasks || !tasks.length) {
    box.className = "empty-state";
    box.textContent = "No roadmap yet. Run career analysis first.";
    return;
  }
  box.className = "";
  const weeks = [...new Set(tasks.map(t => t.week))].sort((a, b) => a - b);
  box.innerHTML = weeks.map(week => `<div class="task-week"><h3 class="week-title">WEEK ${week}</h3>${tasks.filter(t => t.week === week).map(t => `
    <div class="task ${t.status === "done" ? "done" : ""}"><input type="checkbox" data-task="${t.id}" ${t.status === "done" ? "checked" : ""}><div><strong>${escapeHtml(t.title)}</strong><p>${escapeHtml(t.description)}</p>${t.resource ? `<a href="${escapeHtml(t.resource)}" target="_blank" rel="noopener noreferrer">Open learning resource ↗</a>` : ""}</div></div>`).join("")}</div>`).join("");
  box.querySelectorAll("[data-task]").forEach(input => input.addEventListener("change", async () => {
    try {
      await api(`/api/tasks/${input.dataset.task}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: input.checked ? "done" : "todo" })
      });
      input.closest(".task").classList.toggle("done", input.checked);
      await refreshDashboard();
    } catch (err) {
      input.checked = !input.checked;
      toast(err.message);
    }
  }));
}

if ($("load-projects")) {
  $("load-projects").addEventListener("click", async () => {
    const btn = $("load-projects");
    btn.disabled = true;
    try {
      const data = await api("/api/projects");
      const box = $("projects-content");
      if (!box) return;
      if (!data.projects.length) {
        box.innerHTML = '<div class="empty-state">Run career analysis first.</div>';
        return;
      }
      box.innerHTML = data.projects.map(p => `<article class="project-card"><span class="difficulty">${escapeHtml(p.difficulty || "Suggested")}</span><h3>${escapeHtml(p.title)}</h3><p>${escapeHtml(p.description)}</p><div class="skill-row">${(p.skills || []).map(s => `<span class="skill gap">${escapeHtml(s)}</span>`).join("")}</div></article>`).join("");
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
    }
  });
}

if ($("new-question")) {
  $("new-question").addEventListener("click", () => {
    questionIndex = (questionIndex + 1) % questions.length;
    $("question-text").textContent = questions[questionIndex];
    $("interview-answer").value = "";
    $("interview-feedback").innerHTML = "";
  });
}

function renderInterviewFeedback(result) {
  const feedback = $("interview-feedback");
  const dimensions = result.dimensions || {};
  const dimensionLabels = {
    relevance: "Relevance", technical_accuracy: "Technical accuracy", clarity: "Clarity",
    examples: "Examples", trade_offs: "Trade-offs"
  };
  const hasDimensionScores = Object.values(dimensions).some(v => Number.isFinite(Number(v)));
  const dimensionHtml = hasDimensionScores ? `
    <div class="interview-dimensions">
      ${Object.entries(dimensionLabels).map(([key, label]) => {
        const value = dimensions[key];
        return `<div class="dimension-row"><span>${label}</span><strong>${Number.isFinite(Number(value)) ? `${Number(value)}/10` : "Not scored"}</strong></div>`;
      }).join("")}
    </div>` : "";
  const strengths = (result.strengths || []).map(x => `<li>${escapeHtml(x)}</li>`).join("") || "<li>No specific strengths were returned.</li>";
  const improvements = (result.improvements || []).map(x => `<li>${escapeHtml(x)}</li>`).join("") || "<li>Try adding a concrete example and explaining your technical reasoning.</li>";
  feedback.innerHTML = `
    <div class="feedback">
      <div class="feedback-heading"><strong>Evaluation score: ${Number(result.score) || 0}/100</strong><span>${escapeHtml(result.evaluation_mode || "Evaluation")}</span></div>
      ${dimensionHtml}
      <p><b>Strengths</b></p><ul>${strengths}</ul>
      <p><b>Improvements</b></p><ul>${improvements}</ul>
      <p><b>How to improve your answer</b></p><p>${escapeHtml(result.model_answer || "Use a direct answer, technical reasoning, a concrete example, and a result.")}</p>
      ${result.notice ? `<p class="muted">${escapeHtml(result.notice)}</p>` : ""}
    </div>`;
}

if ($("evaluate-answer")) {
  $("evaluate-answer").addEventListener("click", async () => {
    const answer = $("interview-answer").value.trim();
    const role = $("target-role")?.value.trim() || "Software Engineer Intern";
    const question = $("question-text")?.textContent.trim() || "";
    if (answer.length < 10) return toast("Write at least 10 characters before submitting.");
    const btn = $("evaluate-answer");
    btn.disabled = true;
    btn.textContent = "Evaluating answer…";
    if ($("interview-feedback")) $("interview-feedback").innerHTML = '<div class="empty-state">Evaluating your answer. This may take a few seconds…</div>';
    try {
      const result = await api("/api/interview/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_role: role, question, answer })
      });
      renderInterviewFeedback(result);
    } catch (err) {
      if ($("interview-feedback")) $("interview-feedback").innerHTML = "";
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Evaluate my answer →";
    }
  });
}

if ($("application-form")) {
  $("application-form").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api("/api/applications", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: $("company").value.trim(),
          position: $("position").value.trim(),
          status: $("application-status").value,
          applied_date: $("applied-date").value
        })
      });
      e.target.reset();
      await loadApplications();
      await refreshDashboard();
      toast("Application added.");
    } catch (err) {
      toast(err.message);
    }
  });
}

async function loadApplications() {
  try {
    const rows = await api("/api/applications");
    const box = $("applications-list");
    if (!box) return;
    if (!rows.length) {
      box.innerHTML = '<div class="empty-state">No applications tracked yet. Add your first opportunity above.</div>';
      return;
    }
    box.innerHTML = rows.map(a => `<div class="application-row"><strong>${escapeHtml(a.company)}</strong><span>${escapeHtml(a.position)}</span><select data-app="${a.id}">${["Saved", "Applied", "Interview", "Offer", "Rejected"].map(s => `<option ${a.status === s ? "selected" : ""}>${s}</option>`).join("")}</select><span class="muted">${escapeHtml(a.applied_date || "")}</span></div>`).join("");
    box.querySelectorAll("[data-app]").forEach(sel => sel.addEventListener("change", async () => {
      try {
        await api(`/api/applications/${sel.dataset.app}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: sel.value })
        });
        toast("Application status updated.");
      } catch (err) {
        toast(err.message);
      }
    }));
  } catch (err) {
    console.error("Could not load applications:", err);
  }
}

async function refreshDashboard() {
  try {
    const [analysis, tasks, apps] = await Promise.all([
      api("/api/analysis/latest"), api("/api/roadmap"), api("/api/applications")
    ]);
    if ($("metric-score")) $("metric-score").innerHTML = analysis ? `${analysis.score}<small>/100</small>` : "—<small>/100</small>";
    if ($("metric-score-foot")) $("metric-score-foot").textContent = analysis ? "Detected skill match" : "Run your first analysis";
    if ($("metric-skills")) $("metric-skills").textContent = analysis ? analysis.current_skills.length : 0;
    if ($("metric-tasks")) $("metric-tasks").innerHTML = `${tasks.filter(t => t.status === "done").length}<small>/${tasks.length}</small>`;
    if ($("metric-apps")) $("metric-apps").textContent = apps.length;
    if (analysis) {
      if ($("overview-role")) $("overview-role").textContent = analysis.target_role;
      if ($("overview-summary")) $("overview-summary").textContent = analysis.summary;
      if ($("overview-skills")) {
        $("overview-skills").innerHTML = analysis.matched_skills.slice(0, 5).map(s => `<span class="skill">${escapeHtml(s)}</span>`).join("") + analysis.missing_skills.slice(0, 3).map(s => `<span class="skill gap">${escapeHtml(s)}</span>`).join("");
      }
    }
  } catch (err) {
    console.error("Dashboard refresh failed:", err);
  }
}

loadRoadmap();
init();
