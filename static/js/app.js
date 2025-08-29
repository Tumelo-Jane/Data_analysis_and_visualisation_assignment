/* ========= tiny helpers ========= */
const $ = (s, c = document) => c.querySelector(s);
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

/* ========= theme ========= */
(function theme() {
  const KEY = "da-theme", btn = $("#themeToggle"); const saved = localStorage.getItem(KEY);
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  if (btn) {
    btn.setAttribute("aria-pressed", String((saved || "light") === "dark"));
    btn.addEventListener("click", () => {
      const nowDark = document.documentElement.getAttribute("data-theme") !== "dark";
      document.documentElement.setAttribute("data-theme", nowDark ? "dark" : "light");
      localStorage.setItem(KEY, nowDark ? "dark" : "light");
      btn.setAttribute("aria-pressed", String(nowDark));
      setChartDefaults(); rebuildCharts(); writeCaptions();
    });
  }
})();

/* ========= Chart.js + plugins ========= */
(function register() {
  if (!(window.Chart && Chart.register)) return;
  try {
    const z = window["chartjs-plugin-zoom"];
    const zoom = z?.zoomPlugin || z?.default || z; if (zoom) Chart.register(zoom);
  } catch {}
  try {
    const ann = window["chartjs-plugin-annotation"]; Chart.register(ann?.default || ann);
  } catch {}
  setChartDefaults();
})();
function setChartDefaults() {
  if (!window.Chart) return;
  const s = axisColors();
  Chart.defaults.font.family = '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = s.tick;
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.point.radius = 0;
  Chart.defaults.elements.bar.borderRadius = 2;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
}

/* ========= globals ========= */
let METRICS = null, CHARTS = {}, page = 1, pageSize = 12, showGDP = true, showInfl = true;
const ACCENT = getComputedStyle(document.documentElement).getPropertyValue('--accent') || '#7c3aed';
let ANNOTATE_1994 = false;

/* ========= data ========= */
async function fetchMetrics() {
  const r = await fetch('/api/metrics/'); const j = await r.json();
  if (!r.ok || !j.ok) throw new Error(j.error || 'Failed to load data');
  return j;
}
function formatGDP(v) { if (v == null || Number.isNaN(v)) return "—"; return String(v); }

