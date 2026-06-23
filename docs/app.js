/* MarteGas sales dashboard — reads data/dashboard.json (pre-aggregated). */
const COLORS = { GLP: "#ff7a45", GNV: "#3ec9c0" };
const fmt0 = new Intl.NumberFormat("es-DO", { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat("es-DO", { maximumFractionDigits: 1 });
const MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

let DASH = null, CURRENT = null;
const charts = {};

function money(v){ return "RD$ " + fmt0.format(v); }
function el(html){ const t=document.createElement("template"); t.innerHTML=html.trim(); return t.content.firstChild; }
function delta(pct){
  if (pct === null || pct === undefined) return '<span class="muted">s/d</span>';
  const cls = pct >= 0 ? "up" : "down", arrow = pct >= 0 ? "▲" : "▼";
  return `<span class="delta ${cls}">${arrow} ${fmt1.format(Math.abs(pct))}%</span>`;
}

async function init(){
  DASH = await (await fetch("data/dashboard.json?_=" + Date.now())).json();
  const c = DASH.combined;
  document.getElementById("asof-line").textContent = "Datos hasta: " + c.last_date;
  document.getElementById("gen-line").textContent = "Actualizado: " + DASH.generated_at;
  document.getElementById("rec-count").textContent =
    `${fmt0.format(c.total_records)} días de ventas · ${c.first_date} a ${c.last_date}.`;

  renderOverview();
  renderTabs();
  select(DASH.products[0]);
}

function renderOverview(){
  const c = DASH.combined, o = document.getElementById("overview");
  o.innerHTML = "";
  const items = [
    ["Ingresos del año en curso", money(c.ytd_revenue)],
    ["Ingresos históricos totales", money(c.total_revenue)],
    ["Productos", DASH.products.join(" · ")],
    ["Período cubierto", c.first_date + " → " + c.last_date],
  ];
  items.forEach(([lbl,val]) => o.appendChild(
    el(`<div class="ov-item"><div class="lbl">${lbl}</div><div class="big">${val}</div></div>`)));
}

function renderTabs(){
  const t = document.getElementById("tabs"); t.innerHTML = "";
  DASH.products.forEach(p => {
    const tab = el(`<div class="tab ${p}" data-p="${p}">${DASH.product_data[p].label}</div>`);
    tab.onclick = () => select(p);
    t.appendChild(tab);
  });
}

function select(p){
  CURRENT = p;
  document.querySelectorAll(".tab").forEach(t => {
    t.className = "tab " + t.dataset.p + (t.dataset.p === p ? " active" : "");
  });
  const d = DASH.product_data[p];
  document.getElementById("u-volm").textContent = "(" + d.unit + ")";
  document.getElementById("u-price").textContent = "(RD$/" + d.unit + ")";
  renderKpis(p, d);
  renderCharts(p, d);
}

function kpi(cls,lbl,val,sub){
  return `<div class="kpi ${cls}"><div class="lbl">${lbl}</div><div class="val">${val}</div>`
       + `<div class="sub">${sub||""}</div></div>`;
}

function renderKpis(p, d){
  const k = d.kpis, cls = p.toLowerCase(), u = d.unit;
  const g = document.getElementById("kpis"); g.innerHTML = "";
  const cards = [
    kpi(cls, "Último día ("+k.as_of+")", fmt0.format(k.latest_volume)+" "+u, money(k.latest_revenue)),
    kpi(cls, "Mes en curso ("+k.current_month+")", fmt0.format(k.mtd_volume)+" "+u,
        money(k.mtd_revenue)+" · "+k.mtd_days+" días"),
    kpi(cls, "Acumulado del año", fmt0.format(k.ytd_volume)+" "+u, money(k.ytd_revenue)),
    kpi(cls, "Precio actual", k.current_price ? "RD$ "+fmt1.format(k.current_price) : "s/d", "por "+u),
    kpi(cls, "Promedio diario (30d)", fmt0.format(k.avg_daily_volume_30)+" "+u, money(k.avg_daily_revenue_30)+"/día"),
    kpi(cls, "Variación mensual"+(k.mom?` (${k.mom.month})`:""),
        k.mom?delta(k.mom.volume_pct):"s/d", k.mom?"ingresos "+delta(k.mom.revenue_pct):"vs mes anterior"),
    kpi(cls, "Variación interanual"+(k.yoy?` (${k.yoy.month})`:""),
        k.yoy?delta(k.yoy.volume_pct):"s/d", k.yoy?"ingresos "+delta(k.yoy.revenue_pct):"vs año anterior"),
    kpi(cls, "Mejor día histórico", fmt0.format(k.best_day.volume)+" "+u, k.best_day.date+" · "+money(k.best_day.revenue)),
  ];
  g.innerHTML = cards.join("");
}

function mk(id, cfg){
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), cfg);
}
const GRID = "#2a3650", TICK = "#8b97b0";
const baseScales = (yTitle) => ({
  x: { grid:{color:GRID}, ticks:{color:TICK,maxRotation:0,autoSkip:true,maxTicksLimit:14} },
  y: { grid:{color:GRID}, ticks:{color:TICK}, title:{display:!!yTitle,text:yTitle,color:TICK} }
});
const noLegend = { legend:{display:false} };

