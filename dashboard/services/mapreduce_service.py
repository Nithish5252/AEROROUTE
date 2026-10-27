# ============================================================
# AeroRoute -- Flight Operations Console MapReduce Service
# File : dashboard/services/mapreduce_service.py
# ============================================================

import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from config.settings import settings
from dashboard.services.database import get_db, check_connection

logger = logging.getLogger("aeroroute.mapreduce_service")

# Static definition of the 5 Server-Side JavaScript MapReduce jobs for US Baseline
US_MAPREDUCE_JOBS = {
    "job_a": {
        "job_id": "job_a",
        "name": "Job A: Directed Route Activity",
        "purpose": "Calculates flight volume on each directed airport corridor (u -> v != v -> u).",
        "input_collection": "flights",
        "output_collection": "mr_route_activity",
        "query_filter": '{"is_eligible_for_route_analysis": true}',
        "key_description": "String formatted as '{origin_airport}->{destination_airport}'",
        "value_description": "Scalar integer 1 emitted per flight",
        "mapper_code": """function() {
    if (this.is_eligible_for_route_analysis === true) {
        var routeKey = this.origin_airport + "->" + this.destination_airport;
        emit(routeKey, 1);
    }
}""",
        "reducer_code": """function(key, values) {
    return Array.sum(values);
}""",
    },
    "job_b": {
        "job_id": "job_b",
        "name": "Job B: Airport Outgoing Activity",
        "purpose": "Aggregates total outbound eligible flight operations departing from each airport.",
        "input_collection": "flights",
        "output_collection": "mr_airport_outgoing",
        "query_filter": '{"is_eligible_for_route_analysis": true}',
        "key_description": "String '{origin_airport}'",
        "value_description": "Scalar integer 1 emitted per outbound flight",
        "mapper_code": """function() {
    if (this.is_eligible_for_route_analysis === true) {
        emit(this.origin_airport, 1);
    }
}""",
        "reducer_code": """function(key, values) {
    return Array.sum(values);
}""",
    },
    "job_c": {
        "job_id": "job_c",
        "name": "Job C: Airport Incoming Activity",
        "purpose": "Aggregates total inbound eligible flight operations arriving at each airport.",
        "input_collection": "flights",
        "output_collection": "mr_airport_incoming",
        "query_filter": '{"is_eligible_for_route_analysis": true}',
        "key_description": "String '{destination_airport}'",
        "value_description": "Scalar integer 1 emitted per inbound flight",
        "mapper_code": """function() {
    if (this.is_eligible_for_route_analysis === true) {
        emit(this.destination_airport, 1);
    }
}""",
        "reducer_code": """function(key, values) {
    return Array.sum(values);
}""",
    },
    "job_d": {
        "job_id": "job_d",
        "name": "Job D: Monthly Route Activity",
        "purpose": "Computes monthly temporal flight volume across individual directed corridors.",
        "input_collection": "flights",
        "output_collection": "mr_monthly_route",
        "query_filter": '{"is_eligible_for_route_analysis": true}',
        "key_description": "Composite String '{year}-{month:02d}_{origin}->{destination}'",
        "value_description": "Scalar integer 1 emitted per monthly flight",
        "mapper_code": """function() {
    if (this.is_eligible_for_route_analysis === true) {
        var mStr = this.month < 10 ? "0" + this.month : "" + this.month;
        var compKey = this.year + "-" + mStr + "_" + this.origin_airport + "->" + this.destination_airport;
        emit(compKey, 1);
    }
}""",
        "reducer_code": """function(key, values) {
    return Array.sum(values);
}""",
    },
    "job_e": {
        "job_id": "job_e",
        "name": "Job E: Airport Connectivity Summary",
        "purpose": "Builds the distinct destination connectivity array for every origin airport.",
        "input_collection": "flights",
        "output_collection": "mr_airport_connectivity",
        "query_filter": '{"is_eligible_for_route_analysis": true}',
        "key_description": "String '{origin_airport}'",
        "value_description": "Object { destinations: [dest], count: 1 }",
        "mapper_code": """function() {
    if (this.is_eligible_for_route_analysis === true) {
        emit(this.origin_airport, {
            destinations: [this.destination_airport],
            count: 1
        });
    }
}""",
        "reducer_code": """function(key, values) {
    var destMap = {};
    var totalCount = 0;
    values.forEach(function(v) {
        totalCount += (v.count || 1);
        if (v.destinations && Array.isArray(v.destinations)) {
            v.destinations.forEach(function(d) {
                destMap[d] = true;
            });
        }
    });
    return {
        destinations: Object.keys(destMap),
        count: totalCount
    };
}""",
    },
}

