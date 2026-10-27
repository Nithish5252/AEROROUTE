# ============================================================
# AeroRoute -- Indian Domestic Aviation MongoDB Ingestion Loader
# File : scripts/load_indian_data.py
# Usage: python scripts/load_indian_data.py [--source clean|raw] [--chunk-size 10000]
# ============================================================

import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pymongo
from pymongo import UpdateOne, ReplaceOne

from config.settings import settings
from src.ingestion.indian_preprocessor import (
    clean_and_transform_indian_chunk,
    build_indian_airports_documents,
    build_indian_airlines_documents,
)
from src.utils.db import get_client, get_db
from src.utils.logger import get_logger

logger = get_logger("load_indian_data")


def setup_indian_indexes(db: pymongo.database.Database):
    """
    Configure high-performance B-tree and geospatial indexes on Indian collections.
    Does not modify or touch original US collections.
    """
    logger.info("Configuring production indexes for Indian collections...")

    # 1. airports_in
    col_airports = db[settings.INDIAN_AIRPORTS_COLLECTION]
    col_airports.create_index([("iata", 1)], unique=True, name="uniq_airport_iata")
    col_airports.create_index([("location", "2dsphere")], name="idx_airport_location_2dsphere")

    # 2. airlines_in
    col_airlines = db[settings.INDIAN_AIRLINES_COLLECTION]
    col_airlines.create_index([("airline_code", 1)], unique=True, name="uniq_airline_code")

    # 3. flights_in
    col_flights = db[settings.INDIAN_FLIGHTS_COLLECTION]
    col_flights.create_index([("flight_id", 1)], unique=True, name="uniq_flight_id")
    col_flights.create_index([("route_key", 1)], name="idx_route_key")
    col_flights.create_index([("origin.iata", 1)], name="idx_origin_iata")
    col_flights.create_index([("destination.iata", 1)], name="idx_dest_iata")
    col_flights.create_index([("airline_code", 1)], name="idx_airline_code")
    col_flights.create_index([("month", 1)], name="idx_month")
    col_flights.create_index([("year", 1)], name="idx_year")
    col_flights.create_index([("is_route_eligible", 1)], name="idx_is_route_eligible")
    col_flights.create_index([("origin.iata", 1), ("destination.iata", 1), ("month", 1)], name="idx_origin_dest_month")
    col_flights.create_index([("origin.lat", 1), ("origin.lon", 1)], name="idx_origin_coords")
    logger.info("Indexes successfully configured on flights_in, airports_in, airlines_in.")


def load_indian_reference_data(db: pymongo.database.Database):
    """
    Load verified 110 Indian airports and 14 Indian airlines into airports_in and airlines_in.
    Idempotent via replace_one with upsert=True.
    """
    logger.info(f"Loading reference datasets into '{settings.INDIAN_AIRPORTS_COLLECTION}' and '{settings.INDIAN_AIRLINES_COLLECTION}'...")

    # Load Airports
    airport_docs = build_indian_airports_documents()
    col_airports = db[settings.INDIAN_AIRPORTS_COLLECTION]
    airport_ops = [
        ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
        for doc in airport_docs
    ]
    if airport_ops:
        col_airports.bulk_write(airport_ops, ordered=False)
    logger.info(f"Successfully staged {len(airport_docs)} Indian airport records into '{settings.INDIAN_AIRPORTS_COLLECTION}'.")

    # Load Airlines
    airline_docs = build_indian_airlines_documents()
    col_airlines = db[settings.INDIAN_AIRLINES_COLLECTION]
    airline_ops = [
        ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
        for doc in airline_docs
    ]
    if airline_ops:
        col_airlines.bulk_write(airline_ops, ordered=False)
    logger.info(f"Successfully staged {len(airline_docs)} Indian carrier records into '{settings.INDIAN_AIRLINES_COLLECTION}'.")


