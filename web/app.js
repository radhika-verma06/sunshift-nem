const REGION_NAMES = {
  NSW: "New South Wales · NEM region NSW1",
  SA: "South Australia · NEM region SA1",
  VIC: "Victoria · NEM region VIC1",
  QLD: "Queensland · NEM region QLD1",
  TAS: "Tasmania · NEM region TAS1",
};

let weather = null;
let plan = null;
let isStale = false;

const $ = (selector) => document.querySelector(selector);
const value = (selector) => Number($(selector).value);
const fmt = (number, digits = 1) => Number(number || 0).toLocaleString("en-AU", {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
});
const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const finePointerQuery = window.matchMedia("(hover: hover) and (pointer: fine)");

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function currentInputs() {
  return {
    pv_capacity_kw: value("#pv-capacity"),
    average_site_load_kw: value("#site-load"),
    flexible_energy_kwh: value("#flex-energy"),
    max_flexible_power_kw: value("#max-power"),
    transfer_limit_kw: value("#transfer-limit"),
    emissions_factor_kg_kwh: value("#emissions-factor"),
    p2p_price_c_kwh: value("#p2p-price"),
    grid_reference_price_c_kwh: value("#grid-price"),
    charge_from_hour: 7,
    charge_by_hour: 22,
    baseline_from_hour: 17,
    baseline_by_hour: 22,
  };
}

function setMessage(message, kind = "") {
  const element = $("#planner-message");
  element.textContent = message;
  element.dataset.kind = kind;
}

function markPlanStale() {
  if (!plan) return;
  isStale = true;
  $("#record-receipt").disabled = true;
  $("#ledger-status").textContent = "Inputs changed · rebuild plan before recording";
  $("#receipt-detail").hidden = true;
  setMessage("Inputs changed. Rebuild the plan before creating a receipt.", "warning");
}

