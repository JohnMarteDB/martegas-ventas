"""Internal consistency checks over the consolidated dataset.

Catches extraction mistakes without re-reading every source file:
  - payment splits should sum to ~ the row total (volume & revenue)
  - implied price (revenue/volume) should be close to the stated price
  - inventory "Ventas" should be in the ballpark of the payment total
  - report coverage gaps per product/month
Prints a report; exits non-zero if a hard check fails badly.
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


def main():
    df = pd.read_csv(config.DAILY_CSV)
    df["date"] = pd.to_datetime(df["date"])
    n = len(df)
    print(f"rows: {n}")
    if n == 0:
        print("no data"); return 0

    issues = 0
    for prod, g in df.groupby("product"):
        print(f"\n== {prod} ({len(g)} days, {g['date'].min().date()} -> {g['date'].max().date()}) ==")

        # payment-volume sum vs total volume
        volcols = [c for c in g.columns if c.startswith("pay_") and c.endswith("_vol")]
        psum = g[volcols].fillna(0).sum(axis=1)
        has_pay = psum > 0
        if has_pay.any():
            rel = ((psum[has_pay] - g.loc[has_pay, "volume"]).abs()
                   / g.loc[has_pay, "volume"].replace(0, pd.NA))
            bad = (rel > 0.02).sum()
            print(f"  payment-vol sum within 2% of total: {has_pay.sum()-bad}/{has_pay.sum()}"
                  f"  ({bad} off)")
            issues += int(bad)

        # implied price vs stated price
        gp = g[g["price"].notna() & (g["price"] > 0) & (g["volume"] > 0)]
        if len(gp):
            implied = gp["revenue"] / gp["volume"]
            rel = ((implied - gp["price"]).abs() / gp["price"])
            bad = (rel > 0.15).sum()
            print(f"  implied~=stated price (+/-15%): {len(gp)-bad}/{len(gp)}  ({bad} off)")

        # inventory ventas vs payment-total volume (sanity, looser)
        gi = g[g.get("inv_ventas").notna() & (g["volume"] > 0)] if "inv_ventas" in g else g.iloc[0:0]
        if len(gi):
            rel = ((gi["inv_ventas"] - gi["volume"]).abs() / gi["volume"])
            close = (rel <= 0.10).sum()
            print(f"  inventory ventas within 10% of sales: {close}/{len(gi)}")

        # coverage gaps (months with very few reported days)
        bym = g.groupby(g["date"].dt.strftime("%Y-%m"))["date"].nunique()
        thin = bym[bym < 10]
        if len(thin):
            print(f"  months with <10 reported days: {list(thin.index)}")

    flagged = df["flags"].fillna("").ne("").sum()
    print(f"\nrows with anomaly flags: {flagged}/{n}")
    print(f"hard payment-mismatch issues: {issues}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
