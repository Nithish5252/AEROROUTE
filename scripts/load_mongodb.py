# ============================================================
# AeroRoute -- Phase 4: Production MongoDB Loader
# File : scripts/load_mongodb.py
# Usage: python scripts/load_mongodb.py [--drop] [--limit-chunks N]
# ============================================================

import argparse
import datetime
import gc
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pymongo
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError, DuplicateKeyError

from config.settings import settings
from src.ingestion.preprocessor import (
    load_airlines_reference,
    load_airports_reference,
    clean_and_transform_chunk,
)
from src.utils.db import (
    get_client,
    get_db,
    get_collection_stats,
    record_pipeline_start,
    record_pipeline_end,
)
from src.utils.logger import get_logger

logger = get_logger("load_mongodb")


def setup_indexes_pymongo(db: pymongo.database.Database) -> None:
    """
    Ensure all required production indexes exist on MongoDB collections.
    """
    logger.info("Verifying and configuring production indexes...")

    # 1. Airlines
    db[settings.AIRLINES_COLLECTION].create_index(
        "airline_code", unique=True, name="uniq_airline_code"
    )

    # 2. Airports
    db[settings.AIRPORTS_COLLECTION].create_index(
        "iata", unique=True, name="uniq_airport_iata"
    )
    db[settings.AIRPORTS_COLLECTION].create_index(
        [("location", "2dsphere")], name="geo_airport_location"
    )

    # 3. Flights
    flights_col = db[settings.FLIGHTS_COLLECTION]
    flights_col.create_index("flight_id", unique=True, name="uniq_flight_id", background=True)
    flights_col.create_index("route_key", name="idx_route_key", background=True)
    flights_col.create_index("origin.iata", name="idx_origin_iata", background=True)
    flights_col.create_index("destination.iata", name="idx_dest_iata", background=True)
    flights_col.create_index("airline_code", name="idx_airline_code", background=True)
    flights_col.create_index("month", name="idx_month", background=True)
    flights_col.create_index("is_route_eligible", name="idx_is_route_eligible", background=True)
    flights_col.create_index("is_cancelled", name="idx_is_cancelled", background=True)
    flights_col.create_index(
        [("origin.iata", 1), ("destination.iata", 1), ("month", 1)],
        name="idx_origin_dest_month",
        background=True,
    )
    flights_col.create_index(
        [("origin.lat", 1), ("origin.lon", 1)],
        name="idx_origin_coords",
        background=True,
    )

    # 4. Pipeline Runs
    db[settings.PIPELINE_RUNS_COLLECTION].create_index(
        "run_id", unique=True, name="uniq_run_id"
    )
    db[settings.PIPELINE_RUNS_COLLECTION].create_index(
        [("started_at", -1)], name="idx_started_at_desc"
    )
    logger.info("Production indexes successfully configured.")


def bulk_insert_sub_batches(
    collection: pymongo.collection.Collection,
    docs: List[Dict[str, Any]],
    batch_size: int = 10000,
    idempotent_mode: bool = False,
) -> int:
    """
    Insert documents in sub-batches to optimize network payload and memory.
    Supports either fast insert_many(ordered=False) or idempotent upserts.
    """
    total_inserted = 0
    total_docs = len(docs)

    for i in range(0, total_docs, batch_size):
        sub_batch = docs[i : i + batch_size]
        if not sub_batch:
            continue

        if idempotent_mode:
            # Use bulk_write with UpdateOne(upsert=True)
            operations = [
                UpdateOne(
                    {"flight_id": doc["flight_id"]},
                    {"$setOnInsert": doc},
                    upsert=True,
                )
                for doc in sub_batch
            ]
            res = collection.bulk_write(operations, ordered=False)
            total_inserted += (res.upserted_count + res.modified_count)
        else:
            try:
                res = collection.insert_many(sub_batch, ordered=False)
                total_inserted += len(res.inserted_ids)
            except BulkWriteError as bwe:
                # Catch duplicate keys without crashing; tally successful writes
                n_inserted = bwe.details.get("nInserted", 0)
                total_inserted += n_inserted
                logger.warning(f"Bulk write caught {len(bwe.details.get('writeErrors', []))} duplicates. Inserted: {n_inserted}.")

    return total_inserted


