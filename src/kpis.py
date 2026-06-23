"""Compute KPIs and chart series from the consolidated daily dataset.

Returns a single JSON-serializable dict the front-end consumes directly, so the
browser does almost no computation. All money is RD$; volume is galones (GLP)
or m3 (GNV).
"""
from __future__ import annotations
import os, sys, json
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _load():
    df = pd.read_csv(config.DAILY_CSV)
    df = df[df["flags"].fillna("").eq("") | ~df["flags"].fillna("").str.contains(
        "out_of_range")]  # exclude hard-broken rows from aggregates
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["year"] = df["date"].dt.year
    return df


def _pct(cur, prev):
    if prev in (None, 0) or pd.isna(prev):
        return None
    return round(100 * (cur - prev) / prev, 1)


def shift_month(ym, n):
    """Shift a 'YYYY-MM' string by n calendar months."""
    idx = int(ym[:4]) * 12 + (int(ym[5:7]) - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _monthly(dfp):
    g = dfp.groupby("month").agg(
        volume=("volume", "sum"), revenue=("revenue", "sum"),
        days=("date", "nunique")).reset_index()
    g["price_avg"] = (g["revenue"] / g["volume"]).round(2)
    return g


def product_block(df, prod):
    dfp = df[df["product"] == prod].sort_values("date")
    if dfp.empty:
        return None
    monthly = _monthly(dfp)
    last_date = dfp["date"].max()
    cur_month = last_date.strftime("%Y-%m")
    cur_year = last_date.year

    mtd = dfp[dfp["month"] == cur_month]
    ytd = dfp[dfp["year"] == cur_year]
    last30 = dfp[dfp["date"] > last_date - pd.Timedelta(days=30)]

    # Use the last fully-elapsed month as reference; compare to the TRUE adjacent
    # calendar month / same-month-last-year (require them to exist — data has gaps).
    mser = monthly.set_index("month")
    months = list(mser.index)
    mom = yoy = None
    ref = months[-2] if len(months) >= 2 else None
    if ref:
        pm, py = shift_month(ref, -1), shift_month(ref, -12)
        if pm in mser.index:
            mom = {"month": ref,
                   "volume_pct": _pct(mser.loc[ref, "volume"], mser.loc[pm, "volume"]),
                   "revenue_pct": _pct(mser.loc[ref, "revenue"], mser.loc[pm, "revenue"])}
        if py in mser.index:
            yoy = {"month": ref,
                   "volume_pct": _pct(mser.loc[ref, "volume"], mser.loc[py, "volume"]),
                   "revenue_pct": _pct(mser.loc[ref, "revenue"], mser.loc[py, "revenue"])}

    best = dfp.loc[dfp["volume"].idxmax()]

    # payment mix (revenue) over the latest complete month, fallback to last 90d
    pay_cols = [c for c in df.columns if c.startswith("pay_") and c.endswith("_rev")]
    pool = dfp[dfp["month"] == (ref or cur_month)]
    if pool["volume"].sum() == 0:
        pool = last30
    mix = {}
    for c in pay_cols:
        v = pool[c].fillna(0).sum() if c in pool else 0
        if v > 0:
            name = c[4:-4]  # strip pay_ ... _rev
            mix[name] = round(float(v), 2)

    # recent daily series (last 120 days, only days with sales)
    recent = dfp[dfp["date"] > last_date - pd.Timedelta(days=120)]
    daily = [{"date": d.strftime("%Y-%m-%d"), "volume": round(float(v), 1),
              "revenue": round(float(r), 0)}
             for d, v, r in zip(recent["date"], recent["volume"], recent["revenue"])]

    return {
        "unit": config.PRODUCT_UNIT[prod],
        "label": config.PRODUCT_LABEL[prod],
        "coverage": {"start": dfp["date"].min().strftime("%Y-%m-%d"),
                     "end": last_date.strftime("%Y-%m-%d"),
                     "days": int(dfp["date"].nunique())},
        "kpis": {
            "as_of": last_date.strftime("%Y-%m-%d"),
            "current_month": cur_month,
            "latest_volume": round(float(dfp.iloc[-1]["volume"]), 1),
            "latest_revenue": round(float(dfp.iloc[-1]["revenue"]), 0),
            "current_price": (round(float(dfp.iloc[-1]["price"]), 2)
                              if pd.notna(dfp.iloc[-1]["price"]) else None),
            "mtd_volume": round(float(mtd["volume"].sum()), 0),
            "mtd_revenue": round(float(mtd["revenue"].sum()), 0),
            "mtd_days": int(mtd["date"].nunique()),
            "ytd_volume": round(float(ytd["volume"].sum()), 0),
            "ytd_revenue": round(float(ytd["revenue"].sum()), 0),
            "avg_daily_volume_30": round(float(last30["volume"].mean()), 1),
            "avg_daily_revenue_30": round(float(last30["revenue"].mean()), 0),
            "mom": mom, "yoy": yoy,
            "best_day": {"date": best["date"].strftime("%Y-%m-%d"),
                         "volume": round(float(best["volume"]), 1),
                         "revenue": round(float(best["revenue"]), 0)},
        },
        "monthly": [{"month": m, "volume": round(float(v), 1),
                     "revenue": round(float(r), 0), "price_avg": float(p) if pd.notna(p) else None,
                     "days": int(d)}
                    for m, v, r, p, d in zip(monthly["month"], monthly["volume"],
                                             monthly["revenue"], monthly["price_avg"],
                                             monthly["days"])],
        "payment_mix": mix,
        "daily_recent": daily,
    }


def yoy_seasonality(df, prod):
    """volume by calendar month for each year -> {year: [12 values]}."""
    dfp = df[df["product"] == prod]
    out = {}
    for yr, g in dfp.groupby(dfp["date"].dt.year):
        arr = [0.0] * 12
        for m, gg in g.groupby(g["date"].dt.month):
            arr[m - 1] = round(float(gg["volume"].sum()), 0)
        out[str(int(yr))] = arr
    return out


def build_dashboard(generated_at: str):
    df = _load()
    products = {}
    for prod in config.PRODUCTS:
        b = product_block(df, prod)
        if b:
            products[prod] = b

    # combined headline
    cur_year = df["year"].max()
    combined = {
        "ytd_revenue": round(float(df[df["year"] == cur_year]["revenue"].sum()), 0),
        "total_revenue": round(float(df["revenue"].sum()), 0),
        "total_records": int(len(df)),
        "first_date": df["date"].min().strftime("%Y-%m-%d"),
        "last_date": df["date"].max().strftime("%Y-%m-%d"),
    }

    return {
        "generated_at": generated_at,
        "products": list(products.keys()),
        "product_data": products,
        "combined": combined,
        "seasonality": {p: yoy_seasonality(df, p) for p in products},
    }


if __name__ == "__main__":
    print(json.dumps(build_dashboard("test"), ensure_ascii=False, indent=2)[:3000])