function renderCharts(p, d){
  const col = COLORS[p], u = d.unit;
  const mLabels = d.monthly.map(m => m.month);

  mk("chart-vol-month", { type:"bar",
    data:{ labels:mLabels, datasets:[{ label:"Volumen ("+u+")",
      data:d.monthly.map(m=>m.volume), backgroundColor:col, borderRadius:3 }] },
    options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:noLegend, scales:baseScales(u) } });

  mk("chart-rev-month", { type:"bar",
    data:{ labels:mLabels, datasets:[{ label:"Ingresos (RD$)",
      data:d.monthly.map(m=>m.revenue), backgroundColor:col+"cc", borderRadius:3 }] },
    options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:noLegend, scales:baseScales("RD$") } });

  mk("chart-price", { type:"line",
    data:{ labels:mLabels, datasets:[{ label:"Precio prom.",
      data:d.monthly.map(m=>m.price_avg), borderColor:col, backgroundColor:col+"33",
      tension:.25, pointRadius:0, fill:true }] },
    options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:noLegend, scales:baseScales("RD$/"+u) } });

  const mix = d.payment_mix, mixKeys = Object.keys(mix);
  document.getElementById("mix-month").textContent = mixKeys.length ? "(por ingresos)" : "";
  const palette = ["#5b8def","#ff7a45","#3ec9c0","#f7b955","#b07bff","#f87272","#36d399"];
  mk("chart-mix", { type:"doughnut",
    data:{ labels:mixKeys.map(prettyPay), datasets:[{ data:mixKeys.map(k=>mix[k]),
      backgroundColor:palette, borderColor:"#171e2e", borderWidth:2 }] },
    options:{ responsive:true, maintainAspectRatio:false, animation:false,
      plugins:{ legend:{ position:"right", labels:{color:TICK,boxWidth:12} } } } });

  mk("chart-daily", { type:"bar",
    data:{ labels:d.daily_recent.map(x=>x.date.slice(5)), datasets:[{ label:"Volumen diario",
      data:d.daily_recent.map(x=>x.volume), backgroundColor:col, borderRadius:2 }] },
    options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:noLegend, scales:baseScales(u) } });

  const season = DASH.seasonality[p] || {};
  const years = Object.keys(season).sort();
  const palY = ["#4a5a80","#6a7db0","#5b8def","#3ec9c0","#f7b955","#ff7a45","#f87272","#b07bff"];
  mk("chart-season", { type:"line",
    data:{ labels:MONTHS, datasets:years.map((y,i)=>({ label:y, data:season[y].map(v=>v||null),
      borderColor:palY[i%palY.length], backgroundColor:"transparent", tension:.3, pointRadius:2, spanGaps:true })) },
    options:{ responsive:true, maintainAspectRatio:false, animation:false,
      plugins:{ legend:{labels:{color:TICK,boxWidth:12}} }, scales:baseScales(u) } });
}

function prettyPay(k){
  const m = { efectivo:"Efectivo", tarjeta:"Tarjeta", tarjeta_marti:"Tarjeta MARTÍ",
    bonogas:"Bonogas", credito:"Crédito", prepago:"Prepago", tickets:"Tickets", otros:"Otros" };
  return m[k] || k;
}

init().catch(e => {
  document.querySelector("main").innerHTML =
    '<p style="color:#f87272">No se pudo cargar el panel: ' + e + '</p>';
});