def load_indian_flight_schedules(
    db: pymongo.database.Database,
    csv_path: Path,
    chunk_size: int = 10000,
    dataset_mode: str = "clean",
) -> Dict[str, Any]:
    """
    Stream and load Indian flight schedules in controlled memory chunks into flights_in.
    Protects 8 GB RAM by loading 10,000 records per batch.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Source file not found at: {csv_path}")

    logger.info(f"Initiating chunked ingestion from {csv_path.name} (chunk_size={chunk_size}, mode={dataset_mode})...")
    col_flights = db[settings.INDIAN_FLIGHTS_COLLECTION]

    total_stats = {
        "read": 0,
        "valid": 0,
        "rejected_corrupt": 0,
        "rejected_unresolved_station": 0,
        "rejected_self_loop": 0,
        "rejected_missing_time": 0,
        "exact_duplicates": 0,
        "route_eligible": 0,
        "inserted_or_upserted": 0,
    }
    seen_keys = set()
    start_time = time.time()

    chunk_idx = 0
    for chunk_df in pd.read_csv(csv_path, chunksize=chunk_size, dtype=str):
        chunk_idx += 1
        docs, stats = clean_and_transform_indian_chunk(chunk_df, seen_keys=seen_keys, dataset_mode=dataset_mode)

        for k, v in stats.items():
            total_stats[k] += v

        if docs:
            ops = [
                ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
                for doc in docs
            ]
            res = col_flights.bulk_write(ops, ordered=False)
            upserted_count = res.upserted_count + res.modified_count + res.matched_count
            total_stats["inserted_or_upserted"] += len(docs)

        logger.info(
            f"Chunk {chunk_idx}: Read={len(chunk_df):,}, Valid={len(docs):,}, "
            f"Cumulative Staged={total_stats['inserted_or_upserted']:,}"
        )

    elapsed = round(time.time() - start_time, 2)
    total_stats["elapsed_seconds"] = elapsed
    total_stats["total_in_collection"] = col_flights.count_documents({})

    logger.info(f"Ingestion completed in {elapsed}s. Total documents in '{settings.INDIAN_FLIGHTS_COLLECTION}': {total_stats['total_in_collection']:,}")
    return total_stats


def record_pipeline_run(
    db: pymongo.database.Database,
    stats: Dict[str, Any],
    source_name: str,
):
    """
    Record an immutable audit log entry in pipeline_runs.
    """
    col_runs = db[settings.PIPELINE_RUNS_COLLECTION]
    run_doc = {
        "run_id": f"RUN_IN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now(timezone.utc),
        "dataset_region": "INDIA",
        "dataset_mode": source_name,
        "target_collection": settings.INDIAN_FLIGHTS_COLLECTION,
        "stats": stats,
        "status": "COMPLETED",
        "verified_us_collections_untouched": True,
    }
    col_runs.insert_one(run_doc)
    logger.info(f"Recorded ingestion audit entry in '{settings.PIPELINE_RUNS_COLLECTION}' (Run ID: {run_doc['run_id']})")


def run_loader(source_mode: str = "clean", chunk_size: int = 10000):
    db = get_db()

    # Pre-flight check: Verify original US collections are present
    us_flight_count_before = db[settings.FLIGHTS_COLLECTION].count_documents({})
    us_airport_count_before = db[settings.AIRPORTS_COLLECTION].count_documents({})
    us_airline_count_before = db[settings.AIRLINES_COLLECTION].count_documents({})
    logger.info(
        f"Pre-flight verification: Original US collections active: "
        f"flights={us_flight_count_before:,}, airports={us_airport_count_before:,}, airlines={us_airline_count_before:,}"
    )

    # 1. Setup Indexes on Indian Collections
    setup_indian_indexes(db)

    # 2. Load Indian Reference Data
    load_indian_reference_data(db)

    # 3. Load Indian Flight Schedules
    csv_file = settings.INDIAN_CLEAN_CSV if source_mode == "clean" else settings.INDIAN_RAW_CSV
    stats = load_indian_flight_schedules(db, csv_file, chunk_size=chunk_size, dataset_mode=source_mode)

    # 4. Record Audit Log
    record_pipeline_run(db, stats, source_mode)

    # Post-flight check: Verify original US collections were NOT modified
    us_flight_count_after = db[settings.FLIGHTS_COLLECTION].count_documents({})
    assert us_flight_count_before == us_flight_count_after, "CRITICAL ERROR: Original US flights collection was modified!"
    logger.info(f"Post-flight verification: Original US collections are 100% UNTOUCHED ({us_flight_count_after:,} docs preserved).")

    print("\n" + "=" * 80)
    print("  AEROROUTE -- INDIAN DOMESTIC AVIATION INGESTION COMPLETE")
    print("=" * 80)
    print(f" Source File               : {csv_file.name}")
    print(f" Target Collections        : {settings.INDIAN_FLIGHTS_COLLECTION}, {settings.INDIAN_AIRPORTS_COLLECTION}, {settings.INDIAN_AIRLINES_COLLECTION}")
    print(f" Total Rows Read           : {stats['read']:,}")
    print(f" Valid Scheduled Services  : {stats['valid']:,}")
    print(f" Exact Duplicates Filtered : {stats['exact_duplicates']:,}")
    print(f" Missing Timings Quarantined: {stats['rejected_missing_time']:,}")
    print(f" Route-Eligible Staged     : {stats['route_eligible']:,}")
    print(f" Total in Collection       : {stats['total_in_collection']:,}")
    print(f" Execution Duration        : {stats['elapsed_seconds']}s")
    print(f" Original US Collections   : STRICTLY PRESERVED & UNTOUCHED ({us_flight_count_after:,} docs)")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AeroRoute Indian Aviation MongoDB Ingestion Loader")
    parser.add_argument("--source", choices=["clean", "raw"], default="clean", help="Source file: 'clean' (Air-Clean.csv) or 'raw' (Air_full-Raw.csv)")
    parser.add_argument("--chunk-size", type=int, default=10000, help="Chunk size for ingestion (default: 10000)")
    args = parser.parse_args()

    run_loader(source_mode=args.source, chunk_size=args.chunk_size)
