# ============================================================
# AeroRoute -- Flight Operations Console Database Service
# File : dashboard/services/database.py
# ============================================================

import os
import logging
from typing import Any, Dict, Optional, Tuple
import pymongo
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

logger = logging.getLogger("aeroroute.database")

# Environment variables with sensible defaults
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "aeroroutedb")

_client_instance: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """
    Get or create a singleton MongoClient instance with short timeout.
    """
    global _client_instance
    if _client_instance is None:
        try:
            _client_instance = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                maxPoolSize=50,
            )
        except Exception as e:
            logger.error(f"Failed to create MongoClient: {e}")
            raise
    return _client_instance


def get_db(db_name: Optional[str] = None) -> Database:
    """
    Get a reference to the AeroRoute MongoDB database.
    """
    client = get_mongo_client()
    target_db = db_name or MONGO_DB_NAME
    return client[target_db]


def get_collection(name: str, db_name: Optional[str] = None) -> Collection:
    """
    Retrieve a specific collection from the AeroRoute database.
    """
    db = get_db(db_name)
    return db[name]


def check_connection() -> Tuple[bool, str]:
    """
    Verify MongoDB connectivity with an administrative ping.
    Returns:
        (is_connected: bool, message: str)
    """
    try:
        client = get_mongo_client()
        # The ping command is cheap and does not require auth
        client.admin.command("ping")
        return True, "Connected to MongoDB server"
    except pymongo.errors.ServerSelectionTimeoutError:
        return False, "Server selection timeout: MongoDB service not responding"
    except pymongo.errors.ConnectionFailure as e:
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error checking MongoDB: {str(e)}"


def get_collection_counts(region: Optional[str] = None) -> Dict[str, int]:
    """
    Safely retrieve document counts for core AeroRoute collections based on region.
    Returns empty counts if database is unreachable.
    """
    from config.settings import settings

    target_region = (region or getattr(settings, "DATASET_REGION", "INDIA")).upper()

    counts: Dict[str, int] = {}
    try:
        is_conn, _ = check_connection()
        if not is_conn:
            return {}

        db = get_db()
        existing = set(db.list_collection_names())

        # Collections for both regions
        all_cols = [
            "flights", "airports", "airlines",
            "mr_route_activity", "mr_airport_outgoing", "mr_airport_incoming",
            "mr_monthly_route", "mr_airport_connectivity", "pipeline_runs",
            "flights_in", "airports_in", "airlines_in",
            "mr_route_activity_in", "mr_airport_outgoing_in", "mr_airport_incoming_in",
            "mr_monthly_route_in", "mr_airport_connectivity_in",
        ]

        for col_name in all_cols:
            if col_name in existing:
                try:
                    counts[col_name] = db[col_name].count_documents({})
                except Exception:
                    counts[col_name] = 0
            else:
                counts[col_name] = 0

        # Provide normalized aliases based on selected region
        if target_region in ("INDIA", "IN"):
            counts["flights"] = counts.get("flights_in", 0)
            counts["airports"] = counts.get("airports_in", 0)
            counts["airlines"] = counts.get("airlines_in", 0)
            counts["mr_route_activity"] = counts.get("mr_route_activity_in", 0)
            counts["mr_airport_outgoing"] = counts.get("mr_airport_outgoing_in", 0)
            counts["mr_airport_incoming"] = counts.get("mr_airport_incoming_in", 0)
            counts["mr_monthly_route"] = counts.get("mr_monthly_route_in", 0)
            counts["mr_airport_connectivity"] = counts.get("mr_airport_connectivity_in", 0)

    except Exception as e:
        logger.warning(f"Error fetching collection counts: {e}")
        return {}

    return counts
