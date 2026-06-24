# Prompt — Inspect the lowest-volume months (data quality)

> Paste this into a fresh Claude Code session at the repo root
> `G:\.shortcut-targets-by-id\1QemGIsluJH_USVZWtvKFJdVSdotSVGDG\Reporte Marte Comercial - Archivos Correo`.
> It is self-contained.

---

You are auditing the MarteGas sales dataset. Some months show suspiciously low
**monthly volume** on the dashboard. For each low month I need to know whether
it is a **real** low-sales month or a **data defect**, and if a defect, the fix.

## Context you need
- Consolidated dataset: `_sistema-ventas/data/daily_sales.csv`
  columns: `date, product, volume, revenue, price, implied_price, …,
  n_sources, src_spread_pct, flags, source_file, source_sheet, source_ext`.
  Products: `GLP` (galones), `GNV` (m³). One row per (product, date).
- Anomalies/parse errors: `_sistema-ventas/data/anomalies.csv`.
- Parse cache (gzipped): `_sistema-ventas/data/cache/extract_cache.json.gz`
  — maps each source file → `{sig, mtime, records, error}`.
- Raw reports live in `YYYY-MM/DD/` (xls/ods/pdf). The parser detects product
  and date from file CONTENT, dedupes by (product,date), and excludes: empty
  days (vol=0 & rev=0), off-window "ghosts", rows flagged `*_out_of_range`, and
  any date AFTER today (projected day-sheets).
- Known root causes for a low month (rank candidates against these):
  1. **Genuinely low sales** (real) — days reported ≈ calendar days, volumes plausible.
  2. **Few reported days** — the month only has a handful of daily records
     (gaps in the source: the envasadora didn't send some days).
  3. **Files present but not loaded** — Google Drive File Stream lazy-sync left
     a folder looking empty at scan time (fix: re-run `py _sistema-ventas/src/consolidate.py`).
  4. **Parse errors** — encrypted/corrupt files (see anomalies.csv `error`).
  5. **Mis-parse / out-of-range** — a bad source row got flagged & excluded,
     deflating the month.
  6. **Wrong dedup / off-window exclusion** — real days dropped as "ghosts".

## Constraints (this machine)
- Use the `py` launcher, NOT `python`. Read Drive files **sequentially**
  (concurrency hangs DriveFS). Never force-kill python mid-read.
- For console unicode, scripts already set utf-8; if you print, avoid `≈`/`³`.

## Steps
1. Load `daily_sales.csv`. For each product, compute per-month:
   `volume_sum`, `days_reported` (distinct dates), `calendar_days`,
   `coverage = days_reported / calendar_days`, `avg_daily = volume_sum/days_reported`.
2. Rank months by `volume_sum` ascending; take the **bottom 10 per product**
   (also include any month with `coverage < 0.5`).
3. For each flagged month, decide the cause:
   - If `avg_daily` is normal but `days_reported` is low → **few reported days**
     (causes 2/3/6). Then: list the `YYYY-MM/` source day-folders that exist on
     disk vs the dates that produced records — the difference is the missing set.
     Check the cache for those folders' files (parsed? error? zero records?).
     If files exist but produced no record → likely lazy-sync or a parse miss →
     recommend a re-run / open the file to confirm.
   - If `avg_daily` itself is very low → open 1–2 daily source files for that
     month (dump the sheet/PDF) and check the `RESUMEN VENTAS → TOTAL` row vs
     the extracted value — confirm real vs mis-parse.
   - Cross-check `anomalies.csv` for that month (errors, out_of_range, disagreement).
4. Do NOT silently trust the CSV — for the 3 worst months, actually open a
   source file and verify the number against the raw cells.

## Output
A table, one row per flagged month: `month | product | volume | days_reported /
calendar_days | avg_daily | classification (REAL / DATA-GAP / REFETCH /
PARSE-ERROR / MISPARSE) | evidence | recommended action`. Then a short summary
of which months need a fix and the exact command(s) to run.
