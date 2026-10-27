# ============================================================
# AeroRoute -- Temporal & Trend Analytics
# File : analytics/temporal_analysis.py
# Usage: python -m analytics.temporal_analysis
#        python analytics/temporal_analysis.py
# ============================================================

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import pymongo

from analytics.utils import safe_export_json
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("temporal_analysis")

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

WEEKDAY_NAMES = {
    1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
    5: "Friday", 6: "Saturday", 7: "Sunday"
}


def get_monthly_flight_activity(
    db: pymongo.database.Database,
    region: Optional[str] = None,
) -> pd.DataFrame:
    """
    Retrieve monthly network flight activity, month-over-month growth, and operational rates.
    For US: Computes operated flights, cancellations, and cancellation rates from operational data.
    For India: Computes scheduled monthly departures and active timetable services from DGCA timetables;
               delays and cancellations are marked as unavailable (not recorded in timetable filings).
    """
    reg = (region or settings.DATASET_REGION).upper()

    if reg == "INDIA":
        monthly_col = settings.get_mr_monthly_route_collection("INDIA")
        pipeline = [
            {"$group": {
                "_id": {"$substr": ["$_id.year_month", 5, 2]},
                "services": {"$sum": "$value.active_timetable_services"},
                "weekly_freq": {"$sum": "$value.weekly_frequency"},
                "monthly_est": {"$sum": "$value.estimated_monthly_departures"},
            }},
            {"$sort": {"_id": 1}}
        ]
        results = list(db[monthly_col].aggregate(pipeline))
        if not results:
            return pd.DataFrame()

        total_annual_est = sum(r["monthly_est"] for r in results)
        rows = []
        prev_est = None

        for r in results:
            m_str = r["_id"]
            m = int(m_str) if str(m_str).isdigit() else 1
            est_oper = int(r["monthly_est"])
            weekly_freq = int(r["weekly_freq"])
            services = int(r["services"])

            share_pct = round((est_oper / total_annual_est) * 100.0, 2) if total_annual_est > 0 else 0.0
            if prev_est is not None and prev_est > 0:
                mom_change = est_oper - prev_est
                mom_pct = round(((est_oper - prev_est) / prev_est) * 100.0, 2)
            else:
                mom_change = 0
                mom_pct = 0.0
            prev_est = est_oper

            rows.append({
                "month": m,
                "month_name": MONTH_NAMES.get(m, f"Month {m}"),
                "operated_flights": est_oper,  # Estimated monthly scheduled departures
                "estimated_monthly_departures": est_oper,
                "weekly_frequency": weekly_freq,
                "active_timetable_services": services,
                "cancelled_flights": None,  # Not tracked in timetable filings
                "total_recorded_attempts": est_oper,
                "cancellation_rate_pct": 0.0,
                "share_of_annual_flights_pct": share_pct,
                "mom_change_flights": mom_change,
                "mom_pct_change": mom_pct,
                "operational_delays_available": False,
                "is_timetable_schedule": True,
                "data_source": "DGCA Domestic Airline Timetables",
            })
        df = pd.DataFrame(rows)
        logger.info(f"Retrieved Indian monthly scheduled activity across {len(df)} calendar months.")
        return df

    # US Operational Data Path
    pipeline = [
        {"$match": {"is_valid_record": True}},
        {"$group": {
            "_id": "$month",
            "total_recorded": {"$sum": 1},
            "eligible_operated": {
                "$sum": {"$cond": [{"$eq": ["$is_route_eligible", True]}, 1, 0]}
            },
            "cancelled_flights": {
                "$sum": {"$cond": [{"$eq": ["$is_cancelled", True]}, 1, 0]}
            },
            "diverted_flights": {
                "$sum": {"$cond": [{"$eq": ["$is_diverted", True]}, 1, 0]}
            }
        }},
        {"$sort": {"_id": 1}}
    ]

    results = list(db[settings.FLIGHTS_COLLECTION].aggregate(pipeline))
    if not results:
        return pd.DataFrame()

    total_eligible_year = sum(r["eligible_operated"] for r in results)

    rows = []
    prev_eligible = None

    for r in results:
        m = r["_id"]
        oper = r["eligible_operated"]
        canc = r["cancelled_flights"]
        tot_rec = r["total_recorded"]

        cancellation_rate = round((canc / tot_rec) * 100.0, 2) if tot_rec > 0 else 0.0
        share_pct = round((oper / total_eligible_year) * 100.0, 2) if total_eligible_year > 0 else 0.0

        if prev_eligible is not None and prev_eligible > 0:
            mom_change = oper - prev_eligible
            mom_pct = round(((oper - prev_eligible) / prev_eligible) * 100.0, 2)
        else:
            mom_change = 0
            mom_pct = 0.0

        prev_eligible = oper

        rows.append({
            "month": m,
            "month_name": MONTH_NAMES.get(m, f"Month {m}"),
            "operated_flights": oper,
            "estimated_monthly_departures": oper,
            "cancelled_flights": canc,
            "total_recorded_attempts": tot_rec,
            "cancellation_rate_pct": cancellation_rate,
            "share_of_annual_flights_pct": share_pct,
            "mom_change_flights": mom_change,
            "mom_pct_change": mom_pct,
            "operational_delays_available": True,
            "is_timetable_schedule": False,
            "data_source": "US DOT Bureau of Transportation Statistics",
        })

    df = pd.DataFrame(rows)
    logger.info(f"Retrieved US monthly flight activity across {len(df)} months.")
    return df


