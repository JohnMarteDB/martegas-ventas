"""Consolidate every report file into one clean daily dataset.

Pipeline:
  1. Scan REPORTS_DIR for data files (.xls/.xlsx/.ods/.pdf), skip jpg/ini/_dirs.
  2. Parse each file (cached & incremental: only new/changed files are re-read).
  3. Attach folder month, drop empty days, drop off-window "ghost" rows.
  4. Deduplicate by (product, date) keeping the most recent / corrected source.
  5. Flag anomalies (out-of-range, source disagreement, price mismatch).
  6. Write daily_sales.csv/json (full detail) + anomalies.csv + file_manifest.csv.

Run:  py src/consolidate.py            (incremental)
      py src/consolidate.py --rebuild  (ignore cache)
"""
from __future__ import annotations
import os, sys, json, csv, re, gzip, calendar, datetime, argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src import extract
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CACHE_FILE = os.path.join(config.CACHE_DIR, "extract_cache.json.gz")
LEGACY_CACHE = os.path.join(config.CACHE_DIR, "extract_cache.json")
DATA_EXTS = {".xls", ".xlsx", ".ods", ".pdf"}


def _load_cache():
    """Read the gzipped cache; fall back to a legacy plain-json cache once."""
    if os.path.exists(CACHE_FILE):
        with gzip.open(CACHE_FILE, "rt", encoding="utf-8") as f:
            return json.load(f)
    if os.path.exists(LEGACY_CACHE):
        with open(LEGACY_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    with gzip.open(CACHE_FILE, "wt", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    # drop the legacy uncompressed cache once we've written the gz version
    if os.path.exists(LEGACY_CACHE):
        try:
            os.remove(LEGACY_CACHE)
        except OSError:
            pass
GRACE_BEFORE = 7   # days before folder-month start still accepted (late arrivals)
GRACE_AFTER = 2


def sig(path):
    st = os.stat(path)
    return f"{st.st_size}-{int(st.st_mtime)}", st.st_mtime


MONTH_RE = re.compile(r"^\d{4}-\d{2}")

def month_folders(months=None):
    """List YYYY-MM report folders (fast: one listdir of the root)."""
    out = []
    for name in os.listdir(config.REPORTS_DIR):
        if name.startswith(config.IGNORE_DIR_PREFIXES) or not MONTH_RE.match(name):
            continue
        if months and name[:7] not in months:
            continue
        p = os.path.join(config.REPORTS_DIR, name)
        if os.path.isdir(p):
            out.append((name, p))
    return sorted(out)


def scan_files(only=None, months=None):
    """Iterate report files via explicit month/day folders (DriveFS-friendly:
    os.walk over the whole tree is pathologically slow on Google Drive)."""
    files = []
    for _ym, mpath in month_folders(months):
        try:
            entries = os.listdir(mpath)
        except OSError:
            continue
        for ent in entries:
            epath = os.path.join(mpath, ent)
            if os.path.isdir(epath):
                try:
                    dayfiles = os.listdir(epath)
                except OSError:
                    continue
                for fn in dayfiles:
                    if os.path.splitext(fn)[1].lower() in DATA_EXTS:
                        files.append(os.path.join(epath, fn))
            elif os.path.splitext(ent)[1].lower() in DATA_EXTS:
                files.append(epath)
    if only:
        files = [p for p in files if only in p]
    return files


def _parse_worker(path):
    try:
        s, mtime = sig(path)
        recs = extract.extract_file(path)
        return os.path.relpath(path, config.REPORTS_DIR), s, mtime, recs, None
    except Exception as e:
        rel = os.path.relpath(path, config.REPORTS_DIR)
        return rel, "err", 0.0, [], f"{type(e).__name__}: {e}"


def build_cache(rebuild=False, workers=8, only=None, months=None):
    cache = {} if rebuild else _load_cache()

    files = scan_files(only=only, months=months)
    todo = []
    for p in files:
        rel = os.path.relpath(p, config.REPORTS_DIR)
        try:
            s, _ = sig(p)
        except OSError:
            continue
        if rebuild or rel not in cache or cache[rel].get("sig") != s:
            todo.append(p)

    print(f"  {len(files)} data files; {len(todo)} new/changed to parse", flush=True)
    done = 0
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for rel, s, mtime, recs, err in ex.map(_parse_worker, todo):
                cache[rel] = {"sig": s, "mtime": mtime, "records": recs, "error": err}
                done += 1
                if done % 50 == 0:
                    print(f"    parsed {done}/{len(todo)}", flush=True)

    # prune cache entries whose files disappeared (only on a full scan)
    pruned = False
    if not only and not months:
        live = {os.path.relpath(p, config.REPORTS_DIR) for p in files}
        for rel in list(cache):
            if rel not in live:
                del cache[rel]
                pruned = True

    # Only rewrite the cache if something actually changed (gzipped + slow on
    # DriveFS), so quiet nights stay cheap. Also migrate legacy plain-json once.
    if todo or pruned or rebuild or not os.path.exists(CACHE_FILE):
        _save_cache(cache)
    return cache, files


def folder_ym(rel):
    head = rel.replace("\\", "/").split("/")[0]
    if len(head) >= 7 and head[4] == "-":
        return head[:7]
    return None


def in_window(date_str, ym):
    if not ym:
        return True
    y, m = int(ym[:4]), int(ym[5:7])
    start = datetime.date(y, m, 1)
    end = datetime.date(y, m, calendar.monthrange(y, m)[1])
    d = datetime.date.fromisoformat(date_str)
    return (start - datetime.timedelta(days=GRACE_BEFORE)) <= d <= (end + datetime.timedelta(days=GRACE_AFTER))


def consolidate(cache):
    # group candidate records by (product, date)
    groups = defaultdict(list)
    errors = []
    ghosts = []
    future = []
    # Monthly workbooks (esp. GNV) often pre-fill upcoming day-sheets with
    # projected values. A sale can't exist for a date after today, so drop those
    # (they self-correct: once the day passes, the real value overwrites them).
    today_iso = datetime.date.today().isoformat()
    for rel, entry in cache.items():
        if entry.get("error"):
            errors.append({"source_file": rel, "error": entry["error"]})
        ym = folder_ym(rel)
        mt = entry.get("mtime", 0.0)
        fday = 0
        parts = rel.replace("\\", "/").split("/")
        if len(parts) > 1 and parts[1].isdigit():
            fday = int(parts[1])
        for r in entry.get("records", []):
            if r.get("error"):
                errors.append({"source_file": rel, "error": r["error"]})
                continue
            vol = r.get("volume") or 0.0
            rev = r.get("revenue") or 0.0
            if vol == 0 and rev == 0:
                continue                       # empty / unfilled day
            r = dict(r, folder_ym=ym, _mtime=mt, _fday=fday)
            if r["date"] > today_iso:
                future.append(r)               # projected/pre-filled future day
                continue
            if not in_window(r["date"], ym):
                ghosts.append(r)
                continue
            groups[(r["product"], r["date"])].append(r)

    rows = []
    anomalies = list(errors)
    for (product, date), cands in sorted(groups.items()):
        # prefer most recent file, then later cumulative folder-day
        cands.sort(key=lambda r: (r["_mtime"], r["_fday"]), reverse=True)
        best = dict(cands[0])
        vols = [c["volume"] for c in cands if c.get("volume")]
        spread = (max(vols) - min(vols)) if len(vols) > 1 else 0.0
        med = sorted(vols)[len(vols) // 2] if vols else 0.0
        best["n_sources"] = len(cands)
        best["src_spread_pct"] = round(100 * spread / med, 2) if med else 0.0

        flags = []
        b = config.BOUNDS[product]
        if best["volume"] < 0 or best["volume"] > b["vol_max"]:
            flags.append("volume_out_of_range")
        if best["revenue"] < 0 or best["revenue"] > b["rev_max"]:
            flags.append("revenue_out_of_range")
        price = best.get("price")
        if price and not (b["price_min"] <= price <= b["price_max"]):
            flags.append("price_out_of_range")
        if best["volume"] and best["revenue"]:
            implied = best["revenue"] / best["volume"]
            if price and price > 0 and abs(implied - price) / price > 0.15:
                flags.append("implied_price_mismatch")
        if best["src_spread_pct"] > 2:
            flags.append("source_disagreement")
        best["flags"] = ";".join(flags)
        best["implied_price"] = round(best["revenue"] / best["volume"], 4) if best["volume"] else None

        rows.append(best)
        if flags:
            anomalies.append({"date": date, "product": product, "volume": best["volume"],
                              "revenue": best["revenue"], "price": price,
                              "flags": best["flags"], "n_sources": best["n_sources"],
                              "src_spread_pct": best["src_spread_pct"],
                              "source_file": best.get("source_file")})

    rows.sort(key=lambda r: (r["date"], r["product"]))
    return rows, anomalies, ghosts, future


# canonical column order for the CSV
COLS = ["date", "product", "volume", "revenue", "price", "implied_price",
        "volume_neto", "revenue_neto",
        "pay_efectivo_vol", "pay_efectivo_rev", "pay_tarjeta_vol", "pay_tarjeta_rev",
        "pay_tarjeta_marti_vol", "pay_tarjeta_marti_rev", "pay_bonogas_vol",
        "pay_bonogas_rev", "pay_credito_vol", "pay_credito_rev", "pay_prepago_vol",
        "pay_prepago_rev", "pay_tickets_vol", "pay_tickets_rev", "pay_otros_vol",
        "pay_otros_rev", "inv_ventas", "n_sources", "src_spread_pct", "flags",
        "source_file", "source_sheet", "source_ext"]


def write_outputs(rows, anomalies):
    with open(config.DAILY_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(config.DAILY_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, default=str)
    with open(config.ANOMALIES_CSV, "w", newline="", encoding="utf-8-sig") as f:
        cols = ["date", "product", "volume", "revenue", "price", "flags",
                "n_sources", "src_spread_pct", "source_file", "error"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(anomalies)


def summarize(rows, anomalies, ghosts, future):
    from collections import Counter
    print("\n===== CONSOLIDATION SUMMARY =====")
    print(f"clean daily records : {len(rows)}")
    print(f"anomalies/errors    : {len(anomalies)}")
    print(f"off-window ghosts   : {len(ghosts)} (excluded)")
    print(f"future/projected    : {len(future)} (excluded)")
    for prod in config.PRODUCTS:
        pr = [r for r in rows if r["product"] == prod]
        if not pr:
            continue
        dates = sorted(r["date"] for r in pr)
        vol = sum(r["volume"] for r in pr)
        rev = sum(r["revenue"] for r in pr)
        print(f"\n  {prod}: {len(pr)} days  {dates[0]} -> {dates[-1]}")
        print(f"       total volume  = {vol:,.0f} {config.PRODUCT_UNIT[prod]}")
        print(f"       total revenue = RD$ {rev:,.0f}")
    yc = Counter(r["date"][:4] for r in rows)
    print("\n  records per year:", dict(sorted(yc.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel reads; keep low — DriveFS hangs under high concurrency")
    ap.add_argument("--only", default=None, help="path substring filter (testing)")
    ap.add_argument("--month", action="append", default=None,
                    help="limit to YYYY-MM (repeatable); cache keeps other months")
    ap.add_argument("--recent", type=int, default=None,
                    help="limit to the N most recent month folders")
    args = ap.parse_args()

    months = set(args.month) if args.month else None
    if args.recent:
        months = {ym for ym, _ in month_folders()[-args.recent:]}
    if months:
        print(f"Limiting to months: {sorted(months)}")

    print("Building parse cache...")
    cache, _ = build_cache(rebuild=args.rebuild, workers=args.workers,
                           only=args.only, months=months)
    print("Consolidating...")
    rows, anomalies, ghosts, future = consolidate(cache)
    write_outputs(rows, anomalies)
    summarize(rows, anomalies, ghosts, future)
    print(f"\nWrote: {config.DAILY_CSV}")


if __name__ == "__main__":
    main()
