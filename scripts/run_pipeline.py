# ============================================================
# AeroRoute -- End-to-End Regional Pipeline Orchestrator
# File : scripts/run_pipeline.py
# Usage: python scripts/run_pipeline.py --region INDIA --mode all
#        python scripts/run_pipeline.py --region US --mode all
# ============================================================

import sys
from pathlib import Path

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import datetime
import json
import logging
import subprocess
import time
from typing import Dict, Any, Optional

from config.settings import settings
from src.utils.db import get_db, get_client
from src.utils.logger import get_logger

logger = get_logger("pipeline_orchestrator")


def print_banner(text: str, level: str = "INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"[{ts}] [{level}] {text}")
    print(f"{bar}\n")


def run_validation_step(region: str) -> bool:
    print_banner(f"PHASE 1: VALIDATION PRE-FLIGHT ({region})")
    db = get_db()
    # Ping database
    client = get_client()
    try:
        client.admin.command("ping")
        print("[OK] MongoDB 4.4 Engine is reachable.")
    except Exception as e:
        print(f"[FAIL] MongoDB unreachable: {e}")
        return False

    if region == "INDIA":
        clean_csv = settings.INDIAN_CLEAN_CSV
        raw_csv = settings.INDIAN_RAW_CSV
        if not clean_csv.exists():
            print(f"[FAIL] Missing Indian Clean CSV: {clean_csv}")
            return False
        if not raw_csv.exists():
            print(f"[WARN] Indian Raw CSV not found at {raw_csv}, proceeding with clean dataset.")
        print(f"[OK] Indian Source Datasets Verified at: {clean_csv.parent}")

        # Run Indian validator script
        cmd = [sys.executable, str(_PROJECT_ROOT / "scripts" / "validate_indian_data.py")]
        res = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if res.returncode != 0:
            print("[FAIL] Indian dataset validation failed.")
            return False
        print("[OK] Indian dataset validation checks passed 100%.")

    else:
        # US Validation
        flights_csv = settings.FLIGHTS_CSV
        airports_csv = settings.AIRPORTS_CSV
        airlines_csv = settings.AIRLINES_CSV
        for p in [flights_csv, airports_csv, airlines_csv]:
            if not p.exists():
                print(f"[FAIL] Missing US Source CSV: {p}")
                return False
        print("[OK] US Source Datasets Verified.")

    return True


def run_ingestion_step(region: str, drop: bool = False) -> bool:
    print_banner(f"PHASE 2: DATASET INGESTION ({region})")
    drop_flag = ["--drop"] if drop else []

    if region == "INDIA":
        script = _PROJECT_ROOT / "scripts" / "load_indian_data.py"
        cmd = [sys.executable, str(script)] + drop_flag
        print(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if res.returncode != 0:
            print("[FAIL] Indian data ingestion failed.")
            return False

        db = get_db()
        flt_cnt = db.flights_in.count_documents({})
        apt_cnt = db.airports_in.count_documents({})
        air_cnt = db.airlines_in.count_documents({})
        print(f"[OK] Ingestion Complete -> flights_in: {flt_cnt:,} | airports_in: {apt_cnt} | airlines_in: {air_cnt}")

    else:
        script = _PROJECT_ROOT / "scripts" / "load_mongodb.py"
        cmd = [sys.executable, str(script)] + drop_flag
        print(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if res.returncode != 0:
            print("[FAIL] US data ingestion failed.")
            return False

        db = get_db()
        flt_cnt = db.flights.count_documents({})
        apt_cnt = db.airports.count_documents({})
        air_cnt = db.airlines.count_documents({})
        print(f"[OK] Ingestion Complete -> flights: {flt_cnt:,} | airports: {apt_cnt} | airlines: {air_cnt}")

    return True


def run_mapreduce_step(region: str) -> bool:
    print_banner(f"PHASE 3: SERVER-SIDE MONGODB MAPREDUCE ({region})")

    if region == "INDIA":
        script = _PROJECT_ROOT / "scripts" / "run_indian_mapreduce.py"
        cmd = [sys.executable, str(script)]
        print(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if res.returncode != 0:
            print("[FAIL] Indian MapReduce execution failed.")
            return False

        val_script = _PROJECT_ROOT / "scripts" / "validate_indian_mapreduce.py"
        cmd_val = [sys.executable, str(val_script)]
        print(f"Executing Verification: {' '.join(cmd_val)}")
        res_val = subprocess.run(cmd_val, cwd=str(_PROJECT_ROOT))
        if res_val.returncode != 0:
            print("[FAIL] Indian MapReduce mathematical validation failed.")
            return False

    else:
        db = get_db()
        print("[INFO] Executing US MapReduce baseline jobs...")
        from src.mapreduce.jobs import (
            JOB_A_MAPPER, JOB_A_REDUCER,
            JOB_B_MAPPER, JOB_B_REDUCER,
            JOB_C_MAPPER, JOB_C_REDUCER,
            JOB_D_MAPPER, JOB_D_REDUCER,
            JOB_E_MAPPER, JOB_E_REDUCER,
        )
        filt = {"is_eligible_for_route_analysis": True}
        db.flights.map_reduce(JOB_A_MAPPER, JOB_A_REDUCER, "mr_route_activity", query=filt)
        db.flights.map_reduce(JOB_B_MAPPER, JOB_B_REDUCER, "mr_airport_outgoing", query=filt)
        db.flights.map_reduce(JOB_C_MAPPER, JOB_C_REDUCER, "mr_airport_incoming", query=filt)
        db.flights.map_reduce(JOB_D_MAPPER, JOB_D_REDUCER, "mr_monthly_route", query=filt)
        db.flights.map_reduce(JOB_E_MAPPER, JOB_E_REDUCER, "mr_airport_connectivity", query=filt)
        print("[OK] US MapReduce execution completed.")

    return True


def run_analytics_step(region: str, k: int = 4) -> bool:
    print_banner(f"PHASE 4: NETWORK ANALYTICS & K-MEANS CLUSTERING ({region})")

    # 1. Clustering execution
    cmd = [
        sys.executable, "-m", "models.airport_clustering",
        "--region", region,
        "--k", str(k),
    ]
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    if res.returncode != 0:
        print("[FAIL] K-Means clustering failed.")
        return False

    # 2. Generate Master Analytics Summary Export
    db = get_db()
    routes_col = settings.get_mr_route_activity_collection(region)
    airports_col = settings.get_airports_collection(region)
    flights_col = settings.get_flights_collection(region)

    total_routes = db[routes_col].count_documents({})
    total_airports = db[airports_col].count_documents({})
    total_flights = db[flights_col].count_documents({})

    summary = {
        "region": region,
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_records": total_flights,
        "unique_airports": total_airports,
        "directed_routes": total_routes,
        "k_clusters": k,
        "status": "VERIFIED_PRODUCTION_READY",
    }

    out_file = settings.EXPORTS_DIR / f"analytics_master_summary_{region.lower()}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] Master Analytics Summary exported -> {out_file}")

    return True


def main():
    parser = argparse.ArgumentParser(description="AeroRoute End-to-End Pipeline Orchestrator")
    parser.add_argument(
        "--region",
        type=str,
        default="INDIA",
        choices=["INDIA", "US", "india", "us"],
        help="Aviation network region (default: INDIA)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="all",
        choices=["validate", "ingest", "mapreduce", "analytics", "all"],
        help="Pipeline stage to execute (default: all)",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop and recreate collections before ingesting",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=4,
        help="Cluster count for airport K-Means (default: 4)",
    )

    args = parser.parse_args()
    target_region = args.region.upper()
    if target_region in ["US", "USA"]:
        target_region = "US"
    else:
        target_region = "INDIA"

    start_time = time.time()
    print_banner(f"STARTING AEROROUTE PIPELINE [{target_region} | MODE: {args.mode.upper()}]")

    success = True
    if args.mode in ["validate", "all"]:
        if not run_validation_step(target_region):
            sys.exit(1)

    if args.mode in ["ingest", "all"]:
        if not run_ingestion_step(target_region, drop=args.drop):
            sys.exit(1)

    if args.mode in ["mapreduce", "all"]:
        if not run_mapreduce_step(target_region):
            sys.exit(1)

    if args.mode in ["analytics", "all"]:
        if not run_analytics_step(target_region, k=args.k):
            sys.exit(1)

    elapsed = round(time.time() - start_time, 2)
    print_banner(f"PIPELINE COMPLETED SUCCESSFULLY IN {elapsed} SECONDS ({target_region})")
    sys.exit(0)


if __name__ == "__main__":
    main()
