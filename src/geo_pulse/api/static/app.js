const form = document.querySelector("#analysis-form");
const statusBox = document.querySelector("#status");
const errorBox = document.querySelector("#error");
const results = document.querySelector("#results");

for (const id of ["properties", "amenities"]) {
  document.querySelector(`#${id}`).addEventListener("change", (event) => {
    document.querySelector(`#${id}-name`).textContent = event.target.files[0]?.name || "Choose file";
  });
}

function setStatus(text, state) {
  statusBox.textContent = text;
  statusBox.className = `status ${state}`;
  errorBox.hidden = true;
}

function fillList(selector, values) {
  const list = document.querySelector(selector);
  list.replaceChildren(...values.map((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    return item;
  }));
}

function showResult(payload) {
  document.querySelector("#run-id").textContent = `RUN ${payload.run_id}`;
  document.querySelector("#summary").textContent = payload.summary;
  fillList("#findings", payload.findings);
  fillList("#limitations", payload.limitations);
  const reportUrl = `/reports/${payload.run_id}/report`;
  const mapUrl = `/reports/${payload.run_id}/map`;
  document.querySelector("#report-link").href = reportUrl;
  document.querySelector("#map-link").href = mapUrl;
  document.querySelector("#model-link").href = `/models/${payload.run_id}`;
  document.querySelector("#map-frame").src = mapUrl;
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
  setStatus(payload.status === "completed" ? "Analysis complete" : "Completed with limitations", "done");
}

async function submit(endpoint, options = {}) {
  setStatus("Running spatial pipeline…", "running");
  results.hidden = true;
  try {
    const response = await fetch(endpoint, { method: "POST", ...options });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || "Analysis failed");
    showResult(payload);
  } catch (error) {
    setStatus("Analysis failed", "failed");
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submit("/analyses/upload", { body: new FormData(form) });
});

document.querySelector("#demo-button").addEventListener("click", () => {
  const question = encodeURIComponent(document.querySelector("#question").value);
  submit(`/analyses/demo?question=${question}`);
});

async function refreshSourceStatus() {
  try {
    const response = await fetch("/sources/status");
    const status = await response.json();
    const census = status.census_api_key_configured ? "Census ready" : "Census key needed";
    const kaggle = status.kagglehub_installed ? "Kaggle ready" : "Kaggle package missing";
    const osm = status.osmnx_installed ? "OSM ready" : "OSM package missing";
    document.querySelector("#source-badges").textContent = `${kaggle} · ${osm} · ${census}`;
  } catch {
    document.querySelector("#source-badges").textContent = "Source status unavailable";
  }
}

document.querySelector("#external-button").addEventListener("click", () => {
  const payload = {
    question: document.querySelector("#question").value,
    kaggle_dataset: document.querySelector("#kaggle-dataset").value,
    kaggle_filename: document.querySelector("#kaggle-filename").value,
    census_year: Number(document.querySelector("#census-year").value),
    max_rows: Number(document.querySelector("#max-rows").value),
  };
  submit("/analyses/external", {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
});

refreshSourceStatus();
