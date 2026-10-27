# ============================================================
# AeroRoute -- Indian Domestic Aviation Preprocessor & Normalizer
# File : src/ingestion/indian_preprocessor.py
# ============================================================

import datetime
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from src.ingestion.indian_reference_data import (
    INDIAN_AIRLINES_MAP,
    INDIAN_STATION_MAP,
    get_airline_by_name,
    get_airport_by_station,
)
from src.utils.logger import get_logger

logger = get_logger("indian_preprocessor")

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the Great-Circle distance in kilometers between two geographic coordinates.
    """
    R = 6371.0088  # Mean Earth radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def parse_days_of_week(raw_days: Any) -> Tuple[List[str], int, Dict[str, bool]]:
    """
    Parse operating days string (e.g. 'Thursday,Friday,Saturday' or 'Daily').
    Returns:
        (active_days_list, weekly_frequency_count, day_bool_map)
    """
    if pd.isna(raw_days) or raw_days is None:
        return ([], 0, {d.lower(): False for d in DAY_NAMES})

    text = str(raw_days).strip()
    if text.lower() == "daily":
        active = list(DAY_NAMES)
    else:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        active = [p for p in parts if p in DAY_NAMES]

    freq = len(active)
    bool_map = {d.lower(): (d in active) for d in DAY_NAMES}
    return (active, freq, bool_map)


def parse_iso_date(date_val: Any) -> Optional[datetime.date]:
    """
    Parse date value into datetime.date object. Supports YYYY-MM-DD format.
    """
    if pd.isna(date_val) or date_val is None:
        return None
    try:
        dt = pd.to_datetime(date_val)
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None


def format_time_hhmm(time_val: Any) -> Tuple[Optional[str], Optional[int]]:
    """
    Validate and normalize time string (e.g. '17:25').
    Returns:
        (formatted_hhmm_string, integer_minutes_from_midnight)
    """
    if pd.isna(time_val) or time_val is None:
        return (None, None)

    s = str(time_val).strip()
    if not s or s.lower() == "nan":
        return (None, None)

    parts = s.split(":")
    if len(parts) >= 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return (f"{h:02d}:{m:02d}", h * 60 + m)
        except ValueError:
            return (None, None)
    return (None, None)


def clean_and_transform_indian_chunk(
    chunk: pd.DataFrame,
    seen_keys: Optional[Set[str]] = None,
    dataset_mode: str = "clean",
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Transform and normalize a chunk of Indian domestic flight schedule records.
    Strictly preserves data hygiene without fabricating missing records or operational delays.

    Parameters:
        chunk: Pandas DataFrame chunk of raw records.
        seen_keys: In-memory set tracking natural keys for deduplication.
        dataset_mode: 'clean' (deduplicated Air-Clean.csv) or 'raw' (Air_full-Raw.csv revisions).

    Returns:
        (documents_list, processing_stats_dict)
    """
    stats = {
        "read": len(chunk),
        "valid": 0,
        "rejected_corrupt": 0,
        "rejected_unresolved_station": 0,
        "rejected_self_loop": 0,
        "rejected_missing_time": 0,
        "exact_duplicates": 0,
        "route_eligible": 0,
    }

    if seen_keys is None:
        seen_keys = set()

    documents: List[Dict[str, Any]] = []
    records = chunk.to_dict(orient="records")

    for row in records:
        # 1. Airline Resolution
        raw_airline = str(row.get("airline", "")).strip()
        if not raw_airline or raw_airline.lower() == "nan":
            stats["rejected_corrupt"] += 1
            continue

        airline_meta = get_airline_by_name(raw_airline)
        airline_code = airline_meta["airline_code"]
        airline_name = airline_meta["airline_name"]

        # 2. Flight Number
        raw_fn = row.get("flightNumber", "")
        if pd.isna(raw_fn) or str(raw_fn).strip() == "":
            stats["rejected_corrupt"] += 1
            continue
        flight_number = str(raw_fn).strip().upper()

        # 3. Origin & Destination Resolution
        raw_orig = str(row.get("origin", "")).strip()
        raw_dest = str(row.get("destination", "")).strip()

        if not raw_orig or not raw_dest or raw_orig.lower() == "nan" or raw_dest.lower() == "nan":
            stats["rejected_corrupt"] += 1
            continue

        if raw_orig.lower() == raw_dest.lower():
            stats["rejected_self_loop"] += 1
            continue

        orig_meta = get_airport_by_station(raw_orig)
        dest_meta = get_airport_by_station(raw_dest)

        if not orig_meta or not dest_meta:
            stats["rejected_unresolved_station"] += 1
            continue

        orig_iata = orig_meta["iata"]
        dest_iata = dest_meta["iata"]

        if orig_iata == dest_iata:
            stats["rejected_self_loop"] += 1
            continue

        # 4. Schedule Timings & Coordinates
        sched_dep_str, sched_dep_min = format_time_hhmm(row.get("scheduledDepartureTime"))
        sched_arr_str, sched_arr_min = format_time_hhmm(row.get("scheduledArrivalTime"))

        # In Air_full-Raw.csv, some revision rows lack times. Quarantine them safely.
        if sched_dep_str is None or sched_arr_str is None:
            stats["rejected_missing_time"] += 1
            continue

        # 5. Schedule Validity Window & Date Normalization
        valid_from_date = parse_iso_date(row.get("validFrom"))
        valid_to_date = parse_iso_date(row.get("validTo"))

        if valid_from_date is None or valid_to_date is None:
            stats["rejected_corrupt"] += 1
            continue

        year = valid_from_date.year
        month = valid_from_date.month
        day = valid_from_date.day

        # 6. Days of Week & Frequency
        active_days, weekly_freq, day_bools = parse_days_of_week(row.get("daysOfWeek"))

        # 7. Haversine Distance (km)
        dist_km = haversine_distance(
            orig_meta["lat"], orig_meta["lon"],
            dest_meta["lat"], dest_meta["lon"]
        )

        # 8. Deterministic Natural Key
        route_key = f"{orig_iata}->{dest_iata}"
        valid_from_str = valid_from_date.strftime("%Y-%m-%d")
        valid_to_str = valid_to_date.strftime("%Y-%m-%d")

        if dataset_mode == "clean":
            natural_key = f"IND_{airline_code}_{flight_number}_{orig_iata}_{dest_iata}_{valid_from_str}_{sched_dep_str}"
        else:
            # Include valid_to and lastUpdated to preserve valid revision histories
            last_up = str(row.get("lastUpdated", "")).strip()
            natural_key = f"IND_RAW_{airline_code}_{flight_number}_{orig_iata}_{dest_iata}_{valid_from_str}_{valid_to_str}_{sched_dep_str}_{last_up}"

        if natural_key in seen_keys:
            stats["exact_duplicates"] += 1
            continue
        seen_keys.add(natural_key)

        # 9. Document Assembly (Strict Canonical Schema)
        doc = {
            "_id": natural_key,
            "flight_id": natural_key,
            "flight_date": datetime.datetime(year, month, day),
            "year": year,
            "month": month,
            "day": day,
            "airline_code": airline_code,
            "airline_name": airline_name,
            "flight_number": flight_number,
            "flight_callsign": f"{airline_code}{flight_number}",
            "origin": {
                "iata": orig_iata,
                "icao": orig_meta["icao"],
                "name": orig_meta["name"],
                "city": orig_meta["city"],
                "state": orig_meta["state"],
                "country": orig_meta["country"],
                "lat": orig_meta["lat"],
                "lon": orig_meta["lon"],
                "elevation_ft": orig_meta.get("elevation_ft", 0),
            },
            "destination": {
                "iata": dest_iata,
                "icao": dest_meta["icao"],
                "name": dest_meta["name"],
                "city": dest_meta["city"],
                "state": dest_meta["state"],
                "country": dest_meta["country"],
                "lat": dest_meta["lat"],
                "lon": dest_meta["lon"],
                "elevation_ft": dest_meta.get("elevation_ft", 0),
            },
            "route_key": route_key,
            "distance": int(round(dist_km)),
            "distance_km": dist_km,
            "scheduled_departure": sched_dep_min,
            "scheduled_departure_formatted": sched_dep_str,
            "scheduled_arrival": sched_arr_min,
            "scheduled_arrival_formatted": sched_arr_str,
            "days_of_week": active_days,
            "operating_days_count": weekly_freq,
            "is_daily": (weekly_freq == 7),
            "valid_from": valid_from_str,
            "valid_to": valid_to_str,
            "is_route_eligible": True,
            "eligibility_reason": "ELIGIBLE_SCHEDULED_SERVICE",
            # Strict Scientific Honesty Provenance Markers
            "record_type": "SCHEDULED_SERVICE",
            "data_source": "DGCA_Airline_Timetables_2018_2025",
            "operating_status": "SCHEDULED",
            # Explicit non-fabrication nulls
            "is_cancelled": False,
            "is_diverted": False,
            "departure_delay": None,
            "arrival_delay": None,
            "delay_breakdown": None,
            "tail_number": None,
        }
        documents.append(doc)
        stats["valid"] += 1
        stats["route_eligible"] += 1

    return documents, stats


