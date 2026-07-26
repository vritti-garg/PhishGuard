// ============================================================
// PhishGuard frontend logic
// Talks to the FastAPI backend (app.py) running locally.
// Change API_BASE if your backend runs on a different host/port.
// ============================================================

const API_BASE = "https://phishguard-iih7.onrender.com/";

// ---------- Tab switching ----------

const tabs = document.querySelectorAll(".tab");
const views = document.querySelectorAll(".view");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.view));
  tab.addEventListener("keypress", (e) => {
    if (e.key === "Enter" || e.key === " ") switchTab(tab.dataset.view);
  });
});

function switchTab(viewName) {
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.view === viewName));
  views.forEach((v) => v.classList.toggle("active", v.id === `view-${viewName}`));

  if (viewName === "results") loadResultsList();
  if (viewName === "dashboard") loadDashboard();
}

// ---------- Upload view ----------

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const dropzoneText = document.getElementById("dropzoneText");
const uploadResultCard = document.getElementById("uploadResultCard");

dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

async function handleFile(file) {
  if (!file.name.endsWith(".eml")) {
    showUploadError("Only .eml files are supported.");
    return;
  }

  dropzone.classList.add("scanning");
  dropzoneText.textContent = `Analyzing ${file.name}...`;
  uploadResultCard.style.display = "none";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${response.status})`);
    }

    const result = await response.json();
    renderUploadResult(result);
  } catch (err) {
    showUploadError(`Analysis failed: ${err.message}. Is the backend running at ${API_BASE}?`);
  } finally {
    dropzone.classList.remove("scanning");
    dropzoneText.textContent = "Drop a .eml file here, or click to browse";
    fileInput.value = "";
  }
}

function showUploadError(message) {
  uploadResultCard.style.display = "block";
  uploadResultCard.innerHTML = `<div class="reasoning-box" style="color:var(--danger);">${escapeHtml(message)}</div>`;
}

function renderUploadResult(result) {
  uploadResultCard.style.display = "block";
  uploadResultCard.innerHTML = buildDetailHtml(result);
}

// ---------- Results view ----------

const resultsListCard = document.getElementById("resultsListCard");
const resultsDetailCard = document.getElementById("resultsDetailCard");

async function loadResultsList() {
  resultsDetailCard.style.display = "none";
  resultsListCard.innerHTML = `<div class="empty-state">Loading...</div>`;

  try {
    const response = await fetch(`${API_BASE}/api/analyses`);
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    const analyses = await response.json();

    if (analyses.length === 0) {
      resultsListCard.innerHTML = `<div class="empty-state">No emails analyzed yet. Upload one from the Upload tab.</div>`;
      return;
    }

    resultsListCard.innerHTML = analyses
      .map(
        (a) => `
      <div class="result-row" data-id="${a.id}">
        <div class="result-meta">
          <span class="result-subject">${escapeHtml(a.subject)}</span>
          <span class="result-sender">${escapeHtml(a.sender)}</span>
        </div>
        <span class="badge ${a.verdict}">${a.verdict}</span>
      </div>`
      )
      .join("");

    resultsListCard.querySelectorAll(".result-row").forEach((row) => {
      row.addEventListener("click", () => loadResultDetail(row.dataset.id));
    });
  } catch (err) {
    resultsListCard.innerHTML = `<div class="empty-state">Couldn't load results. Is the backend running at ${API_BASE}?</div>`;
  }
}

