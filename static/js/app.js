/* ========= small helpers ========= */
const $  = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
function toast(msg, ms = 1400) {
  const t = $("#toast"); if (!t) return;
  t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), ms);
}
function countUp(el, to, dur = 700) {
  const a = performance.now();
  function step(t) {
    const p = Math.min(1, (t - a) / dur);
    el.textContent = Math.round((to || 0) * p).toLocaleString();
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
function axisColors() {
  const theme = document.documentElement.getAttribute("data-theme") || "light";
  return {
    tick: theme === "dark" ? "#cbd5e1" : "#64748b",
    grid: theme === "dark" ? "rgba(148,163,184,.15)" : "rgba(100,116,139,.18)"
  };
}

/* ========= theme toggle (start in LIGHT) ========= */
(function theme() {
  const KEY = "da-theme";
  const btn = $("#themeToggle");
  const saved = localStorage.getItem(KEY);
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  if (btn) {
    btn.setAttribute("aria-pressed", String((saved || "light") === "dark"));
    btn.addEventListener("click", () => {
      const nowDark = document.documentElement.getAttribute("data-theme") !== "dark";
      document.documentElement.setAttribute("data-theme", nowDark ? "dark" : "light");
      localStorage.setItem(KEY, nowDark ? "dark" : "light");
      btn.setAttribute("aria-pressed", String(nowDark));
      rebuildCharts(); writeCaptions();
    });
  }
})();

/* ========= register Chart.js plugins from CDN safely ========= */
(function registerPlugins() {
  if (!(window.Chart && Chart.register)) return;
  try {
    const zoomPack = window["chartjs-plugin-zoom"];
    const zoomPlugin = zoomPack?.zoomPlugin || zoomPack?.default || zoomPack;
    if (zoomPlugin) Chart.register(zoomPlugin);
  } catch {}
  try {
    const ann = window["chartjs-plugin-annotation"];
    Chart.register(ann?.default || ann);
  } catch {}
})();

/* ========= globals ========= */
let METRICS = null;
let CHARTS = {};
let page = 1, pageSize = 12;
let showGDP = true, showInfl = true, unit = "raw"; // raw or zar_b
const ACCENT = getComputedStyle(document.documentElement).getPropertyValue('--accent') || '#7c3aed';
let ANNOTATE_1994 = false;

/* ========= data fetch ========= */
async function fetchMetrics() {
  const r = await fetch('/api/metrics/');
  const j = await r.json();
  if (!r.ok || !j.ok) throw new Error(j.error || 'Failed to load data');
  return j;
}

/* ========= unit helpers (if you ever return Rands) ========= */
function scaleGDP(v) { return unit === "zar_b" ? v / 1e9 : v; }
function formatGDP(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return unit === "zar_b" ? `R ${Number(v).toFixed(1)}B` : String(v);
}

/* ========= compute pieces in-browser (robust to API shape) ========= */
function ensureComputed(j) {
  const yrs = j.series?.years?.slice() || [];
  const infl = j.series?.inflation?.map(Number) || [];
  const gdp = j.series?.gdp?.map(Number) || [];

  // YoY from GDP growth series
  let yoyYears = [], yoyGDP = [], pos = 0, neg = 0, zero = 0;
  for (let i = 1; i < gdp.length; i++) {
    yoyYears.push(yrs[i]);
    const d = Number(gdp[i] - gdp[i - 1]);
    yoyGDP.push(+d.toFixed(2));
    if (d > 0) pos++; else if (d < 0) neg++; else zero++;
  }

  // 5y rolling statistics
  const W = 5;
  const rollingYears = yrs.filter((_, i) => i >= W - 1);
  const roll = (arr) => arr.map(Number).map((_, idx, a) => {
    if (idx < W - 1) return null;
    const s = a.slice(idx - (W - 1), idx + 1);
    return +(s.reduce((p, v) => p + v, 0) / W).toFixed(2);
  }).filter(x => x != null);
  const rollStd = (arr) => arr.map(Number).map((_, idx, a) => {
    if (idx < W - 1) return null;
    const s = a.slice(idx - (W - 1), idx + 1);
    const m = s.reduce((p, v) => p + v, 0) / W;
    const v = Math.sqrt(s.reduce((p, v) => p + (v - m) ** 2, 0) / W);
    return +v.toFixed(2);
  }).filter(x => x != null);

  // regression (gdp ~ a + b*infl)
  const reg = linearRegression(infl, gdp);

  // histogram (1% bins)
  const { centers, counts } = hist1D(infl, 1);

  // decades
  const byDec = {};
  yrs.forEach((y, i) => {
    const d = Math.floor(y / 10) * 10;
    if (!byDec[d]) byDec[d] = { g: [], p: [] };
    byDec[d].g.push(gdp[i]);
    byDec[d].p.push(infl[i]);
  });
  const decLabels = Object.keys(byDec).sort();
  const decG = decLabels.map(d => +avg(byDec[d].g).toFixed(2));
  const decP = decLabels.map(d => +avg(byDec[d].p).toFixed(2));

  // safe KPIs if backend didn’t include them
  const kpi = j.kpi || {};
  if (kpi.records == null) kpi.records = yrs.length;
  if (kpi.unique_years == null) kpi.unique_years = new Set(yrs).size;
  if (kpi.inflation_mean == null) kpi.inflation_mean = +avg(infl).toFixed(2);
  if (kpi.gdp_max == null) kpi.gdp_max = +Math.max(...gdp).toFixed(2);
  if (kpi.corr_gdp_inflation == null) kpi.corr_gdp_inflation = +corr(infl, gdp).toFixed(2);

  // cumulative GDP growth from first year (baseline 0)
  const base = gdp[0] || 0;
  const cum = gdp.map((v, i) => +(gdp.slice(0, i + 1).reduce((p, x) => p + x, 0)).toFixed(2));

  return {
    ok: true,
    meta: j.meta || {},
    kpi,
    series: { years: yrs, inflation: infl, gdp },
    yoy: { years: yoyYears, gdp: yoyGDP, summary: { positive: pos, negative: neg, zero } },
    rolling: { window: W, years: rollingYears, gdp_ma: roll(gdp), infl_ma: roll(infl), infl_std: rollStd(infl) },
    regression: { slope: reg.slope, intercept: reg.intercept, x_min: Math.min(...infl), x_max: Math.max(...infl) },
    decades: { labels: decLabels, gdp_mean: decG, infl_mean: decP },
    extra: { infl_hist_centers: centers, infl_hist_counts: counts, cum_gdp: cum }
  };
}
function avg(a) { return a.reduce((p, v) => p + v, 0) / (a.length || 1); }
function corr(x, y) {
  const n = Math.min(x.length, y.length);
  let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
  for (let i = 0; i < n; i++) {
    const xi = x[i], yi = y[i];
    sx += xi; sy += yi; sxx += xi * xi; syy += yi * yi; sxy += xi * yi;
  }
  const cov = sxy / n - (sx / n) * (sy / n);
  const vx = sxx / n - (sx / n) ** 2;
  const vy = syy / n - (sy / n) ** 2;
  return cov / Math.sqrt(vx * vy);
}
function linearRegression(x, y) {
  const n = Math.min(x.length, y.length);
  let sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (let i = 0; i < n; i++) { const xi = x[i], yi = y[i]; sx += xi; sy += yi; sxx += xi * xi; sxy += xi * yi; }
  const denom = n * sxx - sx * sx || 1;
  const slope = (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  return { slope, intercept };
}
function hist1D(arr, bin = 1) {
  const min = Math.floor(Math.min(...arr));
  const max = Math.ceil(Math.max(...arr));
  const bins = Math.max(1, Math.round((max - min) / bin));
  const counts = Array(bins).fill(0);
  const centers = Array.from({ length: bins }, (_, i) => min + bin * i + bin / 2);
  arr.forEach(v => {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / bin)));
    counts[idx] += 1;
  });
  return { centers, counts };
}

