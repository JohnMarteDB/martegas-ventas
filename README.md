# MarteGas — Sistema de Ventas (GLP & GNV)

Automated pipeline that reads 7+ years of daily sales "cuadres", consolidates
them into one clean dataset, computes KPIs, and publishes a public dashboard.

```
Gmail script (midnight)  ──▶  Drive folder (YYYY-MM/DD/*.xls|ods|pdf)
                                      │
                  ┌───────────────────┴────────────────────┐
                  ▼                                         ▼
          src/consolidate.py                         src/build_site.py
   (parse + dedupe + flag → data/daily_sales.csv)   (→ docs/data/dashboard.json)
                                      │
                                      ▼
                       GitHub Pages (public dashboard)
```

## What it extracts

Two products, one daily record each (`date, product, volume, revenue, price`)
plus payment-type splits:

| Product | Meaning | Unit | History |
|---|---|---|---|
| **GLP** | Gas Licuado de Propano | galones | 2019 → present |
| **GNV** | Gas Natural (GNV/GNL) | m³ | 2023 → present |

The reports changed format 5 times (see `docs_FORMATOS.md`). The parser is
**label-anchored** and detects product/date from each file's *content*, so it
survives renamed files, typos, copies, `.xls→.ods→.pdf` changes and multiple
files per day. Sales come from the `RESUMEN VENTAS → TOTAL GLP/GNL` row (or, for
2025+ PDFs, the `VENTAS BRUTAS` line).

## Folder layout

```
_sistema-ventas/
  config.py            paths & constants
  src/
    extract.py         one file  -> daily records (the parser)
    consolidate.py     all files -> data/daily_sales.csv  (incremental + cached)
    kpis.py            dataset   -> KPIs & chart series
    build_site.py      writes docs/data/dashboard.json (public, safe aggregates)
    update.py          nightly orchestrator (parse -> build -> git push)
  data/                full/private outputs + parse cache   (git-ignored)
    daily_sales.csv    consolidated dataset (all detail)
    anomalies.csv      flagged rows for review
    update.log         nightly run log
  docs/                the PUBLIC dashboard (GitHub Pages serves this)
    index.html  styles.css  app.js  data/dashboard.json
  scripts/
    update.bat         wrapper for Task Scheduler / manual refresh
    setup_task.ps1     register the nightly scheduled task
    setup_github.ps1   one-time GitHub Pages setup
```

## First-time setup

```bash
pip install -r requirements.txt          # or: py -m pip install -r requirements.txt
py src/consolidate.py --rebuild           # one-time full backfill (slow: Drive I/O)
py src/build_site.py                      # build the dashboard data
```
Open `docs/index.html` locally to preview, then publish:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_github.ps1 -Repo martegas-ventas
powershell -ExecutionPolicy Bypass -File scripts\setup_task.ps1   -At "01:30"
```

## Daily operation (hands-off)

The scheduled task runs `scripts/update.bat` every night at 01:30 (after the
Gmail script). It is **incremental** — only new/changed files are parsed — then
it rebuilds the dashboard and `git push`es, which redeploys GitHub Pages.
Check `data/update.log` to see each run.

Refresh manually any time by double-clicking `scripts/update.bat`.

## KPIs & charts

Per product: latest day, month-to-date, year-to-date (volume + revenue),
current price, 30-day daily average, **MoM** and **YoY** growth, and best day.
Charts: monthly volume, monthly revenue, price evolution, payment mix (donut),
recent daily volume, and a year-over-year seasonality overlay.

## Data quality

`anomalies.csv` flags rows that need a human look: out-of-range values, a meter
reset / negative roll, price vs implied-price mismatch, or disagreement between
multiple source files for the same day. These are **excluded from the public
aggregates** when clearly broken, never silently "fixed".

## Privacy

Only aggregate **volume / revenue / price / payment-mix** reach the public site
(`docs/data/dashboard.json`). Bank deposits, cash-denomination counts, card
references, named clients and supervisor names are **never** extracted into the
published data. The full `data/` folder stays local (git-ignored).
