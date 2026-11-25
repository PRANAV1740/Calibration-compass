"use strict";

/* ----------------------------- API base ----------------------------- */

const DEFAULT_BACKENDS = ["ibm_fez", "ibm_kingston", "ibm_marrakesh"];

const FALLBACK_PRESETS = {
  bell: 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
  ghz: 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0],q[1];\ncx q[1],q[2];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\nmeasure q[2] -> c[2];',
  ring: 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0],q[1];\ncx q[1],q[2];\ncx q[2],q[0];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\nmeasure q[2] -> c[2];',
};

let PRESETS = { ...FALLBACK_PRESETS };
let BACKENDS = [...DEFAULT_BACKENDS];

function getApiBase() {
  let stored = null;
  try { stored = localStorage.getItem("cc_api_base"); } catch (e) {}
  const configured = (window.CC_CONFIG && window.CC_CONFIG.apiBase) || "";
  return (stored || configured || "").replace(/\/+$/, "");
}

function setApiBase(value) {
  try { localStorage.setItem("cc_api_base", value.replace(/\/+$/, "")); } catch (e) {}
}

async function api(path, options) {
  const base = getApiBase();
  if (!base) throw new Error("Set the Backend URL first (top right).");
  const res = await fetch(base + path, options);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = { detail: text }; }
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText;
    throw new Error(detail);
  }
  return data;
}

/* ----------------------------- Elements ----------------------------- */

const el = (id) => document.getElementById(id);
const apiBaseInput = el("apiBase");
const healthDot = el("healthDot");
const qasmArea = el("qasm");
const backendList = el("backendList");
const analyzeBtn = el("analyzeBtn");
const errorBox = el("error");
const results = el("results");

/* ----------------------------- Init ----------------------------- */

function renderBackendChecks() {
  backendList.innerHTML = "";
  BACKENDS.forEach((name) => {
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = name;
    cb.checked = true;
    label.appendChild(cb);
    label.appendChild(document.createTextNode(name));
    backendList.appendChild(label);
  });
}

async function checkHealth() {
  try {
    const data = await api("/api/health", { method: "GET" });
    healthDot.className = "dot ok";
    healthDot.title = "Backend reachable";
    if (Array.isArray(data.backends) && data.backends.length) {
      BACKENDS = data.backends;
      renderBackendChecks();
    }
  } catch (e) {
    healthDot.className = "dot bad";
    healthDot.title = "Backend unreachable: " + e.message;
  }
}

async function loadPresets() {
  try {
    const data = await api("/api/presets", { method: "GET" });
    if (data.presets) PRESETS = data.presets;
    if (Array.isArray(data.backends) && data.backends.length) {
      BACKENDS = data.backends;
      renderBackendChecks();
    }
  } catch (e) { /* keep fallbacks */ }
}

function selectedBackends() {
  return Array.from(backendList.querySelectorAll("input:checked")).map((c) => c.value);
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}
function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }

/* ----------------------------- Rendering ----------------------------- */

function metric(label, value) {
  return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
}

function fmt(x, digits) {
  if (x === null || x === undefined || Number.isNaN(x)) return "N/A";
  return Number(x).toFixed(digits);
}

function renderTable(tableEl, rows, columns) {
  if (!rows || !rows.length) { tableEl.innerHTML = ""; return; }
  const cols = columns || Object.keys(rows[0]);
  const head = "<thead><tr>" + cols.map((c) => `<th>${c}</th>`).join("") + "</tr></thead>";
  const body = "<tbody>" + rows.map((r) =>
    "<tr>" + cols.map((c) => `<td>${r[c] === null || r[c] === undefined ? "" : r[c]}</td>`).join("") + "</tr>"
  ).join("") + "</tbody>";
  tableEl.innerHTML = head + body;
}

let currentReco = null;
let currentQasm = "";