def verify_ingestion_counts(db: pymongo.database.Database, expected_counts: Dict[str, int]) -> bool:
    """
    Verify document counts in MongoDB against processed metrics.
    """
    logger.info("Running post-ingestion document count verification...")
    all_ok = True

    for col_name, expected in expected_counts.items():
        actual = db[col_name].count_documents({})
        if actual == expected:
            logger.info(f"  [OK] Collection '{col_name}': {actual:,} documents (matches expected)")
        else:
            logger.error(f"  [MISMATCH] Collection '{col_name}': actual {actual:,} != expected {expected:,}")
            all_ok = False

    return all_ok


def run_loader(
    drop_existing: bool = True,
    chunk_size: int = 50000,
    batch_size: int = 10000,
    limit_chunks: int = 0,
    verify_after: bool = True,
) -> Dict[str, Any]:
    """
    Execute full MongoDB loading pipeline.
    """
    run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    start_time = time.time()

    logger.info("=======================================================")
    logger.info("  AeroRoute -- Production MongoDB Loader (Phase 4)")
    logger.info("=======================================================")
    logger.info(f"Run ID         : {run_id}")
    logger.info(f"Chunk Size     : {chunk_size:,} rows")
    logger.info(f"Batch Size     : {batch_size:,} docs/sub-batch")
    logger.info(f"Drop Existing  : {drop_existing}")
    logger.info(f"Limit Chunks   : {limit_chunks if limit_chunks > 0 else 'All'}")

    db = get_db()

    # Record pipeline run start
    config_info = {
        "drop_existing": drop_existing,
        "chunk_size": chunk_size,
        "batch_size": batch_size,
        "limit_chunks": limit_chunks,
    }
    record_pipeline_start(run_id, "scripts/load_mongodb.py", config_info)

    try:
        # Step 1: Collection reset if --drop is specified
        if drop_existing:
            logger.info("Dropping existing collections for clean idempotent baseline...")
            db[settings.FLIGHTS_COLLECTION].drop()
            db[settings.AIRPORTS_COLLECTION].drop()
            db[settings.AIRLINES_COLLECTION].drop()

        # Step 2: Setup Indexes
        setup_indexes_pymongo(db)

        # Step 3: Ingest Reference Collections
        logger.info("Loading reference collections...")
        airlines_lookup, airlines_docs = load_airlines_reference(settings.AIRLINES_CSV)
        airports_lookup, airports_docs = load_airports_reference(settings.AIRPORTS_CSV)

        if airlines_docs:
            db[settings.AIRLINES_COLLECTION].insert_many(airlines_docs, ordered=False)
            logger.info(f"Ingested {len(airlines_docs)} airlines.")

        if airports_docs:
            db[settings.AIRPORTS_COLLECTION].insert_many(airports_docs, ordered=False)
            logger.info(f"Ingested {len(airports_docs)} airports.")

        # Step 4: Stream flights.csv in chunks
        flights_csv = settings.FLIGHTS_CSV
        if not flights_csv.exists():
            raise FileNotFoundError(f"flights.csv not found at: {flights_csv}")

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

        total_rows_read = 0
        total_inserted = 0
        total_valid = 0
        total_cancelled = 0
        total_route_eligible = 0
        total_duplicates_prevented = 0
        seen_keys = set()
        chunk_index = 0

        logger.info(f"Streaming {flights_csv} in chunks of {chunk_size:,}...")
        chunk_reader = pd.read_csv(
            flights_csv,
            chunksize=chunk_size,
            dtype=dtype_map,
            low_memory=False,
        )

        flights_col = db[settings.FLIGHTS_COLLECTION]

        for chunk in chunk_reader:
            chunk_index += 1
            docs, stats = clean_and_transform_chunk(
                chunk, airports_lookup, airlines_lookup, seen_keys=seen_keys
            )

            total_rows_read += stats["read"]
            total_valid += stats["valid"]
            total_cancelled += stats["cancelled"]
            total_route_eligible += stats["route_eligible"]
            total_duplicates_prevented += stats["exact_duplicates"]

            # Perform bulk sub-batch insert
            inserted_in_chunk = bulk_insert_sub_batches(
                flights_col, docs, batch_size=batch_size, idempotent_mode=not drop_existing
            )
            total_inserted += inserted_in_chunk

            if chunk_index % 5 == 0 or (limit_chunks > 0 and chunk_index == limit_chunks):
                logger.info(
                    f"Chunk {chunk_index:3d} | Rows Read: {total_rows_read:>9,} | "
                    f"Inserted: {total_inserted:>9,} | "
                    f"Route-Eligible: {total_route_eligible:>9,} | "
                    f"Cancelled: {total_cancelled:>7,}"
                )

            # Strict memory protection for 8 GB RAM laptop
            del chunk, docs, stats
            gc.collect()

            if 0 < limit_chunks <= chunk_index:
                logger.info(f"Reached chunk limit of {limit_chunks}. Stopping loader.")
                break

        elapsed_time = time.time() - start_time

        # Step 5: Post-Ingestion Count Verification
        if verify_after:
            expected_counts = {
                settings.AIRLINES_COLLECTION: len(airlines_docs),
                settings.AIRPORTS_COLLECTION: len(airports_docs),
                settings.FLIGHTS_COLLECTION: total_valid,
            }
            verify_ok = verify_ingestion_counts(db, expected_counts)
        else:
            verify_ok = True

        # Step 6: Record Pipeline Completion Metadata
        metrics = {
            "total_rows_read": total_rows_read,
            "total_inserted": total_inserted,
            "valid_records": total_valid,
            "route_eligible_records": total_route_eligible,
            "cancelled_records": total_cancelled,
            "duplicates_prevented": total_duplicates_prevented,
            "chunks_processed": chunk_index,
            "verification_passed": verify_ok,
        }
        status_str = "SUCCESS" if verify_ok else "COMPLETED_WITH_WARNINGS"
        record_pipeline_end(run_id, status_str, metrics, elapsed_time)

        # Print Final Summary
        flight_storage = get_collection_stats(settings.FLIGHTS_COLLECTION)
        storage_mb = flight_storage["storage_size_bytes"] / (1024 * 1024)
        index_mb = flight_storage["total_index_size_bytes"] / (1024 * 1024)

        print("\n" + "=" * 65)
        print("  AEROROUTE MONGODB INGESTION SUMMARY (PHASE 4)")
        print("=" * 65)
        print(f"  Run ID                   : {run_id}")
        print(f"  Duration                 : {elapsed_time:.1f} seconds")
        print(f"  Total Rows Read          : {total_rows_read:,}")
        print(f"  Total Ingested to Mongo  : {total_inserted:,}")
        print(f"  Route-Eligible Records   : {total_route_eligible:,}")
        print(f"  Cancelled Flights (kept) : {total_cancelled:,}")
        print(f"  Duplicates Prevented     : {total_duplicates_prevented:,}")
        print(f"  Flights Disk Storage     : {storage_mb:.2f} MB (WiredTiger Snappy)")
        print(f"  Flights Total Index Size : {index_mb:.2f} MB")
        print(f"  Pipeline Run Metadata    : Recorded in '{settings.PIPELINE_RUNS_COLLECTION}'")
        print(f"  Verification Status      : {'PASSED' if verify_ok else 'FAILED'}")
        print("=" * 65 + "\n")

        return metrics

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        record_pipeline_end(run_id, "FAILED", {}, elapsed_time, error_message=str(e))
        raise


def main():
    parser = argparse.ArgumentParser(description="AeroRoute Production MongoDB Ingestion Loader")
    parser.add_argument("--drop", action="store_true", default=True, help="Drop existing collections before loading (default: True)")
    parser.add_argument("--no-drop", dest="drop", action="store_false", help="Do not drop existing collections (idempotent upsert mode)")
    parser.add_argument("--chunk-size", type=int, default=settings.CHUNK_SIZE, help=f"CSV chunk size (default: {settings.CHUNK_SIZE})")
    parser.add_argument("--batch-size", type=int, default=settings.BATCH_SIZE, help=f"Bulk write sub-batch size (default: {settings.BATCH_SIZE})")
    parser.add_argument("--limit-chunks", type=int, default=0, help="Process only first N chunks (0 = process all)")
    parser.add_argument("--no-verify", dest="verify", action="store_false", default=True, help="Skip post-ingestion count verification")

    args = parser.parse_args()

    run_loader(
        drop_existing=args.drop,
        chunk_size=args.chunk_size,
        batch_size=args.batch_size,
        limit_chunks=args.limit_chunks,
        verify_after=args.verify,
    )


if __name__ == "__main__":
    main()
