/* SunShift Flex — UI controller. All energy numbers come from /api/flex/plan. */
const state = {
  scenario: null,
  ai: null,
  plan: null,
  view: "coordinated",
  hour: 18,
  playing: false,
  playTimer: null,
  manualMode: false,
  activeSample: null,
  sampleConstraints: null,
  interpretation: null,
  receiptEventId: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const finePointerQuery = window.matchMedia("(hover: hover) and (pointer: fine)");
const HOME_COLORS = { amber: "#e6b65d", coral: "#c77d64", sky: "#9dbed1" };
const fmt = (number, digits = 1) => Number(number || 0).toLocaleString("en-AU", {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
});
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(body.error || `Request failed (${response.status})`);
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  } finally {
    window.clearTimeout(timer);
  }
}

async function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
}

function setMessage(message, kind = "") {
  const element = $("#planner-message");
  element.textContent = message;
  element.dataset.kind = kind;
}

function markerClass(value, goodWhenPositive = true) {
  if (Math.abs(value || 0) < 0.005) return "neutral";
  return (value > 0) === goodWhenPositive ? "good" : "bad";
}

function signed(number, digits = 1, suffix = "") {
  const value = Number(number || 0);
  const sign = value > 0 ? "+" : "";
  return `${sign}${fmt(value, digits)}${suffix}`;
}

function setAIStatus(kind, label) {
  const element = $("#ai-status");
  element.className = `ai-status ${kind}`;
  element.textContent = label;
  const ribbon = $("#ai-ribbon");
  ribbon.className = `ribbon-ai ${kind}`;
  ribbon.textContent = kind === "ready" ? "NEMOTRON READY" : kind === "working" ? "INTERPRETING" : "AI MANUAL";
}

function initRangeProgress() {
  $$('input[type="range"]').forEach((input) => {
    const sync = () => {
      const min = Number(input.min || 0);
      const max = Number(input.max || 100);
      const ratio = max > min ? ((Number(input.value) - min) / (max - min)) * 100 : 0;
      input.style.setProperty("--range-progress", `${ratio}%`);
    };
    input.addEventListener("input", sync);
    sync();
  });
}

function initHeroScene() {
  const scene = $("#hero-scene");
  if (!scene) return;
  scene.classList.add("scene-enter");
  window.setTimeout(() => scene.classList.remove("scene-enter"), 1000);
  const reset = () => {
    scene.classList.remove("is-tilting");
    scene.style.setProperty("--tilt-x", "0deg");
    scene.style.setProperty("--tilt-y", "0deg");
    scene.style.setProperty("--image-x", "0px");
    scene.style.setProperty("--image-y", "0px");
    scene.style.setProperty("--glare-x", "65%");
    scene.style.setProperty("--glare-y", "22%");
  };
  if (motionQuery.matches || !finePointerQuery.matches) return;
  scene.addEventListener("pointermove", (event) => {
    const rect = scene.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    scene.classList.add("is-tilting");
    scene.style.setProperty("--tilt-x", `${(-y * 3.4).toFixed(2)}deg`);
    scene.style.setProperty("--tilt-y", `${(x * 4.4).toFixed(2)}deg`);
    scene.style.setProperty("--image-x", `${(-x * 12).toFixed(1)}px`);
    scene.style.setProperty("--image-y", `${(-y * 8).toFixed(1)}px`);
    scene.style.setProperty("--glare-x", `${((x + 0.5) * 100).toFixed(1)}%`);
    scene.style.setProperty("--glare-y", `${((y + 0.5) * 100).toFixed(1)}%`);
  });
  scene.addEventListener("pointerleave", reset);
  scene.addEventListener("pointercancel", reset);
}

function initSurfaces() {
  if (motionQuery.matches || !finePointerQuery.matches) return;
  $$(".controls-panel, .story-card, .flex-stage-card, .compare-card, .chart-card").forEach((surface) => {
    const reset = () => {
      surface.style.setProperty("--spot-x", "72%");
      surface.style.setProperty("--spot-y", "-4%");
    };
    surface.addEventListener("pointermove", (event) => {
      const rect = surface.getBoundingClientRect();
      surface.style.setProperty("--spot-x", `${((event.clientX - rect.left) / rect.width) * 100}%`);
      surface.style.setProperty("--spot-y", `${((event.clientY - rect.top) / rect.height) * 100}%`);
    });
    surface.addEventListener("pointerleave", reset);
  });
}

function populateManualHours() {
  const options = ['<option value="">Off</option>'];
  for (let hour = 0; hour < 24; hour += 1) {
    options.push(`<option value="${hour}">${String(hour).padStart(2, "0")}:00</option>`);
  }
  $("#manual-start").innerHTML = options.join("");
  $("#manual-end").innerHTML = options.join("");
}

function syncManual(preferences) {
  $("#manual-reserve").value = Number(preferences.battery_reserve_pct ?? 40);
  $("#manual-local").checked = Boolean(preferences.prefer_local_before_export ?? true);
  $("#manual-evening").checked = Boolean(preferences.prioritise_neighbour_evening ?? true);
  $("#manual-start").value = preferences.no_discharge_start_hour ?? "";
  $("#manual-end").value = preferences.no_discharge_end_hour ?? "";
  updateManualLabels();
}

function updateManualLabels() {
  $("#manual-reserve-value").textContent = `${$("#manual-reserve").value}%`;
  const start = $("#manual-start").value;
  const end = $("#manual-end").value;
  $("#manual-window-value").textContent = start !== "" && end !== ""
    ? `${String(start).padStart(2, "0")}:00–${String(end).padStart(2, "0")}:00`
    : "Off";
}