/* ========= compute ========= */
function ensureComputed(j) {
  const yrs = j.series?.years?.slice() || [];
  const infl = (j.series?.inflation || []).map(Number);
  const gdp = (j.series?.gdp || []).map(Number);

  const diff = a => { const out = []; for (let i = 1; i < a.length; i++) out.push(+((a[i] - a[i - 1])).toFixed(3)); return out; };
  const yoyYears = j.yoy?.years || yrs.slice(1);
  const yoyGdp = j.yoy?.gdp || diff(gdp);
  const yoyInfl = j.yoy?.inflation || diff(infl);

  const yearsSummary = (() => { let p = 0, n = 0, z = 0; for (const v of gdp) { if (v > 0) p++; else if (v < 0) n++; else z++; } return { positive: p, negative: n, zero: z }; })();
  const summary = j.yoy?.summary || yearsSummary;

  const W = 5;
  const rollingYears = yrs.filter((_, i) => i >= W - 1);
  const roll = arr => { const out = []; for (let i = W - 1; i < arr.length; i++) { let s = 0; for (let k = i - W + 1; k <= i; k++) s += arr[k]; out.push(+((s / W)).toFixed(3)); } return out; };
  const rollStd = arr => { const out = []; for (let i = W - 1; i < arr.length; i++) { const seg = arr.slice(i - W + 1, i + 1); const m = seg.reduce((p, v) => p + v, 0) / W; const v = Math.sqrt(seg.reduce((p, v) => p + (v - m) ** 2, 0) / W); out.push(+v.toFixed(3)); } return out; };

  const regression = j.regression || linRegWithBounds(infl, gdp);
  const { centers, counts } = hist1D(infl, 1);

  const byDec = {}; yrs.forEach((y, i) => { const d = Math.floor(y / 10) * 10; (byDec[d] ??= { g: [], p: [] }).g.push(gdp[i]); byDec[d].p.push(infl[i]); });
  const decLabels = Object.keys(byDec).sort((a, b) => +a - +b);
  const decG = decLabels.map(d => +avg(byDec[d].g).toFixed(3));
  const decP = decLabels.map(d => +avg(byDec[d].p).toFixed(3));

  const kpi = { ...(j.kpi || {}) };
  if (kpi.records == null) kpi.records = yrs.length;
  if (kpi.unique_years == null) kpi.unique_years = new Set(yrs).size;
  if (kpi.inflation_mean == null) kpi.inflation_mean = +avg(infl).toFixed(2);

  if (kpi.gdp_mean == null) kpi.gdp_mean = +avg(gdp).toFixed(2);
  if (kpi.gdp_std == null) {
    const m = avg(gdp);
    const s = Math.sqrt(gdp.reduce((p, v) => p + (v - m) ** 2, 0) / (gdp.length || 1));
    kpi.gdp_std = +s.toFixed(2);
  }
  if (kpi.gdp_max == null) kpi.gdp_max = +Math.max(...gdp).toFixed(2);
  if (kpi.corr_gdp_inflation == null) kpi.corr_gdp_inflation = +corr(infl, gdp).toFixed(2);

  const cum = gdp.map((_, i) => +(gdp.slice(0, i + 1).reduce((p, x) => p + x, 0)).toFixed(3));

  return {
    ok: true,
    meta: j.meta || {},
    kpi,
    series: { years: yrs, inflation: infl, gdp },
    yoy: { years: yoyYears, gdp: yoyGdp, inflation: yoyInfl, summary },
    rolling: { window: W, years: rollingYears, gdp_ma: roll(gdp), infl_ma: roll(infl), infl_std: rollStd(infl) },
    regression,
    decades: { labels: decLabels, gdp_mean: decG, infl_mean: decP },
    extra: { infl_hist_centers: centers, infl_hist_counts: counts, cum_gdp: cum }
  };
}
function avg(a) { return a.reduce((p, v) => p + v, 0) / (a.length || 1); }
function corr(x, y) { const n = Math.min(x.length, y.length); let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0; for (let i = 0; i < n; i++) { const xi = x[i], yi = y[i]; sx += xi; sy += yi; sxx += xi * xi; syy += yi * yi; sxy += xi * yi; } const cov = sxy / n - (sx / n) * (sy / n); const vx = sxx / n - (sx / n) ** 2; const vy = syy / n - (sy / n) ** 2; return cov / Math.sqrt((vx || 1) * (vy || 1)); }
function linRegWithBounds(x, y) { const n = Math.min(x.length, y.length); let sx = 0, sy = 0, sxx = 0, sxy = 0; for (let i = 0; i < n; i++) { const xi = x[i], yi = y[i]; sx += xi; sy += yi; sxx += xi * xi; sxy += xi * yi; } const denom = n * sxx - sx * sx || 1; const slope = (n * sxy - sx * sy) / denom; const intercept = (sy - slope * sx) / n; return { slope, intercept, x_min: Math.min(...x), x_max: Math.max(...x) }; }
function hist1D(arr, bin = 1) { if (!arr.length) return { centers: [], counts: [] }; const min = Math.floor(Math.min(...arr)); const max = Math.ceil(Math.max(...arr)); const bins = Math.max(1, Math.round((max - min) / bin)); const counts = Array(bins).fill(0); const centers = Array.from({ length: bins }, (_, i) => min + bin * i + bin / 2); arr.forEach(v => { const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / bin))); counts[idx] += 1; }); return { centers, counts }; }

