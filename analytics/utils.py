# ============================================================
# AeroRoute -- Analytics Utilities & Metric Computations
# File : analytics/utils.py
# ============================================================

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union
import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("analytics_utils")


def compute_hhi(values_or_shares: Sequence[Union[int, float]], is_percentage: bool = False) -> float:
    """
    Calculate the Herfindahl-Hirschman Index (HHI) for market / network concentration.

    HHI = sum(s_i ^ 2) where s_i is market share percentage (0 to 100).
    Scale: 0 to 10,000.
    Standard Department of Justice / FTC thresholds:
      - HHI < 100        : Highly competitive / highly dispersed
      - 100 <= HHI < 1500: Unconcentrated network
      - 1500 <= HHI < 2500: Moderately concentrated
      - HHI >= 2500      : Highly concentrated
    """
    arr = np.array(values_or_shares, dtype=float)
    if len(arr) == 0:
        return 0.0

    total = np.sum(arr)
    if total <= 0:
        return 0.0

    if not is_percentage:
        # Convert raw values to percentage shares (0 to 100)
        shares = (arr / total) * 100.0
    else:
        shares = arr

    hhi = float(np.sum(shares ** 2))
    return round(hhi, 2)


def compute_normalized_hhi(values: Sequence[Union[int, float]]) -> float:
    """
    Compute Normalized HHI in the range [0.0, 1.0].
    HHI* = (HHI - 10000 / N) / (10000 - 10000 / N)
    """
    arr = np.array(values, dtype=float)
    n = len(arr)
    if n <= 1:
        return 1.0

    raw_hhi = compute_hhi(arr, is_percentage=False)
    min_hhi = 10000.0 / n
    max_hhi = 10000.0

    if max_hhi == min_hhi:
        return 0.0

    norm_hhi = (raw_hhi - min_hhi) / (max_hhi - min_hhi)
    return round(max(0.0, min(1.0, norm_hhi)), 4)


def interpret_hhi(hhi_value: float) -> str:
    """Provide descriptive market concentration category for an HHI value."""
    if hhi_value < 100.0:
        return "Highly Dispersed / Highly Competitive (< 100)"
    elif hhi_value < 1500.0:
        return "Unconcentrated Network (100 - 1,500)"
    elif hhi_value < 2500.0:
        return "Moderately Concentrated Network (1,500 - 2,500)"
    else:
        return "Highly Concentrated Network (>= 2,500)"


def compute_asymmetry_index(count_ab: float, count_ba: float) -> float:
    """
    Compute Route Directional Asymmetry Index:
    Asym = |V(A->B) - V(B->A)| / (V(A->B) + V(B->A))
    Range: [0.0, 1.0]
      - 0.0: Perfectly symmetric route pair
      - 1.0: Strictly one-way route corridor
    """
    total = count_ab + count_ba
    if total <= 0:
        return 0.0
    return round(abs(count_ab - count_ba) / total, 4)


def safe_export_json(data: Any, filepath: Path) -> Path:
    """
    Safely export dictionary or DataFrame to formatted JSON file.
    Creates parent directories if necessary.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        if isinstance(data, pd.DataFrame):
            # Export DataFrame as records
            json.dump(data.to_dict(orient="records"), f, indent=2, default=str)
        else:
            json.dump(data, f, indent=2, default=str)
    logger.info(f"Exported analytics artifact to: {filepath}")
    return filepath


def extract_numeric_value(val: Any, preferred_key: str = "weekly_frequency") -> float:
    """Extract float numeric value from either a scalar (US) or composite dict (Indian)."""
    if isinstance(val, dict):
        if preferred_key in val:
            return float(val[preferred_key])
        if "weekly_frequency" in val:
            return float(val["weekly_frequency"])
        if "outgoing_weekly_frequency" in val:
            return float(val["outgoing_weekly_frequency"])
        if "incoming_weekly_frequency" in val:
            return float(val["incoming_weekly_frequency"])
        if "timetable_services" in val:
            return float(val["timetable_services"])
        if "total_flights" in val:
            return float(val["total_flights"])
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def extract_route_metrics(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardize metric extraction from a MapReduce route activity document.
    Handles both scalar US format and composite Indian timetable format.
    """
    val = doc.get("value", 0)
    route_key = doc.get("_id", "")
    if isinstance(val, dict):
        weekly_freq = float(val.get("weekly_frequency", 0))
        timetable_services = int(val.get("timetable_services", 0))
        est_monthly = int(val.get("estimated_monthly_departures", round(weekly_freq * 4.2857)))
        dist = float(val.get("distance_km", 0.0))
        airlines = val.get("airlines", [])
        carrier_count = int(val.get("carrier_count", len(airlines)))
        metric_type = val.get("metric_type", "SCHEDULED_ROUTE_CAPACITY")
        data_source = val.get("data_source", "DGCA_Airline_Timetables_2018_2025")
    else:
        weekly_freq = float(val)
        timetable_services = int(val)
        est_monthly = int(val)
        dist = 0.0
        airlines = []
        carrier_count = 1
        metric_type = "OPERATED_FLIGHT_COUNT"
        data_source = "US_DOT_TRANSTATS_2015"

    return {
        "route_key": route_key,
        "weekly_frequency": int(weekly_freq),
        "timetable_services": timetable_services,
        "estimated_monthly_departures": est_monthly,
        "distance_km": dist,
        "airlines": airlines,
        "carrier_count": carrier_count,
        "metric_type": metric_type,
        "data_source": data_source,
    }