function manualPreferences() {
  const start = $("#manual-start").value;
  const end = $("#manual-end").value;
  const hasWindow = start !== "" && end !== "";
  return {
    home_id: $("#your-home").value,
    battery_reserve_pct: Number($("#manual-reserve").value),
    prefer_local_before_export: $("#manual-local").checked,
    prioritise_neighbour_evening: $("#manual-evening").checked,
    no_discharge_start_hour: hasWindow ? Number(start) : null,
    no_discharge_end_hour: hasWindow ? Number(end) : null,
    source: "manual",
  };
}

function tariffValues() {
  return {
    import_c_kwh: Number($("#import-price").value),
    export_c_kwh: Number($("#export-price").value),
    shared_c_kwh: Number($("#shared-price").value),
    transfer_limit_kw: Number($("#transfer-limit").value),
  };
}

function updateTariffLabels() {
  $("#import-price-value").textContent = `${$("#import-price").value}¢/kWh`;
  $("#export-price-value").textContent = `${$("#export-price").value}¢/kWh`;
  $("#shared-price-value").textContent = `${$("#shared-price").value}¢/kWh`;
  $("#transfer-limit-value").textContent = `${$("#transfer-limit").value} kW`;
}

function renderScenario(scenario) {
  state.scenario = scenario;
  state.ai = scenario.ai;
  $("#region-name").textContent = scenario.region_name || "Three homes · South Australia";
  $("#source-label").textContent = scenario.source || "Illustrative synthetic profiles";
  $("#data-quality").textContent = "SIMULATED SCENARIO · NOT SETTLEMENT DATA";
  $("#your-home").innerHTML = scenario.homes.map((home) =>
    `<option value="${esc(home.id)}">${esc(home.name)}</option>`
  ).join("");
  $("#your-home").value = scenario.your_home;
  const samples = scenario.sample_preferences || [];
  $("#sample-chips").innerHTML = samples.map((sample) =>
    `<button type="button" class="sample-chip" data-sample-id="${esc(sample.id)}" title="${esc(sample.text)}">${esc(sample.label)}</button>`
  ).join("");
  if (samples.length) chooseSample(samples[0].id, false);
  else syncManual(scenario.default_preferences || {});
  $("#ai-model").textContent = `${scenario.ai?.model || "NVIDIA Nemotron"} · ${scenario.ai?.service || "Nebius Token Factory"}`;
  if (scenario.ai?.available) {
    setAIStatus("ready", "ready");
    $("#ai-note").textContent = "Nemotron reads your preference. The simulator calculates the energy.";
  } else {
    setAIStatus("unavailable", "unavailable");
    $("#ai-note").textContent = scenario.ai?.message || "Nemotron is unavailable. Manual sample constraints will be used; no model result is fabricated.";
  }
  renderInitialStage();
  updateTariffLabels();
  initRangeProgress();
}

function chooseSample(id, markStale = true) {
  const sample = state.scenario?.sample_preferences?.find((item) => item.id === id);
  if (!sample) return;
  state.activeSample = id;
  state.sampleConstraints = sample.constraints;
  state.manualMode = false;
  $("#preference-text").value = sample.text;
  syncManual(sample.constraints);
  $$(".sample-chip").forEach((chip) => chip.classList.toggle("active", chip.dataset.sampleId === id));
  $("#ai-constraints").innerHTML = state.ai?.available
    ? '<span class="ai-chip">Sample ready · Plan to interpret</span>'
    : renderConstraintChips(sample.constraints, "Manual sample");
  $("#manual-note").textContent = "Sample constraints selected. Nemotron will interpret the text if it is available; otherwise these values are used.";
  if (markStale) markStale();
}

function renderConstraintChips(preferences, sourceLabel = "") {
  const window = preferences.no_discharge_start_hour === null || preferences.no_discharge_start_hour === undefined
    ? "No discharge window"
    : `No discharge ${String(preferences.no_discharge_start_hour).padStart(2, "0")}:00–${String(preferences.no_discharge_end_hour).padStart(2, "0")}:00`;
  const chips = [
    `Battery ≥ ${fmt(preferences.battery_reserve_pct, 0)}%`,
    preferences.prefer_local_before_export ? "Local first" : "Export surplus",
    preferences.prioritise_neighbour_evening ? "Evening battery share" : "Solar sharing only",
    window,
  ];
  const prefix = sourceLabel ? `<span class="ai-chip"><b>${esc(sourceLabel)}</b></span>` : "";
  return prefix + chips.map((chip) => `<span class="ai-chip">${esc(chip)}</span>`).join("");
}

function updateAIPanel(preferences, source, detail = "") {
  if (source === "nemotron") {
    setAIStatus("ready", "validated");
    $("#ai-constraints").innerHTML = renderConstraintChips(preferences, "Nemotron");
    const latency = state.interpretation?.latency_ms;
    $("#ai-note").textContent = `Model output validated by the server${latency ? ` in ${latency} ms` : ""}. The simulator calculated every number.`;
  } else {
    setAIStatus(state.ai?.available ? "manual" : "unavailable", state.ai?.available ? "manual" : "unavailable");
    $("#ai-constraints").innerHTML = renderConstraintChips(preferences, "Manual");
    $("#ai-note").textContent = detail || "Manual constraints selected. Nemotron was not used for this plan; no model result is fabricated.";
  }
}