function svgPath(series, x, y, width, height, maxValue) {
  return series.map((value, index) => {
    const px = x + (index / (series.length - 1)) * width;
    const py = y + height - (Math.max(0, value) / maxValue) * height;
    return `${index === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(" ");
}

function renderChart(result) {
  const container = $("#dispatch-chart");
  const solar = result.solar_kwh;
  const demand = result.site_load_kwh.map((load, index) => load + result.optimized_flexible_kwh[index]);
  const baseline = result.baseline_grid_import_kwh;
  const optimized = result.optimized_grid_import_kwh;
  const maxValue = Math.max(5, ...solar, ...demand, ...baseline) * 1.12;
  const left = 49, top = 16, chartWidth = 814, chartHeight = 176;
  const right = left + chartWidth;
  const bottom = top + chartHeight;
  const yAt = (value) => top + chartHeight - (value / maxValue) * chartHeight;
  const xAt = (index) => left + (index / 23) * chartWidth;
  const series = [solar, demand, baseline, optimized];
  const paths = series.map((line) => svgPath(line, left, top, chartWidth, chartHeight, maxValue));
  const areaPath = (line) => `${line} L${right},${bottom} L${left},${bottom} Z`;
  const grid = [0, .25, .5, .75, 1].map((fraction) => {
    const y = top + chartHeight - fraction * chartHeight;
    return `<line class="chart-grid-line" x1="${left}" y1="${y}" x2="${left + chartWidth}" y2="${y}" />
      <text class="chart-axis-label" x="${left - 11}" y="${y + 3}" text-anchor="end">${fmt(maxValue * fraction, 0)}</text>`;
  }).join("");
  const labels = [0, 4, 8, 12, 16, 20, 23].map((hour) =>
    `<text class="chart-axis-label" x="${xAt(hour)}" y="${top + chartHeight + 17}" text-anchor="middle">${String(result.hours[hour]).padStart(2, "0")}</text>`
  ).join("");
  const shadeStart = xAt(10), shadeEnd = xAt(15);
  const p2p = result.p2p_shared_kwh;
  const p2pDots = p2p.map((amount, index) => amount > 0.15
    ? `<circle class="chart-p2p-dot" cx="${xAt(index)}" cy="${yAt(amount)}" r="2.6"><title>${result.labels?.[index] || `${result.hours[index]}:00`}: ${fmt(amount)} kWh peer-matched</title></circle>`
    : "").join("");
  container.innerHTML = `<svg viewBox="0 0 900 230" preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <linearGradient id="chart-solar-stroke" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#e6b65d" />
        <stop offset=".58" stop-color="#d49b45" />
        <stop offset="1" stop-color="#c97d4d" />
      </linearGradient>
      <linearGradient id="chart-optimized-stroke" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#4f8a70" />
        <stop offset=".65" stop-color="#2e6952" />
        <stop offset="1" stop-color="#1c503e" />
      </linearGradient>
      <linearGradient id="chart-solar-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#e8b660" stop-opacity=".28" />
        <stop offset=".72" stop-color="#e8b660" stop-opacity=".055" />
        <stop offset="1" stop-color="#e8b660" stop-opacity="0" />
      </linearGradient>
      <linearGradient id="chart-optimized-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#4b866e" stop-opacity=".12" />
        <stop offset="1" stop-color="#4b866e" stop-opacity="0" />
      </linearGradient>
      <linearGradient id="chart-window-fill" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#dcead8" stop-opacity=".12" />
        <stop offset=".5" stop-color="#dcead8" stop-opacity=".4" />
        <stop offset="1" stop-color="#dcead8" stop-opacity=".12" />
      </linearGradient>
    </defs>
    <rect x="${shadeStart}" y="${top}" width="${shadeEnd - shadeStart}" height="${chartHeight}" rx="9" fill="url(#chart-window-fill)" />
    <path class="chart-area-solar" d="${areaPath(paths[0])}" />
    <path class="chart-area-optimized" d="${areaPath(paths[3])}" />
    ${grid}
    <path pathLength="1" class="chart-solar chart-line" d="${paths[0]}" />
    <path pathLength="1" class="chart-base chart-line" d="${paths[1]}" />
    <path class="chart-baseline" d="${paths[2]}" />
    <path pathLength="1" class="chart-optimized chart-line" d="${paths[3]}" />
    ${p2pDots}${labels}
    <text class="chart-axis-label chart-window-label" x="${(shadeStart + shadeEnd) / 2}" y="${top + 11}" text-anchor="middle" fill="#5d8065">SOLAR MATCH WINDOW</text>
    <text class="chart-axis-label" x="${left}" y="220">LOCAL HOUR · ${weather.date || "DEMO DAY"}</text>
  </svg>`;
}

function renderSchedule(result) {
  const values = result.p2p_shared_kwh;
  const maximum = Math.max(1, ...values);
  $("#schedule-bars").innerHTML = values.map((amount, index) => {
    const height = amount > 0 ? Math.max(6, (amount / maximum) * 100) : 0;
    const sunny = result.solar_kwh[index] > result.site_load_kwh[index] ? " sunny" : "";
    return `<div class="schedule-hour${sunny}" title="${weather.labels?.[index] || `${result.hours[index]}:00`} · ${fmt(amount)} kWh matched">
      <span class="schedule-hour-value">${amount >= .1 ? fmt(amount, 0) : "·"}</span>
      <div class="schedule-bar-track"><div class="schedule-bar" style="height:${height}%"></div></div>
      <span class="schedule-hour-label">${String(result.hours[index]).padStart(2, "0")}</span>
    </div>`;
  }).join("");
  $("#schedule-total").textContent = `${fmt(values.reduce((a, b) => a + b, 0), 1)} kWh peer-matched`;
}

function renderPlan(result) {
  const metrics = result.metrics;
  const matched = Number(metrics.p2p_energy_matched_kwh || 0);
  animateMatchedAmount(matched);
  $("#story-period").textContent = result.data_quality === "forecast"
    ? `Forecast scenario · ${weather.date || "next day"}`
    : result.data_quality === "user_supplied"
      ? "Your uploaded scenario · not meter-verified"
      : "Illustrative day · not a live trade";
  $("#story-result").innerHTML = matched > 0
    ? `<strong>${fmt(matched, 1)} kWh</strong> is matched in this example day. Your home uses its solar first; the model matches remaining solar with the neighbour's demand. This is a plan, not proof that electricity was delivered.`
    : "With these example inputs, the model found no solar energy to match to the neighbour. Try more solar or less neighbour demand.";
  const dailySellerCredit = Number(metrics.seller_p2p_revenue_aud || 0);
  const monthlySellerCredit = dailySellerCredit * 30;
  animateNumber($("#story-monthly-credit"), monthlySellerCredit, 2);
  $("#story-credit-basis").textContent = `${fmt(dailySellerCredit, 2)}/day × 30 days · ${fmt(matched, 1)} kWh matched at ${fmt(result.inputs.p2p_price_c_kwh, 1)}¢/kWh`;
  animateNumber($("#metric-solar"), metrics.p2p_energy_matched_kwh, 1);
  animateNumber($("#metric-avoided"), metrics.grid_import_avoided_kwh, 1);
  animateNumber($("#metric-peak"), metrics.peak_reduction_kw, 1);
  animateNumber($("#metric-cost"), metrics.buyer_energy_cost_saved_aud, 2);
  animateNumber($("#metric-carbon"), metrics.estimated_co2_avoided_kg, 1);
  $("#peak-caption").textContent = `From ${fmt(metrics.baseline_peak_kw)} to ${fmt(metrics.optimized_peak_kw)} kW`;
  $("#plan-method").textContent = result.method;
  $("#schedule-title").textContent = "Hourly peer-to-peer match";
  renderChart(result);
  renderSchedule(result);
}

function animateNumber(output, target, digits = 1) {
  const next = Number(target || 0);
  const previous = Number(String(output.textContent).replace(/,/g, ""));
  const start = Number.isFinite(previous) ? previous : 0;
  if (motionQuery.matches || Math.abs(next - start) < 0.005) {
    output.textContent = fmt(next, digits);
    return;
  }
  const began = performance.now();
  const duration = 720;
  function tick(now) {
    const progress = Math.min(1, (now - began) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    output.textContent = fmt(start + (next - start) * eased, digits);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function animateMatchedAmount(target) {
  const output = $("#story-match");
  const card = $(".story-card");
  const previous = Number(output.textContent.replace(/,/g, ""));
  const start = Number.isFinite(previous) ? previous : 0;
  if (motionQuery.matches || Math.abs(target - start) < 0.01) {
    output.textContent = fmt(target, 1);
    return;
  }
  card.classList.add("is-updating");
  animateNumber(output, target, 1);
  window.setTimeout(() => card.classList.remove("is-updating"), 1150);
}

function initHeroScene() {
  const scene = $("#hero-scene");
  if (!scene) return;
  scene.classList.add("scene-enter");
  // The entrance animation owns `transform` while it runs; release that layer
  // afterwards so the pointer-driven 3D tilt can take over.
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
    if (motionQuery.matches) return;
    const rect = scene.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    scene.classList.add("is-tilting");
    scene.style.setProperty("--tilt-x", `${(-y * 4.4).toFixed(2)}deg`);
    scene.style.setProperty("--tilt-y", `${(x * 5.8).toFixed(2)}deg`);
    scene.style.setProperty("--image-x", `${(-x * 15).toFixed(1)}px`);
    scene.style.setProperty("--image-y", `${(-y * 10).toFixed(1)}px`);
    scene.style.setProperty("--glare-x", `${((x + 0.5) * 100).toFixed(1)}%`);
    scene.style.setProperty("--glare-y", `${((y + 0.5) * 100).toFixed(1)}%`);
  });
  scene.addEventListener("pointerleave", reset);
  scene.addEventListener("pointercancel", reset);
  motionQuery.addEventListener?.("change", (event) => {
    if (event.matches) reset();
  });
}

function initRangeProgress() {
  document.querySelectorAll('input[type="range"]').forEach((input) => {
    const sync = () => {
      const min = Number(input.min || 0);
      const max = Number(input.max || 100);
      const percent = max > min ? ((Number(input.value) - min) / (max - min)) * 100 : 0;
      input.style.setProperty("--range-fill", `${Math.max(0, Math.min(100, percent)).toFixed(1)}%`);
    };
    sync();
    input.addEventListener("input", sync);
  });
}

function initSurfaceInteractions() {
  if (motionQuery.matches || !finePointerQuery.matches) return;
  const surfaces = document.querySelectorAll(
    ".controls-panel, .story-card, .metric-card, .chart-card, .schedule-card, .evidence-card"
  );
  for (const surface of surfaces) {
    const isMetric = surface.classList.contains("metric-card");
    const reset = () => {
      surface.classList.remove("is-tilting");
      surface.style.setProperty("--spot-x", "72%");
      surface.style.setProperty("--spot-y", "0%");
      if (isMetric) {
        surface.style.setProperty("--card-rx", "0deg");
        surface.style.setProperty("--card-ry", "0deg");
      }
    };
    surface.addEventListener("pointermove", (event) => {
      if (motionQuery.matches) return;
      const rect = surface.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      surface.style.setProperty("--spot-x", `${((x / rect.width) * 100).toFixed(1)}%`);
      surface.style.setProperty("--spot-y", `${((y / rect.height) * 100).toFixed(1)}%`);
      if (!isMetric) return;
      const nx = x / rect.width - 0.5;
      const ny = y / rect.height - 0.5;
      surface.classList.add("is-tilting");
      surface.style.setProperty("--card-rx", `${(-ny * 3).toFixed(2)}deg`);
      surface.style.setProperty("--card-ry", `${(nx * 3.6).toFixed(2)}deg`);
    });
    surface.addEventListener("pointerleave", reset);
    surface.addEventListener("pointercancel", reset);
    motionQuery.addEventListener?.("change", (event) => {
      if (event.matches) reset();
    });
  }
}

function setWeatherLabels() {
  const region = $("#region").value;
  $("#region-name").textContent = weather.region_name || REGION_NAMES[region];
  $("#source-label").textContent = weather.source_label || "Forecast data";
  if (weather.data_quality === "forecast") {
    $("#data-quality").textContent = "LIVE WEATHER FORECAST · NOT NEM DISPATCH";
    $(".ribbon-mark.amber").classList.add("forecast");
  } else if (weather.data_quality === "user_supplied") {
    $("#data-quality").textContent = "USER-SUPPLIED PROFILES · UNVERIFIED";
    $(".ribbon-mark.amber").classList.remove("forecast");
  } else {
    $("#data-quality").textContent = "P2P SCENARIO · NOT SETTLEMENT DATA";
    $(".ribbon-mark.amber").classList.remove("forecast");
  }
  if (weather.attribution) $("#source-label").title = weather.attribution;
}

async function buildPlan() {
  const button = $("#build-plan");
  const storyCard = $(".story-card");
  button.disabled = true;
  button.classList.add("is-busy");
  storyCard?.classList.add("is-building");
  button.querySelector("span:first-child").textContent = "Working it out…";
  setMessage("Checking how much solar is left after your home uses what it needs.");
  try {
    const result = await postJson("/api/optimize", { inputs: currentInputs(), weather });
    plan = result;
    isStale = false;
    renderPlan(result);
    $("#record-receipt").disabled = false;
    $("#ledger-status").textContent = "Plan ready · not settled or meter-verified";
    setMessage("Example ready. The amount is modelled, not measured or physically transferred.", "success");
    $("#receipt-detail").hidden = true;
  } catch (error) {
    plan = null;
    $("#record-receipt").disabled = true;
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-busy");
    storyCard?.classList.remove("is-building");
    button.querySelector("span:first-child").textContent = "Show what could be shared";
  }
}

async function loadLiveWeather() {
  const button = $("#live-weather");
  button.disabled = true;
  button.textContent = "Loading forecast…";
  setMessage("Requesting next-day weather and solar forecast.");
  try {
    weather = await getJson(`/api/forecast?region=${encodeURIComponent($("#region").value)}`);
    weather.region_name = REGION_NAMES[$("#region").value];
    $("#profile-csv").value = "";
    $("#profile-status").textContent = "Using forecast solar + illustrative buyer load.";
    $("#pv-capacity").disabled = false;
    $("#site-load").disabled = false;
    setWeatherLabels();
    markPlanStale();
    if (!plan) setMessage("Forecast loaded. Build a new plan to use it.", "success");
  } catch (error) {
    setMessage(`${error.message} The demo profile is still available.`, "warning");
  } finally {
    button.disabled = false;
    button.textContent = "Load live weather ↗";
  }
}

function createEventId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `sunshift-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function recordReceipt() {
  if (!plan || isStale) return;
  const button = $("#record-receipt");
  button.disabled = true;
  $("#ledger-status").textContent = "Writing local audit receipt…";
  const trades = plan.p2p_shared_kwh.map((kwh, index) => ({
    interval: weather.labels?.[index] || `${String(plan.hours[index]).padStart(2, "0")}:00`,
    seller: "Solar Cooperative · simulated participant",
    buyer: "Community Hub · simulated participant",
    energy_kwh: Number(kwh.toFixed(3)),
  })).filter((trade) => trade.energy_kwh > 0);
  const payload = {
    schema: "sunshift.p2p-plan.v1",
    event_id: createEventId(),
    event_type: "proposed-p2p-energy-match",
    plan_hash: plan.plan_hash,
    region: $("#region").value,
    planning_date: weather.date,
    data_quality: weather.data_quality,
    source: weather.attribution || weather.source_label,
    evidence_status: "modelled; no meter readings or settlement evidence",
    participants: ["Solar Cooperative · simulated participant", "Community Hub · simulated participant"],
    transfer_limit_kw: plan.inputs.transfer_limit_kw,
    p2p_price_c_kwh: plan.inputs.p2p_price_c_kwh,
    price_basis: "user-entered scenario price; not settled",
    metrics: plan.metrics,
    interval_matches: trades,
  };
  try {
    const receipt = await postJson("/api/receipt", payload);
    $("#ledger-status").textContent = "Local hash chain verified · no public chain write";
    const detail = $("#receipt-detail");
    detail.hidden = false;
    detail.innerHTML = `<strong>Unique event:</strong> ${receipt.event_id}<br><strong>Plan SHA-256:</strong> ${plan.plan_hash}<br><strong>Receipt payload SHA-256:</strong> ${receipt.payload_hash}<br><strong>Chain entry SHA-256:</strong> ${receipt.entry_hash}<br><strong>Trade intervals:</strong> ${trades.length} proposed · <strong>Evidence state:</strong> modelled only`;
    button.textContent = "Receipt recorded";
  } catch (error) {
    $("#ledger-status").textContent = error.message;
    button.disabled = false;
  }
}

function bindControls() {
  const fields = ["#pv-capacity", "#site-load", "#flex-energy", "#max-power", "#transfer-limit"];
  const labels = [
    ["#pv-capacity", "#pv-value", " kW"],
    ["#site-load", "#load-value", " kW"],
    ["#flex-energy", "#energy-value", " kWh"],
    ["#max-power", "#power-value", " kW"],
    ["#transfer-limit", "#transfer-value", " kW"],
  ];
  for (const [input, output, unit] of labels) {
    $(input).addEventListener("input", () => {
      $(output).textContent = `${$(input).value}${unit}`;
      markPlanStale();
    });
  }
  for (const field of fields) $(field).addEventListener("change", markPlanStale);
  $("#emissions-factor").addEventListener("input", markPlanStale);
  $("#p2p-price").addEventListener("input", markPlanStale);
  $("#grid-price").addEventListener("input", markPlanStale);
  $("#region").addEventListener("change", () => {
    weather.region_name = REGION_NAMES[$("#region").value];
    if (weather.data_quality === "forecast") {
      getJson("/api/demo").then((demo) => {
        weather = { ...demo, region: $("#region").value, region_name: REGION_NAMES[$("#region").value], source_label: "Illustrative profile · reload live weather for the selected region" };
        setWeatherLabels();
        markPlanStale();
      });
    } else if (weather.data_quality === "illustrative") {
      weather.source_label = "Synthetic scenario · site profiles remain illustrative";
      weather.attribution = "Illustrative profile. The selected NEM region changes the location label only; participant data is not region-specific.";
    }
    setWeatherLabels();
    markPlanStale();
  });
  $("#profile-csv").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const rows = text.trim().split(/\r?\n/).filter(Boolean).map((row) => row.split(",").map((cell) => cell.trim()));
      const header = rows.shift()?.map((cell) => cell.toLowerCase());
      const required = ["hour", "seller_solar_kwh", "buyer_load_kwh"];
      if (!header || required.some((column) => !header.includes(column))) throw new Error("CSV needs hour,seller_solar_kwh,buyer_load_kwh columns.");
      if (rows.length !== 24) throw new Error("CSV must have exactly 24 hourly rows.");
      const columns = Object.fromEntries(required.map((column) => [column, header.indexOf(column)]));
      const parsed = rows.map((row) => ({
        hour: Number(row[columns.hour]),
        solar: Number(row[columns.seller_solar_kwh]),
        load: Number(row[columns.buyer_load_kwh]),
      }));
      parsed.sort((a, b) => a.hour - b.hour);
      if (parsed.some((row, index) => row.hour !== index || !Number.isFinite(row.solar) || !Number.isFinite(row.load) || row.solar < 0 || row.load < 0)) {
        throw new Error("Hours must be unique 0–23 and energy values must be finite and non-negative.");
      }
      weather = {
        ...weather,
        hours: parsed.map((row) => row.hour),
        labels: parsed.map((row) => `${String(row.hour).padStart(2, "0")}:00`),
        ghi_wm2: parsed.map(() => 0),
        solar_kwh_override: parsed.map((row) => row.solar),
        buyer_load_kwh_override: parsed.map((row) => row.load),
        data_quality: "user_supplied",
        source_label: `User CSV · ${file.name} · not independently verified`,
        attribution: "User-supplied participant interval data. Source and meter accuracy have not been independently verified.",
        date: "User-supplied 24-hour profile",
        region_name: REGION_NAMES[$("#region").value],
      };
      $("#pv-capacity").disabled = true;
      $("#site-load").disabled = true;
      $("#profile-status").textContent = "24 rows loaded. CSV solar and buyer load override the two scenario sliders.";
      setWeatherLabels();
      markPlanStale();
    } catch (error) {
      event.target.value = "";
      $("#profile-status").textContent = error.message;
    }
  });
  $("#build-plan").addEventListener("click", buildPlan);
  $("#live-weather").addEventListener("click", loadLiveWeather);
  $("#record-receipt").addEventListener("click", recordReceipt);
}

async function start() {
  bindControls();
  initRangeProgress();
  initHeroScene();
  initSurfaceInteractions();
  try {
    weather = await getJson("/api/demo");
    setWeatherLabels();
    if (weather.deployment_mode === "hosted") {
      $(".privacy-pill").innerHTML = '<span class="lock-icon">◉</span> HOSTED · SCENARIO ONLY';
      $(".evidence-copy p").textContent = "Receipts use a persistent local hash chain in the local demo. Recording is disabled on this hosted preview because serverless files are not durable.";
      $("#record-receipt").disabled = true;
      $("#ledger-status").textContent = "Receipt recording is local-only · hosted preview does not persist receipts";
    } else {
      const ledger = await getJson("/api/ledger/verify");
      $("#ledger-status").textContent = ledger.valid
        ? `Local receipt chain ${ledger.count ? "valid" : "ready"} · ${ledger.count} receipt${ledger.count === 1 ? "" : "s"}`
        : "Local receipt chain failed verification";
    }
    await buildPlan();
  } catch (error) {
    setMessage(`Prototype could not initialise: ${error.message}`, "error");
  }
}

start();