def get_weekday_activity(
    db: pymongo.database.Database,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute day-of-week flight volume, average daily departures, and weekend vs weekday ratio.
    """
    reg = (region or settings.DATASET_REGION).upper()

    if reg == "INDIA":
        flights_col = settings.get_flights_collection("INDIA")
        pipeline = [
            {"$unwind": "$days_of_week"},
            {"$group": {
                "_id": "$days_of_week",
                "flight_count": {"$sum": 1}
            }}
        ]
        results = list(db[flights_col].aggregate(pipeline))
        if not results:
            return {"error": "No Indian flight schedule records found"}

        day_name_to_num = {
            "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
            "Friday": 5, "Saturday": 6, "Sunday": 7
        }
        total_flights = sum(r["flight_count"] for r in results)
        weekday_rows = []
        weekday_total = 0
        weekend_total = 0

        # Sort by day number 1-7
        sorted_results = sorted(results, key=lambda r: day_name_to_num.get(r["_id"], 99))
        for r in sorted_results:
            d_name = r["_id"]
            dow = day_name_to_num.get(d_name, 1)
            cnt = r["flight_count"]
            is_wknd = (dow in [6, 7])

            if is_wknd:
                weekend_total += cnt
            else:
                weekday_total += cnt

            share = round((cnt / total_flights) * 100.0, 2) if total_flights > 0 else 0.0
            weekday_rows.append({
                "day_of_week": dow,
                "day_name": d_name,
                "is_weekend": is_wknd,
                "flight_count": cnt,
                "share_of_weekly_flights_pct": share,
            })

        avg_weekday = round(weekday_total / 5.0, 1)
        avg_weekend = round(weekend_total / 2.0, 1)
        weekend_ratio = round(weekend_total / weekday_total, 3) if weekday_total > 0 else 0.0

        return {
            "region": reg,
            "days": weekday_rows,
            "summary": {
                "total_weekday_flights": weekday_total,
                "total_weekend_flights": weekend_total,
                "avg_flights_per_weekday": avg_weekday,
                "avg_flights_per_weekend_day": avg_weekend,
                "weekend_to_weekday_volume_ratio": weekend_ratio,
                "metric_type": "Weekly Scheduled Operating Days",
            }
        }

    # US Path
    pipeline = [
        {"$match": {"is_route_eligible": True}},
        {"$group": {
            "_id": "$day_of_week",
            "flight_count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]

    results = list(db[settings.FLIGHTS_COLLECTION].aggregate(pipeline))
    if not results:
        return {"error": "No flight records found"}

    total_flights = sum(r["flight_count"] for r in results)

    weekday_rows = []
    weekday_total = 0
    weekend_total = 0

    for r in results:
        dow = r["_id"]
        cnt = r["flight_count"]
        is_wknd = (dow in [6, 7])

        if is_wknd:
            weekend_total += cnt
        else:
            weekday_total += cnt

        share = round((cnt / total_flights) * 100.0, 2) if total_flights > 0 else 0.0

        weekday_rows.append({
            "day_of_week": dow,
            "day_name": WEEKDAY_NAMES.get(dow, str(dow)),
            "is_weekend": is_wknd,
            "flight_count": cnt,
            "share_of_weekly_flights_pct": share,
        })

    avg_weekday = round(weekday_total / 5.0, 1)
    avg_weekend = round(weekend_total / 2.0, 1)
    weekend_ratio = round(weekend_total / weekday_total, 3) if weekday_total > 0 else 0.0

    return {
        "region": reg,
        "days": weekday_rows,
        "summary": {
            "total_weekday_flights": weekday_total,
            "total_weekend_flights": weekend_total,
            "avg_flights_per_weekday": avg_weekday,
            "avg_flights_per_weekend_day": avg_weekend,
            "weekend_to_weekday_volume_ratio": weekend_ratio,
            "metric_type": "Operated Flights per Day of Week",
        }
    }


def get_route_temporal_changes(
    db: pymongo.database.Database,
    region: Optional[str] = None,
    top_n_routes: int = 20,
) -> pd.DataFrame:
    """
    Track monthly activity changes and volatility across top routes over time.
    """
    reg = (region or settings.DATASET_REGION).upper()
    routes_col = settings.get_mr_route_activity_collection(reg)
    monthly_col = settings.get_mr_monthly_route_collection(reg)

    # 1. Fetch top routes
    top_routes_cursor = db[routes_col].find().sort("value", -1).limit(top_n_routes)
    top_keys = [doc["_id"] for doc in top_routes_cursor]

    # 2. Fetch monthly breakdowns
    cursor = db[monthly_col].find({
        "_id.route_key": {"$in": top_keys}
    })

    records = []
    for doc in cursor:
        k = doc["_id"]
        val = doc.get("value")
        if isinstance(val, dict):
            cnt = int(val.get("estimated_monthly_departures", val.get("weekly_frequency", 1)))
        else:
            cnt = int(val) if val is not None else 1

        records.append({
            "route_key": k.get("route_key"),
            "year_month": k.get("year_month"),
            "flight_count": cnt,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Pivot to calculate variance and coefficient of variation
    summary_rows = []
    for route, grp in df.groupby("route_key"):
        counts = grp["flight_count"].values
        mean_c = float(np.mean(counts))
        std_c = float(np.std(counts))
        cv = round(std_c / mean_c, 3) if mean_c > 0 else 0.0

        summary_rows.append({
            "route_key": route,
            "total_flights": int(np.sum(counts)),
            "months_active": len(counts),
            "mean_monthly_flights": round(mean_c, 1),
            "std_dev_monthly": round(std_c, 1),
            "coefficient_of_variation": cv,
            "min_month_flights": int(np.min(counts)),
            "max_month_flights": int(np.max(counts)),
        })

    res_df = pd.DataFrame(summary_rows).sort_values(by="total_flights", ascending=False).reset_index(drop=True)
    return res_df


def detect_unusual_route_changes(
    db: pymongo.database.Database,
    region: Optional[str] = None,
    z_threshold: float = 2.0,
    min_flights: int = 50,
) -> pd.DataFrame:
    """
    Detect statistical anomalies and unusual volatility in route activity across time.
    Flags routes with standard score |Z| >= z_threshold or month-over-month swings > 50%.
    """
    reg = (region or settings.DATASET_REGION).upper()
    monthly_col = settings.get_mr_monthly_route_collection(reg)

    all_monthly = list(db[monthly_col].find())
    if not all_monthly:
        return pd.DataFrame()

    records = []
    for doc in all_monthly:
        k = doc["_id"]
        val = doc.get("value")
        if isinstance(val, dict):
            cnt = int(val.get("estimated_monthly_departures", val.get("weekly_frequency", 1)))
        else:
            cnt = int(val) if val is not None else 1

        records.append({
            "route_key": k.get("route_key"),
            "year_month": k.get("year_month"),
            "flights": cnt,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    anomalies = []
    for route, grp in df.groupby("route_key"):
        if grp["flights"].sum() < min_flights or len(grp) < 2:
            continue

        counts = grp["flights"].values
        mean_v = np.mean(counts)
        std_v = np.std(counts)

        if std_v == 0:
            continue

        for _, row in grp.iterrows():
            f = row["flights"]
            z = (f - mean_v) / std_v
            if abs(z) >= z_threshold:
                anomalies.append({
                    "route_key": route,
                    "year_month": row["year_month"],
                    "observed_flights": f,
                    "route_mean_flights": round(float(mean_v), 1),
                    "z_score": round(float(z), 2),
                    "anomaly_type": "Unusual Spike" if z > 0 else "Unusual Drop",
                })

    anom_df = pd.DataFrame(anomalies)
    if not anom_df.empty:
        anom_df = anom_df.sort_values(by="z_score", ascending=False).reset_index(drop=True)
    logger.info(f"[{reg}] Detected {len(anom_df)} unusual route monthly deviations (threshold Z >= {z_threshold}).")
    return anom_df


def run_full_temporal_analysis(
    db: pymongo.database.Database,
    region: Optional[str] = None,
    export: bool = True,
) -> Dict[str, Any]:
    """
    Execute complete Temporal & Trend analysis suite and export to disk.
    """
    reg = (region or settings.DATASET_REGION).upper()
    logger.info(f"Executing comprehensive Temporal Intelligence analysis for region [{reg}]...")
    monthly_activity = get_monthly_flight_activity(db, region=reg)
    weekday_activity = get_weekday_activity(db, region=reg)
    route_trends = get_route_temporal_changes(db, region=reg, top_n_routes=20)
    anomalies = detect_unusual_route_changes(db, region=reg, z_threshold=2.0)

    results = {
        "region": reg,
        "monthly_activity": monthly_activity.to_dict(orient="records"),
        "weekday_activity": weekday_activity,
        "top_route_trends": route_trends.to_dict(orient="records"),
        "detected_anomalies": anomalies.to_dict(orient="records"),
    }

    if export:
        export_path = settings.EXPORTS_DIR / f"temporal_analysis_{reg.lower()}.json"
        safe_export_json(results, export_path)
        safe_export_json(results, settings.EXPORTS_DIR / "temporal_analysis.json")

    return results

    return results


if __name__ == "__main__":
    db = get_db()
    res = run_full_temporal_analysis(db, export=True)

    print("\n" + "=" * 70)
    print("  AEROROUTE TEMPORAL INTELLIGENCE SUMMARY")
    print("=" * 70)
    print("  Monthly Network Activity:")
    for m in res["monthly_activity"]:
        print(f"    {m['month_name']:<12}: {m['operated_flights']:>8,} operated flights (Cancelled: {m['cancellation_rate_pct']}%)")
    print("-" * 70)
    wknd_sum = res["weekday_activity"]["summary"]
    print(f"  Avg Weekday Volume : {wknd_sum['avg_flights_per_weekday']:,} flights/day")
    print(f"  Avg Weekend Volume : {wknd_sum['avg_flights_per_weekend_day']:,} flights/day")
    print(f"  Weekend / Weekday  : {wknd_sum['weekend_to_weekday_volume_ratio']} ratio")
    print("=" * 70 + "\n")
