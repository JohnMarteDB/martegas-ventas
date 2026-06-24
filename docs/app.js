/* MarteGas — panel público de ventas.
   Lee data/dashboard.json (agregados ya calculados). Todo en español sencillo.
   No cambia la forma de los datos; solo los muestra. */
(function () {
  "use strict";

  /* ---------- Textos de meses ---------- */
  var MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
               "septiembre","octubre","noviembre","diciembre"];
  var MESES_CORTOS = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];

  /* ---------- Formato de números es-DO (coma de miles, punto decimal) ---------- */
  var nf0 = new Intl.NumberFormat("es-DO", { maximumFractionDigits: 0 });
  var nf1 = new Intl.NumberFormat("es-DO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  var nf2 = new Intl.NumberFormat("es-DO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function money(v){ return "RD$ " + nf0.format(Math.round(v)); }
  function precio(v){ return "RD$ " + nf2.format(v); }
  function pesosGrandes(v){            // redondeado y amigable para números grandes
    if (v >= 1e6) return "RD$ " + nf1.format(v / 1e6) + " millones";
    if (v >= 1e3) return "RD$ " + nf0.format(Math.round(v / 1e3)) + " mil";
    return money(v);
  }
  function cantidad(v, u){ return nf0.format(Math.round(v)) + " " + u; }
  function cap(s){ return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  /* ---------- Fechas / meses ---------- */
  function ymParts(ym){ var p = String(ym).split("-"); return { y: +p[0], m: +p[1] }; }
  function mesDe(ym){ return MESES[ymParts(ym).m - 1]; }
  function mesAnio(ym){ var q = ymParts(ym); return cap(MESES[q.m - 1]) + " " + q.y; }
  function prevYM(ym){ var q = ymParts(ym), m = q.m - 1, y = q.y; if (m < 1){ m = 12; y--; } return y + "-" + String(m).padStart(2, "0"); }
  function prevYearYM(ym){ var q = ymParts(ym); return (q.y - 1) + "-" + String(q.m).padStart(2, "0"); }
  function fechaLarga(iso){ var p = String(iso).split("-"); return (+p[2]) + " de " + MESES[(+p[1]) - 1] + " de " + p[0]; }

  /* ---------- ¿Subió o bajó? ---------- */
  function veredicto(pct){
    var a = Math.abs(pct);
    if (a < 0.05) return { kind: "flat", word: "Se mantuvo igual", arrow: "", pctTxt: "" };
    var up = pct > 0;
    return { kind: up ? "up" : "down", word: up ? "Subió" : "Bajó", arrow: up ? "▲" : "▼", pctTxt: nf1.format(a) + "%" };
  }

  /* ---------- Iconos (SVG en línea, sin dependencias) ---------- */
  var ICONS = {
    glp: '<svg class="ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
       + '<path d="M12 2.5c2.2 3 5 5 5 8.8a5 5 0 0 1-10 0c0-1.6.8-2.9 1.7-4 .3 1 .9 1.7 1.8 2 .3-2.6-.7-4.7.5-6.8z" '
       + 'fill="currentColor"/></svg>',
    gnv: '<svg class="ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
       + '<path d="M5 11l1.3-3.6A2 2 0 0 1 8.2 6h7.6a2 2 0 0 1 1.9 1.4L19 11M4 11h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-1v1.5a1 1 0 0 1-2 0V17H7v1.5a1 1 0 0 1-2 0V17H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1z" '
       + 'stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>'
       + '<circle cx="7" cy="14" r="1" fill="currentColor"/><circle cx="17" cy="14" r="1" fill="currentColor"/></svg>',
    check: '<svg class="check" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">'
         + '<path d="M5 12.5l4.5 4.5L19 7" fill="none" stroke="currentColor" stroke-width="2.6" '
         + 'stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };

  /* ---------- Estado ---------- */
  var DASH = null, CURRENT = null, METRIC = "money"; // "money" | "vol"
  var chart = null;

  function $(id){ return document.getElementById(id); }

  /* ============================================================= */
  function init(){
    fetch("data/dashboard.json?_=" + Date.now())
      .then(function (r){ if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (data){ DASH = data; build(); })
      .catch(function (){
        $("app").innerHTML =
          '<p class="failed">No pudimos cargar las ventas en este momento.<br>' +
          'Por favor intenta de nuevo en un rato.</p>';
      });
  }

  function build(){
    renderProducts();
    renderFooter();
    select(DASH.products[0]);
  }

  /* ---------- Botones de producto ---------- */
  function friendly(p){
    if (p === "GLP") return { name: "Gas GLP", sub: "cocina", icon: ICONS.glp, cls: "glp" };
    if (p === "GNV") return { name: "Gas Natural", sub: "vehículos · GNV", icon: ICONS.gnv, cls: "gnv" };
    return { name: p, sub: "", icon: "", cls: "" };
  }

  function renderProducts(){
    var nav = $("products");
    nav.innerHTML = "";
    DASH.products.forEach(function (p){
      var f = friendly(p);
      var b = document.createElement("button");
      b.type = "button";
      b.className = "product-btn " + f.cls;
      b.setAttribute("data-p", p);
      b.setAttribute("aria-pressed", "false");
      b.innerHTML = f.icon
        + '<span class="pname">' + f.name + ' ' + ICONS.check + '</span>'
        + '<span class="psub">' + f.sub + '</span>';
      b.addEventListener("click", function (){ select(p); });
      nav.appendChild(b);
    });
  }

  /* ---------- Seleccionar producto ---------- */
  function select(p){
    CURRENT = p;
    var d = DASH.product_data[p];
    var f = friendly(p);

    // color de acento del producto activo
    var accent = (p === "GNV") ? "var(--gnv)" : "var(--glp)";
    var accentSoft = (p === "GNV") ? "var(--gnv-soft)" : "var(--glp-soft)";
    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-soft", accentSoft);

    // botones activos
    Array.prototype.forEach.call(document.querySelectorAll(".product-btn"), function (b){
      var on = b.getAttribute("data-p") === p;
      b.classList.toggle("is-on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });

    // fecha "Datos al ..." (de cada producto)
    $("asof").textContent = "Datos al " + fechaLarga(d.kpis.as_of);
    $("viewing").innerHTML = "Estás viendo: <b>" + f.name + " (" + f.sub.replace("vehículos · ", "") + ")</b>";

    renderHero(d);
    renderKpis(d);
    renderMonthCompare(d);
    renderChart(d);
    renderYearCompare(d);
    renderBestDay(d, f);
  }

  /* ---------- Héroe: ventas de este mes (parcial, sin flecha) ---------- */
  function renderHero(d){
    var k = d.kpis, u = d.unit;
    var mes = cap(mesDe(k.current_month));
    // ritmo del mes en curso vs. promedio normal (honesto, calculado del JSON)
    var ritmo = "";
    if (k.mtd_days > 0 && k.avg_daily_revenue_30 > 0){
      var pace = k.mtd_revenue / k.mtd_days;
      var r = pace / k.avg_daily_revenue_30;
      if (r >= 1.05) ritmo = " Vamos a buen ritmo este mes.";
      else if (r <= 0.95) ritmo = " Vamos un poco más lento que en las últimas semanas.";
      else ritmo = " Vamos a un ritmo parecido al de las últimas semanas.";
    }
    $("hero").innerHTML =
      '<p class="lbl">Ventas de este mes (' + mesDe(k.current_month) + ')</p>' +
      '<p class="big">' + pesosGrandes(k.mtd_revenue) + '</p>' +
      '<p class="exact">' + money(k.mtd_revenue) + ' · ' + cantidad(k.mtd_volume, u) + '</p>' +
      '<div class="note"><span class="ni" aria-hidden="true">ℹ️</span><span>' +
        mes + ' todavía no termina. Llevamos ' + k.mtd_days + ' día' + (k.mtd_days === 1 ? "" : "s") + '.' + ritmo +
      '</span></div>';
  }

  /* ---------- Tres tarjetas grandes ---------- */
  function renderKpis(d){
    var k = d.kpis, u = d.unit;
    var precioTxt = (k.current_price != null)
      ? '<p class="big">' + precio(k.current_price) + '</p><p class="sub">por ' + u.replace("galones", "galón") + '</p>'
      : '<p class="big">Sin precio hoy</p><p class="sub">por ' + u.replace("galones", "galón") + '</p>';

    $("kpis").innerHTML =
      // Lo que va del año
      '<div class="kpi"><p class="lbl">Lo que va del año</p>' +
        '<p class="big">' + pesosGrandes(k.ytd_revenue) + '</p>' +
        '<p class="sub">' + cantidad(k.ytd_volume, u) + ' vendidos</p></div>' +
      // Precio de hoy
      '<div class="kpi"><p class="lbl">Precio de hoy</p>' + precioTxt + '</div>' +
      // Promedio por día
      '<div class="kpi"><p class="lbl">Promedio por día (últimos 30 días)</p>' +
        '<p class="big">' + money(k.avg_daily_revenue_30) + '</p>' +
        '<p class="sub">' + cantidad(k.avg_daily_volume_30, u) + ' al día</p></div>';
  }

  /* ---------- Comparado con el mes pasado (mom) ---------- */
  function renderMonthCompare(d){
    var k = d.kpis, box = $("cmp-month");
    if (!k.mom){
      box.innerHTML = '<p class="lbl">Comparado con el mes pasado</p>' +
        '<p class="vchip-flat">Sin datos para comparar todavía.</p>';
      return;
    }
    var mes = cap(mesDe(k.mom.month));
    var antes = mesDe(prevYM(k.mom.month));
    var v = veredicto(k.mom.revenue_pct);
    var detalle = (v.kind === "up")
      ? mes + ' vendió más que ' + antes + '.'
      : (v.kind === "down" ? mes + ' vendió menos que ' + antes + '.' : mes + ' vendió casi lo mismo que ' + antes + '.');

    box.innerHTML =
      '<p class="lbl">Comparado con el mes pasado (' + mesDe(k.mom.month) + ')</p>' +
      '<p class="vmain ' + v.kind + '">' +
        (v.arrow ? '<span class="varrow" aria-hidden="true">' + v.arrow + '</span> ' : '') +
        '<span>' + v.word + (v.pctTxt ? ' ' + v.pctTxt : '') + '</span></p>' +
      '<p class="vdetail">' + detalle + '</p>' +
      '<p class="vnote">Miramos ' + mesDe(k.mom.month) + ' porque ' +
        mesDe(k.current_month) + ' todavía no termina.</p>';
  }

  /* ---------- Comparado con el año pasado (yoy) ---------- */
  function renderYearCompare(d){
    var k = d.kpis, box = $("cmp-year");
    if (!k.yoy){
      box.innerHTML = '<p class="vlabel">Comparado con el año pasado</p>' +
        '<p class="vchip-flat">Sin datos para comparar todavía.</p>';
      return;
    }
    var ahora = k.yoy.month;            // ej. 2026-05
    var antes = prevYearYM(ahora);      // ej. 2025-05
    var revMap = {};
    d.monthly.forEach(function (m){ revMap[m.month] = m.revenue; });
    var v = veredicto(k.yoy.revenue_pct);

    var pair = "";
    if (revMap[antes] != null && revMap[ahora] != null){
      pair =
        '<div class="yoy-pair">' +
          '<div class="yoy-one"><div class="yoy-when">' + mesAnio(antes) + '</div>' +
            '<div class="yoy-amt">' + pesosGrandes(revMap[antes]) + '</div></div>' +
          '<div class="yoy-arrow ' + v.kind + '" aria-hidden="true">' + (v.arrow || '•') + '</div>' +
          '<div class="yoy-one now"><div class="yoy-when">' + mesAnio(ahora) + '</div>' +
            '<div class="yoy-amt">' + pesosGrandes(revMap[ahora]) + '</div></div>' +
        '</div>';
    }
    box.innerHTML =
      '<p class="vlabel">Comparado con el año pasado (' + mesDe(ahora) + ')</p>' + pair +
      '<p class="vmain ' + v.kind + '">' +
        (v.arrow ? '<span class="varrow" aria-hidden="true">' + v.arrow + '</span> ' : '') +
        '<span>' + v.word + (v.pctTxt ? ' ' + v.pctTxt : '') + '</span>' +
        '<span class="vsuffix">en dinero</span></p>' +
      '<p class="vnote">' + mesAnio(ahora) + ' comparado con el mismo mes del año pasado.</p>';
  }

  /* ---------- Gráfico de barras: ventas mes por mes ---------- */
  function renderChart(d){
    var u = d.unit;
    var serie = d.monthly.slice(-13);                 // últimos 13 meses
    var lastIdx = serie.length - 1;
    var ultimo = serie[lastIdx];
    var mesActual = mesDe(d.kpis.current_month);

    // Rango de fechas siempre visible (no depende de las etiquetas del eje)
    $("chart-range").textContent =
      "De " + mesDe(serie[0].month) + " de " + ymParts(serie[0].month).y +
      " a " + mesDe(ultimo.month) + " de " + ymParts(ultimo.month).y + ".";

    // Si el gráfico (Chart.js) no cargó, el resto del panel sigue funcionando.
    if (typeof Chart === "undefined"){
      var boxKO = document.querySelector(".chart-box"), tgKO = document.querySelector(".toggle");
      if (boxKO) boxKO.style.display = "none";
      if (tgKO) tgKO.style.display = "none";
      $("chart-range").textContent = "";
      $("chart-note").textContent = "El gráfico no está disponible ahora, pero los números de arriba están al día.";
      return;
    }

    // El año solo en la primera barra; el rango completo va en el subtítulo de arriba.
    var labels = serie.map(function (m, i){
      var q = ymParts(m.month), s = MESES_CORTOS[q.m - 1];
      return (i === 0) ? s + " '" + String(q.y).slice(2) : s;
    });

    var solid = (CURRENT === "GNV") ? "#1B6B3A" : "#0B5FA5";
    var soft  = (CURRENT === "GNV") ? "#A9D3B7" : "#9FC3E2";
    var colors = serie.map(function (_, i){ return i === lastIdx ? soft : solid; });
    var borders = serie.map(function (){ return solid; });
    var bw = serie.map(function (_, i){ return i === lastIdx ? 2 : 0; });

    // etiqueta del botón "Cantidad" (paralela a "RD$ (dinero)")
    $("t-vol").textContent = (u === "m³") ? "m³ (cantidad)" : "Galones (cantidad)";

    var ctx = $("barchart");
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: "bar",
      data: { labels: labels, datasets: [{
        data: serie.map(function (m){ return METRIC === "money" ? m.revenue : m.volume; }),
        backgroundColor: colors, borderColor: borders, borderWidth: bw,
        borderRadius: 6, maxBarThickness: 46
      }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        layout: { padding: { top: 6 } },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: { grid: { display: false }, border: { color: "#C8D0D8" },
               ticks: { color: "#51606E", font: { size: 14 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } },
          y: { beginAtZero: true, grid: { color: "#E3E8EC" }, border: { display: false },
               ticks: { color: "#51606E", font: { size: 14 }, maxTicksLimit: 4, padding: 6,
                        callback: function (val){ return yTick(val); } } }
        }
      }
    });
    updateToggleUI();

    // nota + accesibilidad
    $("chart-note").textContent =
      "La última barra (" + mesActual + ") va incompleta, por eso se ve más baja.";
    ctx.setAttribute("aria-label",
      "Gráfico de ventas mes por mes de " + friendly(CURRENT).name +
      ", de " + mesAnio(serie[0].month) + " a " + mesAnio(ultimo.month) +
      ". La última barra (" + mesActual + ") va incompleta.");
  }

  function yTick(val){
    if (METRIC === "money"){
      if (val >= 1e6){
        var mm = val / 1e6;
        var t = (Math.abs(mm - Math.round(mm)) < 0.05) ? nf0.format(Math.round(mm)) : nf1.format(mm);
        return "RD$ " + t + "M";
      }
      if (val >= 1e3) return "RD$ " + nf0.format(Math.round(val / 1e3)) + " mil";
      return "RD$ " + nf0.format(val);
    }
    if (val >= 1e3) return nf0.format(Math.round(val / 1e3)) + " mil";
    return nf0.format(val);
  }

  function setMetric(m){
    METRIC = m;
    if (!chart) return;
    var d = DASH.product_data[CURRENT];
    var serie = d.monthly.slice(-13);
    chart.data.datasets[0].data = serie.map(function (x){ return METRIC === "money" ? x.revenue : x.volume; });
    chart.update();
    updateToggleUI();
  }

  function updateToggleUI(){
    var money = METRIC === "money";
    $("t-money").classList.toggle("is-on", money);
    $("t-vol").classList.toggle("is-on", !money);
    $("t-money").setAttribute("aria-pressed", money ? "true" : "false");
    $("t-vol").setAttribute("aria-pressed", money ? "false" : "true");
  }

  /* ---------- Pie: mejor día (por producto) ---------- */
  function renderBestDay(d, f){
    var bd = d.kpis.best_day, row = $("best-day");
    if (!row) return;
    if (!bd || !bd.date){ row.textContent = ""; return; }
    row.innerHTML = '<span aria-hidden="true">🏆</span> Tu mejor día con <span class="foot-strong">' + f.name + '</span>: ' +
      fechaLarga(bd.date) + ' · ' + money(bd.revenue);
  }

  /* ---------- Pie general (una vez) ---------- */
  function renderFooter(){
    var c = DASH.combined;
    $("foot").innerHTML =
      '<p class="foot-updated"><span aria-hidden="true">🔄</span> Actualizado automáticamente cada noche</p>' +
      '<p class="foot-row" id="best-day"></p>' +
      '<p class="foot-row">Entre los dos productos, este año la empresa vendió ' +
        '<span class="foot-strong">' + pesosGrandes(c.ytd_revenue) + '</span>.</p>' +
      '<p class="foot-row">Datos desde ' + mesDe(c.first_date) + ' de ' + ymParts(c.first_date).y +
        ' · ' + nf0.format(c.total_records) + ' días de ventas.</p>';
  }

  /* ---------- Conectar botones del gráfico (estáticos en el HTML) ---------- */
  function wireToggle(){
    var tm = $("t-money"), tv = $("t-vol");
    if (tm) tm.addEventListener("click", function (){ setMetric("money"); });
    if (tv) tv.addEventListener("click", function (){ setMetric("vol"); });
  }

  function start(){ wireToggle(); init(); }

  // Los scripts usan defer: el DOM ya está listo cuando corre esto.
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
