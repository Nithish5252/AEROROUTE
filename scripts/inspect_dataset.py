# ============================================================
# AeroRoute Phase 1 â€” Dataset Inspection Script
# File: inspect_dataset.py
# Usage: python inspect_dataset.py
# Requirements: pandas >= 1.3, tqdm (optional)
# ============================================================

import os
import csv
import sys
import gc
import hashlib
from collections import Counter, defaultdict

import pandas as pd

# â”€â”€ Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FLIGHTS_CSV  = "archive/flights.csv"
AIRPORTS_CSV = "archive/airports.csv"
AIRLINES_CSV = "archive/airlines.csv"
CHUNK_SIZE   = 50_000          # rows per chunk â€” safe for 8 GB RAM

# â”€â”€ Utility â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def separator(title):
    width = 65
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)

def check_file_exists(path):
    if not os.path.exists(path):
        print(f"  [ERROR] File not found: {path}")
        return False
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  [OK] {path}  |  {size_mb:.1f} MB")
    return True

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SECTION 0 â€” File Presence and Sizes
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
separator("SECTION 0 â€” File Presence & Sizes")
all_present = all([
    check_file_exists(FLIGHTS_CSV),
    check_file_exists(AIRPORTS_CSV),
    check_file_exists(AIRLINES_CSV),
])
if not all_present:
    print("\n[FATAL] One or more required files are missing. Exiting.")
    sys.exit(1)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SECTION 1 â€” airports.csv  (small file â€” full load is safe)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
separator("SECTION 1 â€” airports.csv Analysis")
airports_df = pd.read_csv(AIRPORTS_CSV, dtype=str)
print(f"  Row count       : {len(airports_df)}")
print(f"  Column count    : {len(airports_df.columns)}")
print(f"  Columns         : {list(airports_df.columns)}")
print(f"\n  Null counts:")
print(airports_df.isnull().sum().to_string(header=False))
print(f"\n  Sample rows:")
print(airports_df.head(3).to_string(index=False))

# Collect known airport IATA codes
known_airport_codes = set(airports_df["IATA_CODE"].dropna().str.strip())
print(f"\n  Distinct IATA codes in airports.csv: {len(known_airport_codes)}")

# Check lat/lon are numeric
airports_df["LATITUDE"]  = pd.to_numeric(airports_df["LATITUDE"],  errors="coerce")
airports_df["LONGITUDE"] = pd.to_numeric(airports_df["LONGITUDE"], errors="coerce")
print(f"\n  LATITUDE  nulls after coerce : {airports_df['LATITUDE'].isnull().sum()}")
print(f"  LONGITUDE nulls after coerce : {airports_df['LONGITUDE'].isnull().sum()}")
print(f"  LATITUDE  range              : {airports_df['LATITUDE'].min():.4f} to {airports_df['LATITUDE'].max():.4f}")
print(f"  LONGITUDE range              : {airports_df['LONGITUDE'].min():.4f} to {airports_df['LONGITUDE'].max():.4f}")

del airports_df
gc.collect()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SECTION 2 â€” airlines.csv  (tiny file)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
separator("SECTION 2 â€” airlines.csv Analysis")
airlines_df = pd.read_csv(AIRLINES_CSV, dtype=str)
print(f"  Row count       : {len(airlines_df)}")
print(f"  Columns         : {list(airlines_df.columns)}")
print(f"\n  Full content:")
print(airlines_df.to_string(index=False))
known_airline_codes = set(airlines_df["IATA_CODE"].dropna().str.strip())

del airlines_df
gc.collect()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SECTION 3 â€” flights.csv  (chunked â€” never fully loaded)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
separator("SECTION 3 â€” flights.csv Chunked Analysis")

# Accumulators
total_rows          = 0
total_duplicates    = 0
null_counts         = Counter()
col_names           = None
month_counter       = Counter()
airline_counter     = Counter()
origin_codes        = set()
dest_codes          = set()
numeric_origin      = 0      # non-IATA (numeric) origin codes
numeric_dest        = 0
distance_min        = float("inf")
distance_max        = float("-inf")
seen_hashes         = set()  # lightweight duplicate detection via row hash
dep_delay_nulls     = 0
arr_delay_nulls     = 0
cancel_count        = 0
divert_count        = 0
cancel_reason_vals  = Counter()
year_set            = set()