/* ========= KPIs, story & captions ========= */
function renderKPIs(k) {
  countUp($("#kpiRecords"), k.records || 0);
  countUp($("#kpiCategories"), k.unique_years || 0);
  countUp($("#kpiAvg"), Math.round(k.inflation_mean ?? 0));
  countUp($("#kpiMax"), Math.round(scaleGDP(k.gdp_max ?? 0)));
}
function simpleSign(r) {
  if (typeof r !== "number" || !isFinite(r)) return "no clear link";
  const a = Math.abs(r);
  if (a < 0.2) return "no clear link";
  if (a < 0.4) return r > 0 ? "weak positive" : "weak negative";
  if (a < 0.6) return r > 0 ? "moderate positive" : "moderate negative";
  return r > 0 ? "strong positive" : "strong negative";
}
function writeStory() {
  if (!METRICS) return;
  const yrs = METRICS.series.years, first = yrs[0], last = yrs[yrs.length - 1];
  const infl = METRICS.series.inflation, gdp = METRICS.series.gdp;
  const iMax = infl.indexOf(Math.max(...infl));
  const iMin = infl.indexOf(Math.min(...infl));
  const cg = METRICS.extra.cum_gdp;
  $("#storyContent").innerHTML = `
    <p>We cover <strong>${first}–${last}</strong> (${yrs.length} years).</p>
    <p>Average inflation: <strong>${(METRICS.kpi.inflation_mean ?? 0).toFixed(2)}%</strong>.
       High: <strong>${yrs[iMax]}</strong> (~${infl[iMax].toFixed(2)}%).
       Low: <strong>${yrs[iMin]}</strong> (~${infl[iMin].toFixed(2)}%).</p>
    <p>Overall GDP (sum of yearly growth) path shown below; use 1994 (dashed line) to compare pre/post.</p>
    <p>GDP and inflation show a <strong>${simpleSign(METRICS.kpi.corr_gdp_inflation)}</strong> relationship (r ≈ ${METRICS.kpi.corr_gdp_inflation}).</p>`;
}
function writeCaptions() {
  if (!METRICS) return;
  const yrs = METRICS.series.years, first = yrs[0], last = yrs[yrs.length - 1];
  const show1994 = first <= 1994 && last >= 1994;
  $("#cap-gdp").textContent     = `GDP from ${first}–${last}${show1994 ? "; dashed line marks 1994" : ""}.`;
  $("#cap-infl").textContent    = `Inflation from ${first - 1}–${last}${show1994 ? "; dashed line marks 1994" : ""}.`;
  $("#cap-overlay").textContent = `GDP (left) and inflation (right) together; compare co-movement.`;
  $("#cap-scatter").textContent = `Each year: x = inflation (%), y = GDP growth (%). Trend summarizes the tendency.`;
  $("#cap-yoy").textContent     = `GDP year-over-year change (Δ). Above 0 = expansion; below 0 = contraction.`;
  $("#cap-donut").textContent   = `Share of positive / negative / zero GDP-YoY years.`;
  $("#cap-decade").textContent  = `Decade averages for GDP & inflation.`;
  $("#cap-rolling").textContent = `5-year rolling means (smoother trends).`;
  $("#cap-hist").textContent    = `Histogram of inflation (%); wider spread ⇒ more volatility.`;
  $("#cap-cum").textContent     = `Cumulative sum of GDP growth from the first year.`;
  $("#cap-vol").textContent     = `Inflation volatility (5-year rolling std).`;
  $("#cap-yoysc").textContent   = `YoY scatter: x = Δinflation, y = ΔGDP (if provided).`;
}

