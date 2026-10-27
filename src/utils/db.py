# ============================================================
# AeroRoute -- MongoDB Connection & Ingestion Metadata Utility
# File : src/utils/db.py
# Usage: from src.utils.db import get_db, record_pipeline_start, record_pipeline_end
# ============================================================

import datetime
import os
import platform
from typing import Any, Dict, Optional
import pymongo
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
_client = None


def get_client() -> pymongo.MongoClient:
    """
    Acquire or reuse a singleton MongoClient instance.
    Fails fast with a 5000ms server selection timeout if MongoDB is not running.
    """
    global _client
    if _client is None:
        logger.info(f"Connecting to MongoDB at {settings.MONGO_URI}")
        _client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
        )
        # Ping server to verify connectivity early
        _client.server_info()
        logger.info("MongoDB connection established successfully.")
    return _client


def get_db() -> pymongo.database.Database:
    """
    Return the application database handle.
    """
    return get_client()[settings.MONGO_DB_NAME]


def get_collection_stats(collection_name: str) -> Dict[str, Any]:
    """
    Retrieve document count and WiredTiger storage metrics for a collection.
    """
    db = get_db()
    try:
        raw_stats = db.command("collStats", collection_name)
        return {
            "count": raw_stats.get("count", 0),
            "size_bytes": raw_stats.get("size", 0),
            "storage_size_bytes": raw_stats.get("storageSize", 0),
            "total_index_size_bytes": raw_stats.get("totalIndexSize", 0),
            "avg_obj_size_bytes": raw_stats.get("avgObjSize", 0),
            "nindexes": raw_stats.get("nindexes", 0),
        }
    except Exception as e:
        logger.warning(f"Could not fetch collStats for '{collection_name}': {e}")
        count = db[collection_name].count_documents({})
        return {
            "count": count,
            "size_bytes": 0,
            "storage_size_bytes": 0,
            "total_index_size_bytes": 0,
            "avg_obj_size_bytes": 0,
            "nindexes": 0,
        }


def record_pipeline_start(run_id: str, script_name: str, config_info: Dict[str, Any]) -> str:
    """
    Insert a preliminary run document into the pipeline_runs collection.
    """
    db = get_db()
    client = get_client()
    server_info = client.server_info()
    mongo_version = server_info.get("version", "unknown")

    doc = {
        "run_id": run_id,
        "script": script_name,
        "status": "RUNNING",
        "started_at": datetime.datetime.now(),
        "completed_at": None,
        "duration_seconds": None,
        "config": config_info,
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "pymongo_version": pymongo.__version__,
            "mongodb_version": mongo_version,
        },
        "metrics": {},
        "storage_stats": {},
    }
    db[settings.PIPELINE_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {"$set": doc},
        upsert=True,
    )
    logger.info(f"Recorded pipeline start in '{settings.PIPELINE_RUNS_COLLECTION}' (run_id: {run_id})")
    return run_id


def record_pipeline_end(
    run_id: str,
    status: str,
    metrics: Dict[str, Any],
    duration_seconds: float,
    error_message: Optional[str] = None,
) -> None:
    """
    Update the run document with final status, metrics, and storage stats.
    """
    db = get_db()
    storage_stats = {
        settings.FLIGHTS_COLLECTION: get_collection_stats(settings.FLIGHTS_COLLECTION),
        settings.AIRPORTS_COLLECTION: get_collection_stats(settings.AIRPORTS_COLLECTION),
        settings.AIRLINES_COLLECTION: get_collection_stats(settings.AIRLINES_COLLECTION),
    }

    update_payload = {
        "status": status,
        "completed_at": datetime.datetime.now(),
        "duration_seconds": round(duration_seconds, 2),
        "metrics": metrics,
        "storage_stats": storage_stats,
    }
    if error_message:
        update_payload["error_message"] = error_message

    db[settings.PIPELINE_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {"$set": update_payload},
    )
    logger.info(f"Recorded pipeline completion in '{settings.PIPELINE_RUNS_COLLECTION}' status: {status}")
