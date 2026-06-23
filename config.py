"""Central configuration for the MarteGas sales system.

All paths are derived relative to this file so the project is portable:
the project folder lives INSIDE the reports folder, so the reports root
is simply this file's parent's parent.
"""
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
# Reports live in the parent folder (this project is a subfolder of it).
REPORTS_DIR = os.path.dirname(PROJECT_DIR)

DATA_DIR = os.path.join(PROJECT_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")
DOCS_DATA_DIR = os.path.join(DOCS_DIR, "data")

# Consolidated outputs (full / internal detail)
DAILY_CSV = os.path.join(DATA_DIR, "daily_sales.csv")
DAILY_JSON = os.path.join(DATA_DIR, "daily_sales.json")
ANOMALIES_CSV = os.path.join(DATA_DIR, "anomalies.csv")
MANIFEST_CSV = os.path.join(DATA_DIR, "file_manifest.csv")

# Product keys
GLP = "GLP"   # Gas Licuado de Propano  (galones)
GNV = "GNV"   # Gas Natural (GNV / GNL) (metros cubicos)

PRODUCTS = [GLP, GNV]
PRODUCT_LABEL = {
    GLP: "GLP – Gas Licuado de Propano",
    GNV: "GNV/GNL – Gas Natural",
}
PRODUCT_UNIT = {GLP: "galones", GNV: "m³"}

# Folders inside REPORTS_DIR to ignore when scanning (project + scratch dirs).
IGNORE_DIR_PREFIXES = ("_", ".")

# Sanity bounds used to flag anomalies (not to silently drop data).
# Daily volumes/revenue outside these are flagged for review.
BOUNDS = {
    GLP: {"vol_max": 60000, "rev_max": 12_000_000, "price_min": 10, "price_max": 400},
    GNV: {"vol_max": 60000, "rev_max": 12_000_000, "price_min": 5,  "price_max": 400},
}

# Data history starts here; anything earlier is treated as a parse error.
MIN_YEAR = 2018
MAX_YEAR = 2031

for d in (DATA_DIR, CACHE_DIR, DOCS_DIR, DOCS_DATA_DIR):
    os.makedirs(d, exist_ok=True)
