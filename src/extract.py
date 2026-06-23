"""Core extraction: turn one report file (.xls/.xlsx/.ods/.pdf) into a list of
normalized daily sales records, one per (product, date).

Strategy is LABEL-ANCHORED, not cell-position-based, because the layout shifts
across eras but the anchor labels are stable:
  - Product is detected from CONTENT (TOTAL GNL / Metros Cubicos / "Natural" -> GNV;
    TOTAL GLP / INVENTARIO GLP / "Producto principal GLP" -> GLP).
  - Date is read from the "FECHA"/"Hora de finalizacion" anchor INSIDE the file
    (folders are unreliable: late arrivals, copies, multiple PDFs per day).
  - Sales come from the RESUMEN VENTAS -> "TOTAL GLP"/"TOTAL GNL"/"TOTAL" row
    (volume, monto RD$); PDFs use the "VENTAS BRUTAS" line.
"""
from __future__ import annotations
import os, re, datetime, unicodedata
import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

EXCEL_EPOCH = datetime.datetime(1899, 12, 30)  # Excel/LibreOffice serial origin


# --------------------------------------------------------------------------- #
# Normalization helpers
# --------------------------------------------------------------------------- #
def norm(v) -> str:
    """ascii-folded, upper-cased, space-collapsed text of a cell (for matching)."""
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v)
    s = s.replace("�", "")                 # drop mojibake replacement char
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")

def to_number(v):
    """Parse a numeric cell, tolerating thousands separators and stray text."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and pd.isna(v):
            return None
        return float(v)
    s = str(v).strip().replace("\xa0", "")
    if not s:
        return None
    # 1,234.56 -> 1234.56  (Dominican/US format used throughout these files)
    s2 = s.replace(",", "")
    try:
        return float(s2)
    except ValueError:
        m = _NUM_RE.search(s)
        if m:
            try:
                return float(m.group(0).replace(",", ""))
            except ValueError:
                return None
    return None


def parse_date(v, year_hint=None):
    """Return datetime.date or None. Handles Timestamp, Excel serial, strings."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (datetime.datetime, pd.Timestamp)):
        d = pd.Timestamp(v).date()
        return d if config.MIN_YEAR <= d.year <= config.MAX_YEAR else None
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, (int, float)) and not pd.isna(v):
        n = float(v)
        if 30000 <= n <= 80000:                 # plausible Excel serial date
            return (EXCEL_EPOCH + datetime.timedelta(days=int(n))).date()
        return None
    s = str(v).strip()
    if not s:
        return None
    s = re.split(r"[ ,]", s)[0]                 # keep date part, drop time
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y",
                "%m/%d/%Y", "%m/%d/%y"):
        try:
            d = datetime.datetime.strptime(s, fmt).date()
            if config.MIN_YEAR <= d.year <= config.MAX_YEAR:
                return d
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Grid model (spreadsheets)
# --------------------------------------------------------------------------- #
class Grid:
    def __init__(self, df: pd.DataFrame):
        self.raw = df.values.tolist()
        self.nrows = len(self.raw)
        self.ncols = max((len(r) for r in self.raw), default=0)
        self.ntext = [[norm(c) for c in r] for r in self.raw]

    def cell(self, r, c):
        if 0 <= r < self.nrows and 0 <= c < len(self.raw[r]):
            return self.raw[r][c]
        return None

    def find(self, predicate, rmax=None):
        """Yield (r, c, normtext) for cells whose normtext matches predicate."""
        for r, row in enumerate(self.ntext):
            if rmax is not None and r > rmax:
                break
            for c, t in enumerate(row):
                if t and predicate(t):
                    yield r, c, t

    def numbers_right(self, r, c, k=2, span=12):
        """First k numeric values to the right of (r,c)."""
        out = []
        for cc in range(c + 1, min(c + 1 + span, self.ncols + 1)):
            n = to_number(self.cell(r, cc))
            if n is not None:
                out.append(n)
                if len(out) >= k:
                    break
        return out

    def value_right(self, r, c, span=8):
        """First non-empty cell to the right (raw)."""
        for cc in range(c + 1, c + 1 + span):
            v = self.cell(r, cc)
            if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip():
                return v
        return None


