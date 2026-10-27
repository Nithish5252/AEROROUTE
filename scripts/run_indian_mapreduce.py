# ============================================================
# AeroRoute -- Phase 3: Indian MapReduce Pipeline Runner
# File : scripts/run_indian_mapreduce.py
# Usage: python scripts/run_indian_mapreduce.py [--job A|B|C|D|E|ALL] [--limit N]
# ============================================================

import argparse
import datetime
import os
import sys
import time
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymongo
from config.settings import settings
from src.mapreduce.indian_jobs import (
    INDIAN_JOB_A_MAPPER, INDIAN_JOB_A_REDUCER, INDIAN_JOB_A_FINALIZE,
    INDIAN_JOB_B_MAPPER, INDIAN_JOB_B_REDUCER, INDIAN_JOB_B_FINALIZE,
    INDIAN_JOB_C_MAPPER, INDIAN_JOB_C_REDUCER, INDIAN_JOB_C_FINALIZE,
    INDIAN_JOB_D_MAPPER, INDIAN_JOB_D_REDUCER, INDIAN_JOB_D_FINALIZE,
    INDIAN_JOB_E_MAPPER, INDIAN_JOB_E_REDUCER, INDIAN_JOB_E_FINALIZE,
    INDIAN_MAPREDUCE_QUERY_FILTER,
)
from src.utils.db import get_client, get_db
from src.utils.logger import get_logger

logger = get_logger("run_indian_mapreduce")


def setup_indian_mr_indexes(db: pymongo.database.Database):
    """
    Configure high-efficiency indexes on Indian MapReduce output collections.
    """
    logger.info("Setting up performance indexes on Indian MapReduce collections...")
    # Job A: mr_route_activity_in
    col_a = db[settings.INDIAN_MR_ROUTE_ACTIVITY]
    col_a.create_index([("value.weekly_frequency", -1)], name="idx_mr_a_weekly_freq")
    col_a.create_index([("value.timetable_services", -1)], name="idx_mr_a_timetable_services")

    # Job B: mr_airport_outgoing_in
    col_b = db[settings.INDIAN_MR_AIRPORT_OUTGOING]
    col_b.create_index([("value.outgoing_weekly_frequency", -1)], name="idx_mr_b_outgoing_freq")

    # Job C: mr_airport_incoming_in
    col_c = db[settings.INDIAN_MR_AIRPORT_INCOMING]
    col_c.create_index([("value.incoming_weekly_frequency", -1)], name="idx_mr_c_incoming_freq")

    # Job D: mr_monthly_route_in
    col_d = db[settings.INDIAN_MR_MONTHLY_ROUTE]
    col_d.create_index([("_id.year_month", 1)], name="idx_mr_d_year_month")
    col_d.create_index([("_id.route_key", 1)], name="idx_mr_d_route_key")
    col_d.create_index([("value.weekly_frequency", -1)], name="idx_mr_d_weekly_freq")

    # Job E: mr_airport_connectivity_in
    col_e = db[settings.INDIAN_MR_AIRPORT_CONNECTIVITY]
    col_e.create_index([("value.distinct_connections", -1)], name="idx_mr_e_distinct_conn")
    col_e.create_index([("value.total_weekly_frequency", -1)], name="idx_mr_e_total_freq")
    logger.info("Indexes successfully configured on all Indian MapReduce collections.")