async function loadResultDetail(id) {
  try {
    const response = await fetch(`${API_BASE}/api/analyses/${id}`);
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    const result = await response.json();

    resultsDetailCard.style.display = "block";
    resultsDetailCard.innerHTML = buildDetailHtml(result);
    resultsDetailCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (err) {
    resultsDetailCard.style.display = "block";
    resultsDetailCard.innerHTML = `<div class="reasoning-box" style="color:var(--danger);">Couldn't load this record.</div>`;
  }
}

// Shared renderer used by both the upload result and the results detail view
function buildDetailHtml(a) {
  const confidencePct = Math.round((a.confidence || 0) * 100);
  const reviewFlag = a.manual_review_required
    ? `<div class="reasoning-box" style="color:var(--warning);">⚠ Automated analysis was inconclusive — flagged for manual review.</div>`
    : "";

  return `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <span class="badge ${a.verdict}">${a.verdict}</span>
      <a class="secondary" style="text-decoration:none;" href="${API_BASE}/api/analyses/${a.id}/report" target="_blank">
        <button class="secondary" type="button">Download PDF report</button>
      </a>
    </div>
    <div class="detail-field"><span class="label">Sender</span><span class="value">${escapeHtml(a.sender)}</span></div>
    <div class="detail-field"><span class="label">Subject</span><span class="value">${escapeHtml(a.subject)}</span></div>
    <div class="detail-field"><span class="label">Technique</span><span class="value">${escapeHtml(a.technique.replaceAll("_", " "))}</span></div>
    <div class="detail-field"><span class="label">Severity</span><span class="value">${escapeHtml(a.severity)}</span></div>
    <div class="detail-field"><span class="label">Confidence</span><span class="value">${confidencePct}%</span></div>
    <div class="detail-field"><span class="label">Analyzed at</span><span class="value">${escapeHtml(a.analyzed_at || "")}</span></div>
    ${reviewFlag}
    <div class="reasoning-box"><strong>Reasoning:</strong> ${escapeHtml(a.reasoning)}</div>
    ${a.coaching_message ? `<div class="coaching-box"><strong>Coaching note:</strong> ${escapeHtml(a.coaching_message)}</div>` : ""}
  `;
}

// ---------- Dashboard view ----------

let techniqueChartInstance = null;
let trendChartInstance = null;

async function loadDashboard() {
  const statGrid = document.getElementById("statGrid");

  try {
    const response = await fetch(`${API_BASE}/api/dashboard`);
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    const data = await response.json();

    // Stat cards
    const counts = data.verdict_counts || {};
    statGrid.innerHTML = `
      <div class="stat-card phishing">
        <div class="stat-number">${counts.phishing || 0}</div>
        <div class="stat-label">Phishing</div>
      </div>
      <div class="stat-card suspicious">
        <div class="stat-number">${counts.suspicious || 0}</div>
        <div class="stat-label">Suspicious</div>
      </div>
      <div class="stat-card legitimate">
        <div class="stat-number">${counts.legitimate || 0}</div>
        <div class="stat-label">Legitimate</div>
      </div>
    `;

    // Top techniques bar chart
    const techniques = data.top_techniques || [];
    const techCtx = document.getElementById("techniqueChart");
    if (techniqueChartInstance) techniqueChartInstance.destroy();
    techniqueChartInstance = new Chart(techCtx, {
      type: "bar",
      data: {
        labels: techniques.map((t) => t.technique.replaceAll("_", " ")),
        datasets: [{ label: "Occurrences", data: techniques.map((t) => t.count), backgroundColor: "#2a6f77" }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });

    // Trend over time line chart
    const trend = data.trend_over_time || [];
    const trendCtx = document.getElementById("trendChart");
    if (trendChartInstance) trendChartInstance.destroy();
    trendChartInstance = new Chart(trendCtx, {
      type: "line",
      data: {
        labels: trend.map((t) => t.date),
        datasets: [
          { label: "Phishing", data: trend.map((t) => t.phishing), borderColor: "#c4392b", tension: 0.2 },
          { label: "Suspicious", data: trend.map((t) => t.suspicious), borderColor: "#b8832a", tension: 0.2 },
          { label: "Legitimate", data: trend.map((t) => t.legitimate), borderColor: "#2f7a4d", tension: 0.2 },
        ],
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });

  } catch (err) {
    statGrid.innerHTML = `<div class="empty-state">Couldn't load dashboard. Is the backend running at ${API_BASE}?</div>`;
  }
}

// ---------- Utility ----------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}