/* ========= content ========= */
function renderKPIs(k) {
  countUp($("#kpiRecords"), k.records || 0);
  countUp($("#kpiCategories"), k.unique_years || 0);
  countUp($("#kpiAvg"), Math.round(k.inflation_mean ?? 0));
  countUp($("#kpiMax"), Math.round(k.gdp_max ?? 0));
}
function writeStory() {
  if (!METRICS) return;
  const yrs = METRICS.series.years;
  const gdp = METRICS.series.gdp.map(Number);
  const infl = METRICS.series.inflation.map(Number);
  const first = yrs[0], last = yrs[yrs.length - 1];

  const mean = arr => arr.reduce((p, v) => p + v, 0) / (arr.length || 1);
  const std = arr => { const m = mean(arr); return Math.sqrt(arr.reduce((p, v) => p + (v - m) ** 2, 0) / (arr.length || 1)); };

  const gMean = +mean(gdp).toFixed(2);
  const gStd = +std(gdp).toFixed(2);
  const iMean = +(METRICS.kpi?.inflation_mean ?? mean(infl)).toFixed(2);
  const iStd = +(METRICS.kpi?.inflation_std ?? std(infl)).toFixed(2);
  const r = +(METRICS.kpi?.corr_gdp_inflation ?? 0).toFixed(2);

  $("#storyContent").innerHTML = `
    <p>Coverage: <strong>${first}–${last}</strong> (${yrs.length} years). The dashed marker shows <strong>1994</strong>.</p>
    <p>Average GDP growth <strong>${gMean}%</strong> (std ${gStd}); average inflation <strong>${iMean}%</strong> (std ${iStd}).</p>
    <p>GDP ↔ inflation correlation: <strong>${r}</strong>.</p>
  `;
}
function writeCaptions() {
  if (!METRICS) return;
  const yrs = METRICS.series.years, first = yrs[0], last = yrs[yrs.length - 1];
  const show1994 = first <= 1994 && last >= 1994;

  $("#cap-gdp").textContent = `GDP from ${first}–${last}${show1994 ? "; dashed line marks 1994" : ""}.`;
  $("#cap-infl").textContent = `Inflation from ${first - 1}–${last}${show1994 ? "; dashed line marks 1994" : ""}.`;
  $("#cap-overlay").textContent = `GDP (left) and inflation (right) together; compare co-movement.`;
  $("#cap-scatter").textContent = `Each year: x = inflation (%), y = GDP growth (%). Trend summarizes the tendency.`;
  $("#cap-yoy").textContent = `GDP year-over-year change (Δ). Above 0 = expansion; below 0 = contraction.`;
  $("#cap-donut").textContent = `Share of positive / negative / zero GDP-YoY years.`;
  $("#cap-rolling").textContent = `5-year rolling means (smoother trends).`;
  $("#cap-hist").textContent = `Histogram of inflation (%); wider spread ⇒ more volatility.`;
  $("#cap-cum").textContent = `Cumulative sum of GDP growth from the first year.`;
  $("#cap-vol").textContent = `Inflation volatility (5-year rolling std).`;
  $("#cap-yoysc").textContent = `YoY scatter: x = Δinflation, y = ΔGDP.`;
}

/* ========= table ========= */
function rowsNow() {
  const y = METRICS.series.years, g = METRICS.series.gdp, i = METRICS.series.inflation;
  return y.map((yy, k) => ({ year: yy, gdp: g[k], inflation: i[k] }));
}
function filtered() {
  const q = ($("#tableSearch")?.value || "").toLowerCase(); let r = rowsNow();
  if (q) r = r.filter(x => String(x.year).includes(q) || String(x.gdp).toLowerCase().includes(q) || String(x.inflation).toLowerCase().includes(q));
  return r;
}
function renderTable() {
  const r = filtered(), pages = Math.max(1, Math.ceil(r.length / pageSize)); page = Math.min(page, pages);
  const start = (page - 1) * pageSize, slice = r.slice(start, start + pageSize), tb = $("#tableBody");
  if (!tb) return;
  tb.innerHTML = slice.map((x, i) => `<tr><td>${start + i + 1}</td><td>${x.year}</td><td class="col-gdp">${formatGDP(x.gdp)}</td><td class="col-infl">${x.inflation}</td></tr>`).join("")
    || `<tr><td colspan="4" class="muted">No rows.</td></tr>`;
  $("#pageInfo") && ($("#pageInfo").textContent = `${page} / ${pages}`);
  $$(".col-gdp").forEach(td => td.style.display = showGDP ? "" : "none");
  $$(".col-infl").forEach(td => td.style.display = showInfl ? "" : "none");   // FIXED syntax
}