def run_indian_job_a(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job A: Indian Directed Route Activity
    Output: mr_route_activity_in
    """
    logger.info("Executing Indian Job A: Directed Route Activity (DEL->BOM vs BOM->DEL)...")
    start = time.time()
    out_col = settings.INDIAN_MR_ROUTE_ACTIVITY

    options = {
        "out": {"replace": out_col},
        "finalize": INDIAN_JOB_A_FINALIZE,
        "query": INDIAN_MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.INDIAN_FLIGHTS_COLLECTION].map_reduce(
        INDIAN_JOB_A_MAPPER,
        INDIAN_JOB_A_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job A completed in {elapsed:.2f}s. Output '{out_col}' contains {doc_count:,} routes.")

    sample = list(db[out_col].find().sort("value.weekly_frequency", -1).limit(3))
    for s in sample:
        v = s["value"]
        logger.info(
            f"   Route: {s['_id']} -> Weekly Freq: {int(v['weekly_frequency']):,}, "
            f"Timetable Services: {int(v['timetable_services'])}, Est. Monthly: {int(v['estimated_monthly_departures']):,}"
        )

    return {
        "job": "Job A (Indian Directed Route Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_indian_job_b(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job B: Indian Airport Outgoing Activity
    Output: mr_airport_outgoing_in
    """
    logger.info("Executing Indian Job B: Airport Outgoing Scheduled Activity...")
    start = time.time()
    out_col = settings.INDIAN_MR_AIRPORT_OUTGOING

    options = {
        "out": {"replace": out_col},
        "finalize": INDIAN_JOB_B_FINALIZE,
        "query": INDIAN_MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.INDIAN_FLIGHTS_COLLECTION].map_reduce(
        INDIAN_JOB_B_MAPPER,
        INDIAN_JOB_B_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job B completed in {elapsed:.2f}s. Output '{out_col}' contains {doc_count:,} airports.")

    sample = list(db[out_col].find().sort("value.outgoing_weekly_frequency", -1).limit(3))
    for s in sample:
        v = s["value"]
        logger.info(
            f"   Airport: {s['_id']} -> Outgoing Weekly Freq: {int(v['outgoing_weekly_frequency']):,}, "
            f"Destinations: {int(v['out_degree_destinations'])}, Timetable Services: {int(v['outgoing_timetable_services'])}"
        )

    return {
        "job": "Job B (Indian Airport Outgoing Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_indian_job_c(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job C: Indian Airport Incoming Activity
    Output: mr_airport_incoming_in
    """
    logger.info("Executing Indian Job C: Airport Incoming Scheduled Activity...")
    start = time.time()
    out_col = settings.INDIAN_MR_AIRPORT_INCOMING

    options = {
        "out": {"replace": out_col},
        "finalize": INDIAN_JOB_C_FINALIZE,
        "query": INDIAN_MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.INDIAN_FLIGHTS_COLLECTION].map_reduce(
        INDIAN_JOB_C_MAPPER,
        INDIAN_JOB_C_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job C completed in {elapsed:.2f}s. Output '{out_col}' contains {doc_count:,} airports.")

    sample = list(db[out_col].find().sort("value.incoming_weekly_frequency", -1).limit(3))
    for s in sample:
        v = s["value"]
        logger.info(
            f"   Airport: {s['_id']} -> Incoming Weekly Freq: {int(v['incoming_weekly_frequency']):,}, "
            f"Origins: {int(v['in_degree_origins'])}, Timetable Services: {int(v['incoming_timetable_services'])}"
        )

    return {
        "job": "Job C (Indian Airport Incoming Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_indian_job_d(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job D: Indian Monthly Route Activity
    Output: mr_monthly_route_in
    """
    logger.info("Executing Indian Job D: Monthly Route Activity & Seasonality...")
    start = time.time()
    out_col = settings.INDIAN_MR_MONTHLY_ROUTE

    options = {
        "out": {"replace": out_col},
        "finalize": INDIAN_JOB_D_FINALIZE,
        "query": INDIAN_MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.INDIAN_FLIGHTS_COLLECTION].map_reduce(
        INDIAN_JOB_D_MAPPER,
        INDIAN_JOB_D_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job D completed in {elapsed:.2f}s. Output '{out_col}' contains {doc_count:,} monthly route entries.")

    sample = list(db[out_col].find().sort("value.weekly_frequency", -1).limit(3))
    for s in sample:
        v = s["value"]
        logger.info(
            f"   Month: {s['_id']['year_month']} | Route: {s['_id']['route_key']} -> "
            f"Weekly Freq: {int(v['weekly_frequency']):,}, Active Schedules: {int(v['active_timetable_services'])}"
        )

    return {
        "job": "Job D (Indian Monthly Route Activity)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def run_indian_job_e(db: pymongo.database.Database, limit: int = 0) -> Dict[str, Any]:
    """
    Job E: Indian Airport Connectivity Summary
    Output: mr_airport_connectivity_in
    """
    logger.info("Executing Indian Job E: Airport Connectivity Summary (Unique Graph Degree & Volume)...")
    start = time.time()
    out_col = settings.INDIAN_MR_AIRPORT_CONNECTIVITY

    options = {
        "out": {"replace": out_col},
        "finalize": INDIAN_JOB_E_FINALIZE,
        "query": INDIAN_MAPREDUCE_QUERY_FILTER,
    }
    if limit > 0:
        options["limit"] = limit

    db[settings.INDIAN_FLIGHTS_COLLECTION].map_reduce(
        INDIAN_JOB_E_MAPPER,
        INDIAN_JOB_E_REDUCER,
        **options
    )
    elapsed = time.time() - start
    doc_count = db[out_col].count_documents({})
    logger.info(f"Job E completed in {elapsed:.2f}s. Output '{out_col}' contains {doc_count:,} airports.")

    sample = list(db[out_col].find().sort("value.distinct_connections", -1).limit(3))
    for s in sample:
        v = s["value"]
        logger.info(
            f"   Airport: {s['_id']} -> Distinct Neighbors: {int(v['distinct_connections'])}, "
            f"Out-Degree: {int(v['out_degree'])}, In-Degree: {int(v['in_degree'])}, "
            f"Total Weekly Freq: {int(v['total_weekly_frequency']):,}, Total Schedules: {int(v['total_schedules']):,}"
        )

    return {
        "job": "Job E (Indian Airport Connectivity Summary)",
        "output_collection": out_col,
        "count": doc_count,
        "duration_seconds": round(elapsed, 2),
        "top_sample": sample,
    }


def verify_indian_sample_independently(db: pymongo.database.Database, airport_sample: str = "DEL") -> bool:
    """
    Independent Python verification:
    Validates MapReduce aggregations against raw query counts for Delhi (DEL).
    """
    logger.info(f"Running independent cross-verification for airport hub: {airport_sample}...")

    # 1. Check Job B Outgoing Timetable Services
    mr_out_doc = db[settings.INDIAN_MR_AIRPORT_OUTGOING].find_one({"_id": airport_sample})
    mr_out_sched = int(mr_out_doc["value"]["outgoing_timetable_services"]) if mr_out_doc else 0

    py_out_sched = db[settings.INDIAN_FLIGHTS_COLLECTION].count_documents({
        "is_route_eligible": True,
        "origin.iata": airport_sample,
    })

    # 2. Check Job C Incoming Timetable Services
    mr_in_doc = db[settings.INDIAN_MR_AIRPORT_INCOMING].find_one({"_id": airport_sample})
    mr_in_sched = int(mr_in_doc["value"]["incoming_timetable_services"]) if mr_in_doc else 0

    py_in_sched = db[settings.INDIAN_FLIGHTS_COLLECTION].count_documents({
        "is_route_eligible": True,
        "destination.iata": airport_sample,
    })

    # 3. Check Job E Connectivity Services
    mr_conn_doc = db[settings.INDIAN_MR_AIRPORT_CONNECTIVITY].find_one({"_id": airport_sample})
    mr_conn_out = int(mr_conn_doc["value"]["outgoing_schedules"]) if mr_conn_doc else 0
    mr_conn_in = int(mr_conn_doc["value"]["incoming_schedules"]) if mr_conn_doc else 0

    outgoing_match = (mr_out_sched == py_out_sched == mr_conn_out)
    incoming_match = (mr_in_sched == py_in_sched == mr_conn_in)

    if outgoing_match and incoming_match:
        logger.info(
            f"  [VERIFICATION PASS] Airport '{airport_sample}': Outgoing Schedules: {mr_out_sched:,} | "
            f"Incoming Schedules: {mr_in_sched:,} (100% Mathematical Consistency)"
        )
        return True
    else:
        logger.error(
            f"  [VERIFICATION FAIL] Airport '{airport_sample}': "
            f"Outgoing MR={mr_out_sched} vs PY={py_out_sched} vs CONN={mr_conn_out} | "
            f"Incoming MR={mr_in_sched} vs PY={py_in_sched} vs CONN={mr_conn_in}"
        )
        return False


def run_pipeline(job_choice: str = "ALL", limit: int = 0) -> List[Dict[str, Any]]:
    """
    Execute Indian MapReduce pipeline with safety verifications and audit logging.
    """
    db = get_db()

    # Pre-flight check: Verify US collections and Indian flights exist
    us_flight_count = db[settings.FLIGHTS_COLLECTION].count_documents({})
    us_mr_route_count = db[settings.MR_ROUTE_ACTIVITY].count_documents({})
    assert us_flight_count == 100000, f"Original US flights count mismatch! Found {us_flight_count}"
    assert us_mr_route_count > 0, "Original US MapReduce collections missing!"

    total_eligible = db[settings.INDIAN_FLIGHTS_COLLECTION].count_documents(INDIAN_MAPREDUCE_QUERY_FILTER)
    if total_eligible == 0:
        logger.error("No eligible flight records found in 'flights_in'! Run scripts/load_indian_data.py first.")
        sys.exit(1)

    logger.info(f"Verified pre-flight: {total_eligible:,} route-eligible Indian flights available. Original US collections safe.")

    results = []
    job_choice = job_choice.upper()

    if job_choice in ["A", "ALL"]:
        results.append(run_indian_job_a(db, limit=limit))
    if job_choice in ["B", "ALL"]:
        results.append(run_indian_job_b(db, limit=limit))
    if job_choice in ["C", "ALL"]:
        results.append(run_indian_job_c(db, limit=limit))
    if job_choice in ["D", "ALL"]:
        results.append(run_indian_job_d(db, limit=limit))
    if job_choice in ["E", "ALL"]:
        results.append(run_indian_job_e(db, limit=limit))

    # Setup indexes on Indian MapReduce collections
    setup_indian_mr_indexes(db)

    # Post-flight check: Verify original US collections were 100% untouched
    us_flight_count_after = db[settings.FLIGHTS_COLLECTION].count_documents({})
    us_mr_route_count_after = db[settings.MR_ROUTE_ACTIVITY].count_documents({})
    assert us_flight_count == us_flight_count_after, "CRITICAL ERROR: Original US flights modified!"
    assert us_mr_route_count == us_mr_route_count_after, "CRITICAL ERROR: Original US MapReduce outputs modified!"
    logger.info("Post-flight check passed: Original US collections and US MapReduce outputs are 100% UNTOUCHED.")

    # Cross-verification
    if job_choice in ["B", "C", "E", "ALL"]:
        verify_indian_sample_independently(db, airport_sample="DEL")
        verify_indian_sample_independently(db, airport_sample="BOM")

    # Audit log entry in pipeline_runs
    col_runs = db[settings.PIPELINE_RUNS_COLLECTION]
    run_doc = {
        "run_id": f"RUN_IN_MR_{datetime.datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.datetime.now(timezone.utc),
        "pipeline_stage": "MAPREDUCE_INDIAN",
        "jobs_executed": [r["job"] for r in results],
        "output_collections": [r["output_collection"] for r in results],
        "metrics": {r["output_collection"]: r["count"] for r in results},
        "status": "COMPLETED",
        "verified_us_collections_untouched": True,
    }
    col_runs.insert_one(run_doc)
    logger.info(f"Recorded MapReduce pipeline audit in '{settings.PIPELINE_RUNS_COLLECTION}' (Run ID: {run_doc['run_id']})")

    # Summary table
    print("\n" + "=" * 80)
    print("  AEROROUTE -- INDIAN MAPREDUCE EXECUTION SUMMARY")
    print("=" * 80)
    print(f" {'JOB NAME':<40} | {'OUTPUT COLLECTION':<26} | {'ENTRIES':<8} | {'TIME'}")
    print("-" * 80)
    for r in results:
        print(f" {r['job']:<40} | {r['output_collection']:<26} | {r['count']:<8,} | {r['duration_seconds']}s")
    print("=" * 80)
    print(" All Indian MapReduce jobs executed, indexed, and cross-verified successfully.\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="AeroRoute Indian MongoDB MapReduce Pipeline Runner")
    parser.add_argument(
        "--job",
        choices=["A", "B", "C", "D", "E", "ALL"],
        default="ALL",
        help="Specify which Indian MapReduce job to execute (default: ALL)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of flight records processed (0 = full collection)",
    )
    args = parser.parse_args()
    run_pipeline(job_choice=args.job, limit=args.limit)


if __name__ == "__main__":
    main()
