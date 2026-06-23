"""Pick representative daily records spanning every era/product and dump the RAW
source evidence next to the extracted values, into data/verify_bundle.txt.

This bundle is then audited by independent reviewers (who never call extract.py),
so any extraction error surfaces. Reading the sampled sources is sequential
(DriveFS-safe). Run AFTER consolidate.py.
"""
from __future__ import annotations
import os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUT = os.path.join(config.DATA_DIR, "verify_bundle.txt")
ENGINES = {".xls": "xlrd", ".xlsx": "openpyxl", ".ods": "odf"}


def pick(df):
    """One record per (year, product), preferring a mid-month day with no flags."""
    df = df[df["volume"] > 0].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["middist"] = (df["date"].dt.day - 15).abs()
    chosen = []
    for (yr, prod), g in df.groupby(["year", "product"]):
        clean = g[g["flags"].fillna("") == ""]
        pool = clean if len(clean) else g
        chosen.append(pool.sort_values("middist").iloc[0])
    # also include up to 2 flagged rows to confirm anomaly handling
    flagged = df[df["flags"].fillna("") != ""]
    for _, r in flagged.head(2).iterrows():
        chosen.append(r)
    return chosen


def dump_evidence(rec, f):
    src = os.path.join(config.REPORTS_DIR, rec["source_file"])
    ext = str(rec["source_ext"]).lower()
    f.write("\n" + "=" * 78 + "\n")
    f.write(f"EXTRACTED:  date={rec['date'].date()}  product={rec['product']}  "
            f"volume={rec['volume']}  revenue={rec['revenue']}  price={rec['price']}\n")
    f.write(f"SOURCE:     {rec['source_file']}  sheet={rec.get('source_sheet')}\n")
    f.write(f"FLAGS:      {rec.get('flags') or '(none)'}\n")
    f.write("-" * 78 + "\nRAW EVIDENCE:\n")
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(src) as pdf:
                txt = "\n".join(p.extract_text() or "" for p in pdf.pages)
            for kw in ("Resumen general", "Precio", "Venta Total", "VENTAS BRUTAS",
                       "VENTAS NETAS", "Hora de finaliz"):
                for line in txt.splitlines():
                    if kw.lower() in line.lower():
                        f.write("  " + line.strip() + "\n")
        else:
            xl = pd.ExcelFile(src, engine=ENGINES.get(ext, "xlrd"))
            sheet = rec.get("source_sheet")
            sheet = sheet if sheet in xl.sheet_names else xl.sheet_names[0]
            g = xl.parse(sheet, header=None, nrows=20).iloc[:, :9]
            f.write(g.to_string(max_rows=20) + "\n")
    except Exception as e:
        f.write(f"  ERROR reading source: {type(e).__name__}: {e}\n")


def main():
    df = pd.read_csv(config.DAILY_CSV)
    recs = pick(df)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("MarteGas extraction audit bundle\n")
        f.write(f"{len(recs)} sampled records across eras/products.\n")
        for rec in recs:
            dump_evidence(rec, f)
    print(f"Wrote {OUT} with {len(recs)} samples")


if __name__ == "__main__":
    main()