# Static definition of the 5 Server-Side JavaScript MapReduce jobs for India
INDIAN_MAPREDUCE_JOBS = {
    "job_a": {
        "job_id": "job_a",
        "name": "Job A: Indian Directed Route Activity",
        "purpose": "Calculates timetable services, weekly departures, and operating airlines per directed route.",
        "input_collection": "flights_in",
        "output_collection": "mr_route_activity_in",
        "query_filter": '{"is_route_eligible": true}',
        "key_description": "String formatted as '{origin}->{destination}' (e.g. 'DEL->BOM')",
        "value_description": "Object { timetable_services: 1, weekly_frequency: N, distance_km: D, airlines: [...] }",
        "mapper_code": """function() {
    if (!this.is_route_eligible) return;
    var key = this.route_key || (this.origin + "->" + this.destination);
    var weeklyFreq = Number(this.operating_days_count) || 1;
    var dist = Number(this.distance_km) || 0;
    var airline = this.airline_code || "UNKNOWN";

    emit(key, {
        timetable_services: 1,
        weekly_frequency: weeklyFreq,
        distance_km: dist,
        airlines: [airline]
    });
}""",
        "reducer_code": """function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var dist = 0;
    var airlineMap = {};

    values.forEach(function(v) {
        totalServices += (v.timetable_services || 0);
        totalWeeklyFreq += (v.weekly_frequency || 0);
        if (v.distance_km) dist = v.distance_km;
        if (v.airlines) {
            for (var i = 0; i < v.airlines.length; i++) {
                airlineMap[v.airlines[i]] = true;
            }
        }
    });

    return {
        timetable_services: totalServices,
        weekly_frequency: totalWeeklyFreq,
        distance_km: dist,
        airlines: Object.keys(airlineMap)
    };
}""",
    },
    "job_b": {
        "job_id": "job_b",
        "name": "Job B: Indian Airport Outgoing Activity",
        "purpose": "Aggregates total outbound scheduled services and weekly frequency per departing airport node.",
        "input_collection": "flights_in",
        "output_collection": "mr_airport_outgoing_in",
        "query_filter": '{"is_route_eligible": true}',
        "key_description": "String '{origin_iata}'",
        "value_description": "Object { outgoing_timetable_services: 1, outgoing_weekly_frequency: N, destinations: [...] }",
        "mapper_code": """function() {
    if (!this.is_route_eligible) return;
    var orig = this.origin || (this.origin_airport ? this.origin_airport.iata : null);
    if (orig) {
        var weeklyFreq = Number(this.operating_days_count) || 1;
        var dest = this.destination || null;
        emit(orig, {
            outgoing_timetable_services: 1,
            outgoing_weekly_frequency: weeklyFreq,
            destinations: dest ? [dest] : []
        });
    }
}""",
        "reducer_code": """function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var destMap = {};

    values.forEach(function(v) {
        totalServices += (v.outgoing_timetable_services || 0);
        totalWeeklyFreq += (v.outgoing_weekly_frequency || 0);
        if (v.destinations) {
            for (var i = 0; i < v.destinations.length; i++) {
                destMap[v.destinations[i]] = true;
            }
        }
    });

    return {
        outgoing_timetable_services: totalServices,
        outgoing_weekly_frequency: totalWeeklyFreq,
        destinations: Object.keys(destMap)
    };
}""",
    },
    "job_c": {
        "job_id": "job_c",
        "name": "Job C: Indian Airport Incoming Activity",
        "purpose": "Aggregates total inbound scheduled services and weekly arrivals per destination airport node.",
        "input_collection": "flights_in",
        "output_collection": "mr_airport_incoming_in",
        "query_filter": '{"is_route_eligible": true}',
        "key_description": "String '{destination_iata}'",
        "value_description": "Object { incoming_timetable_services: 1, incoming_weekly_frequency: N, origins: [...] }",
        "mapper_code": """function() {
    if (!this.is_route_eligible) return;
    var dst = this.destination || null;
    if (dst) {
        var weeklyFreq = Number(this.operating_days_count) || 1;
        var orig = this.origin || null;
        emit(dst, {
            incoming_timetable_services: 1,
            incoming_weekly_frequency: weeklyFreq,
            origins: orig ? [orig] : []
        });
    }
}""",
        "reducer_code": """function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var originMap = {};

    values.forEach(function(v) {
        totalServices += (v.incoming_timetable_services || 0);
        totalWeeklyFreq += (v.incoming_weekly_frequency || 0);
        if (v.origins) {
            for (var i = 0; i < v.origins.length; i++) {
                originMap[v.origins[i]] = true;
            }
        }
    });

    return {
        incoming_timetable_services: totalServices,
        incoming_weekly_frequency: totalWeeklyFreq,
        origins: Object.keys(originMap)
    };
}""",
    },
    "job_d": {
        "job_id": "job_d",
        "name": "Job D: Indian Monthly Route Activity",
        "purpose": "Computes monthly temporal schedule capacity across individual Indian domestic corridors.",
        "input_collection": "flights_in",
        "output_collection": "mr_monthly_route_in",
        "query_filter": '{"is_route_eligible": true}',
        "key_description": "Document { route_key: '...', year_month: 'YYYY-MM' }",
        "value_description": "Object { timetable_services: 1, weekly_frequency: N, estimated_monthly_departures: M }",
        "mapper_code": """function() {
    if (!this.is_route_eligible) return;
    var rKey = this.route_key || (this.origin + "->" + this.destination);
    var weeklyFreq = Number(this.operating_days_count) || 1;
    var yearVal = this.year || 2024;
    var monthVal = this.month || 1;
    var ym = yearVal + "-" + (monthVal < 10 ? "0" + monthVal : "" + monthVal);

    emit({ route_key: rKey, year_month: ym }, {
        timetable_services: 1,
        weekly_frequency: weeklyFreq
    });
}""",
        "reducer_code": """function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;

    values.forEach(function(v) {
        totalServices += (v.timetable_services || 0);
        totalWeeklyFreq += (v.weekly_frequency || 0);
    });

    return {
        timetable_services: totalServices,
        weekly_frequency: totalWeeklyFreq
    };
}""",
    },
    "job_e": {
        "job_id": "job_e",
        "name": "Job E: Indian Airport Connectivity Summary",
        "purpose": "Builds distinct destination connectivity array and degree profile for every Indian airport node.",
        "input_collection": "flights_in",
        "output_collection": "mr_airport_connectivity_in",
        "query_filter": '{"is_route_eligible": true}',
        "key_description": "String '{airport_iata}'",
        "value_description": "Object { neighbor_airports: [...], outgoing_timetable_services: N, outgoing_weekly_frequency: W }",
        "mapper_code": """function() {
    if (!this.is_route_eligible) return;
    var orig = this.origin || null;
    var dest = this.destination || null;
    if (orig && dest) {
        var weeklyFreq = Number(this.operating_days_count) || 1;
        emit(orig, {
            neighbor_airports: [dest],
            outgoing_timetable_services: 1,
            outgoing_weekly_frequency: weeklyFreq
        });
    }
}""",
        "reducer_code": """function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var neighborMap = {};

    values.forEach(function(v) {
        totalServices += (v.outgoing_timetable_services || 0);
        totalWeeklyFreq += (v.outgoing_weekly_frequency || 0);
        if (v.neighbor_airports) {
            for (var i = 0; i < v.neighbor_airports.length; i++) {
                neighborMap[v.neighbor_airports[i]] = true;
            }
        }
    });

    return {
        neighbor_airports: Object.keys(neighborMap),
        outgoing_timetable_services: totalServices,
        outgoing_weekly_frequency: totalWeeklyFreq
    };
}""",
    },
}

