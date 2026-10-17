// Shared shell + page renderers. Every number/chart/marker is fetched from the API.
const NAV = [["dashboard", "speedometer2", "Dashboard"], ["reserves", "geo-alt", "Reserve Intelligence"], ["production", "graph-up-arrow", "Production"],
  ["risk", "exclamation-triangle", "Risk & Actions"], ["scenarios", "sliders", "Scenario Simulator"], ["data", "database", "Data"],
  ["models", "cpu", "Model Insights"], ["about", "info-circle", "About"]];
const $ = (s, r = document) => r.querySelector(s);
const fmt = (n, d = 0) => n == null || isNaN(n) ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
const spin = '<div class="spin"><div class="spinner-border spinner-border-sm me-2"></div>Loading…</div>';
const errBox = (e) => `<div class="alert alert-danger mb-0"><i class="bi bi-x-octagon"></i> ${e.message || e}</div>`;
const kpi = (l, v, s = "", extra = "") => `<div class="col-6 col-lg-4 col-xl-2"><div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="s">${s}${extra}</div></div></div>`;
const badge = (txt, cls) => `<span class="badge ${cls}">${txt}</span>`;
const SYN = '<div class="syn mb-3"><i class="bi bi-flask"></i> Demo / synthetic data — generated for demonstration, not real mine data.</div>';
const PL = { margin: { t: 20, r: 15, b: 40, l: 55 }, font: { family: "Segoe UI, sans-serif", size: 12 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", legend: { orientation: "h", y: 1.15 } };
const plot = (id, traces, layout = {}) => Plotly.newPlot(id, traces, { ...PL, ...layout }, { responsive: true, displaylogo: false });
const COL = { Low: "#2e7d4f", Moderate: "#d97706", High: "#e0661a", "Very High": "#c0392b" };

function shell(active) {
  const cur = NAV.find((n) => n[0] === active);
  document.body.insertAdjacentHTML("afterbegin", `
  <aside class="sidebar" id="side"><a class="brand" href="index.html"><img src="assets/favicon.svg" alt="ManganAI logo"><span>Mangan<span>AI</span></span></a>
   ${NAV.map((n) => `<a class="nav-i ${n[0] === active ? "active" : ""}" href="${n[0]}.html"><i class="bi bi-${n[1]}"></i>${n[2]}</a>`).join("")}</aside>
  <div class="main"><div class="topbar"><button class="btn btn-sm btn-outline-dark d-lg-none" onclick="$('#side').classList.toggle('open')"><i class="bi bi-list"></i></button>
   <h1>${cur ? cur[2] : ""}</h1><span class="ms-auto small text-muted" id="status"></span>
   <button class="btn btn-sm btn-outline-dark" id="btnRefresh" title="Regenerate the synthetic dataset with a new seed"><i class="bi bi-arrow-repeat"></i> Refresh Demo Data</button>
   <button class="btn btn-sm btn-gold" id="btnRetrain" title="Retrain both ML models on the current data"><i class="bi bi-cpu"></i> Retrain Models</button></div>
   <div class="content" id="content">${spin}</div></div>`);
  API.get("/health").then((h) => $("#status").innerHTML = `<i class="bi bi-circle-fill text-success"></i> API · ${h.data.mode} mode`).catch(() => $("#status").innerHTML = '<i class="bi bi-circle-fill text-danger"></i> API offline');
  $("#btnRefresh").onclick = async (e) => { e.target.disabled = true; try { const r = await API.post("/data/refresh", {}); alert("Demo data regenerated (seed " + r.data.metadata.seed + "). Models were NOT retrained — click Retrain Models to refit. Reloading."); location.reload(); } catch (x) { alert(x.message); e.target.disabled = false; } };
  $("#btnRetrain").onclick = async (e) => { e.target.disabled = true; e.target.innerHTML = "Training…"; try { await API.post("/models/retrain"); location.reload(); } catch (x) { alert(x.message); location.reload(); } };
  return $("#content");
}

function recsHtml(recs) {
  return recs.map((r) => `<div class="rec"><div class="d-flex justify-content-between"><strong>${r.title}</strong>${badge(r.priority, "pri-" + r.priority)}</div>
   <div class="small text-muted">${r.reason}</div><div class="small mt-1"><code>${r.affected_factor}</code> ${r.current_value == null ? "" : `current <b>${fmt(r.current_value, 2)}</b> vs threshold <b>${fmt(r.threshold, 2)}</b>`}</div></div>`).join("");
}
function contribChart(id, ex, title) {
  const items = [...ex.contributions].reverse();
  plot(id, [{ type: "bar", orientation: "h", x: items.map((i) => i.contribution), y: items.map((i) => `${i.feature} = ${fmt(i.value, 2)}`), marker: { color: items.map((i) => (i.contribution >= 0 ? "#b8860b" : "#34393f")) } }],
    { margin: { t: 30, r: 15, b: 40, l: 190 }, title: { text: title, font: { size: 13 } }, xaxis: { title: "Contribution to prediction" } });
}
const explainNote = (ex) => `<div class="small text-muted mt-2">Method: ${ex.method}. ${ex.disclaimer}</div>`;

function pointPopup(p, extra) {
  return `<b>${p.id}</b><br>Probability: <b>${fmt(p.prob * 100, 1)}%</b> (${p.category})<br>${extra}`;
}
function baseMap(id, center = [21.2, 79.4], z = 10) {
  const m = L.map(id).setView(center, z);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap", maxZoom: 18 }).addTo(m);
  return m;
}
const dot = (p, r = 5) => L.circleMarker([p.lat, p.lon], { radius: r, color: "#23272e", weight: 1, fillColor: COL[p.category], fillOpacity: .8 });

const pages = {};
pages.index = async (c) => {
  c.innerHTML = `<div class="hero"><img src="assets/logo.svg" alt="ManganAI" style="height:64px;filter:brightness(0) invert(1) sepia(1) saturate(.2)" class="d-none"><img src="assets/favicon.svg" width="70" class="mb-3" alt="">
   <h1 class="display-5 fw-bold">Mangan<span style="color:var(--amber)">AI</span></h1><p class="lead mb-1">AI-Powered Manganese Mining Intelligence Platform</p>
   <p class="text-secondary">From Geological Insight to Production Intelligence</p><a class="btn btn-gold btn-lg" href="dashboard.html">Open Dashboard</a>
   <div class="mt-4 small" id="live">${spin}</div></div>${SYN}`;
  try { const s = (await API.get("/dashboard/summary")).data; $("#live").innerHTML = `Live from the API: ${fmt(s.kpis.mapped_samples)} mapped samples · predicted production ${fmt(s.kpis.predicted_production)} t/day · risk ${s.kpis.risk_level}`; } catch (e) { $("#live").innerHTML = errBox(e); }
};

pages.dashboard = async (c) => {
  try {
    const [s, h, rec, map] = await Promise.all([API.get("/dashboard/summary"), API.get("/production/history?days=180"), API.get("/recommendations"), API.get("/reserves/map")]);
    const k = s.data.kpis, m = s.data.models;
    c.innerHTML = `${SYN}<div class="row g-3 mb-3">${kpi("Mapped Samples", fmt(k.mapped_samples), "geological samples")}${kpi("High Probability Zones", fmt(k.high_probability_zones), "samples with P ≥ 50%")}
     ${kpi("Production Target", fmt(k.production_target), "t/day (30-day avg)")}${kpi("Predicted Production", fmt(k.predicted_production), "t/day (ML)")}
     ${kpi("Expected Shortfall", fmt(k.expected_shortfall), fmt(k.shortfall_percentage, 1) + "% of target")}${kpi("Current Risk", fmt(k.risk_score, 1), "", badge(k.risk_level, "lvl-" + k.risk_level))}</div>
     <div class="row g-3 mb-3"><div class="col-lg-8"><div class="panel"><h2>Target vs actual vs ML prediction (last 180 days)</h2><div id="ch1" class="chart"></div></div></div>
     <div class="col-lg-4"><div class="panel"><h2>Top risk factors</h2><div id="ch2" class="chart"></div></div></div></div>
     <div class="row g-3"><div class="col-lg-5"><div class="panel"><h2>Reserve map <a href="reserves.html" class="small">open</a></h2><div id="map" class="map sm"></div></div></div>
     <div class="col-lg-4"><div class="panel"><h2>Recommendations <a href="risk.html" class="small">details</a></h2>${recsHtml(rec.data.slice(0, 4))}</div></div>
     <div class="col-lg-3"><div class="panel"><h2>Model status</h2><div class="small"><b>Reserve:</b> ${m.reserve.name}<br>ROC-AUC ${fmt(m.reserve.roc_auc, 3)}<br><br><b>Production:</b> ${m.production.name}<br>R² ${fmt(m.production.r2, 3)} · MAPE ${fmt(m.production.mape, 1)}%<br><br><span class="text-muted">Data seed ${s.data.data.seed}, generated ${s.data.data.generated_at}</span></div></div></div></div>`;
    plot("ch1", [{ x: h.data.dates, y: h.data.target, name: "Target", line: { color: "#6b7280", dash: "dot" } }, { x: h.data.dates, y: h.data.actual, name: "Actual", line: { color: "#23272e", width: 1.5 } }, { x: h.data.dates, y: h.data.predicted, name: "ML predicted", line: { color: "#b8860b", width: 1.5 } }], { yaxis: { title: "t/day" } });
    const f = [...s.data.top_risk_factors].reverse();
    plot("ch2", [{ type: "bar", orientation: "h", x: f.map((x) => x.contribution), y: f.map((x) => x.factor), marker: { color: "#b8860b" } }], { margin: { t: 10, r: 10, b: 40, l: 140 }, xaxis: { title: "Risk points" } });
    const mp = baseMap("map", [21.2, 79.4], 9); map.data.samples.forEach((p) => dot(p, 3).addTo(mp));
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.reserves = async (c) => {
  try {
    const [sum, map] = await Promise.all([API.get("/reserves/summary"), API.get("/reserves/map")]);
    const S = sum.data, M = sum.metrics, D = map.data;
    c.innerHTML = `${SYN}<div class="row g-3 mb-3">${kpi("Samples", fmt(S.mapped_samples))}${kpi("Drill holes", fmt(S.drilling_points))}${kpi("Mean probability", fmt(S.mean_probability * 100, 1) + "%")}${kpi("Model ROC-AUC", fmt(M.roc_auc, 3))}${kpi("Recall", fmt(M.recall, 3))}${kpi("Precision", fmt(M.precision, 3))}</div>
     <div class="panel mb-3"><div class="row g-2 align-items-end"><div class="col-6 col-md-3"><label class="form-label small">Probability</label><select id="fp" class="form-select form-select-sm"><option value="">All</option><option>Low</option><option>Moderate</option><option>High</option><option>Very High</option></select></div>
      <div class="col-6 col-md-3"><label class="form-label small">Min grade (% Mn)</label><input id="fg" type="number" class="form-control form-control-sm" value="0" min="0"></div>
      <div class="col-6 col-md-3"><label class="form-label small">Geology</label><select id="fge" class="form-select form-select-sm"><option value="">All</option>${D.geologies.map((g) => `<option>${g}</option>`).join("")}</select></div>
      <div class="col-6 col-md-3"><label class="form-label small">Zone</label><select id="fz" class="form-select form-select-sm"><option value="">All</option>${D.zones.map((g) => `<option>${g}</option>`).join("")}</select></div></div></div>
     <div class="row g-3"><div class="col-lg-8"><div class="panel"><h2>Probability map <span class="small text-muted" id="cnt"></span></h2><div id="map" class="map"></div>
      <div class="small mt-2">${Object.keys(COL).map((k) => `<span class="me-3"><i class="bi bi-circle-fill" style="color:${COL[k]}"></i> ${k}</span>`).join("")}<span><i class="bi bi-diamond-fill"></i> Drill hole</span></div></div></div>
     <div class="col-lg-4"><div class="panel mb-3"><h2>Selected point</h2><div id="sel" class="empty">Click a point on the map.</div><div id="ex" class="chart" style="height:280px"></div></div>
      <div class="panel"><h2>Zone probability</h2><div id="zc" style="height:220px"></div></div></div></div>`;
    const mp = baseMap("map", [21.2, 79.4], 10), layer = L.layerGroup().addTo(mp);
    const draw = () => {
      layer.clearLayers(); const fp = $("#fp").value, fg = +$("#fg").value || 0, fge = $("#fge").value, fz = $("#fz").value; let n = 0;
      D.samples.filter((p) => (!fp || p.category === fp) && p.grade >= fg && (!fge || p.geology === fge) && (!fz || p.zone === fz)).forEach((p) => {
        n++; dot(p).addTo(layer).bindPopup(pointPopup(p, `Geology: ${p.geology}<br>Grade: ${p.grade}% Mn<br>Geo/Drill ind.: ${p.geo_ind}/${p.drill_ind}<br>NDVI ${p.ndvi} · NDWI ${p.ndwi}<br>LST ${p.lst}°C · Rain ${p.rainfall} mm · SM ${p.soil_moisture}`))
          .on("click", async () => {
            $("#sel").innerHTML = `<b>${p.id}</b> · ${badge(p.category, "cat-" + p.category.split(" ")[0])} P=${fmt(p.prob * 100, 1)}%<br><span class="small text-muted">${p.geology} · ${p.grade}% Mn · ${p.zone}</span>`;
            try { const ex = (await API.post("/explain/reserve", { sample_id: p.id })).data; contribChart("ex", ex, "Why this probability (SHAP)"); $("#sel").insertAdjacentHTML("beforeend", explainNote(ex)); } catch (e) { $("#ex").innerHTML = errBox(e); }
          });
      });
      D.drilling.forEach((d) => { if (!fp || d.category === fp) L.marker([d.lat, d.lon], { icon: L.divIcon({ className: "", html: '<i class="bi bi-diamond-fill" style="color:#23272e;font-size:10px"></i>' }) }).addTo(layer).bindPopup(`<b>${d.id}</b><br>Depth ${d.depth} m · ${d.rock}<br>Grade ${d.grade}% · Ore ind. ${d.ore_ind}<br>Nearby-sample P ${fmt(d.prob * 100, 1)}%`); });
      $("#cnt").textContent = `(${n} of ${D.samples.length} samples)`;
    };
    ["fp", "fg", "fge", "fz"].forEach((i) => $("#" + i).addEventListener("input", draw)); draw();
    plot("zc", [{ type: "bar", x: S.zones.map((z) => z.zone), y: S.zones.map((z) => z.mean_probability * 100), marker: { color: "#b8860b" } }], { yaxis: { title: "Mean P (%)" } });
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.production = async (c) => {
  try {
    const [h, f, mt, ex] = await Promise.all([API.get("/production/history?days=365"), API.get("/production/forecast?days=30"), API.get("/models/metrics"), API.post("/explain/production", {})]);
    const pm = mt.data.production, m = pm.metrics;
    c.innerHTML = `${SYN}<div class="row g-3 mb-3">${kpi("Model", pm.model, "chronological validation")}${kpi("MAE", fmt(m.mae, 1), "t/day")}${kpi("RMSE", fmt(m.rmse, 1), "t/day")}${kpi("R²", fmt(m.r2, 3))}${kpi("MAPE", fmt(m.mape, 2) + "%")}</div>
     <div class="row g-3 mb-3"><div class="col-12"><div class="panel"><h2>Last 12 months: target vs actual vs ML prediction</h2><div id="c1" class="chart"></div></div></div>
     <div class="col-lg-7"><div class="panel"><h2>30-day forecast (seasonal-profile inputs → trained model)</h2><div id="c2" class="chart"></div></div></div>
     <div class="col-lg-5"><div class="panel"><h2>Why current production is predicted this way</h2><div id="c3" class="chart"></div>${explainNote(ex.data)}</div></div></div>
     <div class="panel"><h2>Model comparison</h2><table class="table table-sm mb-0"><thead><tr><th>Model</th><th>MAE</th><th>RMSE</th><th>R²</th><th>MAPE %</th></tr></thead><tbody>${Object.entries(pm.all_models).map(([n, v]) => `<tr class="${n === pm.model ? "table-warning" : ""}"><td>${n}</td><td>${fmt(v.mae, 1)}</td><td>${fmt(v.rmse, 1)}</td><td>${fmt(v.r2, 3)}</td><td>${fmt(v.mape, 2)}</td></tr>`).join("")}</tbody></table></div>`;
    const d = h.data;
    plot("c1", [{ x: d.dates, y: d.target, name: "Target", line: { color: "#6b7280", dash: "dot" } }, { x: d.dates, y: d.actual, name: "Actual", line: { color: "#23272e", width: 1.3 } }, { x: d.dates, y: d.predicted, name: "ML predicted", line: { color: "#b8860b", width: 1.3 } }], { yaxis: { title: "t/day" } });
    plot("c2", [{ x: f.data.dates, y: f.data.target, name: "Target", line: { color: "#6b7280", dash: "dot" } }, { x: f.data.dates, y: f.data.predicted, name: "Predicted", line: { color: "#b8860b" } }, { type: "bar", x: f.data.dates, y: f.data.shortfall, name: "Shortfall", marker: { color: "rgba(192,57,43,.45)" } }], { yaxis: { title: "t/day" } });
    contribChart("c3", ex.data, "Feature contributions (current state)");
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.risk = async (c) => {
  try {
    const [r, rec] = await Promise.all([API.get("/risk/current"), API.get("/recommendations")]);
    const R = r.data, o = R.outcome;
    c.innerHTML = `<div class="row g-3 mb-3">${kpi("Risk score", fmt(R.score, 1), "", badge(R.level, "lvl-" + R.level))}${kpi("Target", fmt(o.production_target), "t/day")}${kpi("Predicted", fmt(o.predicted_production), "t/day")}${kpi("Shortfall", fmt(o.expected_shortfall), fmt(o.shortfall_percentage, 1) + "%")}</div>
     <div class="row g-3 mb-3"><div class="col-lg-4"><div class="panel"><h2>Risk score</h2><div id="g" class="chart"></div><div class="small text-muted">0–25 Low · 26–50 Medium · 51–75 High · 76–100 Critical</div></div></div>
     <div class="col-lg-8"><div class="panel"><h2>Factor breakdown (weighted)</h2><table class="table table-sm"><thead><tr><th>Factor</th><th>Value</th><th>Weight</th><th>Points</th></tr></thead><tbody>${R.factors.map((f) => `<tr><td>${f.factor}</td><td>${fmt(f.value, 2)} ${f.unit}</td><td>${f.weight}</td><td><b>${fmt(f.contribution, 1)}</b></td></tr>`).join("")}</tbody></table></div></div></div>
     <div class="panel"><h2>Recommendations (rule engine on current values)</h2>${recsHtml(rec.data)}</div>`;
    plot("g", [{ type: "indicator", mode: "gauge+number", value: R.score, gauge: { axis: { range: [0, 100] }, bar: { color: "#23272e" }, steps: [{ range: [0, 25], color: "#9bd1ae" }, { range: [25, 50], color: "#f5d68a" }, { range: [50, 75], color: "#f2a65a" }, { range: [75, 100], color: "#e08a80" }] } }], { margin: { t: 30, b: 10, l: 25, r: 25 } });
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.scenarios = async (c) => {
  try {
    const cur = (await API.get("/risk/current")).data.features;
    const F = [["equipment_downtime", "Equipment downtime (h/day)", 0, 14, .1], ["equipment_availability", "Equipment availability (0–1)", .3, 1, .01], ["rainfall", "Rainfall (mm/day)", 0, 80, .5], ["weather_factor", "Weather factor (0–1)", .5, 1, .01], ["blasting_delay", "Blasting delay (h)", 0, 10, .1], ["working_days", "Working days / week", 4, 7, 1]];
    c.innerHTML = `${SYN}<div class="row g-3"><div class="col-lg-4"><div class="panel"><h2>Scenario inputs</h2>${F.map(([k, l, a, b, s]) => `<label class="form-label small mb-0">${l}: <b id="v_${k}">${fmt(cur[k], 2)}</b></label><input type="range" class="form-range" id="s_${k}" min="${a}" max="${b}" step="${s}" value="${cur[k]}">`).join("")}
      <button class="btn btn-gold w-100 mt-2" id="run"><i class="bi bi-play-fill"></i> RUN SCENARIO</button><button class="btn btn-outline-dark w-100 mt-2" id="reset">Reset to current</button><button class="btn btn-outline-dark w-100 mt-2" id="save" disabled>Save scenario</button></div></div>
     <div class="col-lg-8"><div id="res" class="empty panel">Adjust inputs and press Run Scenario. The trained production model will be queried on the server.</div></div></div>`;
    F.forEach(([k]) => $("#s_" + k).oninput = (e) => $("#v_" + k).textContent = fmt(e.target.value, 2));
    $("#reset").onclick = () => F.forEach(([k]) => { $("#s_" + k).value = cur[k]; $("#v_" + k).textContent = fmt(cur[k], 2); });
    let last = null;
    $("#run").onclick = async (e) => {
      e.target.disabled = true; $("#res").innerHTML = spin;
      try {
        const inp = {}; F.forEach(([k]) => inp[k] = +$("#s_" + k).value);
        const r = (await API.post("/scenario/simulate", inp)).data; last = { inp, r }; $("#save").disabled = false;
        const a = r.current, b = r.scenario, i = r.impact, sg = (v) => (v > 0 ? "+" : "") + fmt(v, 1);
        $("#res").className = ""; $("#res").innerHTML = `<div class="panel mb-3"><table class="table table-sm mb-0"><thead><tr><th></th><th>CURRENT</th><th>SCENARIO</th><th>IMPACT</th></tr></thead><tbody>
          <tr><td>Production (t/day)</td><td>${fmt(a.predicted_production)}</td><td>${fmt(b.predicted_production)}</td><td class="${i.production_difference < 0 ? "text-danger" : "text-success"}">${sg(i.production_difference)}</td></tr>
          <tr><td>Shortfall (t/day)</td><td>${fmt(a.expected_shortfall)}</td><td>${fmt(b.expected_shortfall)}</td><td class="${i.shortfall_difference > 0 ? "text-danger" : "text-success"}">${sg(i.shortfall_difference)}</td></tr>
          <tr><td>Risk</td><td>${fmt(a.risk_score, 1)} ${badge(a.risk_level, "lvl-" + a.risk_level)}</td><td>${fmt(b.risk_score, 1)} ${badge(b.risk_level, "lvl-" + b.risk_level)}</td><td class="${i.risk_difference > 0 ? "text-danger" : "text-success"}">${sg(i.risk_difference)}</td></tr></tbody></table></div>
          <div class="row g-3"><div class="col-md-6"><div class="panel"><h2>Current vs scenario</h2><div id="cmp" class="chart"></div></div></div><div class="col-md-6"><div class="panel"><h2>Recommendations for scenario</h2>${recsHtml(r.recommendations)}</div></div></div>`;
        plot("cmp", [{ type: "bar", name: "Current", x: ["Target", "Predicted", "Shortfall"], y: [a.production_target, a.predicted_production, a.expected_shortfall], marker: { color: "#6b7280" } }, { type: "bar", name: "Scenario", x: ["Target", "Predicted", "Shortfall"], y: [b.production_target, b.predicted_production, b.expected_shortfall], marker: { color: "#b8860b" } }], { barmode: "group", yaxis: { title: "t/day" } });
      } catch (x) { $("#res").innerHTML = errBox(x); }
      e.target.disabled = false;
    };
    $("#save").onclick = async () => { const n = prompt("Scenario name?"); if (!n || !last) return; try { const r = await API.post("/scenario/save", { name: n, inputs: last.inp, results: { impact: last.r.impact } }); alert("Saved (" + r.data.stored_in + ")"); } catch (x) { alert(x.message); } };
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.data = async (c) => {
  const tbl = (q) => `<tr><td>${q.dataset}</td><td>${fmt(q.rows)}</td><td>${q.columns}</td><td>${fmt(Object.values(q.missing_values).reduce((a, b) => a + b, 0))}</td><td>${q.duplicates}</td><td>${fmt(Object.values(q.invalid_values).reduce((a, b) => a + b, 0))}</td><td>${q.date_range ? q.date_range.join(" → ") : "—"}</td><td>${badge(q.status, q.status === "valid" ? "bg-success" : q.status === "warnings" ? "bg-warning text-dark" : "bg-danger")}</td></tr>`;
  const head = "<thead><tr><th>Dataset</th><th>Rows</th><th>Cols</th><th>Missing</th><th>Dupes</th><th>Invalid</th><th>Date range</th><th>Status</th></tr></thead>";
  try {
    const q = (await API.get("/data/quality")).data;
    c.innerHTML = `${SYN}<div class="row g-3 mb-3"><div class="col-lg-5"><div class="panel"><h2>Upload CSV</h2><select id="ds" class="form-select mb-2">${["geological", "production", "drilling", "equipment", "weather", "blasting"].map((d) => `<option>${d}</option>`).join("")}</select>
      <input type="file" id="f" accept=".csv" class="form-control mb-2"><button id="up" class="btn btn-gold">Upload &amp; validate</button><div class="small text-muted mt-2">Files go to temporary storage (data/temp). Nothing is permanent until you press Save.</div><div id="upr" class="mt-3"></div></div></div>
      <div class="col-lg-7"><div class="panel"><h2>Demo dataset quality</h2><div class="small text-muted mb-2">Seed ${q.metadata.seed} · generated ${q.metadata.generated_at}</div><div class="table-responsive"><table class="table table-sm">${head}<tbody>${Object.values(q.demo).map(tbl).join("")}</tbody></table></div></div></div></div>`;
    $("#up").onclick = async () => {
      const f = $("#f").files[0], r = $("#upr"); if (!f) { r.innerHTML = '<div class="alert alert-warning">Choose a CSV file first.</div>'; return; }
      r.innerHTML = spin;
      try {
        const d = (await API.upload($("#ds").value, f)).data;
        r.innerHTML = `<div class="table-responsive"><table class="table table-sm">${head}<tbody>${tbl(d)}</tbody></table></div>${d.missing_required_columns.length ? `<div class="alert alert-danger">Missing required columns: ${d.missing_required_columns.join(", ")}</div>` : ""}
         ${Object.keys(d.invalid_values).length ? `<div class="small">Invalid values: ${Object.entries(d.invalid_values).map(([k, v]) => `${k}: ${v}`).join(", ")}</div>` : ""}
         <div class="table-responsive mt-2" style="max-height:220px"><table class="table table-sm small"><thead><tr>${d.columns_list.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>${d.preview.map((row) => `<tr>${d.columns_list.map((x) => `<td>${row[x] ?? ""}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
         ${d.status !== "invalid" ? '<button id="sv" class="btn btn-sm btn-outline-dark mt-2">Save permanently</button>' : ""}`;
        const sv = $("#sv"); if (sv) sv.onclick = async () => { try { alert((await API.post("/data/save/" + d.dataset)).data.note); } catch (x) { alert(x.message); } };
      } catch (x) { r.innerHTML = errBox(x); }
    };
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.models = async (c) => {
  try {
    const r = await API.get("/models/summary"), D = r.data;
    const sec = (k, title, rows) => { const m = D[k]; return `<div class="col-12"><div class="panel"><h2>${title}: ${m.name}</h2><div class="small text-muted mb-2">${m.n_train} training / ${m.n_test} test records · ${m.validation} · trained ${m.trained_at}</div>
      <div class="row g-3"><div class="col-lg-4"><table class="table table-sm">${rows}</table><div class="small"><b>Features (${m.features.length}):</b> ${m.features.join(", ")}</div></div>
      <div class="col-lg-4"><div id="${k}_imp" class="chart"></div></div><div class="col-lg-4"><div id="${k}_shap" class="chart"></div><div class="small text-muted">${m.shap.method}</div></div></div></div></div>`; };
    const mr = D.reserve.metrics, mp = D.production.metrics;
    const rr = ["accuracy", "precision", "recall", "f1", "roc_auc"].map((k) => `<tr><td>${k}</td><td>${fmt(mr[k], 3)}</td></tr>`).join("") + `<tr><td>confusion [[TN,FP],[FN,TP]]</td><td>${JSON.stringify(mr.confusion_matrix)}</td></tr>`;
    const pr = ["mae", "rmse", "r2", "mape"].map((k) => `<tr><td>${k.toUpperCase()}</td><td>${fmt(mp[k], 3)}</td></tr>`).join("");
    c.innerHTML = `${SYN}<div class="row g-3">${sec("reserve", "Reserve model", rr)}${sec("production", "Production model", pr)}</div><div class="small text-muted mt-3">${r.disclaimer}</div>`;
    ["reserve", "production"].forEach((k) => {
      const bar = (id, obj, t) => { const e = Object.entries(obj).slice(0, 10).reverse(); plot(id, [{ type: "bar", orientation: "h", x: e.map((x) => x[1]), y: e.map((x) => x[0]), marker: { color: "#b8860b" } }], { margin: { t: 30, r: 10, b: 30, l: 140 }, title: { text: t, font: { size: 13 } } }); };
      bar(k + "_imp", D[k].importance, "Model feature importance"); bar(k + "_shap", D[k].shap.importance, "Mean |SHAP| (global)");
    });
  } catch (e) { c.innerHTML = errBox(e); }
};

pages.about = async (c) => {
  c.innerHTML = `<div class="panel"><img src="assets/logo.svg" alt="ManganAI" style="height:60px" class="mb-3"><p><b>ManganAI</b> turns geological, drilling, environmental and operational data into manganese mineralization probability, production prediction, risk analysis, explainable ML and what-if simulation.</p>
   <p class="mb-1"><b>Pipeline:</b> demo data → Pandas → scikit-learn/XGBoost → FastAPI → JavaScript → UI.</p>
   <p class="mb-1"><b>Limits:</b> all data is synthetic. Satellite indicators are supporting evidence, not proof of deposits. SHAP explains model behavior, not causality. Not for real exploration or investment decisions.</p>
   <p class="mb-0 text-muted small" id="h">${spin}</p></div>`;
  try { const h = (await API.get("/health")).data; $("#h").textContent = `Backend mode: ${h.mode} · XGBoost: ${h.xgboost ? "yes" : "no (gradient boosting fallback)"}`; } catch (e) { $("#h").textContent = e.message; }
};

document.addEventListener("DOMContentLoaded", () => { const p = document.body.dataset.page; pages[p](shell(p)); });