def build_indian_airports_documents() -> List[Dict[str, Any]]:
    """
    Construct MongoDB documents for unique Indian airports (107 unique IATAs covering
    all 110 raw dataset station names) with GeoJSON Point indexing.
    """
    airport_dict: Dict[str, Dict[str, Any]] = {}
    for station_name, meta in INDIAN_STATION_MAP.items():
        iata = meta["iata"]
        if iata not in airport_dict:
            airport_dict[iata] = {
                "_id": iata,
                "iata": iata,
                "icao": meta["icao"],
                "name": meta["name"],
                "city": meta["city"],
                "state": meta["state"],
                "country": meta["country"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "elevation_ft": meta["elevation_ft"],
                "tier": meta["tier"],
                "station_aliases": [station_name],
                "location": {
                    "type": "Point",
                    "coordinates": [meta["lon"], meta["lat"]],
                },
                "metrics": {
                    "scheduled_routes_out": 0,
                    "scheduled_routes_in": 0,
                    "weekly_services_out": 0,
                    "weekly_services_in": 0,
                }
            }
        else:
            if station_name not in airport_dict[iata]["station_aliases"]:
                airport_dict[iata]["station_aliases"].append(station_name)
    return list(airport_dict.values())


def build_indian_airlines_documents() -> List[Dict[str, Any]]:
    """
    Construct MongoDB documents for all 14 Indian domestic carriers.
    """
    docs = []
    for name, meta in INDIAN_AIRLINES_MAP.items():
        doc = {
            "_id": meta["airline_code"],
            "airline_code": meta["airline_code"],
            "icao": meta["icao"],
            "airline_name": meta["airline_name"],
            "callsign": meta["callsign"],
            "country": meta["country"],
            "base_hub": meta["base"],
        }
        docs.append(doc)
    return docs
