# Prompt — Redesign the MarteGas dashboard (mobile-first, light theme, for non-technical owners)

> Paste into a FRESH Claude Code session at the repo root
> `G:\.shortcut-targets-by-id\1QemGIsluJH_USVZWtvKFJdVSdotSVGDG\Reporte Marte Comercial - Archivos Correo`.
> Self-contained.

---

Redesign the public dashboard front-end. The audience is the **company owners —
older, NOT computer-savvy — viewing on their PHONE**. Optimize for instant
comprehension at a glance.

## Hard requirements
- **LIGHT theme. White/near-white background, dark text.** No dark mode at all.
- **Mobile-first**, single column, large touch targets (≥48px). Must look great
  at 360–400px wide and also fine on desktop.
- **Plain Spanish, no jargon.** Replace "MTD/YoY/KPI/MoM" with everyday wording:
  e.g. "Ventas de este mes", "Lo que va del año", "Comparado con el mes pasado",
  "Comparado con el año pasado", "Precio de hoy", "Mejor día".
- **Big, bold numbers** with clear labels and units (galones / m³ / RD$).
  Use ↑/↓ with green/red and a one-word plain meaning ("subió"/"bajó").
- Few, simple visuals (an elderly owner should not be overwhelmed): keep the
  monthly trend and a simple comparison; drop anything cluttered. Charts must
  have large fonts, few gridlines, clear axis labels.
- Two products **GLP** and **GNV** shown as two big, obvious buttons/tabs (with
  the friendly names), or stacked sections — whichever is clearer on a phone.
- Numbers formatted es-DO (e.g. `RD$ 1,587,416`). Round sensibly (no decimals on
  big numbers). Show the "as of" date prominently in plain Spanish.
- Accessible: WCAG AA contrast, font ≥17px body / huge KPI numbers, no reliance
  on hover, works with no interaction.

## DO NOT change
- The Python pipeline (`src/*.py`) or the data contract. Only edit `docs/`
  (`index.html`, `styles.css`, `app.js`) and keep reading `docs/data/dashboard.json`.
- The site is a static GitHub Pages site (no build step). You may keep using
  Chart.js via CDN, or switch to a lighter approach — your call, but no bundler.

## Data contract — `docs/data/dashboard.json` (already generated; do not change shape)
```
{
  generated_at: "YYYY-MM-DD HH:MM",
  products: ["GLP","GNV"],
  product_data: {
    GLP: {
      unit: "galones", label: "GLP – Gas Licuado de Propano",
      coverage: { start, end, days },
      kpis: {
        as_of, current_month,
        latest_volume, latest_revenue, current_price,
        mtd_volume, mtd_revenue, mtd_days,
        ytd_volume, ytd_revenue,
        avg_daily_volume_30, avg_daily_revenue_30,
        mom: { month, volume_pct, revenue_pct } | null,
        yoy: { month, volume_pct, revenue_pct } | null,
        best_day: { date, volume, revenue }
      },
      monthly: [ { month:"YYYY-MM", volume, revenue, price_avg, days }, ... ],
      payment_mix: { efectivo, tarjeta, tarjeta_marti, bonogas, tickets, ... },  // by revenue RD$
      daily_recent: [ { date:"YYYY-MM-DD", volume, revenue }, ... ]  // ~last 120 days
    },
    GNV: { ...same shape, unit:"m³"... }
  },
  combined: { ytd_revenue, total_revenue, total_records, first_date, last_date },
  seasonality: { GLP: { "2019":[12 monthly volumes], ... }, GNV: {...} }
}
```
Note: `mom`/`yoy` may be null when there's no comparable month — handle gracefully
("sin datos para comparar").

## Suggested layout (mobile, top → bottom)
1. Header: "MarteGas — Ventas", and big "Datos al <fecha en español, p.ej. 22 de junio de 2026>".
2. Two large product buttons: "Gas GLP (cocina)" and "Gas Natural (GNV)" — pick
   friendly subtitles the owners recognize. Selecting one shows its section.
3. 3–4 huge KPI cards stacked: "Ventas de este mes" (volumen + RD$),
   "Lo que va del año" (RD$), "Precio de hoy", "Promedio por día".
   Each with a plain ↑/↓ vs last month.
4. One clear bar chart: monthly sales (let them pick volume or RD$ with a simple
   toggle). Big labels, show only ~last 12–24 months by default with a way to see all.
5. Optional: a simple "este mes vs mismo mes del año pasado" comparison.
6. Footer: tiny note "Actualizado automáticamente cada noche."

## Workflow
1. Read the current `docs/index.html`, `styles.css`, `app.js` to see what exists.
2. Rebuild them light + mobile-first per the above.
3. Verify with the preview tools at a **mobile viewport (375×812)** AND desktop:
   start a static server (`py -m http.server 8000 --directory _sistema-ventas/docs`),
   screenshot, check contrast/readability, confirm charts render and the GLP/GNV
   toggle works, no console errors. Iterate until it looks clean and legible.
4. When done, commit and push from `_sistema-ventas` (the live site auto-deploys):
   `git add -A && git commit -m "Rediseño del panel: claro, móvil, lenguaje sencillo" && git push`
   (the GitHub credential is already cached; first clean stray `.git/**/desktop.ini`).
5. Confirm the live site updated: https://johnmartedb.github.io/martegas-ventas/

## Environment notes
- Use the `py` launcher (not `python`). The repo lives inside Google Drive.
- Before any git op, delete stray `desktop.ini` inside `.git` (Drive injects them).
- Keep everything in Spanish for the owners; keep it warm, simple, and uncluttered.
