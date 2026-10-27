# ============================================================
# AeroRoute -- Airport Intelligence Analytics
# File : analytics/airport_analysis.py
# Usage: python -m analytics.airport_analysis
#        python analytics/airport_analysis.py
# ============================================================

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pymongo

from analytics.utils import safe_export_json, extract_numeric_value
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("airport_analysis")


def _get_airports_metadata_map(
    db: pymongo.database.Database,
    region: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """Retrieve airport metadata lookup dictionary from the active regional collection."""
    coll_name = settings.get_airports_collection(region)
    airports_cursor = db[coll_name].find(
        {},
        {"iata": 1, "name": 1, "city": 1, "state": 1, "country": 1, "lat": 1, "lon": 1, "tier": 1}
    )
    meta_map = {}
    is_india = coll_name == settings.INDIAN_AIRPORTS_COLLECTION
    default_country = "India" if is_india else "USA"

    for ap in airports_cursor:
        iata = ap.get("iata") or ap.get("_id")
        if iata:
            meta_map[iata] = {
                "name": ap.get("name", "Unknown Airport"),
                "city": ap.get("city", "Unknown City"),
                "state": ap.get("state", "NA"),
                "country": ap.get("country", default_country),
                "lat": ap.get("lat"),
                "lon": ap.get("lon"),
                "tier": ap.get("tier", "Standard"),
            }
    return meta_map


def get_airports_ranked_by_outgoing(
    db: pymongo.database.Database,
    limit: int = 20,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Rank airports by total outgoing flight capacity / operations.
    Sourced from MapReduce 'mr_airport_outgoing' (US) or 'mr_airport_outgoing_in' (India).
    """
    meta_map = _get_airports_metadata_map(db, region=region)
    coll_name = settings.get_mr_airport_outgoing_collection(region)
    cursor = db[coll_name].find()

    records = []
    for doc in cursor:
        iata = doc["_id"]
        meta = meta_map.get(iata, {})
        val = doc["value"]
        out_freq = extract_numeric_value(val, "outgoing_weekly_frequency")
        out_sched = int(val.get("outgoing_timetable_services", out_freq)) if isinstance(val, dict) else int(out_freq)
        dest_count = int(val.get("out_degree_destinations", len(val.get("destinations", [])))) if isinstance(val, dict) else 0

        records.append({
            "iata": iata,
            "name": meta.get("name", "Unknown"),
            "city": meta.get("city", "Unknown"),
            "state": meta.get("state", "NA"),
            "country": meta.get("country", "Unknown"),
            "outgoing_flights": int(out_freq),
            "weekly_frequency": int(out_freq),
            "timetable_services": out_sched,
            "out_degree_destinations": dest_count,
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(by="outgoing_flights", ascending=False).reset_index(drop=True)
        if limit > 0:
            df = df.head(limit)

    logger.info(f"Retrieved top {len(df)} airports by outgoing capacity from '{coll_name}'.")
    return df


def get_airports_ranked_by_incoming(
    db: pymongo.database.Database,
    limit: int = 20,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Rank airports by total incoming flight capacity / operations.
    Sourced from MapReduce 'mr_airport_incoming' (US) or 'mr_airport_incoming_in' (India).
    """
    meta_map = _get_airports_metadata_map(db, region=region)
    coll_name = settings.get_mr_airport_incoming_collection(region)
    cursor = db[coll_name].find()

    records = []
    for doc in cursor:
        iata = doc["_id"]
        meta = meta_map.get(iata, {})
        val = doc["value"]
        in_freq = extract_numeric_value(val, "incoming_weekly_frequency")
        in_sched = int(val.get("incoming_timetable_services", in_freq)) if isinstance(val, dict) else int(in_freq)
        orig_count = int(val.get("in_degree_origins", len(val.get("origins", [])))) if isinstance(val, dict) else 0

        records.append({
            "iata": iata,
            "name": meta.get("name", "Unknown"),
            "city": meta.get("city", "Unknown"),
            "state": meta.get("state", "NA"),
            "country": meta.get("country", "Unknown"),
            "incoming_flights": int(in_freq),
            "weekly_frequency": int(in_freq),
            "timetable_services": in_sched,
            "in_degree_origins": orig_count,
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(by="incoming_flights", ascending=False).reset_index(drop=True)
        if limit > 0:
            df = df.head(limit)

    logger.info(f"Retrieved top {len(df)} airports by incoming capacity from '{coll_name}'.")
    return df


def get_total_observed_airport_activity(
    db: pymongo.database.Database,
    limit: int = 20,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Rank airports by total combined movement volume (Incoming + Outgoing).
    Sourced from 'mr_airport_connectivity' (US) or 'mr_airport_connectivity_in' (India).
    """
    meta_map = _get_airports_metadata_map(db, region=region)
    coll_name = settings.get_mr_airport_connectivity_collection(region)
    cursor = db[coll_name].find()

    records = []
    for doc in cursor:
        iata = doc["_id"]
        val = doc["value"]
        meta = meta_map.get(iata, {})

        out_f = int(extract_numeric_value(val.get("outgoing_weekly_frequency", val.get("outgoing_flights", 0))))
        in_f = int(extract_numeric_value(val.get("incoming_weekly_frequency", val.get("incoming_flights", 0))))
        tot_f = int(extract_numeric_value(val.get("total_weekly_frequency", val.get("total_flights", out_f + in_f))))
        tot_sched = int(val.get("total_schedules", tot_f))

        ratio = round(out_f / in_f, 3) if in_f > 0 else 1.0

        records.append({
            "iata": iata,
            "name": meta.get("name", "Unknown"),
            "city": meta.get("city", "Unknown"),
            "state": meta.get("state", "NA"),
            "country": meta.get("country", "Unknown"),
            "total_flights": tot_f,
            "weekly_movements": tot_f,
            "total_schedules": tot_sched,
            "outgoing_flights": out_f,
            "incoming_flights": in_f,
            "out_in_ratio": ratio,
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(by="total_flights", ascending=False).reset_index(drop=True)
        if limit > 0:
            df = df.head(limit)

    logger.info(f"Retrieved top {len(df)} airports by total activity from '{coll_name}'.")
    return df


def get_airport_connectivity_rankings(
    db: pymongo.database.Database,
    limit: int = 20,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Rank airports by network connectivity metrics:
      - Distinct neighbors (undirected degree)
      - Out-degree (destinations)
      - In-degree (origins)
      - Total movement strength
      - Average movements per unique connection
    """
    meta_map = _get_airports_metadata_map(db, region=region)
    coll_name = settings.get_mr_airport_connectivity_collection(region)
    cursor = db[coll_name].find()

    records = []
    for doc in cursor:
        iata = doc["_id"]
        val = doc["value"]
        meta = meta_map.get(iata, {})

        distinct_conn = int(val.get("distinct_connections", 0))
        out_deg = int(val.get("out_degree", 0))
        in_deg = int(val.get("in_degree", 0))
        tot_f = int(extract_numeric_value(val.get("total_weekly_frequency", val.get("total_flights", 0))))
        avg_per_conn = round(tot_f / distinct_conn, 1) if distinct_conn > 0 else 0.0

        records.append({
            "iata": iata,
            "name": meta.get("name", "Unknown"),
            "city": meta.get("city", "Unknown"),
            "state": meta.get("state", "NA"),
            "country": meta.get("country", "Unknown"),
            "distinct_neighbors_degree": distinct_conn,
            "distinct_destinations_out": out_deg,
            "distinct_origins_in": in_deg,
            "total_flight_volume_strength": tot_f,
            "avg_flights_per_connection": avg_per_conn,
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(by="distinct_neighbors_degree", ascending=False).reset_index(drop=True)
        if limit > 0:
            df = df.head(limit)

    logger.info(f"Retrieved top {len(df)} airports by topological connectivity from '{coll_name}'.")
    return df


def get_airport_profile(
    db: pymongo.database.Database,
    airport_code: str,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve comprehensive analytical profile for a single airport hub.
    """
    code = airport_code.strip().upper()
    meta_map = _get_airports_metadata_map(db, region=region)
    meta = meta_map.get(code, {})

    conn_coll = settings.get_mr_airport_connectivity_collection(region)
    route_coll = settings.get_mr_route_activity_collection(region)

    conn_doc = db[conn_coll].find_one({"_id": code})
    val = conn_doc.get("value", {}) if conn_doc else {}

    # Query top outbound routes departing this airport
    top_dest_cursor = db[route_coll].find({
        "_id": {"$regex": f"^{code}->"}
    }).limit(5)

    top_destinations = []
    for doc in top_dest_cursor:
        r_key = doc["_id"]
        dest = r_key.split("->")[1] if "->" in r_key else "UNKNOWN"
        freq = int(extract_numeric_value(doc["value"], "weekly_frequency"))
        top_destinations.append({
            "route": r_key,
            "destination": dest,
            "flights": freq,
            "weekly_frequency": freq,
        })
    top_destinations = sorted(top_destinations, key=lambda x: x["flights"], reverse=True)

    out_f = int(extract_numeric_value(val.get("outgoing_weekly_frequency", val.get("outgoing_flights", 0))))
    in_f = int(extract_numeric_value(val.get("incoming_weekly_frequency", val.get("incoming_flights", 0))))
    tot_f = int(extract_numeric_value(val.get("total_weekly_frequency", val.get("total_flights", out_f + in_f))))

    return {
        "iata": code,
        "name": meta.get("name", "Unknown Airport"),
        "city": meta.get("city", "Unknown City"),
        "state": meta.get("state", "NA"),
        "country": meta.get("country", "Unknown"),
        "coordinates": {"lat": meta.get("lat"), "lon": meta.get("lon")},
        "total_flights": tot_f,
        "weekly_movements": tot_f,
        "outgoing_flights": out_f,
        "incoming_flights": in_f,
        "distinct_neighbors_degree": int(val.get("distinct_connections", 0)),
        "distinct_destinations_out": int(val.get("out_degree", 0)),
        "distinct_origins_in": int(val.get("in_degree", 0)),
        "neighbor_airports": val.get("neighbor_airports", []),
        "top_outbound_routes": top_destinations,
    }


def run_full_airport_analysis(
    db: pymongo.database.Database,
    export: bool = True,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute complete Airport Intelligence analysis suite and export to disk.
    """
    r_label = (region or settings.DATASET_REGION).upper()
    logger.info(f"Executing comprehensive Airport Intelligence analysis for region: {r_label}...")
    sample_code = "DEL" if r_label in ("INDIA", "IN") else "ATL"

    top_outgoing = get_airports_ranked_by_outgoing(db, limit=20, region=region)
    top_incoming = get_airports_ranked_by_incoming(db, limit=20, region=region)
    top_activity = get_total_observed_airport_activity(db, limit=20, region=region)
    top_connectivity = get_airport_connectivity_rankings(db, limit=20, region=region)
    sample_hub = get_airport_profile(db, airport_code=sample_code, region=region)

    results = {
        "region": r_label,
        "top_outgoing_airports": top_outgoing.to_dict(orient="records"),
        "top_incoming_airports": top_incoming.to_dict(orient="records"),
        "top_activity_airports": top_activity.to_dict(orient="records"),
        "top_connectivity_airports": top_connectivity.to_dict(orient="records"),
        "sample_hub_profile": sample_hub,
    }

    if export:
        suffix = "_in" if r_label in ("INDIA", "IN") else ""
        export_path = settings.EXPORTS_DIR / f"airport_intelligence{suffix}.json"
        safe_export_json(results, export_path)

    return results


if __name__ == "__main__":
    db = get_db()
    for reg in ["INDIA", "US"]:
        res = run_full_airport_analysis(db, export=True, region=reg)
        print(f"\n=== AIRPORT INTELLIGENCE REGION: {reg} ===")
        print(f"Top Connected Hubs:")
        for a in res["top_connectivity_airports"][:3]:
            print(f"  {a['iata']:<5} ({a['city']}): {a['distinct_neighbors_degree']} neighbors | {a['total_flight_volume_strength']:,} volume")