/* ========= chart options ========= */
function commonOptions({ legend = true, beginAtZero = false, xTitle = "Year", yTitle = "Value", dual = false, y1Title = "Value" } = {}) {
  const s = axisColors();
  const ann = ANNOTATE_1994 ? { annotations: { v1994: { type: 'line', xMin: 1994, xMax: 1994, borderDash: [6, 4], borderWidth: 1, borderColor: ACCENT } } } : {};
  const base = {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    animation: { duration: 350 },
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

/* ========= build charts ========= */
function buildCharts() {
  if (!METRICS) return;
  const yrs = METRICS.series.years;
  const gdpRaw = METRICS.series.gdp.map(Number);
  const infl = METRICS.series.inflation.map(Number);
  ANNOTATE_1994 = yrs[0] <= 1994 && yrs[yrs.length - 1] >= 1994;

  const palette = {
    blue: getComputedStyle(document.documentElement).getPropertyValue('--line-blue') || '#60a5fa',
    pink: getComputedStyle(document.documentElement).getPropertyValue('--line-pink') || '#f472b6',
    bar: getComputedStyle(document.documentElement).getPropertyValue('--bar-blue') || '#2563eb'
  };

  const xMin = Math.min(...infl), xMax = Math.max(...infl), xPad = Math.max(1, (xMax - xMin) * 0.1);
  const yMin = Math.min(...gdpRaw), yMax = Math.max(...gdpRaw), yPad = Math.max(1, (yMax - yMin) * 0.1);

  destroy('gdp');
  const gdpCanvas = $("#gdpChart");
  if (gdpCanvas) {
    CHARTS.gdp = new Chart(gdpCanvas, {
      type: "line",
      data: { labels: yrs, datasets: [{ label: "GDP (%)", data: gdpRaw, tension: .25, borderColor: palette.blue, fill: false }] },
      options: commonOptions({ legend: false, yTitle: "GDP (%)" })
    });
  }

  destroy('infl');
  const inflCanvas = $("#inflChart");
  if (inflCanvas) {
    CHARTS.infl = new Chart(inflCanvas, {
      type: "bar",
      data: { labels: yrs, datasets: [{ label: "Inflation (%)", data: infl, backgroundColor: palette.bar }] },
      options: commonOptions({ legend: false, beginAtZero: true, yTitle: "Inflation (%)" })
    });
  }

  destroy('overlay');
  const overlayCanvas = $("#overlayChart");
  if (overlayCanvas) {
    CHARTS.overlay = new Chart(overlayCanvas, {
      type: "line",
      data: {
        labels: yrs,
        datasets: [
          { label: "GDP (%)", data: gdpRaw, yAxisID: "y", tension: .25, borderColor: palette.blue },
          { label: "Inflation (%)", data: infl, yAxisID: "y1", tension: .25, borderColor: palette.pink }
        ]
      },
      options: commonOptions({ legend: true, dual: true, yTitle: "GDP (%)", y1Title: "Inflation (%)" })
    });
  }

  destroy('scatter');
  const scatterCanvas = $("#scatterChart");
  if (scatterCanvas) {
    const pts = infl.map((x, i) => ({ x, y: gdpRaw[i] }));
    const { slope, intercept, x_min, x_max } = METRICS.regression || linRegWithBounds(infl, gdpRaw);
    const lineX1 = (x_min ?? xMin) - xPad, lineX2 = (x_max ?? xMax) + xPad;
    const lineY1 = slope * lineX1 + intercept, lineY2 = slope * lineX2 + intercept;
    const sopts = commonOptions({ legend: true, xTitle: "Inflation (%)", yTitle: "GDP (%)" });
    sopts.scales.x.min = lineX1; sopts.scales.x.max = lineX2;
    sopts.scales.y.min = Math.min(lineY1, lineY2, yMin - yPad); sopts.scales.y.max = Math.max(lineY1, lineY2, yMax + yPad);
    CHARTS.scatter = new Chart(scatterCanvas, {
      type: "scatter",
      data: {
        datasets: [
          { label: "Years", data: pts, backgroundColor: palette.blue },
          { label: "Trend", type: "line", data: [{ x: lineX1, y: lineY1 }, { x: lineX2, y: lineY2 }], pointRadius: 0, borderColor: ACCENT }
        ]
      },
      options: sopts
    });
  }

  destroy('yoy');
  const yoyCanvas = $("#yoyChart");
  if (yoyCanvas) {
    CHARTS.yoy = new Chart(yoyCanvas, {
      type: "line",
      data: { labels: METRICS.yoy.years, datasets: [{ label: "GDP YoY (Δ)", data: METRICS.yoy.gdp, tension: .25, fill: true, borderColor: palette.blue, backgroundColor: "rgba(96,165,250,.12)" }] },
      options: commonOptions({ legend: false, yTitle: "GDP YoY (Δ)" })
    });
  }

  destroy('donut');
  const donutCanvas = $("#donutChart");
  if (donutCanvas) {
    const S = METRICS.yoy.summary, donutColors = ['#60a5fa', '#fca5a5', '#fbbf24']; const t = axisColors();
    CHARTS.donut = new Chart(donutCanvas, {
      type: "doughnut",
      data: { labels: ["Positive", "Negative", "Zero"], datasets: [{ data: [S.positive, S.negative, S.zero], backgroundColor: donutColors, borderWidth: 0, hoverOffset: 6 }] },
      options: { responsive: true, cutout: '64%', plugins: { legend: { position: 'top', labels: { color: t.tick } }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed} years` } } } }
    });
  }

  destroy('decade');
  const decadeCanvas = $("#decadeChart");
  if (decadeCanvas) {
    CHARTS.decade = new Chart(decadeCanvas, {
      type: "bar",
      data: {
        labels: METRICS.decades.labels,
        datasets: [
          { label: "GDP mean (%)", data: METRICS.decades.gdp_mean, backgroundColor: palette.blue },
          { label: "Inflation mean (%)", data: METRICS.decades.infl_mean, backgroundColor: palette.pink }
        ]
      },
      options: commonOptions({ legend: true, yTitle: "Mean value" })
    });
  }

  destroy('rolling');
  const rollingCanvas = $("#rollingChart");
  if (rollingCanvas) {
    CHARTS.rolling = new Chart(rollingCanvas, {
      type: "line",
      data: {
        labels: METRICS.rolling.years,
        datasets: [
          { label: `GDP MA(${METRICS.rolling.window})`, data: METRICS.rolling.gdp_ma, tension: .25, borderColor: palette.blue },
          { label: `Inflation MA(${METRICS.rolling.window})`, data: METRICS.rolling.infl_ma, tension: .25, borderColor: palette.pink }
        ]
      },
      options: commonOptions({ legend: true, yTitle: "Rolling mean" })
    });
  }

  destroy('hist');
  const histCanvas = $("#histChart");
  if (histCanvas) {
    CHARTS.hist = new Chart(histCanvas, {
      type: "bar",
      data: { labels: METRICS.extra.infl_hist_centers.map(v => v.toFixed(0)), datasets: [{ label: "Count", data: METRICS.extra.infl_hist_counts, backgroundColor: palette.bar }] },
      options: commonOptions({ legend: false, beginAtZero: true, xTitle: "Inflation (%)", yTitle: "Frequency" })
    });
  }

  destroy('cum');
  const cumCanvas = $("#cumChart");
  if (cumCanvas) {
    CHARTS.cum = new Chart(cumCanvas, {
      type: "line",
      data: { labels: yrs, datasets: [{ label: "Cum. GDP Growth", data: METRICS.extra.cum_gdp, tension: .25, borderColor: palette.blue }] },
      options: commonOptions({ legend: false, yTitle: "Cumulative (sum of growth)" })
    });
  }

  destroy('vol');
  const volCanvas = $("#volChart");
  if (volCanvas && METRICS.rolling.infl_std?.length === METRICS.rolling.years?.length) {
    CHARTS.vol = new Chart(volCanvas, {
      type: "line",
      data: { labels: METRICS.rolling.years, datasets: [{ label: "Inflation Std (5y)", data: METRICS.rolling.infl_std, tension: .25, borderColor: palette.pink }] },
      options: commonOptions({ legend: false, yTitle: "Rolling Std (5y)" })
    });
  }

  destroy('yoyScatter');
  const yoyScCanvas = $("#yoyScatterChart");
  if (yoyScCanvas && METRICS.yoy.inflation?.length === METRICS.yoy.gdp?.length && METRICS.yoy.gdp.length) {
    CHARTS.yoyScatter = new Chart(yoyScCanvas, {
      type: "scatter",
      data: { datasets: [{ label: "YoY points", data: METRICS.yoy.inflation.map((x, i) => ({ x, y: METRICS.yoy.gdp[i] })), backgroundColor: palette.blue }] },
      options: commonOptions({ legend: false, xTitle: "Inflation YoY", yTitle: "GDP YoY" })
    });
  }

  [CHARTS.gdp, CHARTS.infl, CHARTS.overlay, CHARTS.scatter].forEach(ch => {
    if (ch?.options?.plugins?.zoom) {
      ch.options.plugins.zoom.onZoomComplete = ({ chart }) => filterTableToVisibleRange(chart);
    }
  });
}
function rebuildCharts() { buildCharts(); }

function filterTableToVisibleRange(chart) {
  const sc = chart.scales?.x; if (!sc) return; const min = sc.min, max = sc.max; if (min == null || max == null) return;
  const y = METRICS.series.years; const rows = rowsNow().filter((_, i) => y[i] >= min && y[i] <= max);
  page = 1; const tb = $("#tableBody"); if (!tb) return; const slice = rows.slice(0, pageSize);
  tb.innerHTML = slice.map((r, i) => `<tr><td>${i + 1}</td><td>${r.year}</td><td class="col-gdp">${formatGDP(r.gdp)}</td><td class="col-infl">${r.inflation}</td></tr>`).join("")
    || `<tr><td colspan="4" class="muted">No rows in range.</td></tr>`;
  $("#pageInfo") && ($("#pageInfo").textContent = "filtered");
}

/* ========= datasets modal ========= */
async function ensureMetricsLoaded() {
  if (!METRICS) {
    const raw = await fetchMetrics();
    METRICS = ensureComputed(raw);
  }
}
function datasetCardHTML(d, key) {
  return `
    <div class="dataset-card" data-kind="${key}">
      <h4 style="margin:0 0 6px 0">${d.name}</h4>
      <div class="muted" style="font-size:13px">Years: <strong>${d.year_min ?? "—"}–${d.year_max ?? "—"}</strong></div>
      <div class="muted" style="font-size:13px">Non-null: <strong>${d.non_null_points}</strong>, Nulls: <strong>${d.null_points}</strong></div>
      <code style="display:block;white-space:pre-wrap;margin:8px 0">${(d.columns_preview || []).join(", ")}</code>
      <button class="btn sm preview-btn">Preview rows</button>
      <div class="preview-tbl" style="margin-top:10px"></div>
    </div>`;
}
async function renderDatasetCards() {
  await ensureMetricsLoaded();
  const wrap = $("#datasetCards"); if (!wrap || !METRICS?.meta?.datasets) return;
  const g = METRICS.meta.datasets.gdp, i = METRICS.meta.datasets.inflation;
  wrap.innerHTML = datasetCardHTML(g, "gdp") + datasetCardHTML(i, "inflation");
}
async function handlePreviewClick(e) {
  const btn = e.target.closest(".preview-btn"); if (!btn) return;
  const card = e.target.closest(".dataset-card"); if (!card) return;
  const kind = card.getAttribute("data-kind");
  const host = card.querySelector(".preview-tbl");
  host.innerHTML = "<div class='muted'>Loading…</div>";
  try {
    const r = await fetch(`/api/preview/?kind=${encodeURIComponent(kind)}&limit=10`);
    const j = await r.json();
    if (!r.ok || j.ok === false) throw new Error(j.error || "Failed");
    const rows = j.rows || [];
    if (!rows.length) { host.innerHTML = "<div class='muted'>No rows.</div>"; return; }
    const html = `
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>#</th><th>Year</th><th>Value</th></tr></thead>
          <tbody>${rows.map((r,i)=>`<tr><td>${i+1}</td><td>${r.year}</td><td>${r.value}</td></tr>`).join("")}</tbody>
        </table>
      </div>`;
    host.innerHTML = html;
  } catch (err) {
    console.error(err);
    host.innerHTML = "<div class='muted'>Failed to load preview.</div>";
  }
}
function showModal(show) { const m = $("#datasetModal"); if (!m) return; m.classList.toggle("show", !!show); m.setAttribute("aria-hidden", show ? "false" : "true"); }

/* ========= UI ========= */
function wireUI() {
  $("#tableSearch")?.addEventListener("input", () => { page = 1; renderTable(); });
  $("#prevPage")?.addEventListener("click", () => { if (page > 1) { page--; renderTable(); } });
  $("#nextPage")?.addEventListener("click", () => { page++; renderTable(); });
  $("#showGDP")?.addEventListener("change", e => { showGDP = e.target.checked; renderTable(); });
  $("#showInfl")?.addEventListener("change", e => { showInfl = e.target.checked; renderTable(); });
  $("#reload")?.addEventListener("click", init);
  $("#datasetBtn")?.addEventListener("click", async () => { await renderDatasetCards(); showModal(true); });
  $("#datasetCards")?.addEventListener("click", handlePreviewClick);
  $("#modalClose")?.addEventListener("click", () => showModal(false));
  $("#modalCancel")?.addEventListener("click", () => showModal(false));
  $("#resetZoom")?.addEventListener("click", () => { Object.values(CHARTS).forEach(ch => { try { ch.resetZoom && ch.resetZoom(); } catch (_) {} }); toast("Zoom reset"); renderTable(); });
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
    toast("Loaded ✓");
  } catch (e) { console.error(e); toast(e.message || "Failed to load"); }
}
document.addEventListener("DOMContentLoaded", () => { wireUI(); if ($("#gdpChart")) init(); });