# dtypes to use when reading (reduces RAM by ~30%)
DTYPE_MAP = {
    "YEAR": "Int16", "MONTH": "Int8", "DAY": "Int8", "DAY_OF_WEEK": "Int8",
    "FLIGHT_NUMBER": "Int32", "SCHEDULED_DEPARTURE": "Int32",
    "DISTANCE": "Int32", "DIVERTED": "Int8", "CANCELLED": "Int8",
    "DEPARTURE_DELAY": "float32", "ARRIVAL_DELAY": "float32",
    "AIR_TIME": "float32", "ELAPSED_TIME": "float32",
}

print(f"  Reading in chunks of {CHUNK_SIZE:,} rows â€¦")
chunk_reader = pd.read_csv(
    FLIGHTS_CSV,
    chunksize=CHUNK_SIZE,
    dtype=DTYPE_MAP,
    low_memory=False,
    na_values=["", "NA", "N/A"],
    keep_default_na=True,
)

chunk_num = 0
for chunk in chunk_reader:
    chunk_num += 1
    row_count   = len(chunk)
    total_rows += row_count

    # Capture column names once
    if col_names is None:
        col_names = list(chunk.columns)

    # Null accumulation
    for col in chunk.columns:
        null_counts[col] += chunk[col].isnull().sum()

    # Month distribution
    if "MONTH" in chunk.columns:
        month_counter.update(chunk["MONTH"].dropna().astype(int).tolist())

    # Year check
    if "YEAR" in chunk.columns:
        year_set.update(chunk["YEAR"].dropna().astype(int).tolist())

    # Airline codes
    if "AIRLINE" in chunk.columns:
        airline_counter.update(chunk["AIRLINE"].dropna().tolist())

    # Airport code collection + numeric check
    if "ORIGIN_AIRPORT" in chunk.columns:
        origin_series = chunk["ORIGIN_AIRPORT"].dropna().str.strip()
        origin_codes.update(origin_series.tolist())
        numeric_origin += origin_series.str.isnumeric().sum()

    if "DESTINATION_AIRPORT" in chunk.columns:
        dest_series = chunk["DESTINATION_AIRPORT"].dropna().str.strip()
        dest_codes.update(dest_series.tolist())
        numeric_dest += dest_series.str.isnumeric().sum()

    # Distance range
    if "DISTANCE" in chunk.columns:
        d_min = chunk["DISTANCE"].min()
        d_max = chunk["DISTANCE"].max()
        if pd.notna(d_min) and d_min < distance_min:
            distance_min = d_min
        if pd.notna(d_max) and d_max > distance_max:
            distance_max = d_max

    # Delay nulls
    if "DEPARTURE_DELAY" in chunk.columns:
        dep_delay_nulls += chunk["DEPARTURE_DELAY"].isnull().sum()
    if "ARRIVAL_DELAY" in chunk.columns:
        arr_delay_nulls += chunk["ARRIVAL_DELAY"].isnull().sum()

    # Cancellation stats
    if "CANCELLED" in chunk.columns:
        cancel_count += (chunk["CANCELLED"] == 1).sum()
    if "DIVERTED" in chunk.columns:
        divert_count += (chunk["DIVERTED"] == 1).sum()
    if "CANCELLATION_REASON" in chunk.columns:
        cancel_reason_vals.update(
            chunk["CANCELLATION_REASON"].dropna().tolist()
        )

    # Lightweight duplicate detection (hash first 6 key fields)
    key_cols = ["YEAR", "MONTH", "DAY", "AIRLINE",
                "FLIGHT_NUMBER", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT",
                "SCHEDULED_DEPARTURE"]
    available_key_cols = [c for c in key_cols if c in chunk.columns]
    chunk_keys = chunk[available_key_cols].astype(str).agg("|".join, axis=1)
    for key in chunk_keys:
        h = hashlib.md5(key.encode()).hexdigest()
        if h in seen_hashes:
            total_duplicates += 1
        else:
            seen_hashes.add(h)

    if chunk_num % 10 == 0:
        print(f"    â€¦ processed {total_rows:,} rows so far (chunk {chunk_num})")

    del chunk
    gc.collect()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SECTION 4 â€” Summary Report
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
separator("SECTION 4 â€” flights.csv Summary Report")

