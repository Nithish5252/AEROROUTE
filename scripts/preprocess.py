# ============================================================
# AeroRoute -- Phase 3: Data Preprocessing & Ingestion Pipeline
# File : scripts/preprocess.py
# Usage: python scripts/preprocess.py [--drop] [--limit-chunks N]
# ============================================================

import argparse
import datetime
import gc
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path so config and src imports work reliably
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pymongo
from pymongo.errors import BulkWriteError, DuplicateKeyError

from config.settings import settings
from src.ingestion.preprocessor import (
    load_airlines_reference,
    load_airports_reference,
    clean_and_transform_chunk,
)
from src.utils.db import get_client, get_db
from src.utils.logger import get_logger

logger = get_logger("preprocess")


def setup_indexes(db: pymongo.database.Database) -> None:
    """
    Create optimal indexes on MongoDB collections for queries and MapReduce.
    """
    logger.info("Setting up database indexes...")
    # Airlines collection
    db[settings.AIRLINES_COLLECTION].create_index("airline_code", unique=True)

    # Airports collection
    db[settings.AIRPORTS_COLLECTION].create_index("iata", unique=True)
    db[settings.AIRPORTS_COLLECTION].create_index([("location", "2dsphere")])

    # Flights collection
    flights_col = db[settings.FLIGHTS_COLLECTION]
    flights_col.create_index("flight_id")
    flights_col.create_index("route_key")
    flights_col.create_index("origin.iata")
    flights_col.create_index("destination.iata")
    flights_col.create_index("airline_code")
    flights_col.create_index("month")
    flights_col.create_index("is_route_eligible")
    flights_col.create_index("is_cancelled")
    flights_col.create_index([("origin.iata", 1), ("destination.iata", 1), ("month", 1)])
    flights_col.create_index([("origin.lat", 1), ("origin.lon", 1)])
    logger.info("Indexes successfully configured.")