/* ========= table ========= */
function rowsNow() {
  const y = METRICS.series.years;
  const g = METRICS.series.gdp.map(scaleGDP);
  const i = METRICS.series.inflation;
  return y.map((yy, k) => ({ year: yy, gdp: g[k], inflation: i[k] }));
}
function filtered() {
  const q = ($("#tableSearch")?.value || "").toLowerCase();
  let r = rowsNow();
  if (q) r = r.filter(x => String(x.year).includes(q) || String(x.gdp).toLowerCase().includes(q) || String(x.inflation).toLowerCase().includes(q));
  return r;
}
function renderTable() {
  const r = filtered(), pages = Math.max(1, Math.ceil(r.length / pageSize));
  page = Math.min(page, pages);
  const start = (page - 1) * pageSize, slice = r.slice(start, start + pageSize), tb = $("#tableBody");
  tb.innerHTML = slice.map((x, i) =>
    `<tr><td>${start + i + 1}</td><td>${x.year}</td><td class="col-gdp">${formatGDP(x.gdp)}</td><td class="col-infl">${x.inflation}</td></tr>`
  ).join("") || `<tr><td colspan="4" class="muted">No rows.</td></tr>`;
  $("#pageInfo").textContent = `${page} / ${pages}`;
  $$(".col-gdp").forEach(td => td.style.display = showGDP ? "" : "none");
  $$(".col-infl").forEach(td => td.style.display = showInfl ? "" : "none");
}