function markStale() {
  if (!state.plan) return;
  state.stale = true;
  $("#record-plan").disabled = true;
  $("#receipt-status").textContent = "Inputs changed. Build a fresh plan before recording a receipt.";
  $("#story-period").textContent = "Inputs changed · rebuild the plan";
  setMessage("Inputs changed. Plan again to refresh the comparison.", "warning");
}

async function planDay() {
  if (!state.scenario) return;
  stopPlay();
  const button = $("#plan-button");
  const label = button.querySelector("span:first-child");
  button.disabled = true;
  button.classList.add("is-busy");
  label.textContent = "Working it out…";
  setMessage("Interpreting the preference and checking the constraints…");
  const text = $("#preference-text").value.trim();
  const homeId = $("#your-home").value;
  let preferences = null;
  let source = "manual";

  if (state.manualMode || !state.ai?.available) {
    preferences = { ...manualPreferences(), home_id: homeId, source: "manual" };
    updateAIPanel(preferences, "manual", state.ai?.available
      ? "Manual constraints selected. Nemotron was not called for this plan."
      : "Nemotron is unavailable. Manual sample constraints are being used; no model result is fabricated.");
  } else {
    if (!text) {
      setMessage("Write a preference or choose a sample first.", "error");
      button.disabled = false;
      button.classList.remove("is-busy");
      label.textContent = "Plan energy sharing";
      return;
    }
    setAIStatus("working", "interpreting");
    $("#ai-constraints").textContent = "Nemotron is reading the preference…";
    try {
      const interpretation = await postJson("/api/flex/interpret", { text, home_id: homeId });
      state.interpretation = interpretation;
      preferences = interpretation.preferences;
      source = "nemotron";
      updateAIPanel(preferences, source);
    } catch (error) {
      const fallback = state.sampleConstraints || manualPreferences();
      preferences = { ...fallback, home_id: homeId, source: "manual" };
      const unavailable = error.status === 503 || error.body?.code === "ai_unavailable";
      setAIStatus(unavailable ? "unavailable" : "error", unavailable ? "unavailable" : "error");
      $("#ai-constraints").innerHTML = renderConstraintChips(preferences, "Manual");
      $("#ai-note").textContent = unavailable
        ? "Nemotron is unavailable. These manual sample constraints are being used instead; no model result is fabricated."
        : "The Nemotron call failed. Manual sample constraints are being used instead; no model result is fabricated.";
    }
  }

  try {
    setMessage("Running the deterministic simulation…");
    const result = await postJson("/api/flex/plan", { preferences, tariffs: tariffValues() });
    state.plan = result;
    state.stale = false;
    state.view = "coordinated";
    state.hour = 18;
    state.receiptEventId = null;
    renderPlan();
    setMessage(result.constraints.ok
      ? `Plan ready. ${fmt(result.comparison.shared_kwh, 1)} kWh could be allocated locally; zero constraint violations.`
      : `Plan built with ${result.constraints.violations.length} constraint issue(s). Inspect the validation panel.`,
    result.constraints.ok ? "ok" : "error");
    const hosted = state.scenario?.deployment_mode === "hosted";
    $("#record-plan").disabled = hosted;
    $("#receipt-status").textContent = hosted
      ? "Hosted demo: local receipts are disabled because function storage is not durable. Run locally to record one."
      : "Record the exact plan in the local hash-chain ledger.";
    requestExplanation(result);
  } catch (error) {
    setMessage(error.message || "The plan could not be calculated.", "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-busy");
    label.textContent = "Plan energy sharing";
  }
}

function buildExplanationSummary(result) {
  return {
    scenario: result.scenario?.name,
    home_count: result.homes?.length,
    tariffs: {
      import_c_kwh: result.tariffs.import_c_kwh,
      export_c_kwh: result.tariffs.export_c_kwh,
      shared_c_kwh: result.tariffs.shared_c_kwh,
      transfer_limit_kw: result.tariffs.transfer_limit_kw,
    },
    preferences: {
      home_id: result.preferences.home_id,
      battery_reserve_pct: result.preferences.battery_reserve_pct,
      prefer_local_before_export: result.preferences.prefer_local_before_export,
      prioritise_neighbour_evening: result.preferences.prioritise_neighbour_evening,
      no_discharge_start_hour: result.preferences.no_discharge_start_hour,
      no_discharge_end_hour: result.preferences.no_discharge_end_hour,
      source: result.preferences.source,
    },
    independent: {
      local_solar_kwh: result.comparison.independent_local_solar_kwh,
      grid_import_kwh: result.comparison.independent_grid_import_kwh,
      grid_export_kwh: result.comparison.independent_grid_export_kwh,
      cost_aud: result.comparison.independent_cost_aud,
    },
    coordinated: {
      local_solar_kwh: result.comparison.coordinated_local_solar_kwh,
      grid_import_kwh: result.comparison.coordinated_grid_import_kwh,
      grid_export_kwh: result.comparison.coordinated_grid_export_kwh,
      cost_aud: result.comparison.coordinated_cost_aud,
      shared_kwh: result.comparison.shared_kwh,
      battery_shared_kwh: result.comparison.battery_shared_kwh,
    },
    comparison: {
      import_delta_kwh: result.comparison.grid_import_delta_kwh,
      cost_delta_aud: result.comparison.cost_delta_aud,
    },
  };
}

