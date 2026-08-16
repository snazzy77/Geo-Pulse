const form = document.querySelector("#surveillance-form");
const statusBox = document.querySelector("#status");
const errorBox = document.querySelector("#error");
const results = document.querySelector("#results");
const liveFields = document.querySelector("#live-mode-fields");
const customFields = document.querySelector("#custom-mode-fields");
const themeToggle = document.querySelector("#theme-toggle");
const themeColor = document.querySelector("#theme-color");
let stageTimer = null;

const THEME_STORAGE_KEY = "geo-pulse-theme";

function setTheme(theme, persist = true) {
  const selectedTheme = theme === "villain" ? "villain" : "hero";
  const isVillain = selectedTheme === "villain";
  document.documentElement.dataset.theme = selectedTheme;
  themeToggle.setAttribute("aria-checked", String(isVillain));
  themeToggle.setAttribute(
    "aria-label",
    isVillain ? "Switch to Light theme" : "Switch to Dark theme",
  );
  themeToggle.title = isVillain ? "Activate Light theme" : "Activate Dark theme";
  themeColor.content = isVillain ? "#0b0301" : "#010609";
  if (persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, selectedTheme);
    } catch {
      // The theme still works when browser storage is unavailable.
    }
  }
}

themeToggle.addEventListener("click", () => {
  setTheme(document.documentElement.dataset.theme === "villain" ? "hero" : "villain");
});

const stageLabels = {
  live: [
    "Fetch CDC PLACES, Census tracts, and OSM hazards",
    "Merge tract FIPS and build exposure buffers",
    "Fit population-offset Poisson model",
    "Detect spikes and run Moran's I",
    "Publish surveillance map and policy memo",
  ],
  custom: [
    "Validate uploaded health and pollution datasets",
    "Build industrial buffers and exposure scores",
    "Fit geographic Poisson surveillance model",
    "Detect spikes and run Moran's I",
    "Publish surveillance map and policy memo",
  ],
};

function currentMode() {
  return document.querySelector('input[name="analysis_mode"]:checked').value;
}

function setMode(mode) {
  const isLive = mode === "live";
  liveFields.hidden = !isLive;
  customFields.hidden = isLive;
  liveFields.querySelectorAll("input, select").forEach((field) => {
    field.disabled = !isLive;
  });
  customFields.querySelectorAll("input, select").forEach((field) => {
    field.disabled = isLive;
  });
  for (const id of ["outcomes", "hazards"]) {
    document.querySelector(`#${id}`).required = !isLive;
  }
  document.querySelector("#places-max-hazards").disabled = !isLive;
  document.querySelector("#hazard-limit-control").classList.toggle("mode-inactive", !isLive);
  document.querySelectorAll("#stages li").forEach((stage, index) => {
    stage.textContent = stageLabels[mode][index];
    stage.classList.remove("active", "complete", "failed");
  });
  setStatus(isLive ? "Ready for live federal streaming" : "Ready for custom uploads", "idle");
}

document.querySelectorAll('input[name="analysis_mode"]').forEach((control) => {
  control.addEventListener("change", (event) => setMode(event.target.value));
});

for (const id of ["outcomes", "hazards"]) {
  document.querySelector(`#${id}`).addEventListener("change", (event) => {
    const fallback = id === "outcomes" ? "Choose health file" : "Choose pollution file";
    document.querySelector(`#${id}-name`).textContent = event.target.files[0]?.name || fallback;
  });
}

document.querySelector("#alert-threshold").addEventListener("input", (event) => {
  document.querySelector("#alert-threshold-value").textContent =
    `${Number(event.target.value).toFixed(1)}σ`;
});

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

function startStageAnimation() {
  const stages = [...document.querySelectorAll("#stages li")];
  stages.forEach((stage) => stage.classList.remove("active", "complete", "failed"));
  let current = 0;
  stages[current].classList.add("active");
  stageTimer = window.setInterval(() => {
    if (current >= stages.length - 1) return;
    stages[current].classList.remove("active");
    stages[current].classList.add("complete");
    current += 1;
    stages[current].classList.add("active");
  }, 1400);
}

function finishStages(success) {
  window.clearInterval(stageTimer);
  const stages = [...document.querySelectorAll("#stages li")];
  if (success) {
    stages.forEach((stage) => {
      stage.classList.remove("active", "failed");
      stage.classList.add("complete");
    });
    return;
  }
  const active = stages.find((stage) => stage.classList.contains("active"));
  if (active) active.classList.add("failed");
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
  document.querySelector("#model-link").hidden = !payload.artifacts.model_summary;
  document.querySelector("#matrix-link").href = `/reports/${payload.run_id}/matrix`;
  document.querySelector("#matrix-link").hidden = !payload.artifacts.surveillance_matrix;
  document.querySelector("#map-frame").src = mapUrl;
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
  setStatus(
    payload.status === "completed" ? "Analysis complete" : "Completed with limitations",
    "done",
  );
}

async function submit(endpoint, options = {}) {
  setStatus("Running surveillance pipeline…", "running");
  results.hidden = true;
  startStageAnimation();
  document.querySelector("#command-center").scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
  try {
    const response = await fetch(endpoint, { method: "POST", ...options });
    const responseText = await response.text();
    let payload = {};
    try {
      payload = JSON.parse(responseText);
    } catch {
      throw new Error(responseText || "The server returned an invalid response");
    }
    if (!response.ok) throw new Error(payload.detail || payload.error || "Analysis failed");
    finishStages(true);
    showResult(payload);
  } catch (error) {
    finishStages(false);
    setStatus("Analysis failed", "failed");
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
}

function selectedDemographicControls() {
  return [...document.querySelectorAll('input[name="demographic_controls"]:checked')]
    .map((control) => control.value);
}

function selectedHazardTypes() {
  const selected = document.querySelector("#places-hazard-type").value;
  return selected === "all"
    ? ["industrial_zone", "factory", "refinery", "power_plant"]
    : [selected];
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const mode = currentMode();
  if (mode === "custom") {
    submit("/analyses/health-upload", { body: new FormData(form) });
    return;
  }
  const countyFips = document.querySelector("#places-county-fips").value.trim();
  if (!/^\d{5}$/.test(countyFips)) {
    setStatus("Enter a five-digit county FIPS", "failed");
    errorBox.textContent = "County FIPS must contain the two-digit state and three-digit county code.";
    errorBox.hidden = false;
    return;
  }
  submit("/analyses/places-live", {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: document.querySelector("#question").value,
      place: document.querySelector("#places-place").value.trim(),
      county_fips: countyFips,
      measure_id: document.querySelector("#places-measure").value,
      buffer_m: Number(document.querySelector("#buffer-m").value),
      alert_threshold: Number(document.querySelector("#alert-threshold").value),
      demographic_controls: selectedDemographicControls(),
      hazard_types: selectedHazardTypes(),
      max_hazards_per_type: Number(document.querySelector("#places-max-hazards").value),
    }),
  });
});

async function refreshSourceStatus() {
  try {
    const response = await fetch("/sources/status");
    const status = await response.json();
    const census = status.census_api_key_configured ? "Census ready" : "Census key needed";
    const osm = status.osmnx_installed ? "OSM ready" : "OSM package missing";
    const cdc = status.cdc_places_available ? "CDC PLACES ready" : "CDC unavailable";
    document.querySelector("#source-badges").textContent = `${cdc} · ${osm} · ${census}`;
  } catch {
    document.querySelector("#source-badges").textContent = "Live source status unavailable";
  }
}

setTheme(document.documentElement.dataset.theme, false);
setMode("live");
refreshSourceStatus();
