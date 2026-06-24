"""Generate realistic raw CSVs with intentional data quality issues to be cleaned."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random, os

random.seed(42)
np.random.seed(42)

RAW = "data/raw"

# ── Funds master ──────────────────────────────────────────────────────────────
FUNDS = [
    (100001, "HDFC Top 100 Fund - Growth",        "HDFC Mutual Fund",    "Equity",   "Large Cap",   0.95),
    (100002, "ICICI Pru Bluechip Fund - Growth",  "ICICI Prudential MF", "Equity",   "Large Cap",   1.05),
    (100003, "SBI Small Cap Fund - Growth",        "SBI Mutual Fund",     "Equity",   "Small Cap",   1.85),
    (100004, "Axis Midcap Fund - Growth",          "Axis Mutual Fund",    "Equity",   "Mid Cap",     1.65),
    (100005, "Mirae Asset Large Cap - Growth",     "Mirae Asset MF",      "Equity",   "Large Cap",   0.55),
    (100006, "Parag Parikh Flexi Cap - Growth",    "PPFAS MF",            "Equity",   "Flexi Cap",   1.28),
    (100007, "Kotak Gilt Fund - Growth",           "Kotak Mahindra MF",   "Debt",     "Gilt",        0.42),
    (100008, "DSP Tax Saver Fund - Growth",        "DSP MF",              "ELSS",     "ELSS",        1.10),
    (100009, "Nippon India Liquid Fund",           "Nippon India MF",     "Debt",     "Liquid",      0.22),
    (100010, "Aditya Birla SL Arbitrage Fund",     "Aditya Birla SL MF",  "Hybrid",   "Arbitrage",   0.98),
]

# ── 1. nav_history.csv ────────────────────────────────────────────────────────
start = datetime(2023, 1, 1)
rows = []
for amfi, name, amc, cat, sub, er in FUNDS:
    nav = random.uniform(20, 500)
    d = start
    while d <= datetime(2024, 12, 31):
        # introduce missing NAV on some weekdays (holidays) + all weekends naturally
        if d.weekday() < 5:  # weekday
            if random.random() < 0.04:          # 4% missing (holidays)
                rows.append({"amfi_code": amfi, "scheme_name": name,
                              "date": d.strftime("%d-%m-%Y"), "nav": None})
            elif random.random() < 0.02:        # 2% duplicate
                rows.append({"amfi_code": amfi, "scheme_name": name,
                              "date": d.strftime("%d-%m-%Y"), "nav": round(nav, 4)})
                rows.append({"amfi_code": amfi, "scheme_name": name,
                              "date": d.strftime("%d-%m-%Y"), "nav": round(nav, 4)})
            elif random.random() < 0.005:       # 0.5% bad NAV
                rows.append({"amfi_code": amfi, "scheme_name": name,
                              "date": d.strftime("%d-%m-%Y"), "nav": -1.0})
            else:
                rows.append({"amfi_code": amfi, "scheme_name": name,
                              "date": d.strftime("%d-%m-%Y"), "nav": round(nav, 4)})
            nav *= (1 + np.random.normal(0.0004, 0.008))
            nav = max(nav, 1.0)
        d += timedelta(days=1)

pd.DataFrame(rows).to_csv(f"{RAW}/nav_history.csv", index=False)
print(f"nav_history: {len(rows):,} rows")

# ── 2. investor_transactions.csv ──────────────────────────────────────────────
STATES = ["Maharashtra","Karnataka","Tamil Nadu","Delhi","Gujarat","Rajasthan",
          "West Bengal","Telangana","Uttar Pradesh","Madhya Pradesh"]
KYC_VALS = ["verified","Verified","VERIFIED","pending","Pending","failed","Failed","N/A",""]
TXN_TYPES = ["SIP","sip","Sip","Lumpsum","lumpsum","LUMPSUM","Redemption","redemption","REDEMPTION","SWP","dividend"]

txn_rows = []
for i in range(5000):
    amfi = random.choice(FUNDS)[0]
    txn_type = random.choice(TXN_TYPES)
    amount = random.uniform(-500, 200000) if random.random() < 0.03 else random.uniform(500, 200000)
    d = start + timedelta(days=random.randint(0, 729))
    # mix date formats
    fmt = random.choice(["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"])
    txn_rows.append({
        "transaction_id": f"TXN{100000+i}",
        "investor_id":    f"INV{random.randint(1000,9999)}",
        "amfi_code":      amfi,
        "transaction_type": txn_type,
        "amount":         round(amount, 2),
        "date":           d.strftime(fmt),
        "state":          random.choice(STATES),
        "kyc_status":     random.choice(KYC_VALS),
        "units":          round(amount / random.uniform(20, 500), 4) if amount > 0 else None,
    })

pd.DataFrame(txn_rows).to_csv(f"{RAW}/investor_transactions.csv", index=False)
print(f"investor_transactions: {len(txn_rows):,} rows")

# ── 3. scheme_performance.csv ─────────────────────────────────────────────────
perf_rows = []
for amfi, name, amc, cat, sub, er in FUNDS:
    for year in [2022, 2023, 2024]:
        ret_1y  = round(random.uniform(-15, 45), 2)
        ret_3y  = round(random.uniform(-5,  30), 2)
        ret_5y  = round(random.uniform(5,   25), 2)
        # inject anomalies
        if random.random() < 0.05: ret_1y = "N/A"
        if random.random() < 0.03: ret_3y = 999.9       # spike
        if random.random() < 0.02: er_val = random.uniform(3.0, 5.0)  # out of range
        else:                      er_val = er + random.uniform(-0.1, 0.1)
        aum = round(random.uniform(500, 80000), 2)
        perf_rows.append({
            "amfi_code":     amfi,
            "scheme_name":   name,
            "amc":           amc,
            "category":      cat,
            "sub_category":  sub,
            "year":          year,
            "return_1y":     ret_1y,
            "return_3y":     ret_3y,
            "return_5y":     ret_5y,
            "expense_ratio": round(er_val, 4),
            "aum_cr":        aum,
            "benchmark":     "Nifty 50" if cat == "Equity" else "CRISIL Composite",
        })

pd.DataFrame(perf_rows).to_csv(f"{RAW}/scheme_performance.csv", index=False)
print(f"scheme_performance: {len(perf_rows):,} rows")
print("Raw data generated ✓")
