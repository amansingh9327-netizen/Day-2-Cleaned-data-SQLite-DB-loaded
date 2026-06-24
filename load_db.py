"""
Task 5: Load cleaned CSVs into bluestock_mf.db using SQLAlchemy.
Populates: dim_fund, dim_date, fact_nav, fact_transactions,
           fact_performance, fact_aum.
"""
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os, datetime

DB_PATH  = "bluestock_mf.db"
PROC     = "data/processed"
SQL_FILE = "sql/schema.sql"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# ── Apply schema ──────────────────────────────────────────────────────────────
with engine.connect() as conn:
    conn.execute(text("PRAGMA foreign_keys = ON"))
    schema_sql = open(SQL_FILE).read()
    for stmt in schema_sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
    conn.commit()
print("✓ Schema applied")

# ── Load cleaned CSVs ─────────────────────────────────────────────────────────
nav  = pd.read_csv(f"{PROC}/nav_history_clean.csv", parse_dates=["date"])
txn  = pd.read_csv(f"{PROC}/investor_transactions_clean.csv", parse_dates=["date"])
perf = pd.read_csv(f"{PROC}/scheme_performance_clean.csv")

# ── dim_fund ──────────────────────────────────────────────────────────────────
fund_cols = ["amfi_code","scheme_name","amc","category","sub_category","benchmark"]
dim_fund = (
    perf[fund_cols]
    .drop_duplicates("amfi_code")
    .reset_index(drop=True)
)
dim_fund.insert(0, "fund_id", range(1, len(dim_fund)+1))
dim_fund["is_active"] = 1
dim_fund.to_sql("dim_fund", engine, if_exists="replace", index=False)
print(f"✓ dim_fund         : {len(dim_fund):,} rows")

# ── dim_date ──────────────────────────────────────────────────────────────────
all_dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")
MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]
DAY_NAMES   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

dim_date_rows = []
for d in all_dates:
    is_me  = int(d == d + pd.offsets.MonthEnd(0))
    is_qe  = int(d.month in (3,6,9,12) and is_me)
    is_ye  = int(d.month == 12 and is_me)
    dim_date_rows.append({
        "date_id":        int(d.strftime("%Y%m%d")),
        "full_date":      d.strftime("%Y-%m-%d"),
        "year":           d.year,
        "quarter":        (d.month - 1) // 3 + 1,
        "month":          d.month,
        "month_name":     MONTH_NAMES[d.month - 1],
        "week":           d.isocalendar()[1],
        "day_of_week":    d.weekday(),
        "day_name":       DAY_NAMES[d.weekday()],
        "is_month_end":   is_me,
        "is_quarter_end": is_qe,
        "is_year_end":    is_ye,
    })
dim_date = pd.DataFrame(dim_date_rows)
dim_date.to_sql("dim_date", engine, if_exists="replace", index=False)
print(f"✓ dim_date         : {len(dim_date):,} rows")

# ── Helper: amfi_code → fund_id lookup ───────────────────────────────────────
fund_lkp = dim_fund.set_index("amfi_code")["fund_id"].to_dict()
# Helper: date string → date_id
date_lkp = dim_date.set_index("full_date")["date_id"].to_dict()

# ── fact_nav ──────────────────────────────────────────────────────────────────
nav["fund_id"]  = nav["amfi_code"].map(fund_lkp)
nav["date_id"]  = nav["date"].dt.strftime("%Y-%m-%d").map(date_lkp)
fact_nav = nav[["fund_id","date_id","nav"]].dropna(subset=["fund_id","date_id"])
fact_nav = fact_nav.drop_duplicates(subset=["fund_id","date_id"])
fact_nav.to_sql("fact_nav", engine, if_exists="replace", index=False)
print(f"✓ fact_nav         : {len(fact_nav):,} rows")

# ── fact_transactions ─────────────────────────────────────────────────────────
txn["fund_id"]  = txn["amfi_code"].map(fund_lkp)
txn["date_id"]  = txn["date"].dt.strftime("%Y-%m-%d").map(date_lkp)
fact_txn = txn[[
    "transaction_id","investor_id","fund_id","date_id",
    "transaction_type","amount","units","state","kyc_status"
]].dropna(subset=["fund_id","date_id"])
fact_txn.to_sql("fact_transactions", engine, if_exists="replace", index=False)
print(f"✓ fact_transactions: {len(fact_txn):,} rows")

# ── fact_performance ──────────────────────────────────────────────────────────
perf["fund_id"] = perf["amfi_code"].map(fund_lkp)
fact_perf = perf[[
    "fund_id","year","return_1y","return_3y","return_5y","expense_ratio","anomaly_flag"
]].dropna(subset=["fund_id"])
fact_perf.to_sql("fact_performance", engine, if_exists="replace", index=False)
print(f"✓ fact_performance : {len(fact_perf):,} rows")

# ── fact_aum ──────────────────────────────────────────────────────────────────
fact_aum = perf[["fund_id","year","aum_cr"]].dropna(subset=["fund_id"])
fact_aum.to_sql("fact_aum", engine, if_exists="replace", index=False)
print(f"✓ fact_aum         : {len(fact_aum):,} rows")

# ── Row-count verification ────────────────────────────────────────────────────
print("\n── Verification (source CSV vs DB) ───────────────────────────────────────")
checks = {
    "fact_nav":          (len(fact_nav),   "fact_nav"),
    "fact_transactions": (len(fact_txn),   "fact_transactions"),
    "fact_performance":  (len(fact_perf),  "fact_performance"),
    "fact_aum":          (len(fact_aum),   "fact_aum"),
    "dim_fund":          (len(dim_fund),   "dim_fund"),
    "dim_date":          (len(dim_date),   "dim_date"),
}
all_ok = True
with engine.connect() as conn:
    for label, (expected, table) in checks.items():
        actual = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        status = "✓" if actual == expected else "✗ MISMATCH"
        if actual != expected: all_ok = False
        print(f"  {status}  {label:22s}  expected={expected:,}  db={actual:,}")

print(f"\n{'✅ All row counts match!' if all_ok else '⚠️  Some mismatches found — investigate!'}")
