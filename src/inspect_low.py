"""Rank lowest-volume months per product and classify each as real vs data-gap.
Uses daily_sales.csv + the parse cache (no heavy Drive I/O)."""
import os, sys, gzip, json, calendar
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

df = pd.read_csv(config.DAILY_CSV)
df["date"] = pd.to_datetime(df["date"])
df["month"] = df["date"].dt.strftime("%Y-%m")

# cache: month -> list of (relfile, n_records, error)
cache_path = os.path.join(config.CACHE_DIR, "extract_cache.json.gz")
with gzip.open(cache_path, "rt", encoding="utf-8") as f:
    cache = json.load(f)
cache_by_month = {}
for rel, e in cache.items():
    m = rel.replace("\\", "/").split("/")[0]
    cache_by_month.setdefault(m, []).append(
        (rel, len(e.get("records") or []), e.get("error")))

for prod in ["GLP", "GNV"]:
    g = df[df["product"] == prod]
    months = sorted(g["month"].unique())
    rows = []
    for m in months:
        gm = g[g["month"] == m]
        y, mo = int(m[:4]), int(m[5:7])
        caldays = calendar.monthrange(y, mo)[1]
        dr = gm["date"].dt.day.nunique()
        vol = gm["volume"].sum()
        files = cache_by_month.get(m, [])
        errs = sum(1 for _, _, er in files if er)
        rows.append({"month": m, "vol": vol, "days": dr, "cal": caldays,
                     "cov": dr / caldays, "avg": vol / dr if dr else 0,
                     "files": len(files), "errs": errs})
    rstats = pd.DataFrame(rows)
    avg_daily_overall = (rstats["vol"].sum() / rstats["days"].sum())
    first_m, last_m = months[0], months[-1]

    flagged = rstats[(rstats["vol"] <= rstats["vol"].nsmallest(10).max()) |
                     (rstats["cov"] < 0.5)].sort_values("vol")

    print("\n" + "=" * 100)
    print(f"{prod}: {len(months)} months. Overall avg/day = {avg_daily_overall:,.0f}. "
          f"Flagging {len(flagged)} low/low-coverage months.")
    print("=" * 100)
    print(f"{'month':9} {'volume':>11} {'days/cal':>9} {'cov':>5} {'avg/day':>9} "
          f"{'files':>5} {'err':>3}  note")
    for _, r in flagged.iterrows():
        note = []
        if r["month"] in (first_m, last_m): note.append("BOUNDARY/partial")
        if r["errs"]: note.append(f"{int(r['errs'])} parse-error(s)")
        if r["avg"] < 0.5 * avg_daily_overall and r["days"] >= 10:
            note.append("LOW avg/day")
        if r["days"] < 0.5 * r["cal"]: note.append("FEW days reported")
        if r["files"] == 0: note.append("NO files in cache (lazy-sync?)")
        print(f"{r['month']:9} {r['vol']:>11,.0f} {int(r['days']):>4}/{int(r['cal']):<4} "
              f"{r['cov']:>5.0%} {r['avg']:>9,.0f} {int(r['files']):>5} {int(r['errs']):>3}  "
              f"{'; '.join(note)}")
