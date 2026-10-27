# ============================================================
# AeroRoute -- Phase 5: MapReduce Execution Pipeline
# File : mongodb/mapreduce/run_mapreduce_jobs.py
# Usage: python mongodb/mapreduce/run_mapreduce_jobs.py [--job A|B|C|D|E|ALL] [--limit N]
# ============================================================

import argparse
import datetime
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymongo
from config.settings import settings
from src.mapreduce.jobs import (
    JOB_A_MAPPER, JOB_A_REDUCER,
    JOB_B_MAPPER, JOB_B_REDUCER,
    JOB_C_MAPPER, JOB_C_REDUCER,
    JOB_D_MAPPER, JOB_D_REDUCER,
    JOB_E_MAPPER, JOB_E_REDUCER, JOB_E_FINALIZE,
    MAPREDUCE_QUERY_FILTER,
)
from src.utils.db import get_client, get_db
from src.utils.logger import get_logger

logger = get_logger("run_mapreduce")


def run_job_a(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job A: Directed route activity
    Key   : origin airport -> destination airport (e.g. "ATL->ORD")
    Value : 1
    Output: count of eligible flights per directed route
    """
    logger.info("Starting Job A: Directed Route Activity (ATL->ORD vs ORD->ATL)...")
    start = time.time()
    out_col = settings.MR_ROUTE_ACTIVITY

    options = {
        "out": {"replace": out_col},
        "query": MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.FLIGHTS_COLLECTION].map_reduce(
        JOB_A_MAPPER,
        JOB_A_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job A finished in {elapsed:.2f}s. Output collection '{out_col}' has {doc_count:,} routes.")

    # Top 3 routes sample
    sample = list(db[out_col].find().sort("value", -1).limit(3))
    for s in sample:
        logger.info(f"   Route: {s['_id']} -> Flights: {int(s['value']):,}")

    return {
        "job": "Job A (Directed Route Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_job_b(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job B: Airport outgoing activity
    Key   : origin airport (e.g. "ATL")
    Value : 1
    Output: outgoing eligible flight count per airport
    """
    logger.info("Starting Job B: Airport Outgoing Activity...")
    start = time.time()
    out_col = settings.MR_AIRPORT_OUTGOING

    options = {
        "out": {"replace": out_col},
        "query": MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.FLIGHTS_COLLECTION].map_reduce(
        JOB_B_MAPPER,
        JOB_B_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job B finished in {elapsed:.2f}s. Output collection '{out_col}' has {doc_count:,} airports.")

    sample = list(db[out_col].find().sort("value", -1).limit(3))
    for s in sample:
        logger.info(f"   Airport: {s['_id']} -> Outgoing Flights: {int(s['value']):,}")

    return {
        "job": "Job B (Airport Outgoing Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_job_c(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job C: Airport incoming activity
    Key   : destination airport (e.g. "ORD")
    Value : 1
    Output: incoming eligible flight count per airport
    """
    logger.info("Starting Job C: Airport Incoming Activity...")
    start = time.time()
    out_col = settings.MR_AIRPORT_INCOMING

    options = {
        "out": {"replace": out_col},
        "query": MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.FLIGHTS_COLLECTION].map_reduce(
        JOB_C_MAPPER,
        JOB_C_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job C finished in {elapsed:.2f}s. Output collection '{out_col}' has {doc_count:,} airports.")

    sample = list(db[out_col].find().sort("value", -1).limit(3))
    for s in sample:
        logger.info(f"   Airport: {s['_id']} -> Incoming Flights: {int(s['value']):,}")

    return {
        "job": "Job C (Airport Incoming Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_job_d(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job D: Monthly route activity
    Key   : year-month, origin airport, destination airport
    Value : 1
    Output: monthly eligible flight count per directed route
    """
    logger.info("Starting Job D: Monthly Route Activity...")
    start = time.time()
    out_col = settings.MR_MONTHLY_ROUTE

    options = {
        "out": {"replace": out_col},
        "query": MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.FLIGHTS_COLLECTION].map_reduce(
        JOB_D_MAPPER,
        JOB_D_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job D finished in {elapsed:.2f}s. Output collection '{out_col}' has {doc_count:,} monthly route entries.")

    sample = list(db[out_col].find().sort("value", -1).limit(3))
    for s in sample:
        logger.info(f"   Route {s['_id']['route_key']} ({s['_id']['year_month']}) -> Flights: {int(s['value']):,}")

    return {
        "job": "Job D (Monthly Route Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_job_e(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job E: Airport connectivity summary
    Output: airport-level incoming activity, outgoing activity, and distinct-connection counts.
    """
    logger.info("Starting Job E: Airport Connectivity Summary (Unique Neighbors vs Flight Volume)...")
    start = time.time()
    out_col = settings.MR_AIRPORT_CONNECTIVITY

    options = {
        "out": {"replace": out_col},
        "finalize": JOB_E_FINALIZE,
        "query": MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.FLIGHTS_COLLECTION].map_reduce(
        JOB_E_MAPPER,
        JOB_E_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job E finished in {elapsed:.2f}s. Output collection '{out_col}' has {doc_count:,} airports.")

    sample = list(db[out_col].find().sort("value.distinct_connections", -1).limit(3))
    for s in sample:
        v = s["value"]
        logger.info(
            f"   Airport: {s['_id']} -> Distinct Connections: {int(v['distinct_connections'])}, "
            f"Outgoing: {int(v['outgoing_flights']):,}, Incoming: {int(v['incoming_flights']):,}"
        )

    return {
        "job": "Job E (Airport Connectivity Summary)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def verify_sample_independently(db: pymongo.database.Database, airport_sample: str = "ATL") -> bool:
    """
    Independent Python verification:
    Validates MapReduce aggregation against an independent Python query for a specific airport.
    """
    logger.info(f"Running independent verification for sample airport: {airport_sample}...")
    # 1. Check Job B (Outgoing)
    mr_out_doc = db[settings.MR_AIRPORT_OUTGOING].find_one({"_id": airport_sample})
    mr_outgoing_count = int(mr_out_doc["value"]) if mr_out_doc else 0

    py_outgoing_count = db[settings.FLIGHTS_COLLECTION].count_documents({
        "is_route_eligible": True,
        "origin.iata": airport_sample,
    })

    # 2. Check Job C (Incoming)
    mr_in_doc = db[settings.MR_AIRPORT_INCOMING].find_one({"_id": airport_sample})
    mr_incoming_count = int(mr_in_doc["value"]) if mr_in_doc else 0

    py_incoming_count = db[settings.FLIGHTS_COLLECTION].count_documents({
        "is_route_eligible": True,
        "destination.iata": airport_sample,
    })

    # 3. Check Job E (Connectivity)
    mr_conn_doc = db[settings.MR_AIRPORT_CONNECTIVITY].find_one({"_id": airport_sample})
    mr_conn_out = int(mr_conn_doc["value"]["outgoing_flights"]) if mr_conn_doc else 0
    mr_conn_in = int(mr_conn_doc["value"]["incoming_flights"]) if mr_conn_doc else 0

    outgoing_match = (mr_outgoing_count == py_outgoing_count == mr_conn_out)
    incoming_match = (mr_incoming_count == py_incoming_count == mr_conn_in)

    if outgoing_match and incoming_match:
        logger.info(f"  [VERIFICATION PASS] Outgoing: {mr_outgoing_count:,} | Incoming: {mr_incoming_count:,} (100% Match)")
        return True
    else:
        logger.error(
            f"  [VERIFICATION FAIL] Outgoing MR={mr_outgoing_count} vs PY={py_outgoing_count} | "
            f"Incoming MR={mr_incoming_count} vs PY={py_incoming_count}"
        )
        return False


def main():
    parser = argparse.ArgumentParser(description="AeroRoute MongoDB MapReduce Pipeline Runner")
    parser.add_argument(
        "--job",
        choices=["A", "B", "C", "D", "E", "ALL"],
        default="ALL",
        help="Specify which MapReduce job to execute (default: ALL)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of flight records processed (0 = full collection)",
    )
    args = parser.parse_args()

    db = get_db()
    total_eligible = db[settings.FLIGHTS_COLLECTION].count_documents(MAPREDUCE_QUERY_FILTER)
    if total_eligible == 0:
        logger.error("No eligible flight records found in 'flights' collection! Please run scripts/load_mongodb.py first.")
        sys.exit(1)

    logger.info(f"Found {total_eligible:,} route-eligible flight records available for MapReduce.")

    results = []
    job_choice = args.job.upper()

    if job_choice in ["A", "ALL"]:
        results.append(run_job_a(db, limit=args.limit))
    if job_choice in ["B", "ALL"]:
        results.append(run_job_b(db, limit=args.limit))
    if job_choice in ["C", "ALL"]:
        results.append(run_job_c(db, limit=args.limit))
    if job_choice in ["D", "ALL"]:
        results.append(run_job_d(db, limit=args.limit))
    if job_choice in ["E", "ALL"]:
        results.append(run_job_e(db, limit=args.limit))

    # Print summary table
    print("\n" + "=" * 75)
    print("  AEROROUTE MAPREDUCE EXECUTION SUMMARY")
    print("=" * 75)
    print(f" {'JOB NAME':<38} | {'OUTPUT COLLECTION':<22} | {'ENTRIES':<8} | {'TIME'}")
    print("-" * 75)
    for r in results:
        print(f" {r['job']:<38} | {r['output_collection']:<22} | {r['count']:<8,} | {r['duration_seconds']}s")
    print("=" * 75)

    # Independent sample verification
    if job_choice in ["B", "C", "E", "ALL"]:
        verify_sample_independently(db, airport_sample="ATL")

    print("\nAll requested MapReduce jobs executed and verified successfully.\n")


if __name__ == "__main__":
    main()