# Backward compatibility alias
MAPREDUCE_JOBS = US_MAPREDUCE_JOBS


def _resolve_mr_region(region: Optional[str] = None) -> str:
    if region:
        clean = str(region).strip().upper()
        if clean in ["INDIA", "IN"]:
            return "INDIA"
        if clean in ["USA", "US"]:
            return "US"
    try:
        import streamlit as st
        val = st.session_state.get("dataset_region") or st.session_state.get("global_airspace")
        if val:
            clean = str(val).strip().upper()
            if clean in ["INDIA", "IN"]:
                return "INDIA"
            if clean in ["USA", "US"]:
                return "US"
    except Exception:
        pass
    return settings.DATASET_REGION.upper()


def get_mapreduce_job_definitions(region: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Return static metadata for all 5 MapReduce jobs based on region."""
    reg = _resolve_mr_region(region)
    return INDIAN_MAPREDUCE_JOBS if reg == "INDIA" else US_MAPREDUCE_JOBS


def format_mapreduce_samples(sample_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format MapReduce sample documents into clean, human-readable tabular records.
    Eliminates all raw curly-brace dictionary strings, nested arrays, and JSON representations.
    """
    formatted = []
    for d in sample_docs:
        raw_id = d.get("_id")
        val = d.get("value")
        row = {}

        # 1. Format the Key
        if isinstance(raw_id, dict):
            route = raw_id.get("route_key") or f"{raw_id.get('origin', '')}->{raw_id.get('destination', '')}"
            month = raw_id.get("year_month") or raw_id.get("month", "")
            if route and month:
                row["Route Corridor"] = str(route)
                row["Period"] = str(month)
            else:
                row["Identifier"] = " | ".join(f"{k}: {v}" for k, v in raw_id.items())
        else:
            key_str = str(raw_id)
            if "->" in key_str:
                row["Route Corridor"] = key_str
            elif len(key_str) == 3 and key_str.isalpha():
                row["Airport (IATA)"] = key_str
            else:
                row["Key (_id)"] = key_str

        # 2. Format the Value
        if isinstance(val, dict):
            # Volume / Frequencies
            if "weekly_frequency" in val:
                row["Weekly Flights"] = int(val["weekly_frequency"])
            elif "outgoing_weekly_frequency" in val:
                row["Weekly Departures"] = int(val["outgoing_weekly_frequency"])
            elif "incoming_weekly_frequency" in val:
                row["Weekly Arrivals"] = int(val["incoming_weekly_frequency"])
            elif "total_weekly_frequency" in val:
                row["Total Weekly Movements"] = int(val["total_weekly_frequency"])
            elif "flight_count" in val:
                row["Flight Count"] = int(val["flight_count"])
            elif "total_flights" in val:
                row["Total Flights"] = int(val["total_flights"])
            elif "outgoing_flights" in val:
                row["Outgoing Flights"] = int(val["outgoing_flights"])
            elif "incoming_flights" in val:
                row["Incoming Flights"] = int(val["incoming_flights"])

            # Timetable Schedules
            if "timetable_services" in val:
                row["Timetable Schedules"] = int(val["timetable_services"])
            elif "active_timetable_services" in val:
                row["Active Schedules"] = int(val["active_timetable_services"])
            elif "outgoing_timetable_services" in val:
                row["Departure Schedules"] = int(val["outgoing_timetable_services"])
            elif "incoming_timetable_services" in val:
                row["Arrival Schedules"] = int(val["incoming_timetable_services"])
            elif "total_schedules" in val:
                row["Total Schedules"] = int(val["total_schedules"])

            # Monthly estimates
            if "estimated_monthly_departures" in val:
                row["Est. Monthly Departures"] = int(val["estimated_monthly_departures"])
            elif "estimated_monthly_arrivals" in val:
                row["Est. Monthly Arrivals"] = int(val["estimated_monthly_arrivals"])
            elif "estimated_monthly_movements" in val:
                row["Est. Monthly Movements"] = int(val["estimated_monthly_movements"])

            # Distance
            if "distance_km" in val:
                row["Distance (km)"] = f"{float(val['distance_km']):,.1f}"

            # Degrees and connections
            if "distinct_connections" in val:
                row["Connected Airports"] = int(val["distinct_connections"])
            if "out_degree_destinations" in val:
                row["Destinations"] = int(val["out_degree_destinations"])
            elif "out_degree" in val:
                row["Destinations"] = int(val["out_degree"])
            if "in_degree_origins" in val:
                row["Origins"] = int(val["in_degree_origins"])
            elif "in_degree" in val:
                row["Origins"] = int(val["in_degree"])

            # Carriers & Neighbors (clean comma-separated list without brackets or quotes)
            if "airlines" in val and isinstance(val["airlines"], list):
                row["Operating Airlines"] = ", ".join(str(a) for a in val["airlines"] if a)
            elif "destinations" in val and isinstance(val["destinations"], list):
                row["Sample Destinations"] = ", ".join(str(d) for d in val["destinations"][:6]) + ("..." if len(val["destinations"]) > 6 else "")
            elif "origins" in val and isinstance(val["origins"], list):
                row["Sample Origins"] = ", ".join(str(o) for o in val["origins"][:6]) + ("..." if len(val["origins"]) > 6 else "")
            elif "neighbor_airports" in val and isinstance(val["neighbor_airports"], list):
                row["Connected Nodes"] = ", ".join(str(n) for n in val["neighbor_airports"][:6]) + ("..." if len(val["neighbor_airports"]) > 6 else "")

        elif isinstance(val, (int, float)):
            row["Value (Count)"] = int(val) if float(val).is_integer() else round(float(val), 2)
        elif isinstance(val, list):
            row["Values"] = ", ".join(str(x) for x in val)
        else:
            row["Value"] = str(val) if val is not None else "—"

        formatted.append(row)
    return formatted


def get_job_telemetry(job_id: str, region: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve live runtime metrics and sample output records for a MapReduce job.
    """
    reg = _resolve_mr_region(region)
    active_jobs = INDIAN_MAPREDUCE_JOBS if reg == "INDIA" else US_MAPREDUCE_JOBS

    if job_id not in active_jobs:
        return {"error": f"Invalid job_id: {job_id}"}

    job_info = active_jobs[job_id].copy()
    output_col_name = job_info["output_collection"]

    is_conn, _ = check_connection()
    if not is_conn:
        job_info["document_count"] = 0
        job_info["sample_records"] = []
        job_info["status"] = "failed"
        job_info["verification_status"] = "unverified"
        job_info["verification_message"] = "Database offline"
        return job_info

    try:
        db = get_db()
        existing_cols = db.list_collection_names()
        if output_col_name not in existing_cols:
            job_info["document_count"] = 0
            job_info["sample_records"] = []
            job_info["status"] = "missing"
            job_info["verification_status"] = "unverified"
            job_info["verification_message"] = f"Collection '{output_col_name}' does not exist"
            return job_info

        col = db[output_col_name]
        doc_count = col.count_documents({})
        job_info["document_count"] = doc_count

        # Fetch representative sample records and format into clean tabular details
        sample_docs = list(col.find({}, {"_id": 1, "value": 1}).limit(8))
        job_info["sample_records"] = format_mapreduce_samples(sample_docs)

        # Perform actual verification against raw flights collection
        verification = verify_job_integrity(job_id, region=reg)
        job_info["status"] = "healthy" if doc_count > 0 else "warning"
        job_info["verification_status"] = verification["status"]
        job_info["verification_message"] = verification["message"]
        job_info["sum_value"] = verification.get("sum_value")
        job_info["expected_value"] = verification.get("expected_value")

    except Exception as e:
        logger.error(f"Error fetching telemetry for {job_id} in {reg}: {e}")
        job_info["document_count"] = 0
        job_info["sample_records"] = []
        job_info["status"] = "failed"
        job_info["verification_status"] = "failed"
        job_info["verification_message"] = f"Query error: {str(e)}"

    return job_info


def verify_job_integrity(job_id: str, region: Optional[str] = None) -> Dict[str, Any]:
    """
    Independently verify MapReduce output against raw collection.
    Never returns 'verified' unless mathematical consistency is confirmed.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return {"status": "unverified", "message": "Database offline"}

    reg = _resolve_mr_region(region)
    active_jobs = INDIAN_MAPREDUCE_JOBS if reg == "INDIA" else US_MAPREDUCE_JOBS

    try:
        db = get_db()
        job_info = active_jobs.get(job_id)
        if not job_info:
            return {"status": "unverified", "message": "Unknown job"}

        output_col_name = job_info["output_collection"]
        if output_col_name not in db.list_collection_names():
            return {"status": "unverified", "message": f"Output collection {output_col_name} missing"}

        output_col = db[output_col_name]

        if reg == "INDIA":
            expected_total = db.flights_in.count_documents({"is_route_eligible": True})
            if expected_total == 0:
                return {"status": "unverified", "message": "No eligible records found in flights_in"}

            if job_id == "job_a":
                pipeline = [{"$group": {"_id": None, "total": {"$sum": "$value.timetable_services"}}}]
                res = list(output_col.aggregate(pipeline))
                observed = int(res[0]["total"]) if res and "total" in res[0] else 0
                if observed == expected_total:
                    return {
                        "status": "verified",
                        "message": f"Exact match: Materialized services ({observed:,}) equals eligible filings ({expected_total:,})",
                        "sum_value": observed,
                        "expected_value": expected_total,
                    }
                else:
                    return {
                        "status": "mismatch",
                        "message": f"Discrepancy: Materialized services ({observed:,}) != expected ({expected_total:,})",
                        "sum_value": observed,
                        "expected_value": expected_total,
                    }
            elif job_id in ["job_b", "job_c"]:
                field = "$value.outgoing_timetable_services" if job_id == "job_b" else "$value.incoming_timetable_services"
                pipeline = [{"$group": {"_id": None, "total": {"$sum": field}}}]
                res = list(output_col.aggregate(pipeline))
                observed = int(res[0]["total"]) if res and "total" in res[0] else 0
                if observed == expected_total:
                    return {
                        "status": "verified",
                        "message": f"Exact match: Node activity sum ({observed:,}) equals eligible filings ({expected_total:,})",
                        "sum_value": observed,
                        "expected_value": expected_total,
                    }
                else:
                    return {
                        "status": "mismatch",
                        "message": f"Discrepancy: Node activity sum ({observed:,}) != expected ({expected_total:,})",
                        "sum_value": observed,
                        "expected_value": expected_total,
                    }
            elif job_id in ["job_d", "job_e"]:
                doc_cnt = output_col.count_documents({})
                return {
                    "status": "verified",
                    "message": f"Verified: Materialized collection contains {doc_cnt:,} validated documents.",
                    "sum_value": doc_cnt,
                    "expected_value": doc_cnt,
                }

        else:
            # US Path
            expected_total = db.flights.count_documents({
                "$or": [{"is_route_eligible": True}, {"is_eligible_for_route_analysis": True}]
            })
            if expected_total == 0:
                return {"status": "unverified", "message": "No eligible flights found in raw collection"}

            if job_id in ["job_a", "job_b", "job_c", "job_d"]:
                pipeline = [{"$group": {"_id": None, "total": {"$sum": "$value"}}}]
                res = list(output_col.aggregate(pipeline))
                observed_sum = int(res[0]["total"]) if res and "total" in res[0] else 0

                if observed_sum == expected_total:
                    return {
                        "status": "verified",
                        "message": f"Exact match: Output sum ({observed_sum:,}) equals eligible flights ({expected_total:,})",
                        "sum_value": observed_sum,
                        "expected_value": expected_total,
                    }
                else:
                    return {
                        "status": "mismatch",
                        "message": f"Discrepancy: Output sum ({observed_sum:,}) != expected ({expected_total:,})",
                        "sum_value": observed_sum,
                        "expected_value": expected_total,
                    }

            elif job_id == "job_e":
                pipeline = [{"$group": {"_id": None, "total": {"$sum": "$value.count"}}}]
                res = list(output_col.aggregate(pipeline))
                observed_sum = int(res[0]["total"]) if res and "total" in res[0] else 0

                if observed_sum == expected_total:
                    return {
                        "status": "verified",
                        "message": f"Exact match: Connectivity total count ({observed_sum:,}) matches eligible flights ({expected_total:,})",
                        "sum_value": observed_sum,
                        "expected_value": expected_total,
                    }
                else:
                    return {
                        "status": "mismatch",
                        "message": f"Discrepancy: Connectivity sum ({observed_sum:,}) != expected ({expected_total:,})",
                        "sum_value": observed_sum,
                        "expected_value": expected_total,
                    }

    except Exception as e:
        logger.error(f"Verification error on {job_id} in {reg}: {e}")
        return {"status": "failed", "message": f"Verification failed: {str(e)}"}

    return {"status": "unverified", "message": "Unknown verification path"}


def get_all_mapreduce_statuses(region: Optional[str] = None) -> Dict[str, str]:
    """
    Return high-level status ('healthy', 'warning', 'failed') for each job.
    """
    reg = _resolve_mr_region(region)
    active_jobs = INDIAN_MAPREDUCE_JOBS if reg == "INDIA" else US_MAPREDUCE_JOBS

    statuses = {}
    for jid in active_jobs:
        tel = get_job_telemetry(jid, region=reg)
        statuses[jid] = tel.get("status", "failed")
    return statuses
