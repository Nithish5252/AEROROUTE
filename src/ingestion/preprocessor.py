# ============================================================
# AeroRoute -- Data Cleaning, Quality Control & Normalization
# File : src/ingestion/preprocessor.py
# ============================================================

import datetime
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Valid cancellation reasons per US DOT Bureau of Transportation Statistics
CANCELLATION_REASONS = {
    "A": "Carrier / Airline",
    "B": "Weather",
    "C": "National Air System",
    "D": "Security",
}

# Verified FAA/BTS geographic coordinates for 3 airports with missing values in airports.csv
AIRPORT_COORD_FALLBACK = {
    "ECP": (30.3582, -85.7956),  # Northwest Florida Beaches International Airport
    "PBG": (44.6509, -73.4681),  # Plattsburgh International Airport
    "UST": (29.9592, -81.3397),  # Northeast Florida Regional Airport
}


def format_hhmm(val: Any) -> Optional[str]:
    """
    Convert raw HHMM integer/float to HH:MM string.
    Examples:
        800.0   -> '08:00'
        1430    -> '14:30'
        45      -> '00:45'
        2400.0  -> '00:00'
        NaN     -> None
    """
    if val is None or pd.isna(val):
        return None
    try:
        val_int = int(round(float(val)))
        if val_int < 0 or val_int > 2400:
            return None
        if val_int == 2400:
            return "00:00"
        hours = val_int // 100
        minutes = val_int % 100
        if hours > 23 or minutes > 59:
            return None
        return f"{hours:02d}:{minutes:02d}"
    except (ValueError, TypeError, OverflowError):
        return None


def parse_flight_date(year: Any, month: Any, day: Any) -> Optional[datetime.date]:
    """
    Safely construct datetime.date object. Returns None if invalid.
    """
    try:
        y = int(year)
        m = int(month)
        d = int(day)
        return datetime.date(y, m, d)
    except (ValueError, TypeError):
        return None


def load_airlines_reference(path) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """
    Load airlines.csv lookup table.
    Returns:
        (lookup_dict, mongo_documents)
    """
    df = pd.read_csv(path, dtype=str)
    lookup: Dict[str, str] = {}
    docs: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        iata = str(row.get("IATA_CODE", "")).strip().upper()
        airline_name = str(row.get("AIRLINE", "")).strip()
        if iata:
            lookup[iata] = airline_name
            docs.append({
                "_id": iata,
                "airline_code": iata,
                "airline_name": airline_name,
            })
    logger.info(f"Loaded {len(lookup)} airlines from {path}")
    return lookup, docs