# --------------------------------------------------------------------------- #
# Product detection
# --------------------------------------------------------------------------- #
def detect_product(g: Grid):
    joined = " ".join(t for row in g.ntext for t in row if t)
    if ("TOTAL GNL" in joined or "METROS CUBICOS" in joined
            or "TROPIGAS NATURAL" in joined or "INVENTARIO GNL" in joined):
        return config.GNV
    if ("TOTAL GLP" in joined or "INVENTARIO GLP" in joined
            or ("RESUMEN VENTAS" in joined and "GALONES" in joined)):
        return config.GLP
    return None


# --------------------------------------------------------------------------- #
# Spreadsheet sheet -> record
# --------------------------------------------------------------------------- #
PAY_LABELS = {
    "EFECTIVO": "efectivo",
    "TARJETA": "tarjeta", "TARJETAS": "tarjeta", "LOTES DE TARJETAS": "tarjeta",
    "BONOGAS": "bonogas",
    "CREDITO": "credito",
    "PREPAGO": "prepago",
    "OTROS": "otros",
}

def _find_total_row(g: Grid, product, resumen_rc):
    """Locate the RESUMEN VENTAS total row -> (row, col_of_label)."""
    want = "TOTAL GLP" if product == config.GLP else "TOTAL GNL"
    exact = [(r, c) for r, c, t in g.find(lambda t: t == want)]
    if exact:
        return exact[0]
    # 2019 era: label is just "TOTAL" inside the RESUMEN VENTAS column block.
    if resumen_rc is not None:
        r0, c0 = resumen_rc
        cands = [(r, c) for r, c, t in g.find(lambda t: t == "TOTAL")
                 if r0 < r < r0 + 16 and abs(c - c0) <= 1]
        if cands:
            cands.sort(key=lambda rc: (rc[0], abs(rc[1] - c0)))
            return cands[0]
    return None


def extract_sheet(df: pd.DataFrame, source) -> dict | None:
    g = Grid(df)
    if g.nrows < 6:
        return None
    product = detect_product(g)
    if not product:
        return None

    # date
    date = None
    for r, c, t in g.find(lambda t: t.startswith("FECHA")):
        date = parse_date(g.value_right(r, c))
        if date:
            break
    if not date:
        return None

    # price
    price = None
    for r, c, t in g.find(lambda t: t.startswith("PRECIO")):
        v = g.value_right(r, c)
        price = to_number(v)
        if price:
            break

    # RESUMEN VENTAS anchor + total row
    resumen = next(((r, c) for r, c, t in g.find(lambda t: "RESUMEN VENTAS" in t)), None)
    tot = _find_total_row(g, product, resumen)
    if not tot:
        return None
    tr, tc = tot
    nums = g.numbers_right(tr, tc, k=2)
    if len(nums) < 2:
        return None
    volume, revenue = nums[0], nums[1]

    rec = {
        "date": date.isoformat(),
        "product": product,
        "volume": volume,
        "revenue": revenue,
        "price": price,
    }

    # payment breakdown (rows between RESUMEN VENTAS header and TOTAL row)
    if resumen is not None:
        r0, c0 = resumen
        for r, c, t in g.find(lambda t: True):
            if not (r0 < r < tr and abs(c - c0) <= 1):
                continue
            key = PAY_LABELS.get(t.rstrip(":").strip())
            if key:
                pn = g.numbers_right(r, c, k=2)
                if pn:
                    rec[f"pay_{key}_vol"] = pn[0]
                    if len(pn) > 1:
                        rec[f"pay_{key}_rev"] = pn[1]

    # inventory cross-check (CONTROL INVENTARIO -> VENTAS row)
    for r, c, t in g.find(lambda t: t == "VENTAS"):
        iv = g.numbers_right(r, c, k=3, span=4)
        if iv:
            rec["inv_ventas"] = iv[0]
            break

    rec.update(source)
    return rec


