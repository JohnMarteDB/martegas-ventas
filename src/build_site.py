"""Generate the public dashboard data (docs/data/dashboard.json).

The HTML/CSS/JS in docs/ are static and authored once; this script only
refreshes the data the page reads. Safe-for-public by construction: it emits
ONLY aggregate volume/revenue/price/KPIs — never bank deposits, cash counts,
card references or client names from the source reports.
"""
from __future__ import annotations
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src import kpis
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    dash = kpis.build_dashboard(ts)
    out = os.path.join(config.DOCS_DATA_DIR, "dashboard.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dash, f, ensure_ascii=False)
    size = os.path.getsize(out)
    print(f"Wrote {out} ({size/1024:.1f} KB)")
    for p in dash["products"]:
        k = dash["product_data"][p]["kpis"]
        print(f"  {p}: as_of {k['as_of']}  MTD vol {k['mtd_volume']:,.0f}  "
              f"YTD rev RD$ {k['ytd_revenue']:,.0f}")


if __name__ == "__main__":
    main()