def load_airports_reference(path) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Load airports.csv lookup table with FAA coordinate fallback.
    Returns:
        (lookup_dict, mongo_documents)
    """
    df = pd.read_csv(path, dtype={"IATA_CODE": str, "AIRPORT": str, "CITY": str, "STATE": str, "COUNTRY": str})
    lookup: Dict[str, Dict[str, Any]] = {}
    docs: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        iata = str(row.get("IATA_CODE", "")).strip().upper()
        if not iata:
            continue

        lat_val = pd.to_numeric(row.get("LATITUDE"), errors="coerce")
        lon_val = pd.to_numeric(row.get("LONGITUDE"), errors="coerce")

        lat = float(lat_val) if pd.notna(lat_val) else None
        lon = float(lon_val) if pd.notna(lon_val) else None

        # Apply fallback if coordinates are missing in raw CSV
        if (lat is None or lon is None) and iata in AIRPORT_COORD_FALLBACK:
            lat, lon = AIRPORT_COORD_FALLBACK[iata]
            logger.info(f"Enriched missing coordinates for airport {iata} using FAA fallback: ({lat}, {lon})")

        airport_name = str(row.get("AIRPORT", "")).strip()
        city = str(row.get("CITY", "")).strip()
        state = str(row.get("STATE", "")).strip()
        country = str(row.get("COUNTRY", "")).strip()

        meta = {
            "iata": iata,
            "name": airport_name,
            "city": city,
            "state": state,
            "country": country,
            "lat": lat,
            "lon": lon,
        }
        lookup[iata] = meta

        doc = {
            "_id": iata,
            "iata": iata,
            "name": airport_name,
            "city": city,
            "state": state,
            "country": country,
            "lat": lat,
            "lon": lon,
            "metrics": {
                "total_departures": 0,
                "total_arrivals": 0,
                "out_degree": 0,
                "in_degree": 0,
                "avg_departure_delay": 0.0,
                "avg_arrival_delay": 0.0,
                "cluster_id": None,
            }
        }
        if lat is not None and lon is not None:
            doc["location"] = {
                "type": "Point",
                "coordinates": [lon, lat],
            }
        docs.append(doc)

    logger.info(f"Loaded {len(lookup)} airports from {path}")
    return lookup, docs


def clean_and_transform_chunk(
    chunk: pd.DataFrame,
    airports_ref: Dict[str, Dict[str, Any]],
    airlines_ref: Dict[str, str],
    seen_keys: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Clean, validate, classify, and normalize a chunk of flight records.

    Rules applied:
    1. Schema validation (valid date, valid carrier, distance > 0, origin != dest).
    2. Date parsing into datetime.date / ISO format.
    3. HHMM integer time parsing into normalized 'HH:MM' string and numeric HHMM.
    4. Airport code resolution against airports.csv.
    5. Duplicate detection using natural flight key.
    6. Cohort categorization:
       - is_valid_record (meets basic data integrity)
       - is_cancelled (cancelled == 1)
       - is_diverted (diverted == 1)
       - is_route_eligible (valid AND not cancelled AND both airports resolved in airports.csv with coordinates AND origin != dest)
    7. Delay breakdown structuring (0.0 for on-time completed flights, null for cancelled/diverted).
    """
    stats = {
        "read": len(chunk),
        "valid": 0,
        "rejected_corrupt": 0,
        "exact_duplicates": 0,
        "cancelled": 0,
        "diverted": 0,
        "route_eligible": 0,
        "route_ineligible": 0,
        "unresolved_airport": 0,
        "cancellation_reason_A": 0,
        "cancellation_reason_B": 0,
        "cancellation_reason_C": 0,
        "cancellation_reason_D": 0,
        "cancellation_reason_UNKNOWN": 0,
    }

    if seen_keys is None:
        seen_keys = set()

    documents: List[Dict[str, Any]] = []

    records = chunk.to_dict(orient="records")

    for row in records:
        # --- 1. Date Validation ---
        raw_year = row.get("YEAR")
        raw_month = row.get("MONTH")
        raw_day = row.get("DAY")
        flight_date = parse_flight_date(raw_year, raw_month, raw_day)

        if flight_date is None:
            stats["rejected_corrupt"] += 1
            continue

        year = flight_date.year
        month = flight_date.month
        day = flight_date.day
        day_of_week = int(row.get("DAY_OF_WEEK")) if pd.notna(row.get("DAY_OF_WEEK")) else flight_date.isoweekday()

        # --- 2. Airline Validation ---
        airline_code = str(row.get("AIRLINE", "")).strip().upper()
        if not airline_code or airline_code == "NAN":
            stats["rejected_corrupt"] += 1
            continue
        airline_name = airlines_ref.get(airline_code, "Unknown Airline")

        # --- 3. Flight Number ---
        fn_val = row.get("FLIGHT_NUMBER")
        flight_number = int(fn_val) if pd.notna(fn_val) else 0

        # --- 4. Tail Number ---
        raw_tail = row.get("TAIL_NUMBER")
        tail_number = str(raw_tail).strip().upper() if pd.notna(raw_tail) and str(raw_tail).strip() != "" and str(raw_tail) != "nan" else None

        # --- 5. Airport Codes Validation ---
        orig_val = row.get("ORIGIN_AIRPORT")
        dest_val = row.get("DESTINATION_AIRPORT")
        if pd.isna(orig_val) or pd.isna(dest_val) or orig_val is None or dest_val is None:
            stats["rejected_corrupt"] += 1
            continue

        raw_origin = str(orig_val).strip().upper()
        raw_dest = str(dest_val).strip().upper()

        if not raw_origin or raw_origin in ("NAN", "NONE", "NULL") or not raw_dest or raw_dest in ("NAN", "NONE", "NULL"):
            stats["rejected_corrupt"] += 1
            continue

        if raw_origin == raw_dest:
            stats["rejected_corrupt"] += 1
            continue

        origin_meta = airports_ref.get(raw_origin)
        dest_meta = airports_ref.get(raw_dest)

        airports_resolved = (origin_meta is not None) and (dest_meta is not None)
        is_numeric_airport = raw_origin.isnumeric() or raw_dest.isnumeric()

        if not airports_resolved:
            stats["unresolved_airport"] += 1

        origin_dict = origin_meta if origin_meta else {
            "iata": raw_origin,
            "name": None,
            "city": None,
            "state": None,
            "country": None,
            "lat": None,
            "lon": None,
        }
        dest_dict = dest_meta if dest_meta else {
            "iata": raw_dest,
            "name": None,
            "city": None,
            "state": None,
            "country": None,
            "lat": None,
            "lon": None,
        }

        # Check coordinates presence
        has_coordinates = (origin_dict.get("lat") is not None) and (dest_dict.get("lat") is not None)

        # --- 6. Distance Validation ---
        dist_val = pd.to_numeric(row.get("DISTANCE"), errors="coerce")
        if pd.isna(dist_val) or dist_val <= 0:
            stats["rejected_corrupt"] += 1
            continue
        distance = int(round(dist_val))

        # --- 7. Cancellation and Diversion Handling ---
        can_val = pd.to_numeric(row.get("CANCELLED"), errors="coerce")
        cancelled = int(can_val) if pd.notna(can_val) and can_val == 1 else 0
        is_cancelled = (cancelled == 1)

        div_val = pd.to_numeric(row.get("DIVERTED"), errors="coerce")
        diverted = int(div_val) if pd.notna(div_val) and div_val == 1 else 0
        is_diverted = (diverted == 1)

        cancellation_reason = None
        cancellation_desc = None
        if is_cancelled:
            stats["cancelled"] += 1
            raw_reason = str(row.get("CANCELLATION_REASON", "")).strip().upper()
            if raw_reason in CANCELLATION_REASONS:
                cancellation_reason = raw_reason
                cancellation_desc = CANCELLATION_REASONS[raw_reason]
                stats[f"cancellation_reason_{raw_reason}"] += 1
            else:
                cancellation_reason = "UNKNOWN"
                cancellation_desc = "Unknown Reason"
                stats["cancellation_reason_UNKNOWN"] += 1

        if is_diverted:
            stats["diverted"] += 1

        # --- 8. Natural Flight Key & Duplicate Check ---
        sched_dep_raw = pd.to_numeric(row.get("SCHEDULED_DEPARTURE"), errors="coerce")
        sched_dep_int = int(sched_dep_raw) if pd.notna(sched_dep_raw) else 0

        natural_key = f"{year}_{month:02d}_{day:02d}_{airline_code}_{flight_number}_{raw_origin}_{raw_dest}_{sched_dep_int}"

        if natural_key in seen_keys:
            stats["exact_duplicates"] += 1
            continue
        seen_keys.add(natural_key)

        # --- 9. Cohort Classification ---
        # 1) All valid recorded flight entries: is_valid_record = True
        # 2) Records eligible for operated-route activity analysis:
        #    is_route_eligible = True only if not cancelled, airports resolved in airports.csv with coordinates, origin != dest
        # 3) Cancelled records: is_cancelled = True
        is_valid_record = True
        stats["valid"] += 1

        if not is_cancelled and airports_resolved and has_coordinates:
            is_route_eligible = True
            eligibility_reason = "ELIGIBLE"
            stats["route_eligible"] += 1
        else:
            is_route_eligible = False
            stats["route_ineligible"] += 1
            if is_cancelled:
                eligibility_reason = "CANCELLED_FLIGHT"
            elif is_numeric_airport:
                eligibility_reason = "NUMERIC_DOT_AIRPORT_ID"
            elif not airports_resolved:
                eligibility_reason = "ORPHAN_AIRPORT_CODE"
            elif not has_coordinates:
                eligibility_reason = "MISSING_AIRPORT_COORDINATES"
            else:
                eligibility_reason = "INELIGIBLE_OTHER"

        # --- 10. Times & Delays ---
        sched_arr_raw = pd.to_numeric(row.get("SCHEDULED_ARRIVAL"), errors="coerce")
        sched_arr_int = int(sched_arr_raw) if pd.notna(sched_arr_raw) else 0

        dep_time_num = pd.to_numeric(row.get("DEPARTURE_TIME"), errors="coerce")
        arr_time_num = pd.to_numeric(row.get("ARRIVAL_TIME"), errors="coerce")
        wheels_off_num = pd.to_numeric(row.get("WHEELS_OFF"), errors="coerce")
        wheels_on_num = pd.to_numeric(row.get("WHEELS_ON"), errors="coerce")

        dep_delay_raw = pd.to_numeric(row.get("DEPARTURE_DELAY"), errors="coerce")
        arr_delay_raw = pd.to_numeric(row.get("ARRIVAL_DELAY"), errors="coerce")
        taxi_out_raw = pd.to_numeric(row.get("TAXI_OUT"), errors="coerce")
        taxi_in_raw = pd.to_numeric(row.get("TAXI_IN"), errors="coerce")
        sched_time_raw = pd.to_numeric(row.get("SCHEDULED_TIME"), errors="coerce")
        elapsed_time_raw = pd.to_numeric(row.get("ELAPSED_TIME"), errors="coerce")
        air_time_raw = pd.to_numeric(row.get("AIR_TIME"), errors="coerce")

        departure_delay = float(dep_delay_raw) if pd.notna(dep_delay_raw) else None
        arrival_delay = float(arr_delay_raw) if pd.notna(arr_delay_raw) else None
        taxi_out = float(taxi_out_raw) if pd.notna(taxi_out_raw) else None
        taxi_in = float(taxi_in_raw) if pd.notna(taxi_in_raw) else None
        scheduled_time = float(sched_time_raw) if pd.notna(sched_time_raw) else None
        elapsed_time = float(elapsed_time_raw) if pd.notna(elapsed_time_raw) else None
        air_time = float(air_time_raw) if pd.notna(air_time_raw) else None

        # --- 11. Delay Breakdown ---
        if is_cancelled or is_diverted:
            delay_breakdown = None
        else:
            air_sys = pd.to_numeric(row.get("AIR_SYSTEM_DELAY"), errors="coerce")
            sec = pd.to_numeric(row.get("SECURITY_DELAY"), errors="coerce")
            air_l = pd.to_numeric(row.get("AIRLINE_DELAY"), errors="coerce")
            late_ac = pd.to_numeric(row.get("LATE_AIRCRAFT_DELAY"), errors="coerce")
            wthr = pd.to_numeric(row.get("WEATHER_DELAY"), errors="coerce")

            delay_breakdown = {
                "air_system": float(air_sys) if pd.notna(air_sys) else 0.0,
                "security": float(sec) if pd.notna(sec) else 0.0,
                "airline": float(air_l) if pd.notna(air_l) else 0.0,
                "late_aircraft": float(late_ac) if pd.notna(late_ac) else 0.0,
                "weather": float(wthr) if pd.notna(wthr) else 0.0,
            }

        # --- 12. Document Assembly ---
        doc = {
            "flight_id": natural_key,
            "flight_date": datetime.datetime(year, month, day),
            "year": year,
            "month": month,
            "day": day,
            "day_of_week": day_of_week,
            "airline_code": airline_code,
            "airline_name": airline_name,
            "flight_number": flight_number,
            "tail_number": tail_number,
            "origin": origin_dict,
            "destination": dest_dict,
            "route_key": f"{raw_origin}->{raw_dest}",
            "distance": distance,
            "scheduled_departure": sched_dep_int,
            "scheduled_departure_formatted": format_hhmm(sched_dep_int),
            "departure_time": float(dep_time_num) if pd.notna(dep_time_num) else None,
            "departure_time_formatted": format_hhmm(dep_time_num),
            "departure_delay": departure_delay,
            "taxi_out": taxi_out,
            "wheels_off": float(wheels_off_num) if pd.notna(wheels_off_num) else None,
            "wheels_off_formatted": format_hhmm(wheels_off_num),
            "scheduled_time": scheduled_time,
            "elapsed_time": elapsed_time,
            "air_time": air_time,
            "wheels_on": float(wheels_on_num) if pd.notna(wheels_on_num) else None,
            "wheels_on_formatted": format_hhmm(wheels_on_num),
            "taxi_in": taxi_in,
            "scheduled_arrival": sched_arr_int,
            "scheduled_arrival_formatted": format_hhmm(sched_arr_int),
            "arrival_time": float(arr_time_num) if pd.notna(arr_time_num) else None,
            "arrival_time_formatted": format_hhmm(arr_time_num),
            "arrival_delay": arrival_delay,
            "diverted": diverted,
            "cancelled": cancelled,
            "cancellation_reason": cancellation_reason,
            "cancellation_description": cancellation_desc,
            "delay_breakdown": delay_breakdown,
            # Quality & Cohort Flags
            "is_valid_record": is_valid_record,
            "is_cancelled": is_cancelled,
            "is_diverted": is_diverted,
            "is_route_eligible": is_route_eligible,
            "eligibility_reason": eligibility_reason,
        }
        documents.append(doc)

    return documents, stats
