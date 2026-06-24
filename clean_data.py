"""
Task 1-3: Clean nav_history, investor_transactions, scheme_performance.
Outputs go to data/processed/.
"""
import pandas as pd
import numpy as np
import re, os, warnings
warnings.filterwarnings("ignore")

RAW  = "data/raw"
PROC = "data/processed"
os.makedirs(PROC, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TASK 1 – Clean nav_history.csv
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── TASK 1: Cleaning nav_history.csv ──────────────────────────────────────")
nav = pd.read_csv(f"{RAW}/nav_history.csv")
print(f"  Raw rows          : {len(nav):,}")

# 1a. Parse dates (format is DD-MM-YYYY in raw)
nav["date"] = pd.to_datetime(nav["date"], format="%d-%m-%Y", errors="coerce")
bad_dates = nav["date"].isna().sum()
print(f"  Unparseable dates : {bad_dates}")
nav = nav.dropna(subset=["date"])

# 1b. Remove duplicates (keep first)
before = len(nav)
nav = nav.drop_duplicates(subset=["amfi_code", "date"], keep="first")
print(f"  Duplicates removed: {before - len(nav)}")

# 1c. Validate NAV > 0 — flag then remove negatives/zeros
invalid_nav = nav[nav["nav"] <= 0].shape[0]
print(f"  Invalid NAV (≤0)  : {invalid_nav}")
nav.loc[nav["nav"] <= 0, "nav"] = np.nan  # treat as missing before forward-fill

# 1d. Build a full date spine (weekdays only) per fund, then merge & forward-fill
print("  Building full weekday spine and forward-filling NAV …")
all_dates = pd.date_range("2023-01-01", "2024-12-31", freq="B")  # business days
fund_codes = nav["amfi_code"].unique()
spine = pd.MultiIndex.from_product([fund_codes, all_dates],
                                   names=["amfi_code", "date"]).to_frame(index=False)

# Bring in scheme_name from nav (take first occurrence per amfi_code)
name_map = nav[["amfi_code","scheme_name"]].drop_duplicates("amfi_code")
nav_clean = spine.merge(nav[["amfi_code","date","nav"]], on=["amfi_code","date"], how="left")
nav_clean = nav_clean.merge(name_map, on="amfi_code", how="left")

# Forward-fill within each fund
nav_clean = nav_clean.sort_values(["amfi_code","date"])
nav_clean["nav"] = nav_clean.groupby("amfi_code")["nav"].ffill()

# After ffill there may still be NaNs at the very start — back-fill those
nav_clean["nav"] = nav_clean.groupby("amfi_code")["nav"].bfill()

# Final validation: ensure all NAV > 0
nav_clean = nav_clean[nav_clean["nav"] > 0]
nav_clean["nav"] = nav_clean["nav"].round(4)
nav_clean["date"] = nav_clean["date"].dt.date  # store as date string

# Reorder columns
nav_clean = nav_clean[["amfi_code","scheme_name","date","nav"]]
nav_clean.to_csv(f"{PROC}/nav_history_clean.csv", index=False)
print(f"  Clean rows        : {len(nav_clean):,}")
print("  ✓ Saved nav_history_clean.csv")


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 2 – Clean investor_transactions.csv
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── TASK 2: Cleaning investor_transactions.csv ────────────────────────────")
txn = pd.read_csv(f"{RAW}/investor_transactions.csv")
print(f"  Raw rows          : {len(txn):,}")

# 2a. Standardise transaction_type
TYPE_MAP = {
    "sip": "SIP", "Sip": "SIP", "SIP": "SIP",
    "lumpsum": "Lumpsum", "LUMPSUM": "Lumpsum", "Lumpsum": "Lumpsum",
    "redemption": "Redemption", "REDEMPTION": "Redemption", "Redemption": "Redemption",
    "SWP": "SWP", "dividend": "Dividend",
}
before_types = txn["transaction_type"].value_counts().to_dict()
txn["transaction_type"] = txn["transaction_type"].map(TYPE_MAP).fillna("Unknown")
print(f"  Type normalisation: {before_types} → {txn['transaction_type'].value_counts().to_dict()}")

# 2b. Fix date formats — try multiple formats
def parse_date_flexible(s):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return pd.to_datetime(s, format=fmt)
        except Exception:
            pass
    return pd.NaT

txn["date"] = txn["date"].apply(parse_date_flexible)
bad_dates = txn["date"].isna().sum()
print(f"  Unparseable dates : {bad_dates}")
txn = txn.dropna(subset=["date"])
txn["date"] = txn["date"].dt.date

# 2c. Validate amount > 0
invalid_amt = (txn["amount"] <= 0).sum()
print(f"  Invalid amounts(≤0): {invalid_amt}")
txn = txn[txn["amount"] > 0]

# 2d. KYC status enum validation
VALID_KYC = {"verified", "pending", "failed"}
txn["kyc_status"] = txn["kyc_status"].str.strip().str.lower()
txn["kyc_status"] = txn["kyc_status"].apply(
    lambda x: x if x in VALID_KYC else "unknown"
)
print(f"  KYC distribution  : {txn['kyc_status'].value_counts().to_dict()}")

# 2e. Remove duplicates on transaction_id
dup = txn.duplicated(subset=["transaction_id"]).sum()
txn = txn.drop_duplicates(subset=["transaction_id"])
print(f"  Duplicate txn_ids : {dup}")

txn.to_csv(f"{PROC}/investor_transactions_clean.csv", index=False)
print(f"  Clean rows        : {len(txn):,}")
print("  ✓ Saved investor_transactions_clean.csv")


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 3 – Clean scheme_performance.csv
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── TASK 3: Cleaning scheme_performance.csv ───────────────────────────────")
perf = pd.read_csv(f"{RAW}/scheme_performance.csv")
print(f"  Raw rows          : {len(perf):,}")

# 3a. Coerce return columns to numeric; flag non-numeric
for col in ["return_1y", "return_3y", "return_5y"]:
    before = perf[col].dtype
    perf[col] = pd.to_numeric(perf[col], errors="coerce")
    nulls = perf[col].isna().sum()
    print(f"  {col}: dtype {before} → float64, NaNs introduced: {nulls}")

# 3b. Flag anomalies: returns outside realistic bounds [-50%, +100%]
BOUNDS = {"return_1y": (-50, 100), "return_3y": (-30, 80), "return_5y": (-20, 60)}
flags = []
for col, (lo, hi) in BOUNDS.items():
    mask = (perf[col] < lo) | (perf[col] > hi)
    count = mask.sum()
    if count:
        print(f"  Anomaly [{col} outside ({lo},{hi})]: {count} rows → capped")
        flags.extend(perf[mask].index.tolist())
    perf[col] = perf[col].clip(lo, hi)

perf["anomaly_flag"] = perf.index.isin(set(flags))

# 3c. Expense ratio range validation: 0.1% – 2.5%
er_bad = ((perf["expense_ratio"] < 0.1) | (perf["expense_ratio"] > 2.5)).sum()
print(f"  expense_ratio out of [0.1,2.5]: {er_bad} rows → capped")
perf["expense_ratio"] = perf["expense_ratio"].clip(0.1, 2.5).round(4)

# 3d. Fill remaining NaN returns with median per category
for col in ["return_1y", "return_3y", "return_5y"]:
    perf[col] = perf.groupby("category")[col].transform(
        lambda x: x.fillna(x.median())
    )

perf.to_csv(f"{PROC}/scheme_performance_clean.csv", index=False)
print(f"  Clean rows        : {len(perf):,}")
print("  ✓ Saved scheme_performance_clean.csv")

print("\n✅ All three files cleaned and saved to data/processed/")