/* ========= chart options ========= */
function commonOptions({ legend = true, beginAtZero = false, xTitle = "Year", yTitle = "Value", dual = false, y1Title = "Value" } = {}) {
  const s = axisColors();
  const ann = ANNOTATE_1994 ? {
    annotations: {
      v1994: { type: 'line', xMin: 1994, xMax: 1994, borderDash: [6, 4], borderWidth: 1, borderColor: ACCENT }
    }
  } : {};
  const base = {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    animation: { duration: 400 },
    plugins: {
      legend: { display: legend, labels: { color: s.tick } },
      zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } },
      annotation: ann
    },
    scales: {
      x: { title: { display: true, text: xTitle, color: s.tick }, ticks: { color: s.tick }, grid: { color: s.grid } },
      y: { beginAtZero, title: { display: true, text: yTitle, color: s.tick }, ticks: { color: s.tick }, grid: { color: s.grid } }
    }
  };
  if (dual) base.scales.y1 = { position: 'right', title: { display: true, text: y1Title, color: s.tick }, grid: { drawOnChartArea: false }, ticks: { color: s.tick } };
  return base;
}
function destroy(id) { if (CHARTS[id]) { CHARTS[id].destroy(); CHARTS[id] = null; } }

/* ========= build charts (fixed scatter & doughnut) ========= */
function buildCharts() {
  const yrs = METRICS.series.years;
  const gdpRaw = METRICS.series.gdp.map(Number);
  const infl = METRICS.series.inflation.map(Number);
  const gdp = gdpRaw.map(scaleGDP);

  ANNOTATE_1994 = yrs[0] <= 1994 && yrs[yrs.length - 1] >= 1994;

  // ranges for tidy axes
  const xMin = Math.min(...infl), xMax = Math.max(...infl), xPad = Math.max(1, (xMax - xMin) * 0.1);
  const yMin = Math.min(...gdpRaw), yMax = Math.max(...gdpRaw), yPad = Math.max(1, (yMax - yMin) * 0.1);

  destroy('gdp');
  CHARTS.gdp = new Chart($("#gdpChart"), {
    type: "line",
    data: { labels: yrs, datasets: [{ label: "GDP", data: gdp, tension: .25, borderColor: ACCENT }] },
    options: commonOptions({ legend: false, yTitle: unit === "zar_b" ? "GDP (Rand billions)" : "GDP growth (%)" })
  });

  destroy('infl');
  CHARTS.infl = new Chart($("#inflChart"), {
    type: "bar",
    data: { labels: yrs, datasets: [{ label: "Inflation (%)", data: infl }] },
    options: commonOptions({ legend: false, beginAtZero: true, yTitle: "Inflation (%)" })
  });

  destroy('overlay');
  CHARTS.overlay = new Chart($("#overlayChart"), {
    type: "line",
    data: {
      labels: yrs,
      datasets: [
        { label: "GDP", data: gdp, yAxisID: "y", tension: .25 },
        { label: "Inflation (%)", data: infl, yAxisID: "y1", tension: .25 }
      ]
    },
    options: commonOptions({ legend: true, dual: true, yTitle: unit === "zar_b" ? "GDP (Rand billions)" : "GDP growth (%)", y1Title: "Inflation (%)" })
  });

  destroy('scatter');
  const points = infl.map((x, i) => ({ x, y: gdpRaw[i] })); // unscaled for correlation visual
  const { slope, intercept } = linearRegression(infl, gdpRaw);
  const lineX1 = xMin - xPad, lineX2 = xMax + xPad;
  const lineY1 = slope * lineX1 + intercept, lineY2 = slope * lineX2 + intercept;
  const scatterOpts = commonOptions({ legend: true, xTitle: "Inflation (%)", yTitle: "GDP growth (%)" });
  scatterOpts.scales.x.min = lineX1; scatterOpts.scales.x.max = lineX2;
  scatterOpts.scales.y.min = Math.min(lineY1, lineY2, yMin - yPad);
  scatterOpts.scales.y.max = Math.max(lineY1, lineY2, yMax + yPad);
  CHARTS.scatter = new Chart($("#scatterChart"), {
    type: "scatter",
    data: {
      datasets: [
        { label: "Years", data: points },
        { label: "Trend", type: "line", data: [{ x: lineX1, y: lineY1 }, { x: lineX2, y: lineY2 }], pointRadius: 0, borderColor: ACCENT }
      ]
    },
    options: scatterOpts
  });

  destroy('yoy');
  CHARTS.yoy = new Chart($("#yoyChart"), {
    type: "line",
    data: { labels: METRICS.yoy.years, datasets: [{ label: "GDP YoY (Δ)", data: METRICS.yoy.gdp, tension: .25, fill: true }] },
    options: commonOptions({ legend: false, yTitle: "GDP YoY (Δ)" })
  });

  // ✅ true doughnut: no axes, real counts
  destroy('donut');
  const S = METRICS.yoy.summary;
  const donutColors = ['#60a5fa', '#fca5a5', '#fbbf24'];
  const sAxis = axisColors();
  CHARTS.donut = new Chart($("#donutChart"), {
    type: "doughnut",
    data: {
      labels: ["Positive", "Negative", "Zero"],
      datasets: [{ data: [S.positive, S.negative, S.zero], backgroundColor: donutColors, borderWidth: 0, hoverOffset: 6 }]
    },
    options: {
      responsive: true,
      cutout: '64%',
      plugins: {
        legend: { position: 'top', labels: { color: sAxis.tick } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed} years` } }
      }
    }
  });

  destroy('decade');
  CHARTS.decade = new Chart($("#decadeChart"), {
    type: "bar",
    data: {
      labels: METRICS.decades.labels,
      datasets: [
        { label: "GDP mean (%)", data: METRICS.decades.gdp_mean },
        { label: "Inflation mean (%)", data: METRICS.decades.infl_mean }
      ]
    },
    options: commonOptions({ legend: true, yTitle: "Mean value" })
  });

  destroy('rolling');
  CHARTS.rolling = new Chart($("#rollingChart"), {
    type: "line",
    data: {
      labels: METRICS.rolling.years,
      datasets: [
        { label: `GDP MA(${METRICS.rolling.window})`, data: METRICS.rolling.gdp_ma, tension: .25 },
        { label: `Inflation MA(${METRICS.rolling.window})`, data: METRICS.rolling.infl_ma, tension: .25 }
      ]
    },
    options: commonOptions({ legend: true, yTitle: "Rolling mean" })
  });

  destroy('hist');
  CHARTS.hist = new Chart($("#histChart"), {
    type: "bar",
    data: {
      labels: METRICS.extra.infl_hist_centers.map(v => v.toFixed(0)),
      datasets: [{ label: "Count", data: METRICS.extra.infl_hist_counts }]
    },
    options: commonOptions({ legend: false, beginAtZero: true, xTitle: "Inflation (%)", yTitle: "Frequency" })
  });

  destroy('cum');
  CHARTS.cum = new Chart($("#cumChart"), {
    type: "line",
    data: { labels: yrs, datasets: [{ label: "Cum. GDP Growth", data: METRICS.extra.cum_gdp, tension: .25 }] },
    options: commonOptions({ legend: false, yTitle: "Cumulative (sum of growth)" })
  });

  destroy('yoyScatter');
  if (METRICS.yoy.inflation && METRICS.yoy.inflation.length === METRICS.yoy.gdp.length) {
    CHARTS.yoyScatter = new Chart($("#yoyScatterChart"), {
      type: "scatter",
      data: { datasets: [{ label: "YoY points", data: METRICS.yoy.inflation.map((x, i) => ({ x, y: METRICS.yoy.gdp[i] })) }] },
      options: commonOptions({ legend: false, xTitle: "Inflation YoY", yTitle: "GDP YoY" })
    });
  }

  // hook zoom reset to table filtering
  [CHARTS.gdp, CHARTS.infl, CHARTS.overlay, CHARTS.scatter].forEach(ch => {
    if (ch?.options?.plugins?.zoom) {
      ch.options.plugins.zoom.onZoomComplete = ({ chart }) => filterTableToVisibleRange(chart);
    }
  });
}
function rebuildCharts() { buildCharts(); }

function filterTableToVisibleRange(chart) {
  const sc = chart.scales?.x; if (!sc) return;
  const min = sc.min, max = sc.max; if (min == null || max == null) return;
  const y = METRICS.series.years;
  const rows = rowsNow().filter((_, i) => y[i] >= min && y[i] <= max);
  page = 1;
  const tb = $("#tableBody");
  const slice = rows.slice(0, pageSize);
  tb.innerHTML = slice.map((r, i) =>
    `<tr><td>${i + 1}</td><td>${r.year}</td><td class="col-gdp">${formatGDP(r.gdp)}</td><td class="col-infl">${r.inflation}</td></tr>`
  ).join("") || `<tr><td colspan="4" class="muted">No rows in range.</td></tr>`;
  $("#pageInfo").textContent = "filtered";
}

/* ========= UI wiring ========= */
function renderDatasetCards() {
  const wrap = $("#datasetCards"); if (!wrap || !METRICS?.meta?.datasets) return;
  const g = METRICS.meta.datasets.gdp, i = METRICS.meta.datasets.inflation;
  wrap.innerHTML = [g, i].map(d => `
    <div class="dataset-card" data-name="${d.name}">
      <h4 style="margin:0 0 6px 0">${d.name}</h4>
      <div class="muted" style="font-size:13px">Rows: <strong>${d.row_count}</strong></div>
      <div class="muted" style="font-size:13px">Years: <strong>${d.year_min ?? "—"}–${d.year_max ?? "—"}</strong></div>
      <div class="muted" style="font-size:13px">Non-null: <strong>${d.non_null_points}</strong>, Nulls: <strong>${d.null_points}</strong></div>
      <code style="display:block;white-space:pre-wrap;margin-top:4px">${(d.columns_preview||[]).join(", ")}</code>
    </div>`).join("");
}
function showModal(show) {
  const m = $("#datasetModal"); if (!m) return;
  m.classList.toggle("show", !!show);
  m.setAttribute("aria-hidden", show ? "false" : "true");
}
function wireUI() {
  $("#tableSearch")?.addEventListener("input", () => { page = 1; renderTable(); });
  $("#prevPage")?.addEventListener("click", () => { if (page > 1) { page--; renderTable(); } });
  $("#nextPage")?.addEventListener("click", () => { page++; renderTable(); });
  $("#showGDP")?.addEventListener("change", e => { showGDP = e.target.checked; renderTable(); });
  $("#showInfl")?.addEventListener("change", e => { showInfl = e.target.checked; renderTable(); });
  $("#unitSelect")?.addEventListener("change", e => { unit = e.target.value; renderKPIs(METRICS.kpi); buildCharts(); renderTable(); writeCaptions(); });
  $("#reload")?.addEventListener("click", init);
  $("#datasetBtn")?.addEventListener("click", () => { renderDatasetCards(); showModal(true); });
  $("#modalClose")?.addEventListener("click", () => showModal(false));
  $("#modalCancel")?.addEventListener("click", () => showModal(false));
  $("#resetZoom")?.addEventListener("click", () => {
    Object.values(CHARTS).forEach(ch => { try { ch.resetZoom && ch.resetZoom(); } catch (_) {} });
    toast("Zoom reset"); renderTable();
  });
}

/* ========= init ========= */
async function init() {
  try {
    toast("Loading…");
    const raw = await fetchMetrics();
    METRICS = ensureComputed(raw);
    renderKPIs(METRICS.kpi);
    buildCharts();
    renderTable();
    writeStory();
    writeCaptions();
    renderDatasetCards();
    toast("Loaded ✓");
  } catch (e) {
    console.error(e); toast(e.message || "Failed to load");
  }
}

document.addEventListener("DOMContentLoaded", () => { wireUI(); if ($("#gdpChart")) init(); });