async function requestExplanation(result) {
  const deterministic = [result.summary.headline, result.summary.points?.[4], result.summary.disclaimer].filter(Boolean).join(" ");
  $("#explanation-text").textContent = deterministic;
  $("#explanation-source").textContent = "Deterministic summary from the simulator.";
  if (!state.ai?.available) return;
  try {
    const response = await postJson("/api/flex/explain", { summary: buildExplanationSummary(result) });
    if (state.plan !== result) return;
    $("#explanation-text").textContent = response.explanation;
    $("#explanation-source").textContent = `${response.model} via Nebius Token Factory · explains the calculated result; every cited number is checked against it.`;
  } catch {
    $("#explanation-source").textContent = "Deterministic summary from the simulator. The optional Nemotron explanation was unavailable.";
  }
}

function animateNumber(output, target, digits = 1) {
  if (!output) return;
  const next = Number(target || 0);
  const previous = Number(String(output.textContent).replace(/[^0-9.-]/g, ""));
  const start = Number.isFinite(previous) ? previous : 0;
  if (motionQuery.matches || Math.abs(next - start) < 0.005) {
    output.textContent = fmt(next, digits);
    return;
  }
  const began = performance.now();
  const duration = 620;
  function tick(now) {
    const progress = Math.min(1, (now - began) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    output.textContent = fmt(start + (next - start) * eased, digits);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function homeIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 11.5 12 4l8.5 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-5.5h5V20"/><path d="M16.5 5.5V3h2v4.5"/></svg>`;
}

function currentSeries() {
  if (!state.plan) return null;
  return state.plan[state.view]?.series || null;
}

function homeStatus(values, home) {
  if (values) {
    if ((values.shared_out_kw?.[state.hour] || 0) > 0.05) return { label: "SHARING", className: "is-surplus", card: "is-supplying" };
    if ((values.shared_in_kw?.[state.hour] || 0) > 0.05) return { label: "RECEIVING", className: "is-need", card: "is-receiving" };
    if ((values.export_kw?.[state.hour] || 0) > 0.05) return { label: "EXPORTING", className: "is-surplus", card: "is-supplying" };
    if ((values.import_kw?.[state.hour] || 0) > 0.05) return { label: "IMPORTING", className: "is-need", card: "is-receiving" };
    return { label: "BALANCED", className: "is-balanced", card: "" };
  }
  const surplus = Number(home.daily_solar_kwh || 0) - Number(home.daily_demand_kwh || 0);
  if (surplus > 1) return { label: "SURPLUS", className: "is-surplus", card: "is-supplying" };
  if (surplus < -1) return { label: "NEED", className: "is-need", card: "is-receiving" };
  return { label: "MIXED", className: "is-balanced", card: "" };
}

function flowMarkup(values, home, status) {
  if (!values) {
    return `<span>Daily solar <b>${fmt(home.daily_solar_kwh, 1)} kWh</b></span><br><span>Daily demand <b>${fmt(home.daily_demand_kwh, 1)} kWh</b></span>`;
  }
  const sharedOut = values.shared_out_kw[state.hour] || 0;
  const sharedIn = values.shared_in_kw[state.hour] || 0;
  const batteryShared = values.battery_shared_kw[state.hour] || 0;
  const solarShared = values.solar_shared_kw[state.hour] || 0;
  const imported = values.import_kw[state.hour] || 0;
  const exported = values.export_kw[state.hour] || 0;
  const charge = values.battery_charge_kw[state.hour] || 0;
  const discharge = values.battery_own_discharge_kw[state.hour] || 0;
  if (sharedOut > 0.05) {
    const parts = [];
    if (solarShared > 0.05) parts.push(`${fmt(solarShared, 1)} kW solar`);
    if (batteryShared > 0.05) parts.push(`${fmt(batteryShared, 1)} kW battery`);
    return `<b>${fmt(sharedOut, 1)} kW</b> to the local pool${parts.length ? ` (${parts.join(" + ")})` : ""}.`;
  }
  if (sharedIn > 0.05) {
    return `<b>${fmt(sharedIn, 1)} kW</b> received locally${imported > 0.05 ? `, plus ${fmt(imported, 1)} kW from the grid` : ""}.`;
  }
  if (exported > 0.05) return `<b>${fmt(exported, 1)} kW</b> exported to the grid.`;
  if (imported > 0.05) return `<b>${fmt(imported, 1)} kW</b> imported from the grid.`;
  if (charge > 0.05) return `Battery charging at <b>${fmt(charge, 1)} kW</b>.`;
  if (discharge > 0.05) return `Battery serving <b>${fmt(discharge, 1)} kW</b> of the home.`;
  return "No active flow this hour.";
}

function renderHomeCards() {
  const homes = state.plan?.homes || state.scenario?.homes || [];
  const series = currentSeries();
  $("#home-stage").innerHTML = homes.map((home) => {
    const values = series?.[home.id] || null;
    const status = homeStatus(values, home);
    const solar = values ? values.solar_kw[state.hour] : home.daily_solar_kwh;
    const demand = values ? values.demand_kw[state.hour] : home.daily_demand_kwh;
    const soc = values ? values.soc_kwh[state.hour] : home.battery.initial_soc_kwh;
    const socPct = Math.max(0, Math.min(100, (soc / home.battery.capacity_kwh) * 100));
    const color = HOME_COLORS[home.color] || HOME_COLORS.amber;
    const flowClass = status.label === "SHARING" || status.label === "EXPORTING" ? "supply" : status.label === "RECEIVING" || status.label === "IMPORTING" ? "receive" : "";
    return `<article class="home-card ${status.card}" style="--home-color:${color}">
      <div class="home-head"><div class="home-icon">${homeIcon()}</div><div><div class="home-name">${esc(home.name)}</div><div class="home-sub">${values ? `Hour ${String(state.hour).padStart(2, "0")}:00 · ${fmt(solar, 1)} kW solar` : "Daily profile"}</div></div><span class="home-status ${status.className}">${status.label}</span></div>
      <div class="home-meters"><div class="home-meter solar"><span>Solar</span><b>${fmt(solar, 1)}<small>kW</small></b></div><div class="home-meter demand"><span>Demand</span><b>${fmt(demand, 1)}<small>kW</small></b></div></div>
      <div class="home-battery"><div class="home-battery-head"><span>Battery</span><b>${fmt(socPct, 0)}%</b></div><div class="home-battery-track"><i class="home-battery-fill" style="width:${socPct}%"></i></div></div>
      <div class="home-flow ${flowClass}">${flowMarkup(values, home, status)}</div>
    </article>`;
  }).join("");
}

function renderStory() {
  if (!state.plan) return;
  const comparison = state.plan.comparison;
  const shared = comparison.shared_kwh;
  const coordinated = state.plan.coordinated.totals;
  const imports = comparison.coordinated_grid_import_kwh;
  const exports = comparison.coordinated_grid_export_kwh;
  const savings = comparison.savings_aud;
  animateNumber($("#story-shared"), shared, 1);
  $("#story-result").innerHTML = shared > 0.05
    ? `<strong>${fmt(shared, 1)} kWh</strong> is allocated locally before surplus goes to the grid.`
    : "These constraints allow no local sharing. Both scenarios match.";
  $("#story-import").textContent = `${fmt(imports, 1)} kWh`;
  $("#story-export").textContent = `${fmt(exports, 1)} kWh`;
  $("#story-cost").textContent = `${savings >= 0 ? "−$" : "+$"}${fmt(Math.abs(savings), 2)}`;
  $("#story-cost").className = savings > 0.005 ? "good" : savings < -0.005 ? "bad" : "";
  const monthly = state.plan.monthly;
  const monthlyLabel = monthly.savings_aud >= 0 ? "−$" : "+$";
  $("#story-monthly").textContent = `${monthlyLabel}${fmt(Math.abs(monthly.savings_aud), 0)}`;
  $("#story-monthly-basis").textContent = "Same sample day × 30; not a forecast.";
  $("#story-period").textContent = "Simulated day · not a bill";
}

function renderStage() {
  if (!state.plan) return;
  const series = currentSeries();
  const shared = Object.values(series).reduce((sum, values) => sum + (values.shared_in_kw[state.hour] || 0), 0);
  const imported = Object.values(series).reduce((sum, values) => sum + (values.import_kw[state.hour] || 0), 0);
  const exported = Object.values(series).reduce((sum, values) => sum + (values.export_kw[state.hour] || 0), 0);
  $("#pool-shared").textContent = `${fmt(shared, 1)} kW`;
  $("#pool-fill").style.width = `${Math.min(100, (shared / Math.max(0.1, state.plan.tariffs.transfer_limit_kw)) * 100)}%`;
  $("#grid-import").textContent = fmt(imported, 1);
  $("#grid-export").textContent = fmt(exported, 1);
  $("#stage-hour").textContent = `${String(state.hour).padStart(2, "0")}:00`;
  $("#stage-slider").value = state.hour;
  $("#stage-note").textContent = state.view === "independent"
    ? "Independent homes: no local allocation is applied in this view."
    : shared > 0.05
      ? `${fmt(shared, 1)} kW is moving through the simulated local pool at this hour.`
      : "No local sharing at this hour; each home uses its own solar and battery.";
  $("#view-coordinated").classList.toggle("active", state.view === "coordinated");
  $("#view-independent").classList.toggle("active", state.view === "independent");
}

function totalDemandAt(hour) {
  if (state.plan) {
    return Object.values(state.plan.coordinated.series).reduce((sum, values) => sum + (values.demand_kw[hour] || 0), 0);
  }
  return (state.scenario?.homes || []).reduce((sum, home) => sum + (home.demand_kw[hour] || 0), 0);
}

function sharedAt(hour) {
  if (!state.plan || state.view !== "coordinated") return 0;
  return Object.values(state.plan.coordinated.series).reduce((sum, values) => sum + (values.shared_in_kw[hour] || 0), 0);
}

function renderTimeline() {
  if (!state.scenario) return;
  const maxDemand = Math.max(1, ...Array.from({ length: 24 }, (_, hour) => totalDemandAt(hour)));
  const cells = Array.from({ length: 24 }, (_, hour) => {
    const height = Math.max(8, (totalDemandAt(hour) / maxDemand) * 100);
    const shared = sharedAt(hour);
    return `<button type="button" class="timeline-cell${shared > 0.02 ? " has-share" : ""}" data-hour="${hour}" title="${String(hour).padStart(2, "0")}:00 · ${fmt(totalDemandAt(hour), 1)} kWh demand${shared > 0.02 ? ` · ${fmt(shared, 1)} kWh shared` : ""}"><span class="timeline-bar" style="height:${height}%"></span><span class="timeline-share"></span></button>`;
  }).join("");
  $("#stage-timeline").innerHTML = cells;
  const labels = Array.from({ length: 24 }, (_, hour) =>
    `<span class="${[0, 4, 8, 12, 16, 20, 23].includes(hour) ? "show" : ""}">${String(hour).padStart(2, "0")}</span>`
  ).join("");
  let labelRow = $("#timeline-labels");
  if (!labelRow) {
    labelRow = document.createElement("div");
    labelRow.id = "timeline-labels";
    labelRow.className = "timeline-labels";
    $("#stage-timeline").after(labelRow);
  }
  labelRow.innerHTML = labels;
  updateTimelineActive();
}

function updateTimelineActive() {
  $$(".timeline-cell").forEach((cell) => cell.classList.toggle("active", Number(cell.dataset.hour) === state.hour));
}

function renderInitialStage() {
  state.hour = 18;
  $("#stage-slider").value = state.hour;
  $("#stage-hour").textContent = "18:00";
  $("#pool-shared").textContent = "—";
  $("#pool-fill").style.width = "0%";
  $("#grid-import").textContent = "—";
  $("#grid-export").textContent = "—";
  $("#stage-note").textContent = "Pick a home, leave the sample preference, then plan the day.";
  $("#stage-play").disabled = true;
  $("#stage-play").textContent = "▶ Play day";
  $("#stage-slider").disabled = true;
  renderHomeCards();
  renderTimeline();
}

function setHour(hour) {
  state.hour = Math.max(0, Math.min(23, Number(hour)));
  $("#stage-slider").value = state.hour;
  $("#stage-hour").textContent = `${String(state.hour).padStart(2, "0")}:00`;
  renderHomeCards();
  if (state.plan) renderStage();
  updateTimelineActive();
}

function stopPlay() {
  state.playing = false;
  if (state.playTimer) window.clearInterval(state.playTimer);
  state.playTimer = null;
  const button = $("#stage-play");
  button.classList.remove("playing");
  button.textContent = "▶ Play day";
}

function togglePlay() {
  if (!state.plan) return;
  if (state.playing) {
    stopPlay();
    return;
  }
  state.playing = true;
  const button = $("#stage-play");
  button.classList.add("playing");
  button.textContent = "❚❚ Pause";
  if (state.hour >= 23) state.hour = -1;
  state.playTimer = window.setInterval(() => {
    state.hour += 1;
    if (state.hour > 23) {
      stopPlay();
      return;
    }
    setHour(state.hour);
  }, 780);
}

function renderPlan() {
  renderHomeCards();
  renderStory();
  renderStage();
  renderCompare();
  renderChart();
  renderTable();
  renderConstraints();
  renderAssumptions();
  renderTimeline();
  $("#stage-play").disabled = false;
  $("#stage-slider").disabled = false;
}

function renderCompare() {
  if (!state.plan) return;
  const c = state.plan.comparison;
  const set = (id, value) => { $(id).textContent = value; };
  set("#ind-local", `${fmt(c.independent_local_solar_kwh, 1)} kWh`);
  set("#ind-import", `${fmt(c.independent_grid_import_kwh, 1)} kWh`);
  set("#ind-export", `${fmt(c.independent_grid_export_kwh, 1)} kWh`);
  set("#ind-cost", `$${fmt(c.independent_cost_aud, 2)}`);
  set("#ind-self", `${fmt(c.self_sufficiency_independent_pct, 1)}%`);
  set("#co-local", `${fmt(c.coordinated_local_solar_kwh, 1)} kWh`);
  set("#co-import", `${fmt(c.coordinated_grid_import_kwh, 1)} kWh`);
  set("#co-export", `${fmt(c.coordinated_grid_export_kwh, 1)} kWh`);
  set("#co-cost", `$${fmt(c.coordinated_cost_aud, 2)}`);
  set("#co-self", `${fmt(c.self_sufficiency_coordinated_pct, 1)}%`);
  set("#co-shared", `${fmt(c.shared_kwh, 1)} kWh`);
  set("#co-battery-shared", c.battery_shared_kwh > 0.05 ? `${fmt(c.battery_shared_kwh, 1)} kWh came from batteries` : "solar sharing only");
  const deltas = [
    ["#delta-local", c.local_solar_delta_kwh, true, " kWh"],
    ["#delta-import", c.grid_import_delta_kwh, false, " kWh"],
    ["#delta-export", c.grid_export_delta_kwh, false, " kWh"],
    ["#delta-self", c.self_sufficiency_coordinated_pct - c.self_sufficiency_independent_pct, true, " pts"],
  ];
  for (const [selector, value, positiveGood, suffix] of deltas) {
    const element = $(selector);
    element.textContent = signed(value, 1, suffix);
    element.className = `delta ${markerClass(value, positiveGood)}`;
  }
  const costDelta = $("#delta-cost");
  costDelta.textContent = `${c.cost_delta_aud >= 0 ? "+$" : "−$"}${fmt(Math.abs(c.cost_delta_aud), 2)}`;
  costDelta.className = `delta ${markerClass(c.cost_delta_aud, false)}`;
  $("#compare-badge").textContent = state.plan.constraints.ok ? "SIMULATED · 0 VIOLATIONS" : `SIMULATED · ${state.plan.constraints.violations.length} ISSUES`;
  $("#compare-summary").innerHTML = `<strong>${esc(state.plan.summary.headline)}</strong>`;
  const monthly = state.plan.monthly;
  const monthlyChange = monthly.savings_aud >= 0 ? "lower" : "higher";
  $("#compare-monthly").textContent = `30-day illustration: $${fmt(Math.abs(monthly.savings_aud), 0)} ${monthlyChange}. Same sample day × 30; not a forecast.`;
}

function svgPath(series, x, y, width, height, maxValue) {
  return series.map((value, index) => {
    const px = x + (index / (series.length - 1)) * width;
    const py = y + height - (Math.max(0, value) / maxValue) * height;
    return `${index === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(" ");
}

function renderChart() {
  if (!state.plan) return;
  const independent = Array.from({ length: 24 }, (_, hour) =>
    Object.values(state.plan.independent.series).reduce((sum, values) => sum + values.import_kw[hour], 0)
  );
  const coordinated = Array.from({ length: 24 }, (_, hour) =>
    Object.values(state.plan.coordinated.series).reduce((sum, values) => sum + values.import_kw[hour], 0)
  );
  const shared = Array.from({ length: 24 }, (_, hour) => sharedAt(hour));
  const maxValue = Math.max(5, ...independent, ...coordinated, ...shared) * 1.15;
  const left = 48, top = 16, chartWidth = 800, chartHeight = 154;
  const bottom = top + chartHeight;
  const yAt = (value) => top + chartHeight - (value / maxValue) * chartHeight;
  const xAt = (index) => left + (index / 23) * chartWidth;
  const grid = [0, .25, .5, .75, 1].map((fraction) => {
    const y = top + chartHeight - fraction * chartHeight;
    return `<line class="chart-grid-line" x1="${left}" y1="${y}" x2="${left + chartWidth}" y2="${y}"/><text class="chart-axis-label" x="${left - 10}" y="${y + 3}" text-anchor="end">${fmt(maxValue * fraction, 0)}</text>`;
  }).join("");
  const labels = [0, 4, 8, 12, 16, 20, 23].map((hour) =>
    `<text class="chart-axis-label" x="${xAt(hour)}" y="${bottom + 17}" text-anchor="middle">${String(hour).padStart(2, "0")}</text>`
  ).join("");
  const bars = shared.map((value, index) => {
    if (value <= 0.01) return "";
    const height = Math.max(1, (value / maxValue) * chartHeight);
    return `<rect class="chart-share-bar" x="${xAt(index) - 4}" y="${bottom - height}" width="8" height="${height}" rx="2"><title>${String(index).padStart(2, "0")}:00 · ${fmt(value, 1)} kWh shared</title></rect>`;
  }).join("");
  const independentPath = svgPath(independent, left, top, chartWidth, chartHeight, maxValue);
  const coordinatedPath = svgPath(coordinated, left, top, chartWidth, chartHeight, maxValue);
  $("#flex-chart").innerHTML = `<svg viewBox="0 0 900 200" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id="flex-opt-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4b866e" stop-opacity=".14"/><stop offset="1" stop-color="#4b866e" stop-opacity="0"/></linearGradient></defs>
    ${grid}${bars}
    <path class="chart-area-optimized" d="${coordinatedPath} L${left + chartWidth},${bottom} L${left},${bottom} Z" fill="url(#flex-opt-fill)"/>
    <path class="chart-baseline" d="${independentPath}"/>
    <path class="chart-optimized" d="${coordinatedPath}"/>
    ${labels}
    <text class="chart-axis-label" x="${left}" y="194">LOCAL HOUR</text>
  </svg>`;
}

function renderTable() {
  if (!state.plan) return;
  const rows = state.plan.homes.map((home) => {
    const totals = state.plan.coordinated.totals[home.id];
    return `<tr><td>${esc(home.name)}</td><td>${fmt(totals.import_kwh, 1)} kWh</td><td>${fmt(totals.export_kwh, 1)} kWh</td><td>${fmt(totals.shared_in_kwh, 1)} kWh</td><td>${fmt(totals.shared_out_kwh, 1)} kWh</td><td>$${fmt(totals.energy_cost_aud, 2)}</td></tr>`;
  }).join("");
  $("#home-table tbody").innerHTML = rows;
}

function renderConstraints() {
  if (!state.plan) return;
  const checks = state.plan.constraints.checks || [];
  const warnings = state.plan.constraints.warnings || [];
  const violations = state.plan.constraints.violations || [];
  const badge = $("#constraint-badge");
  badge.textContent = violations.length ? `${violations.length} ISSUES` : "0 VIOLATIONS";
  badge.className = `constraint-badge${violations.length ? " fail" : ""}`;
  const items = checks.map((check) =>
    `<li class="${check.passed ? "" : "fail"}">${esc(check.name)}</li>`
  );
  for (const warning of warnings) items.push(`<li class="warn">${esc(warning)}</li>`);
  for (const violation of violations) items.push(`<li class="fail">${esc(violation)}</li>`);
  $("#constraint-list").innerHTML = items.join("") || "<li>No checks were returned.</li>";
}

function renderAssumptions() {
  if (!state.plan) return;
  const t = state.plan.tariffs;
  const home = state.plan.homes.find((item) => item.id === state.plan.preferences.home_id);
  $("#assumption-values").innerHTML = `
    <div><b>Scenario:</b> ${esc(state.plan.scenario.name)} · ${esc(state.plan.scenario.source)}</div>
    <div><b>Tariffs:</b> import ${fmt(t.import_c_kwh, 0)}¢/kWh, export ${fmt(t.export_c_kwh, 0)}¢/kWh, local shared ${fmt(t.shared_c_kwh, 0)}¢/kWh. Energy only; supply, network, tax and settlement excluded.</div>
    <div><b>Sharing limit:</b> ${fmt(t.transfer_limit_kw, 1)} kW per interval. <b>Battery efficiency:</b> ${fmt(home?.battery?.efficiency * 100, 0)}% each way.</div>
    <div><b>Monthly:</b> ${esc(state.plan.monthly.assumption)}</div>
    <div><b>Preference home:</b> ${esc(home?.name || state.plan.preferences.home_id)} · <b>source:</b> ${esc(state.plan.preferences.source)}.</div>`;
}

async function recordPlan() {
  if (!state.plan) return;
  const button = $("#record-plan");
  button.disabled = true;
  const eventId = (window.crypto?.randomUUID?.() || `flex-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  state.receiptEventId = eventId;
  $("#receipt-status").textContent = "Writing the local receipt…";
  try {
    const receipt = await postJson("/api/flex/receipt", {
      event_id: eventId,
      plan_hash: state.plan.plan_hash,
      event_type: "flex_plan",
      scenario_id: state.plan.scenario.id,
      preferences: state.plan.preferences,
      comparison: state.plan.comparison,
      constraints_ok: state.plan.constraints.ok,
    });
    $("#receipt-status").textContent = `Local receipt recorded · ${receipt.entry_hash.slice(0, 12)}… · local only, not a blockchain transaction.`;
  } catch (error) {
    button.disabled = false;
    $("#receipt-status").textContent = error.message || "The local receipt could not be recorded.";
  }
}

function useManualMode(message) {
  state.manualMode = true;
  state.activeSample = null;
  $$(".sample-chip").forEach((chip) => chip.classList.remove("active"));
  const preferences = { ...manualPreferences(), source: "manual" };
  updateAIPanel(preferences, "manual");
  $("#manual-note").textContent = "Manual values will be used without a Nemotron call.";
  if (message) setMessage(message, "");
  markStale();
}

function bindEvents() {
  $("#plan-button").addEventListener("click", planDay);
  $("#sample-chips").addEventListener("click", (event) => {
    const chip = event.target.closest(".sample-chip");
    if (chip) chooseSample(chip.dataset.sampleId, true);
  });
  $("#preference-text").addEventListener("input", () => {
    state.activeSample = null;
    state.sampleConstraints = null;
    state.manualMode = false;
    $$(".sample-chip").forEach((chip) => chip.classList.remove("active"));
    if (state.ai?.available) {
      setAIStatus("ready", "ready");
      $("#ai-constraints").textContent = "New preference ready for Nemotron.";
      $("#ai-note").textContent = "Nemotron reads your preference. The simulator calculates the energy.";
    } else {
      setAIStatus("unavailable", "unavailable");
      $("#ai-constraints").textContent = "Free text is not interpreted while Nemotron is unavailable. The manual constraints below will be used.";
      $("#ai-note").textContent = "No model result is fabricated. Set NEBIUS_API_KEY on the server to interpret the text; until then, the slider and checkboxes control the plan.";
    }
    markStale();
  });
  $("#your-home").addEventListener("change", () => {
    if (state.ai?.available) {
      setAIStatus("ready", "ready");
      $("#ai-constraints").textContent = "New home selected. Plan to interpret a preference for it.";
    }
    markStale();
  });
  $("#manual-reserve").addEventListener("input", () => {
    $("#manual-reserve-value").textContent = `${$("#manual-reserve").value}%`;
    useManualMode();
  });
  $("#manual-start").addEventListener("change", () => { updateManualLabels(); useManualMode(); });
  $("#manual-end").addEventListener("change", () => { updateManualLabels(); useManualMode(); });
  $("#manual-local").addEventListener("change", () => useManualMode());
  $("#manual-evening").addEventListener("change", () => useManualMode());
  $("#manual-apply").addEventListener("click", () => useManualMode("Manual constraints selected. Plan to run the simulator."));
  for (const selector of ["#import-price", "#export-price", "#shared-price", "#transfer-limit"]) {
    $(selector).addEventListener("input", () => { updateTariffLabels(); markStale(); });
  }
  $("#stage-play").addEventListener("click", togglePlay);
  $("#stage-slider").addEventListener("input", () => { stopPlay(); setHour(Number($("#stage-slider").value)); });
  $("#stage-timeline").addEventListener("click", (event) => {
    const cell = event.target.closest(".timeline-cell");
    if (!cell) return;
    stopPlay();
    setHour(Number(cell.dataset.hour));
  });
  $("#view-coordinated").addEventListener("click", () => setView("coordinated"));
  $("#view-independent").addEventListener("click", () => setView("independent"));
  $("#record-plan").addEventListener("click", recordPlan);
}

function setView(view) {
  if (!state.plan) return;
  if (state.view === view) return;
  state.view = view;
  stopPlay();
  renderHomeCards();
  renderStage();
  renderTimeline();
}

async function init() {
  initHeroScene();
  initSurfaces();
  populateManualHours();
  bindEvents();
  initRangeProgress();
  $("#home-stage").innerHTML = '<div class="stage-loading">Loading the three-home sample…</div>';
  try {
    const scenario = await fetchJson("/api/flex/scenario");
    renderScenario(scenario);
    setMessage("Sample loaded. Check the preference and plan the day.", "");
  } catch (error) {
    setMessage("The Flex scenario could not be loaded. Check the local server logs.", "error");
    $("#ai-note").textContent = "Scenario unavailable. The page cannot run a simulation without the local API.";
    setAIStatus("error", "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
