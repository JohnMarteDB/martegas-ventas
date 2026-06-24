"""For suspicious months, dump from the cache what each source file produced:
how many records, their product/date range, and how many were non-empty.
Reveals why few days survived (empty sheets / off-month / duplicates)."""
import os, sys, gzip, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

months = sys.argv[1:] or ["2020-09", "2024-08", "2023-02"]
with gzip.open(os.path.join(config.CACHE_DIR, "extract_cache.json.gz"), "rt", encoding="utf-8") as f:
    cache = json.load(f)

for target in months:
    print("\n" + "=" * 90); print("MONTH", target); print("=" * 90)
    files = {rel: e for rel, e in cache.items()
             if rel.replace("\\", "/").split("/")[0] == target}
    if not files:
        print("  (no files in cache for this month — folder was empty at scan time / lazy-sync)")
        continue
    for rel, e in sorted(files.items()):
        recs = e.get("records") or []
        if e.get("error"):
            print(f"  {rel.split(chr(92))[-1][:40]:42}  ERROR: {e['error'][:50]}")
            continue
        glp = [r for r in recs if r.get("product") == "GLP"]
        gnv = [r for r in recs if r.get("product") == "GNV"]
        def span(rs):
            ds = sorted(r["date"] for r in rs if r.get("date"))
            nz = sum(1 for r in rs if (r.get("volume") or 0) > 0)
            return f"{len(rs)} recs ({nz} nonzero) {ds[0]}..{ds[-1]}" if ds else "0"
        # which months do the dates fall in?
        ms = Counter(r["date"][:7] for r in recs if r.get("date"))
        print(f"  {rel.split(chr(92))[-1][:38]:40}")
        if glp: print(f"      GLP: {span(glp)}")
        if gnv: print(f"      GNV: {span(gnv)}")
        if ms: print(f"      date-months: {dict(ms)}")