def save_data_quality_report(report_data: dict, output_path: Path) -> None:
    """
    Write machine-readable Data Quality Report to JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, default=str)
    logger.info(f"Machine-readable Data Quality Report saved to: {output_path}")


def run_pipeline(
    drop_existing: bool = True,
    chunk_size: int = 50000,
    limit_chunks: int = 0,
    skip_mongo: bool = False,
    report_path: Path = None,
) -> dict:
    """
    Execute full Phase 3 preprocessing and quality control pipeline.
    """
    start_time = time.time()
    logger.info("=======================================================")
    logger.info("  AeroRoute -- Phase 3: Data Preprocessing & Quality Control")
    logger.info("=======================================================")
    logger.info(f"Chunk Size     : {chunk_size:,} rows")
    logger.info(f"Limit Chunks   : {limit_chunks if limit_chunks > 0 else 'All (Full Dataset)'}")
    logger.info(f"Drop Existing  : {drop_existing}")
    logger.info(f"Skip MongoDB   : {skip_mongo}")

    if report_path is None:
        report_path = settings.PROCESSED_DIR / "data_quality_report.json"

    # --- 1. Database Connection ---
    db = None
    if not skip_mongo:
        db = get_db()
        if drop_existing:
            logger.info("Dropping existing collections for clean rerun...")
            db[settings.FLIGHTS_COLLECTION].drop()
            db[settings.AIRPORTS_COLLECTION].drop()
            db[settings.AIRLINES_COLLECTION].drop()

    # --- 2. Reference Tables Ingestion ---
    logger.info(f"Reading airlines reference: {settings.AIRLINES_CSV}")
    airlines_lookup, airlines_docs = load_airlines_reference(settings.AIRLINES_CSV)

    logger.info(f"Reading airports reference: {settings.AIRPORTS_CSV}")
    airports_lookup, airports_docs = load_airports_reference(settings.AIRPORTS_CSV)

    if not skip_mongo and db is not None:
        if airlines_docs:
            db[settings.AIRLINES_COLLECTION].insert_many(airlines_docs, ordered=False)
            logger.info(f"Inserted {len(airlines_docs)} airlines into '{settings.AIRLINES_COLLECTION}'.")
        if airports_docs:
            db[settings.AIRPORTS_COLLECTION].insert_many(airports_docs, ordered=False)
            logger.info(f"Inserted {len(airports_docs)} airports into '{settings.AIRPORTS_COLLECTION}'.")
        setup_indexes(db)

    # --- 3. Chunked Processing of flights.csv ---
    flights_csv = settings.FLIGHTS_CSV
    if not flights_csv.exists():
        logger.error(f"flights.csv not found at: {flights_csv}")
        raise FileNotFoundError(f"flights.csv not found at: {flights_csv}")

    total_stats = {
        "total_rows_read": 0,
        "valid_records_accepted": 0,
        "rejected_corrupt_records": 0,
        "exact_duplicates_removed": 0,
        "cancelled_records": 0,
        "diverted_records": 0,
        "route_eligible_records": 0,
        "route_ineligible_records": 0,
        "unresolved_airport_codes": 0,
        "cancellation_breakdown": {
            "A_carrier": 0,
            "B_weather": 0,
            "C_national_air_system": 0,
            "D_security": 0,
            "UNKNOWN": 0,
        },
    }

    seen_keys = set()
    chunk_index = 0

    dtype_map = {
        "YEAR": "Int16", "MONTH": "Int8", "DAY": "Int8", "DAY_OF_WEEK": "Int8",
        "FLIGHT_NUMBER": "Int32", "SCHEDULED_DEPARTURE": "float32",
        "DISTANCE": "float32", "DIVERTED": "Int8", "CANCELLED": "Int8",
        "DEPARTURE_DELAY": "float32", "ARRIVAL_DELAY": "float32",
        "AIR_TIME": "float32", "ELAPSED_TIME": "float32",
        "SCHEDULED_TIME": "float32", "TAXI_OUT": "float32", "TAXI_IN": "float32",
        "SCHEDULED_ARRIVAL": "float32", "DEPARTURE_TIME": "float32",
        "ARRIVAL_TIME": "float32", "WHEELS_OFF": "float32", "WHEELS_ON": "float32",
        "AIR_SYSTEM_DELAY": "float32", "SECURITY_DELAY": "float32",
        "AIRLINE_DELAY": "float32", "LATE_AIRCRAFT_DELAY": "float32", "WEATHER_DELAY": "float32",
    }

    logger.info(f"Streaming {flights_csv} in chunks of {chunk_size:,} rows...")
    chunk_reader = pd.read_csv(
        flights_csv,
        chunksize=chunk_size,
        dtype=dtype_map,
        low_memory=False,
    )

    for chunk in chunk_reader:
        chunk_index += 1
        docs, stats = clean_and_transform_chunk(
            chunk, airports_lookup, airlines_lookup, seen_keys=seen_keys
        )

        # Aggregate counters
        total_stats["total_rows_read"] += stats["read"]
        total_stats["valid_records_accepted"] += stats["valid"]
        total_stats["rejected_corrupt_records"] += stats["rejected_corrupt"]
        total_stats["exact_duplicates_removed"] += stats["exact_duplicates"]
        total_stats["cancelled_records"] += stats["cancelled"]
        total_stats["diverted_records"] += stats["diverted"]
        total_stats["route_eligible_records"] += stats["route_eligible"]
        total_stats["route_ineligible_records"] += stats["route_ineligible"]
        total_stats["unresolved_airport_codes"] += stats["unresolved_airport"]
        total_stats["cancellation_breakdown"]["A_carrier"] += stats["cancellation_reason_A"]
        total_stats["cancellation_breakdown"]["B_weather"] += stats["cancellation_reason_B"]
        total_stats["cancellation_breakdown"]["C_national_air_system"] += stats["cancellation_reason_C"]
        total_stats["cancellation_breakdown"]["D_security"] += stats["cancellation_reason_D"]
        total_stats["cancellation_breakdown"]["UNKNOWN"] += stats["cancellation_reason_UNKNOWN"]

        # Bulk insert to MongoDB
        if not skip_mongo and db is not None and docs:
            try:
                db[settings.FLIGHTS_COLLECTION].insert_many(docs, ordered=False)
            except BulkWriteError as bwe:
                # If duplicate keys occur during insert, log details without aborting
                logger.warning(f"Chunk {chunk_index} bulk write warning: {len(bwe.details.get('writeErrors', []))} duplicate keys skipped.")

        # Progress log
        if chunk_index % 5 == 0 or (limit_chunks > 0 and chunk_index == limit_chunks):
            pct_eligible = (total_stats["route_eligible_records"] / total_stats["total_rows_read"]) * 100 if total_stats["total_rows_read"] > 0 else 0
            logger.info(
                f"Chunk {chunk_index:3d} | Read: {total_stats['total_rows_read']:>9,} | "
                f"Valid: {total_stats['valid_records_accepted']:>9,} | "
                f"Cancelled: {total_stats['cancelled_records']:>7,} | "
                f"Route-Eligible: {total_stats['route_eligible_records']:>9,} ({pct_eligible:.1f}%)"
            )

        # Explicit garbage collection to strictly protect 8 GB RAM
        del chunk, docs, stats
        gc.collect()

        if 0 < limit_chunks <= chunk_index:
            logger.info(f"Reached chunk limit of {limit_chunks}. Stopping chunk reader.")
            break

    elapsed_time = time.time() - start_time

    # --- 4. Quality Report Construction ---
    data_quality_report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "execution_duration_seconds": round(elapsed_time, 2),
        "chunk_size": chunk_size,
        "chunks_processed": chunk_index,
        "summary": {
            "total_rows_read": total_stats["total_rows_read"],
            "valid_records_accepted": total_stats["valid_records_accepted"],
            "rejected_corrupt_records": total_stats["rejected_corrupt_records"],
            "exact_duplicates_removed": total_stats["exact_duplicates_removed"],
            "cancelled_records": total_stats["cancelled_records"],
            "diverted_records": total_stats["diverted_records"],
            "route_eligible_records": total_stats["route_eligible_records"],
            "route_ineligible_records": total_stats["route_ineligible_records"],
        },
        "percentages": {
            "valid_records_rate": round(total_stats["valid_records_accepted"] / max(total_stats["total_rows_read"], 1) * 100, 2),
            "cancelled_rate": round(total_stats["cancelled_records"] / max(total_stats["total_rows_read"], 1) * 100, 2),
            "route_eligible_rate": round(total_stats["route_eligible_records"] / max(total_stats["total_rows_read"], 1) * 100, 2),
            "diverted_rate": round(total_stats["diverted_records"] / max(total_stats["total_rows_read"], 1) * 100, 2),
        },
        "route_eligibility_breakdown": {
            "cancelled_flights": total_stats["cancelled_records"],
            "unresolved_airport_codes": total_stats["unresolved_airport_codes"],
            "corrupt_records": total_stats["rejected_corrupt_records"],
        },
        "cancellation_breakdown": total_stats["cancellation_breakdown"],
        "reference_catalogue": {
            "airlines_loaded": len(airlines_lookup),
            "airports_loaded": len(airports_lookup),
        },
        "pipeline_health_status": "PASSED" if total_stats["rejected_corrupt_records"] == 0 else "PASSED_WITH_WARNINGS",
    }

    # Save to disk
    save_data_quality_report(data_quality_report, report_path)

    # Console Summary
    print("\n" + "=" * 65)
    print("  AEROROUTE DATA PREPROCESSING & QC SUMMARY")
    print("=" * 65)
    print(f"  Duration                 : {elapsed_time:.1f} seconds")
    print(f"  Total Rows Read          : {total_stats['total_rows_read']:,}")
    print(f"  Valid Records Accepted   : {total_stats['valid_records_accepted']:,} ({data_quality_report['percentages']['valid_records_rate']}%)")
    print(f"  Corrupt Records Rejected : {total_stats['rejected_corrupt_records']:,}")
    print(f"  Duplicate Keys Removed   : {total_stats['exact_duplicates_removed']:,}")
    print(f"  Cancelled Flights (kept) : {total_stats['cancelled_records']:,} ({data_quality_report['percentages']['cancelled_rate']}%)")
    print(f"  Diverted Flights         : {total_stats['diverted_records']:,} ({data_quality_report['percentages']['diverted_rate']}%)")
    print(f"  Route-Eligible Records   : {total_stats['route_eligible_records']:,} ({data_quality_report['percentages']['route_eligible_rate']}%)")
    print(f"  Route-Ineligible Records : {total_stats['route_ineligible_records']:,}")
    print(f"  Unresolved Airport Codes : {total_stats['unresolved_airport_codes']:,}")
    print(f"  Pipeline Status          : {data_quality_report['pipeline_health_status']}")
    print(f"  Report Location          : {report_path.resolve()}")
    print("=" * 65 + "\n")

    return data_quality_report


def main():
    parser = argparse.ArgumentParser(description="AeroRoute Phase 3 Preprocessing & Quality Control Pipeline")
    parser.add_argument("--drop", action="store_true", default=True, help="Drop existing MongoDB collections before loading (default: True)")
    parser.add_argument("--no-drop", dest="drop", action="store_false", help="Do not drop existing collections")
    parser.add_argument("--chunk-size", type=int, default=settings.CHUNK_SIZE, help=f"Chunk size (default: {settings.CHUNK_SIZE})")
    parser.add_argument("--limit-chunks", type=int, default=0, help="Process only first N chunks (0 = process all)")
    parser.add_argument("--skip-mongo", action="store_true", default=False, help="Skip MongoDB inserts (profiling only)")
    parser.add_argument("--report-path", type=str, default="", help="Path to write data_quality_report.json")

    args = parser.parse_args()
    report_file = Path(args.report_path) if args.report_path else settings.PROCESSED_DIR / "data_quality_report.json"

    run_pipeline(
        drop_existing=args.drop,
        chunk_size=args.chunk_size,
        limit_chunks=args.limit_chunks,
        skip_mongo=args.skip_mongo,
        report_path=report_file,
    )


if __name__ == "__main__":
    main()