function renderResults(data) {
  results.hidden = false;
  currentReco = data.recommendation;
  currentQasm = qasmArea.value;

  // reset QPU area
  el("jobInfo").hidden = true;
  el("qpuResult").hidden = true;

  // 3. circuit analysis
  const c = data.circuit;
  el("circuitMetrics").innerHTML =
    metric("Logical qubits", c.logical_qubits) +
    metric("Original depth", c.depth) +
    metric("Operations", c.operations);
  el("circuitDiagram").textContent = c.diagram || "";

  // 4. backend status
  const statusCard = el("statusCard");
  if (data.status && data.status.length) {
    statusCard.hidden = false;
    renderTable(el("statusTable"), data.status,
      ["Backend", "Status", "Operational", "Pending jobs"]);
  } else {
    statusCard.hidden = true;
  }

  const recoCard = el("recoCard");
  const rankedCard = el("rankedCard");

  if (!data.recommendation) {
    recoCard.hidden = true;
    rankedCard.hidden = true;
    showError(data.message || "No recommendation could be produced.");
    return;
  }
  clearError();
  recoCard.hidden = false;

  // 5. recommendation
  const r = data.recommendation;
  el("recoMain").textContent = `${r.backend} · Candidate ${r.candidate}`;
  el("recoQubits").textContent = `Physical qubits: [${(r.physical_qubits || []).join(", ")}]`;
  el("recoRisk").textContent = fmt(r.combined_risk, 6);

  // confidence
  const conf = data.confidence || {};
  el("confidenceMetrics").innerHTML =
    metric("Assessment", conf.label || "N/A") +
    metric("Risk margin", conf.margin === null || conf.margin === undefined ? "N/A" : fmt(conf.margin, 6)) +
    metric("Final candidates", conf.final_candidates != null ? conf.final_candidates : "N/A");

  const note = el("confidenceNote");
  const notes = {
    "Close call": ["warn", "Close call: the top candidates have very similar calibration risk. Treat the recommendation as a preference, not a guarantee."],
    "Moderate preference": ["", "Moderate preference: the recommended candidate has a noticeable calibration-risk advantage."],
    "Strong preference": ["good", "Strong preference: the recommended candidate has a clear calibration-risk advantage."],
  };
  if (notes[conf.label]) {
    note.className = "note " + notes[conf.label][0];
    note.textContent = notes[conf.label][1];
    note.hidden = false;
  } else {
    note.hidden = true;
  }

  // KPIs
  el("kpiMetrics").innerHTML =
    metric("Readout loss", fmt(r.readout_loss, 5)) +
    metric("Gate loss", fmt(r.gate_loss, 5)) +
    metric("2Q gates", r["2Q_gates"]) +
    metric("Compiled depth", r.depth);

  el("whyText").innerHTML =
    `CalibrationCompass selected <b>${r.backend} candidate ${r.candidate}</b> because it has ` +
    `the lowest combined live calibration risk among the ${conf.final_candidates} final candidates.`;

  // ranked candidates
  if (data.results && data.results.length) {
    rankedCard.hidden = false;
    const rows = data.results.map((row) => ({
      backend: row.backend,
      candidate: row.candidate,
      combined_risk: fmt(row.combined_risk, 6),
      readout_loss: fmt(row.readout_loss, 5),
      gate_loss: fmt(row.gate_loss, 5),
      "2Q_gates": row["2Q_gates"],
      depth: row.depth,
    }));
    renderTable(el("rankedTable"), rows,
      ["backend", "candidate", "combined_risk", "readout_loss", "gate_loss", "2Q_gates", "depth"]);
  } else {
    rankedCard.hidden = true;
  }

  recoCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ----------------------------- Actions ----------------------------- */

async function analyze() {
  clearError();
  const backends = selectedBackends();
  if (!backends.length) { showError("Select at least one backend."); return; }
  if (!qasmArea.value.trim()) { showError("Enter or choose a circuit first."); return; }

  const original = analyzeBtn.innerHTML;
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = '<span class="spinner"></span>Refreshing calibration data…';
  try {
    const data = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qasm: qasmArea.value, backends }),
    });
    renderResults(data);
  } catch (e) {
    results.hidden = true;
    showError(e.message);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = original;
  }
}

async function runQpu() {
  if (!currentReco) return;
  const btn = el("runQpuBtn");
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Submitting job to IBM Quantum…';
  try {
    const data = await api("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        qasm: currentQasm,
        backend: currentReco.backend,
        candidate_seed: currentReco.candidate,
        shots: 512,
      }),
    });
    el("jobId").textContent = data.job_id;
    el("jobInfo").hidden = false;
    el("qpuResult").hidden = true;
  } catch (e) {
    el("qpuResult").className = "note bad";
    el("qpuResult").textContent = "QPU submission failed: " + e.message;
    el("qpuResult").hidden = false;
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

function renderCounts(counts) {
  let html = "";
  for (const [reg, dist] of Object.entries(counts)) {
    html += `<div style="margin-top:0.5rem"><b>${reg}</b><div class="counts-grid">`;
    for (const [bits, n] of Object.entries(dist)) {
      html += `<div class="count-cell"><div class="bits">${bits}</div><div class="n">${n}</div></div>`;
    }
    html += "</div></div>";
  }
  return html;
}

async function checkResult() {
  const jobId = el("jobId").textContent;
  if (!jobId) return;
  const box = el("qpuResult");
  const btn = el("checkResultBtn");
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Checking…';
  try {
    const data = await api("/api/result/" + encodeURIComponent(jobId), { method: "GET" });
    box.hidden = false;
    if (data.ready) {
      box.className = "note good";
      box.innerHTML = "<b>QPU result is ready.</b> Measurement counts by register:" + renderCounts(data.counts);
    } else if (data.terminal) {
      box.className = "note bad";
      box.innerHTML = `QPU job finished without results. Status: ${data.status}` +
        (data.error ? `<div class="muted">IBM Runtime details: ${data.error}</div>` : "");
    } else {
      box.className = "note";
      box.textContent = `Job is not finished yet. Current status: ${data.status}`;
    }
  } catch (e) {
    box.hidden = false;
    box.className = "note bad";
    box.textContent = "Could not retrieve result: " + e.message;
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

/* ----------------------------- Wire-up ----------------------------- */

document.querySelectorAll("[data-preset]").forEach((b) => {
  b.addEventListener("click", () => {
    const key = b.getAttribute("data-preset");
    qasmArea.value = PRESETS[key] || FALLBACK_PRESETS[key] || "";
  });
});

el("qasmFile").addEventListener("change", (ev) => {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { qasmArea.value = reader.result; };
  reader.readAsText(file);
});

analyzeBtn.addEventListener("click", analyze);
el("runQpuBtn").addEventListener("click", runQpu);
el("checkResultBtn").addEventListener("click", checkResult);

apiBaseInput.addEventListener("change", async () => {
  setApiBase(apiBaseInput.value.trim());
  await checkHealth();
  await loadPresets();
});

// boot
(function init() {
  apiBaseInput.value = getApiBase();
  qasmArea.value = FALLBACK_PRESETS.ghz;
  renderBackendChecks();
  if (getApiBase()) { checkHealth(); loadPresets(); }
})();