# --------------------------------------------------------------------------- #
# PDF (2025+ marti.do GLP daily export)
# --------------------------------------------------------------------------- #
def extract_pdf(path, source) -> list[dict]:
    import pdfplumber
    txt_pages = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            txt_pages.append(pg.extract_text() or "")
    full = "\n".join(txt_pages)
    nfull = norm(full)

    if "PRODUCTO PRINCIPAL GLP" not in nfull and "RESUMEN DE VENTAS GLP" not in nfull:
        # Not the expected GLP daily report.
        if "GNL" in nfull or "NATURAL" in nfull:
            product = config.GNV
        else:
            product = config.GLP
    else:
        product = config.GLP

    # date: prefer "Hora de finalizacion D/M/YY", then inicio, then header
    date = None
    for pat in (r"FINALIZACION\s+(\d{1,2}/\d{1,2}/\d{2,4})",
                r"HORA DE INICIO\s+(\d{1,2}/\d{1,2}/\d{2,4})"):
        m = re.search(pat, nfull)
        if m:
            date = parse_date(m.group(1))
            if date:
                break

    def money(label):
        # e.g. "VENTAS BRUTAS 6,492.725 gls RD$ 860,935.392"
        m = re.search(label + r"\s+([\d,]+\.?\d*)\s*GLS\s*RD\$?\s*([\d,]+\.?\d*)", nfull)
        if m:
            return to_number(m.group(1)), to_number(m.group(2))
        return None, None

    vol, rev = money("VENTAS BRUTAS")
    nvol, nrev = money("VENTAS NETAS")

    price = None
    m = re.search(r"PRECIO\s+([\d,]+\.?\d*)", nfull)
    if m:
        price = to_number(m.group(1))

    if vol is None:
        m = re.search(r"VENTA TOTAL\s+([\d,]+\.?\d*)", nfull)
        if m:
            vol = to_number(m.group(1))
        # revenue fallback: meter grand total "Total <vol> <rev>"
        mt = re.findall(r"\bTOTAL\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)", nfull)
        if mt and rev is None:
            rev = to_number(mt[-1][1])

    if date is None or vol is None:
        return []

    rec = {
        "date": date.isoformat(),
        "product": product,
        "volume": vol,
        "revenue": rev,
        "price": price,
    }
    if nvol is not None:
        rec["volume_neto"] = nvol
        rec["revenue_neto"] = nrev

    # payment breakdown from "Resumen de ventas GLP" block
    for label, key in (("EFECTIVO", "efectivo"), ("LOTES DE TARJETAS", "tarjeta"),
                       ("BONOGAS", "bonogas"), ("TARJETA MARTI", "tarjeta_marti"),
                       ("TICKETS", "tickets")):
        m = re.search(label + r"\s+([\d,]+\.?\d*)\s*GLS\s*RD\$?\s*([\d,]+\.?\d*)", nfull)
        if m:
            rec[f"pay_{key}_vol"] = to_number(m.group(1))
            rec[f"pay_{key}_rev"] = to_number(m.group(2))
    rec.update(source)
    return [rec]


# --------------------------------------------------------------------------- #
# File dispatch
# --------------------------------------------------------------------------- #
ENGINES = {".xls": "xlrd", ".xlsx": "openpyxl", ".ods": "odf"}

def extract_file(path) -> list[dict]:
    rel = os.path.relpath(path, config.REPORTS_DIR)
    ext = os.path.splitext(path)[1].lower()
    base_src = {"source_file": rel, "source_ext": ext}

    if ext == ".pdf":
        try:
            return extract_pdf(path, base_src)
        except Exception as e:
            return [{"error": f"{type(e).__name__}: {e}", **base_src}]

    if ext not in ENGINES:
        return []

    out = []
    try:
        xl = pd.ExcelFile(path, engine=ENGINES[ext])
    except Exception as e:
        return [{"error": f"open: {type(e).__name__}: {e}", **base_src}]

    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet, header=None, dtype=object)
        except Exception:
            continue
        try:
            rec = extract_sheet(df, {**base_src, "source_sheet": str(sheet)})
        except Exception as e:
            rec = {"error": f"sheet '{sheet}': {type(e).__name__}: {e}", **base_src}
        if rec:
            out.append(rec)
    return out


if __name__ == "__main__":
    import json
    for p in sys.argv[1:]:
        recs = extract_file(p)
        print(f"\n### {p}  -> {len(recs)} record(s)")
        for r in recs[:6]:
            print(json.dumps(r, ensure_ascii=False, default=str))
