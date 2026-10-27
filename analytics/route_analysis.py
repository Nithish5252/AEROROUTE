# ============================================================
# AeroRoute -- Route Intelligence Analytics
# File : analytics/route_analysis.py
# Usage: python -m analytics.route_analysis
#        python analytics/route_analysis.py
# ============================================================

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import pymongo

from analytics.utils import (
    compute_asymmetry_index,
    compute_hhi,
    compute_normalized_hhi,
    interpret_hhi,
    safe_export_json,
    extract_numeric_value,
    extract_route_metrics,
)
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("route_analysis")


def get_busiest_directed_routes(
    db: pymongo.database.Database,
    limit: int = 20,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Retrieve top directed flight corridors ranked by frequency.
    For US: Ranked by operated flight count.
    For India: Ranked by weekly scheduled flight frequency, distinguishing timetable service filings.
    """
    coll_name = settings.get_mr_route_activity_collection(region)
    cursor = db[coll_name].find()

    records = []
    for doc in cursor:
        m = extract_route_metrics(doc)
        route_key = m["route_key"]
        orig, dest = route_key.split("->") if "->" in route_key else (route_key, "UNKNOWN")
        
        # Primary rank metric is weekly_frequency for India, flight_count for US
        records.append({
            "route_key": route_key,
            "origin": orig,
            "destination": dest,
            "flight_count": m["weekly_frequency"],
            "weekly_frequency": m["weekly_frequency"],
            "timetable_services": m["timetable_services"],
            "estimated_monthly_departures": m["estimated_monthly_departures"],
            "distance_km": m["distance_km"],
            "airlines": m["airlines"],
            "carrier_count": m["carrier_count"],
            "metric_type": m["metric_type"],
            "data_source": m["data_source"],
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.sort_values(by="flight_count", ascending=False).reset_index(drop=True)

    total_flights = df["flight_count"].sum()
    if total_flights > 0:
        df["share_of_total_pct"] = ((df["flight_count"] / total_flights) * 100.0).round(3)
        df["cumulative_share_pct"] = (df["share_of_total_pct"].cumsum()).round(3)
    else:
        df["share_of_total_pct"] = 0.0
        df["cumulative_share_pct"] = 0.0

    if limit > 0:
        df = df.head(limit)

    logger.info(f"Retrieved top {len(df)} busiest directed routes from '{coll_name}'.")
    return df


def get_route_frequency_distribution(
    db: pymongo.database.Database,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute statistical distribution metrics of corridor volumes across all directed routes.
    Includes parametric (mean, std) and non-parametric (quantiles, binned counts) metrics.
    """
    coll_name = settings.get_mr_route_activity_collection(region)
    all_routes = list(db[coll_name].find({}, {"value": 1}))
    if not all_routes:
        return {"error": f"Collection '{coll_name}' is empty"}

    counts = np.array([extract_numeric_value(r["value"], "weekly_frequency") for r in all_routes], dtype=float)
    total_flights = float(np.sum(counts))
    n_routes = len(counts)

    quantiles = np.percentile(counts, [25, 50, 75, 90, 95, 99])

    # Categorical frequency bins
    max_c = max(np.max(counts), 1000.0)
    bins = [0, 10, 25, 50, 100, 250, 500, 1000, max(50000, max_c + 1)]
    labels = ["1-10", "11-25", "26-50", "51-100", "101-250", "251-500", "501-1000", "1000+"]
    bin_counts = pd.cut(counts, bins=bins, labels=labels).value_counts().sort_index().to_dict()

    return {
        "total_distinct_directed_routes": n_routes,
        "total_network_flights": int(total_flights),
        "mean_flights_per_route": round(float(np.mean(counts)), 2),
        "std_dev_flights": round(float(np.std(counts)), 2),
        "min_flights": int(np.min(counts)),
        "p25": round(float(quantiles[0]), 2),
        "median_p50": round(float(quantiles[1]), 2),
        "p75": round(float(quantiles[2]), 2),
        "p90": round(float(quantiles[3]), 2),
        "p95": round(float(quantiles[4]), 2),
        "p99": round(float(quantiles[5]), 2),
        "max_flights": int(np.max(counts)),
        "frequency_bins": {k: int(v) for k, v in bin_counts.items()},
    }


def get_most_active_airport_pairs(
    db: pymongo.database.Database,
    limit: int = 20,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Aggregate directed routes into undirected (bidirectional) city pairs.
    Example: Combines (DEL -> BOM) and (BOM -> DEL) into (BOM <-> DEL).
    Computes total corridor volume, directional split, and directional asymmetry index.
    """
    coll_name = settings.get_mr_route_activity_collection(region)
    all_routes = list(db[coll_name].find())
    pair_map: Dict[str, Dict[str, Any]] = {}

    for doc in all_routes:
        route_key = doc["_id"]
        val = extract_numeric_value(doc["value"], "weekly_frequency")
        if "->" not in route_key:
            continue
        orig, dest = route_key.split("->")

        pair_nodes = sorted([orig, dest])
        pair_key = f"{pair_nodes[0]} <-> {pair_nodes[1]}"

        if pair_key not in pair_map:
            pair_map[pair_key] = {
                "pair_key": pair_key,
                "airport_1": pair_nodes[0],
                "airport_2": pair_nodes[1],
                f"{pair_nodes[0]}->{pair_nodes[1]}": 0,
                f"{pair_nodes[1]}->{pair_nodes[0]}": 0,
                "total_pair_flights": 0,
            }

        pair_map[pair_key][f"{orig}->{dest}"] = int(val)
        pair_map[pair_key]["total_pair_flights"] += int(val)

    rows = []
    for pair_key, d in pair_map.items():
        a1 = d["airport_1"]
        a2 = d["airport_2"]
        dir_1 = d[f"{a1}->{a2}"]
        dir_2 = d[f"{a2}->{a1}"]
        asym = compute_asymmetry_index(dir_1, dir_2)

        rows.append({
            "pair_key": pair_key,
            "airport_1": a1,
            "airport_2": a2,
            "total_pair_flights": d["total_pair_flights"],
            f"flights_{a1}_to_{a2}": dir_1,
            f"flights_{a2}_to_{a1}": dir_2,
            "asymmetry_index": asym,
            "symmetry_status": "Symmetric" if asym <= 0.05 else ("Moderately Asymmetric" if asym <= 0.20 else "Highly Asymmetric"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="total_pair_flights", ascending=False).reset_index(drop=True)
        if limit > 0:
            df = df.head(limit)
    return df


def get_reverse_direction_comparisons(
    db: pymongo.database.Database,
    min_flights: int = 50,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Compare bidirectional route pairs to analyze route directional balance.
    Filters for routes with at least `min_flights` total volume to prevent low-sample noise.
    """
    pairs_df = get_most_active_airport_pairs(db, limit=0, region=region)
    if pairs_df.empty:
        return pairs_df

    filtered = pairs_df[pairs_df["total_pair_flights"] >= min_flights].copy()
    filtered = filtered.sort_values(by="asymmetry_index", ascending=False).reset_index(drop=True)
    return filtered


def get_monthly_route_activity(
    db: pymongo.database.Database,
    top_n_routes: int = 10,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Retrieve monthly time series flight volume for top directed corridors.
    Sourced from 'mr_monthly_route' (US) or 'mr_monthly_route_in' (India).
    """
    top_routes_df = get_busiest_directed_routes(db, limit=top_n_routes, region=region)
    if top_routes_df.empty:
        return pd.DataFrame()

    top_keys = top_routes_df["route_key"].tolist()
    coll_name = settings.get_mr_monthly_route_collection(region)

    cursor = db[coll_name].find({
        "_id.route_key": {"$in": top_keys}
    })

    records = []
    for doc in cursor:
        k = doc["_id"]
        val = extract_numeric_value(doc["value"], "weekly_frequency")
        active_sched = int(doc["value"].get("active_timetable_services", val)) if isinstance(doc["value"], dict) else int(val)
        records.append({
            "route_key": k.get("route_key"),
            "year_month": k.get("year_month"),
            "origin": k.get("origin"),
            "destination": k.get("destination"),
            "flight_count": int(val),
            "weekly_frequency": int(val),
            "active_schedules": active_sched,
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(by=["route_key", "year_month"]).reset_index(drop=True)
    return df


def get_weekday_route_activity(
    db: pymongo.database.Database,
    top_n_routes: int = 5,
    region: Optional[str] = None
) -> pd.DataFrame:
    """
    Retrieve day-of-week distribution (Mon ... Sun) for top routes.
    For US: Aggregate day_of_week integers 1..7.
    For India: Aggregate operating days from unwound days_of_week array.
    """
    top_routes_df = get_busiest_directed_routes(db, limit=top_n_routes, region=region)
    if top_routes_df.empty:
        return pd.DataFrame()

    top_keys = top_routes_df["route_key"].tolist()
    flights_coll = settings.get_flights_collection(region)
    is_indian = flights_coll == settings.INDIAN_FLIGHTS_COLLECTION

    records = []
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_abbr = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
    dow_to_name = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

    if is_indian:
        pipeline = [
            {"$match": {"is_route_eligible": True, "route_key": {"$in": top_keys}}},
            {"$unwind": "$days_of_week"},
            {"$group": {
                "_id": {"route_key": "$route_key", "day_name": "$days_of_week"},
                "flight_count": {"$sum": 1}
            }},
            {"$sort": {"_id.route_key": 1}}
        ]
        results = list(db[flights_coll].aggregate(pipeline))
        for r in results:
            d_name = r["_id"]["day_name"]
            dow_idx = (day_order.index(d_name) + 1) if d_name in day_order else 0
            records.append({
                "route_key": r["_id"]["route_key"],
                "day_of_week": dow_idx,
                "day_name": day_abbr.get(d_name, d_name[:3]),
                "flight_count": r["flight_count"],
            })
    else:
        pipeline = [
            {"$match": {"is_route_eligible": True, "route_key": {"$in": top_keys}}},
            {"$group": {
                "_id": {"route_key": "$route_key", "day_of_week": "$day_of_week"},
                "flight_count": {"$sum": 1}
            }},
            {"$sort": {"_id.route_key": 1, "_id.day_of_week": 1}}
        ]
        results = list(db[flights_coll].aggregate(pipeline))
        for r in results:
            dow = r["_id"]["day_of_week"]
            records.append({
                "route_key": r["_id"]["route_key"],
                "day_of_week": dow,
                "day_name": dow_to_name.get(dow, str(dow)),
                "flight_count": r["flight_count"],
            })

    return pd.DataFrame(records)


def get_route_concentration_metrics(
    db: pymongo.database.Database,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute route activity concentration metrics:
      - Herfindahl-Hirschman Index (HHI)
      - Normalized HHI (0 to 1)
      - Top 10, Top 50, Top 100 cumulative shares (C10, C50, C100)
    """
    coll_name = settings.get_mr_route_activity_collection(region)
    all_routes = list(db[coll_name].find({}, {"value": 1}))
    if not all_routes:
        return {"error": f"{coll_name} is empty"}

    counts = sorted([extract_numeric_value(r["value"], "weekly_frequency") for r in all_routes], reverse=True)
    total_flights = sum(counts)
    n_routes = len(counts)

    hhi = compute_hhi(counts, is_percentage=False)
    norm_hhi = compute_normalized_hhi(counts)
    interpretation = interpret_hhi(hhi)

    top_10_share = round((sum(counts[:10]) / total_flights) * 100.0, 2) if n_routes >= 10 and total_flights > 0 else 100.0
    top_50_share = round((sum(counts[:50]) / total_flights) * 100.0, 2) if n_routes >= 50 and total_flights > 0 else 100.0
    top_100_share = round((sum(counts[:100]) / total_flights) * 100.0, 2) if n_routes >= 100 and total_flights > 0 else 100.0

    return {
        "total_directed_routes": n_routes,
        "total_network_flights": int(total_flights),
        "hhi": hhi,
        "normalized_hhi": norm_hhi,
        "concentration_category": interpretation,
        "top_10_routes_share_pct": top_10_share,
        "top_50_routes_share_pct": top_50_share,
        "top_100_routes_share_pct": top_100_share,
    }


def run_full_route_analysis(
    db: pymongo.database.Database,
    export: bool = True,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute complete Route Intelligence analysis suite and optionally export to disk.
    """
    r_label = (region or settings.DATASET_REGION).upper()
    logger.info(f"Executing comprehensive Route Intelligence analysis for region: {r_label}...")
    busiest_routes = get_busiest_directed_routes(db, limit=20, region=region)
    freq_dist = get_route_frequency_distribution(db, region=region)
    top_pairs = get_most_active_airport_pairs(db, limit=20, region=region)
    concentration = get_route_concentration_metrics(db, region=region)

    results = {
        "region": r_label,
        "summary": concentration,
        "frequency_distribution": freq_dist,
        "top_20_directed_routes": busiest_routes.to_dict(orient="records"),
        "top_20_airport_pairs": top_pairs.to_dict(orient="records"),
    }

    if export:
        suffix = "_in" if r_label in ("INDIA", "IN") else ""
        export_path = settings.EXPORTS_DIR / f"route_intelligence{suffix}.json"
        safe_export_json(results, export_path)

    return results


if __name__ == "__main__":
    db = get_db()
    for reg in ["INDIA", "US"]:
        res = run_full_route_analysis(db, export=True, region=reg)
        conc = res["summary"]
        print(f"\n=== REGION: {reg} ===")
        print(f"Total Routes : {conc['total_directed_routes']:,}")
        print(f"Total Volume : {conc['total_network_flights']:,}")
        print(f"Top 3 Corridors:")
        for r in res["top_20_directed_routes"][:3]:
            print(f"  {r['route_key']:<12} : {r['flight_count']:>6,} ({r['share_of_total_pct']}%)")