print(f"\n  Total rows (excl. header)   : {total_rows:,}")
print(f"  Total columns               : {len(col_names)}")
print(f"  Column names                : {col_names}")
print(f"\n  Year values found           : {sorted(year_set)}")
print(f"  Months present              : {sorted(month_counter.keys())}")
print(f"\n  Month distribution:")
for m in sorted(month_counter.keys()):
    print(f"    Month {m:2d} : {month_counter[m]:>8,} flights")

print(f"\n  Distinct ORIGIN codes       : {len(origin_codes)}")
print(f"  Distinct DEST codes         : {len(dest_codes)}")
print(f"  Numeric (non-IATA) ORIGIN   : {numeric_origin:,}  [non-zero = REVIEW NEEDED]")
print(f"  Numeric (non-IATA) DEST     : {numeric_dest:,}  [non-zero = REVIEW NEEDED]")

print(f"\n  Airlines in flights.csv     : {len(airline_counter)}")
print(f"  Airline codes found         : {sorted(airline_counter.keys())}")
unknown_airlines = set(airline_counter.keys()) - known_airline_codes
print(f"  Airlines NOT in airlines.csv: {unknown_airlines}  [empty = OK]")

orphan_airports = (origin_codes | dest_codes) - known_airport_codes
print(f"\n  Airport codes in flights but NOT in airports.csv: {len(orphan_airports)}")
if orphan_airports:
    print(f"    {sorted(orphan_airports)[:30]}  (showing first 30)")

print(f"\n  Distance range (miles)      : {distance_min} â€“ {distance_max}")
print(f"\n  Cancelled flights           : {cancel_count:,}  ({cancel_count/total_rows*100:.2f}%)")
print(f"  Diverted flights            : {divert_count:,}  ({divert_count/total_rows*100:.2f}%)")
print(f"  Cancellation reasons found  : {dict(cancel_reason_vals)}")
print(f"\n  DEPARTURE_DELAY nulls       : {dep_delay_nulls:,}  ({dep_delay_nulls/total_rows*100:.2f}%)")
print(f"  ARRIVAL_DELAY nulls         : {arr_delay_nulls:,}  ({arr_delay_nulls/total_rows*100:.2f}%)")

separator("SECTION 5 â€” Null Counts Per Column (sorted by severity)")
null_pct = {col: (cnt, cnt/total_rows*100) for col, cnt in null_counts.items()}
for col, (cnt, pct) in sorted(null_pct.items(), key=lambda x: -x[1][0]):
    flag = "  â† EXPECTED" if col in [
        "CANCELLATION_REASON","AIR_SYSTEM_DELAY","SECURITY_DELAY",
        "AIRLINE_DELAY","LATE_AIRCRAFT_DELAY","WEATHER_DELAY"
    ] else ""
    print(f"  {col:<30} {cnt:>8,}  ({pct:5.2f}%){flag}")

separator("SECTION 6 â€” Duplicate Record Check")
print(f"  Approximate duplicate key groups detected: {total_duplicates:,}")
if total_duplicates == 0:
    print("  [OK] No duplicate records detected.")
else:
    print(f"  [WARNING] {total_duplicates:,} potential duplicate rows found â€” review before ingestion.")

separator("SECTION 7 â€” Dataset Validation Verdict")
issues = []
if total_rows < 5_800_000:
    issues.append(f"Row count {total_rows:,} is below expected 5,819,079")
if len(col_names) != 31:
    issues.append(f"Column count {len(col_names)} â‰  expected 31")
if numeric_origin > 0:
    issues.append(f"{numeric_origin:,} numeric origin codes (non-IATA) found")
if len(orphan_airports) > 0:
    issues.append(f"{len(orphan_airports)} airport codes not in airports.csv")
if unknown_airlines:
    issues.append(f"Unknown airline codes: {unknown_airlines}")
if total_duplicates > 0:
    issues.append(f"{total_duplicates:,} duplicate records detected")

if not issues:
    print("\n  âœ… DATASET VALIDATED â€” No critical issues found.")
    print("  Report these results and proceed to Phase 2.")
else:
    print(f"\n  âš ï¸  {len(issues)} issue(s) require attention before Phase 2:")
    for i, issue in enumerate(issues, 1):
        print(f"    {i}. {issue}")

print("\n" + "=" * 65)
print("  Inspection complete. Share the full output with your mentor.")
print("=" * 65 + "\n")
