# ============================================================
# AeroRoute -- Flight Operations Console Analytics Service
# File : dashboard/services/analytics_service.py
# ============================================================

import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import networkx as nx

from config.settings import settings
from dashboard.services.database import get_db, check_connection
import analytics.network_analysis as net_analytics
import analytics.temporal_analysis as temp_analytics

logger = logging.getLogger("aeroroute.analytics_service")


def _resolve_region(airspace: Optional[str] = None, region: Optional[str] = None) -> str:
    """Resolve regional identifier to 'INDIA' or 'US'."""
    target = region or airspace
    if target:
        clean = str(target).strip().upper()
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


# ------------------------------------------------------------
# Route Intelligence
# ------------------------------------------------------------

def get_route_spotlight(
    airspace: Optional[str] = None,
    origin: Optional[str] = None,
    dest: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the busiest directed route, its reverse-direction activity, and share of total.
    Pulls live data from MongoDB MapReduce collections based on selected region.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return {}

    reg = _resolve_region(airspace, region)
    db = get_db()
    routes_col = settings.get_mr_route_activity_collection(reg)

    try:
        query: Dict[str, Any] = {}
        if origin and origin != "All Airports" and dest and dest != "All Airports":
            query["_id"] = f"{origin}->{dest}"
        elif origin and origin != "All Airports":
            query["_id"] = {"$regex": f"^{origin}->"}
        elif dest and dest != "All Airports":
            query["_id"] = {"$regex": f"->{dest}$"}

        sort_field = "value.weekly_frequency" if reg == "INDIA" else "value"
        cursor = db[routes_col].find(query).sort(sort_field, -1).limit(1)
        top_list = list(cursor)
        if not top_list:
            top_list = list(db[routes_col].find().sort(sort_field, -1).limit(1))
            if not top_list:
                return {}

        top_doc = top_list[0]
        busiest_key = top_doc["_id"]
        orig_val, dest_val = busiest_key.split("->", 1) if "->" in busiest_key else (busiest_key, "UNKNOWN")

        val = top_doc.get("value")
        if isinstance(val, dict):
            volume = int(val.get("weekly_frequency", val.get("timetable_services", 0)))
        else:
            volume = int(val) if val is not None else 0

        reverse_key = f"{dest_val}->{orig_val}"
        rev_doc = db[routes_col].find_one({"_id": reverse_key})
        if rev_doc:
            rev_val = rev_doc.get("value")
            if isinstance(rev_val, dict):
                reverse_volume = int(rev_val.get("weekly_frequency", rev_val.get("timetable_services", 0)))
            else:
                reverse_volume = int(rev_val) if rev_val is not None else 0
        else:
            reverse_volume = 0

        # Total network flights / weekly frequency
        if reg == "INDIA":
            total_flights = 183324  # Total weekly scheduled frequency
            share_pct = round(volume / total_flights * 100, 2)
            region_title = "Indian Civil Aviation Route Spotlight"
            region_scope = "weekly scheduled flights"
        else:
            total_flights = db.flights.count_documents({
                "$or": [{"is_route_eligible": True}, {"is_eligible_for_route_analysis": True}]
            })
            share_pct = round(volume / total_flights * 100, 2) if total_flights > 0 else 0.0
            region_title = "National US Route Spotlight"
            region_scope = "total eligible US operated flights"

        return {
            "route_key": busiest_key,
            "origin": orig_val,
            "dest": dest_val,
            "volume": volume,
            "reverse_key": reverse_key,
            "reverse_volume": reverse_volume,
            "asymmetry_delta": abs(volume - reverse_volume),
            "share_pct": share_pct,
            "total_flights": total_flights,
            "region_title": region_title,
            "region_scope": region_scope,
            "region": reg,
        }
    except Exception as e:
        logger.error(f"Error computing route spotlight: {e}")
        return {}


def get_top_directed_routes(
    limit: int = 10,
    origin: Optional[str] = None,
    dest: Optional[str] = None,
    airspace: Optional[str] = None,
    region: Optional[str] = None,
) -> pd.DataFrame:
    """
    Retrieve top directed routes sorted by volume descending.
    Pulls live data from regional MongoDB MapReduce collections.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(columns=["route_key", "origin", "destination", "flights"])

    reg = _resolve_region(airspace, region)
    db = get_db()
    routes_col = settings.get_mr_route_activity_collection(reg)

    try:
        query: Dict[str, Any] = {}
        if origin and dest and origin != "All Airports" and dest != "All Airports":
            query["_id"] = f"{origin}->{dest}"
        elif origin and origin != "All Airports":
            query["_id"] = {"$regex": f"^{origin}->"}
        elif dest and dest != "All Airports":
            query["_id"] = {"$regex": f"->{dest}$"}

        sort_field = "value.weekly_frequency" if reg == "INDIA" else "value"
        cursor = db[routes_col].find(query).sort(sort_field, -1).limit(limit)

        records = []
        for doc in cursor:
            k = doc["_id"]
            orig, dst = k.split("->", 1) if "->" in k else (k, "UNKNOWN")
            val = doc.get("value")
            if isinstance(val, dict):
                f_count = int(val.get("weekly_frequency", val.get("timetable_services", 0)))
                timetable_srv = int(val.get("timetable_services", 0))
                carrier_cnt = int(val.get("carrier_count", 0))
                dist = float(val.get("distance_km", 0.0))
            else:
                f_count = int(val) if val is not None else 0
                timetable_srv = f_count
                carrier_cnt = 0
                dist = 0.0

            records.append({
                "route_key": k,
                "origin": orig,
                "destination": dst,
                "flights": f_count,
                "weekly_frequency": f_count,
                "timetable_services": timetable_srv,
                "carrier_count": carrier_cnt,
                "distance_km": dist,
            })
        return pd.DataFrame(records)
    except Exception as e:
        logger.error(f"Error fetching top directed routes for {reg}: {e}")
        return pd.DataFrame(columns=["route_key", "origin", "destination", "flights"])


def get_route_concentration_metrics(airspace: Optional[str] = None, region: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate Herfindahl-Hirschman Index (HHI) and top-10 share from regional mr_route_activity.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return {}

    reg = _resolve_region(airspace, region)
    db = get_db()
    routes_col = settings.get_mr_route_activity_collection(reg)

    try:
        cursor = db[routes_col].find({}, {"value": 1})
        volumes = []
        for doc in cursor:
            v = doc.get("value")
            if isinstance(v, dict):
                volumes.append(float(v.get("weekly_frequency", v.get("timetable_services", 0))))
            else:
                volumes.append(float(v) if v is not None else 0.0)

        if not volumes:
            return {}

        total_vol = sum(volumes)
        if total_vol == 0:
            return {}

        shares = [v / total_vol for v in volumes]
        hhi = sum(s ** 2 for s in shares)

        sorted_vols = sorted(volumes, reverse=True)
        top_10_vol = sum(sorted_vols[:10])
        top_10_share = (top_10_vol / total_vol) * 100

        return {
            "region": reg,
            "hhi": round(hhi, 5),
            "hhi_category": "Highly Decentralized" if hhi < 0.01 else "Moderately Concentrated",
            "top_10_share_pct": round(top_10_share, 2),
            "total_routes": len(volumes),
            "total_flights": int(total_vol),
        }
    except Exception as e:
        logger.error(f"Error calculating route concentration for {reg}: {e}")
        return {}


def get_route_detail(origin: str, dest: str, airspace: Optional[str] = None, region: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Detailed operational summary for a specific directed corridor.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return None

    reg = _resolve_region(airspace, region)
    db = get_db()
    routes_col = settings.get_mr_route_activity_collection(reg)

    try:
        route_key = f"{origin}->{dest}"
        doc = db[routes_col].find_one({"_id": route_key})
        if not doc:
            volume = 0
            distance_km = 0.0
        else:
            val = doc.get("value")
            if isinstance(val, dict):
                volume = int(val.get("weekly_frequency", val.get("timetable_services", 0)))
                distance_km = float(val.get("distance_km", 0.0))
            else:
                volume = int(val) if val is not None else 0
                distance_km = 0.0

        # Reverse corridor
        rev_key = f"{dest}->{origin}"
        rev_doc = db[routes_col].find_one({"_id": rev_key})
        if not rev_doc:
            rev_volume = 0
        else:
            rev_val = rev_doc.get("value")
            if isinstance(rev_val, dict):
                rev_volume = int(rev_val.get("weekly_frequency", rev_val.get("timetable_services", 0)))
            else:
                rev_volume = int(rev_val) if rev_val is not None else 0

        # Carrier breakdown
        if reg == "INDIA":
            carrier_pipeline = [
                {"$match": {"origin": origin, "destination": dest}},
                {"$group": {"_id": "$airline_code", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            carrier_res = list(db.flights_in.aggregate(carrier_pipeline))
        else:
            carrier_pipeline = [
                {"$match": {
                    "$or": [
                        {"route_key": route_key},
                        {"origin.iata": origin, "destination.iata": dest},
                        {"origin_airport": origin, "destination_airport": dest},
                    ],
                    "$and": [{"$or": [{"is_route_eligible": True}, {"is_eligible_for_route_analysis": True}]}],
                }},
                {"$group": {"_id": {"$ifNull": ["$airline_code", "$carrier"]}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            carrier_res = list(db.flights.aggregate(carrier_pipeline))

        carriers = [{"carrier": c["_id"], "count": c["count"]} for c in carrier_res if c.get("_id")]

        return {
            "route_key": route_key,
            "origin": origin,
            "dest": dest,
            "volume": volume,
            "reverse_key": rev_key,
            "reverse_volume": rev_volume,
            "asymmetry_delta": abs(volume - rev_volume),
            "carriers": carriers,
            "distance_km": distance_km,
            "region": reg,
        }
    except Exception as e:
        logger.error(f"Error fetching route detail for {origin}->{dest}: {e}")
        return None


def get_monthly_route_activity(origin: str, dest: str, airspace: Optional[str] = None, region: Optional[str] = None) -> pd.DataFrame:
    """
    Retrieve month-by-month flight counts for a specific corridor from mr_monthly_route.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(columns=["month_label", "flights"])

    reg = _resolve_region(airspace, region)
    db = get_db()
    monthly_col = settings.get_mr_monthly_route_collection(reg)

    try:
        route_key = f"{origin}->{dest}"
        records = []
        if reg == "INDIA":
            cursor = db[monthly_col].find({"_id.route_key": route_key})
            for doc in cursor:
                k = doc["_id"]
                val = doc.get("value")
                cnt = int(val.get("estimated_monthly_departures", val.get("weekly_frequency", 1))) if isinstance(val, dict) else int(val)
                records.append({
                    "month_label": k.get("year_month"),
                    "flights": cnt,
                })
        else:
            pattern = f"_{origin}->{dest}$"
            cursor = db[monthly_col].find({"_id": {"$regex": pattern}})
            for doc in cursor:
                k = doc["_id"]
                month_part = k.split("_")[0] if "_" in k else k
                records.append({
                    "month_label": month_part,
                    "flights": int(doc["value"]),
                })

        df = pd.DataFrame(records)
        if not df.empty:
            df = df.sort_values("month_label")
        return df
    except Exception as e:
        logger.error(f"Error fetching monthly route activity for {origin}->{dest}: {e}")
        return pd.DataFrame(columns=["month_label", "flights"])


def get_weekday_route_activity(origin: str, dest: str, airspace: Optional[str] = None, region: Optional[str] = None) -> pd.DataFrame:
    """
    Retrieve day-of-week flight counts for a specific corridor.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(columns=["day_name", "day_of_week", "flights"])

    reg = _resolve_region(airspace, region)
    db = get_db()
    day_map = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

    try:
        if reg == "INDIA":
            pipeline = [
                {"$match": {"origin": origin, "destination": dest}},
                {"$unwind": "$days_of_week"},
                {"$group": {"_id": "$days_of_week", "flights": {"$sum": 1}}},
            ]
            res = list(db.flights_in.aggregate(pipeline))
            name_to_num = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5, "Saturday": 6, "Sunday": 7}
            records = []
            for r in res:
                d_name = r["_id"]
                dow = name_to_num.get(d_name, 1)
                records.append({
                    "day_of_week": dow,
                    "day_name": day_map.get(dow, str(dow)),
                    "flights": int(r["flights"]),
                })
        else:
            pipeline = [
                {"$match": {
                    "$or": [
                        {"route_key": f"{origin}->{dest}"},
                        {"origin.iata": origin, "destination.iata": dest},
                        {"origin_airport": origin, "destination_airport": dest},
                    ],
                    "$and": [{"$or": [{"is_route_eligible": True}, {"is_eligible_for_route_analysis": True}]}],
                }},
                {"$group": {"_id": "$day_of_week", "flights": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]
            res = list(db.flights.aggregate(pipeline))
            records = []
            for r in res:
                dow = r["_id"]
                records.append({
                    "day_of_week": dow,
                    "day_name": day_map.get(dow, f"Day {dow}"),
                    "flights": int(r["flights"]),
                })

        df = pd.DataFrame(records)
        if not df.empty:
            df = df.sort_values("day_of_week")
        return df
    except Exception as e:
        logger.error(f"Error fetching weekday route activity for {origin}->{dest}: {e}")
        return pd.DataFrame(columns=["day_name", "day_of_week", "flights"])


# ------------------------------------------------------------
# Airport Network Intelligence
# ------------------------------------------------------------

def get_top_airports(
    by: str = "total",
    limit: int = 15,
    airspace: Optional[str] = None,
    region: Optional[str] = None,
) -> pd.DataFrame:
    """
    Retrieve top airports ranked by total activity, outgoing flights, or incoming flights.
    Dynamically queries MongoDB MapReduce collections based on selected region.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(columns=["airport", "flights"])

    reg = _resolve_region(airspace, region)
    db = get_db()

    outgoing_col = settings.get_mr_airport_outgoing_collection(reg)
    incoming_col = settings.get_mr_airport_incoming_collection(reg)
    conn_col = settings.get_mr_airport_connectivity_collection(reg)

    try:
        if reg == "INDIA":
            if by == "outgoing":
                cursor = db[outgoing_col].find().sort("value.weekly_frequency", -1).limit(limit)
                records = [{"airport": d["_id"], "flights": int(d["value"].get("weekly_frequency", 0))} for d in cursor]
                return pd.DataFrame(records)
            elif by == "incoming":
                cursor = db[incoming_col].find().sort("value.weekly_frequency", -1).limit(limit)
                records = [{"airport": d["_id"], "flights": int(d["value"].get("weekly_frequency", 0))} for d in cursor]
                return pd.DataFrame(records)
            else:
                cursor = db[conn_col].find().sort("value.total_weekly_frequency", -1).limit(limit)
                records = []
                for d in cursor:
                    val = d.get("value", {})
                    out_f = int(val.get("outgoing_weekly_frequency", 0))
                    in_f = int(val.get("incoming_weekly_frequency", 0))
                    tot_f = int(val.get("total_weekly_frequency", out_f + in_f))
                    records.append({
                        "airport": d["_id"],
                        "outgoing": out_f,
                        "incoming": in_f,
                        "total_flights": tot_f,
                        "flights": tot_f,
                    })
                return pd.DataFrame(records)

        # US Path
        if by == "outgoing":
            cursor = db[outgoing_col].find().sort("value", -1).limit(limit)
            return pd.DataFrame([{"airport": d["_id"], "flights": int(d["value"])} for d in cursor])
        elif by == "incoming":
            cursor = db[incoming_col].find().sort("value", -1).limit(limit)
            return pd.DataFrame([{"airport": d["_id"], "flights": int(d["value"])} for d in cursor])
        else:
            out_docs = {d["_id"]: int(d["value"]) for d in db[outgoing_col].find()}
            in_docs = {d["_id"]: int(d["value"]) for d in db[incoming_col].find()}
            all_airports = set(out_docs.keys()).union(in_docs.keys())

            totals = []
            for apt in all_airports:
                out_f = out_docs.get(apt, 0)
                in_f = in_docs.get(apt, 0)
                totals.append({
                    "airport": apt,
                    "outgoing": out_f,
                    "incoming": in_f,
                    "total_flights": out_f + in_f,
                    "flights": out_f + in_f,
                })
            df = pd.DataFrame(totals)
            if not df.empty:
                df = df.sort_values("total_flights", ascending=False).head(limit)
            return df
    except Exception as e:
        logger.error(f"Error fetching top airports by {by} for {reg}: {e}")
        return pd.DataFrame(columns=["airport", "flights"])


def get_airport_profile(iata: str, airspace: Optional[str] = None, region: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve detailed operational and topological profile for a single airport.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return None

    reg = _resolve_region(airspace, region)
    db = get_db()

    airports_col = settings.get_airports_collection(reg)
    outgoing_col = settings.get_mr_airport_outgoing_collection(reg)
    incoming_col = settings.get_mr_airport_incoming_collection(reg)
    conn_col = settings.get_mr_airport_connectivity_collection(reg)

    try:
        if reg == "INDIA":
            apt_doc = db[airports_col].find_one({"$or": [{"iata": iata}, {"_id": iata}]}) or {}
            conn_doc = db[conn_col].find_one({"_id": iata}) or {}
            c_val = conn_doc.get("value", {})

            outgoing = int(c_val.get("outgoing_weekly_frequency", 0))
            incoming = int(c_val.get("incoming_weekly_frequency", 0))
            total = int(c_val.get("total_weekly_frequency", outgoing + incoming))
            out_degree = int(c_val.get("out_degree", 0))
            in_degree = int(c_val.get("in_degree", 0))
            destinations = c_val.get("neighbor_airports", [])

            return {
                "iata": iata,
                "name": apt_doc.get("name", f"{iata} Airport"),
                "city": apt_doc.get("city", "—"),
                "state": apt_doc.get("state", "—"),
                "country": "India",
                "latitude": apt_doc.get("lat"),
                "longitude": apt_doc.get("lon"),
                "outgoing_flights": outgoing,
                "incoming_flights": incoming,
                "total_flights": total,
                "out_degree": out_degree,
                "in_degree": in_degree,
                "destinations_sample": destinations[:10],
                "region": reg,
            }

        # US Path
        apt_doc = db[airports_col].find_one({"iata_code": iata}) or {}
        out_doc = db[outgoing_col].find_one({"_id": iata})
        in_doc = db[incoming_col].find_one({"_id": iata})
        conn_doc = db[conn_col].find_one({"_id": iata})

        outgoing = int(out_doc["value"]) if out_doc else 0
        incoming = int(in_doc["value"]) if in_doc else 0
        destinations = conn_doc.get("value", {}).get("destinations", []) if conn_doc else []
        inbound_origins = db.flights.distinct("origin_airport", {"destination_airport": iata, "is_eligible_for_route_analysis": True})

        return {
            "iata": iata,
            "name": apt_doc.get("airport_name", f"{iata} Airport"),
            "city": apt_doc.get("city", "—"),
            "state": apt_doc.get("state", "—"),
            "country": apt_doc.get("country", "USA"),
            "latitude": apt_doc.get("latitude"),
            "longitude": apt_doc.get("longitude"),
            "outgoing_flights": outgoing,
            "incoming_flights": incoming,
            "total_flights": outgoing + incoming,
            "out_degree": len(destinations),
            "in_degree": len(inbound_origins),
            "destinations_sample": destinations[:10],
            "region": reg,
        }
    except Exception as e:
        logger.error(f"Error fetching airport profile for {iata} in {reg}: {e}")
        return None


def get_airport_network_graph(
    top_n: int = 30,
    airspace: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract a sub-graph of top airports and connecting directed edges for Plotly visualization.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(), pd.DataFrame()

    reg = _resolve_region(airspace, region)
    db = get_db()
    routes_col = settings.get_mr_route_activity_collection(reg)
    airports_col = settings.get_airports_collection(reg)

    try:
        top_df = get_top_airports(by="total", limit=top_n, airspace=reg)
        if top_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        top_airports = set(top_df["airport"].tolist())

        edges = []
        cursor = db[routes_col].find()
        for doc in cursor:
            k = doc["_id"]
            if "->" in k:
                u, v = k.split("->", 1)
                if u in top_airports and v in top_airports:
                    val = doc.get("value")
                    weight = int(val.get("weekly_frequency", 1)) if isinstance(val, dict) else int(val)
                    edges.append({
                        "source": u,
                        "target": v,
                        "weight": weight,
                    })

        nodes = []
        for _, row in top_df.iterrows():
            apt = row["airport"]
            if reg == "INDIA":
                doc = db[airports_col].find_one({"$or": [{"iata": apt}, {"_id": apt}]}) or {}
                nodes.append({
                    "airport": apt,
                    "name": doc.get("name", apt),
                    "total_flights": int(row["total_flights"]),
                    "latitude": doc.get("lat"),
                    "longitude": doc.get("lon"),
                })
            else:
                doc = db[airports_col].find_one({"iata_code": apt}) or {}
                nodes.append({
                    "airport": apt,
                    "name": doc.get("airport_name", apt),
                    "total_flights": int(row["total_flights"]),
                    "latitude": doc.get("latitude"),
                    "longitude": doc.get("longitude"),
                })

        return pd.DataFrame(nodes), pd.DataFrame(edges)
    except Exception as e:
        logger.error(f"Error generating network graph for {reg}: {e}")
        return pd.DataFrame(), pd.DataFrame()


def get_airport_centrality_metrics(airspace: Optional[str] = None, region: Optional[str] = None) -> pd.DataFrame:
    """
    Compute NetworkX Betweenness, Degree, and PageRank metrics from mr_route_activity edges.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame()

    reg = _resolve_region(airspace, region)
    db = get_db()

    try:
        G = net_analytics.build_airport_directed_graph(db, region=reg)
        if G.number_of_nodes() == 0:
            return pd.DataFrame()

        df = net_analytics.compute_centrality_metrics(G)
        if not df.empty:
            df["airport"] = df["iata"]
        return df
    except Exception as e:
        logger.error(f"Error computing centrality metrics for {reg}: {e}")
        return pd.DataFrame()


# ------------------------------------------------------------
# Temporal Intelligence
# ------------------------------------------------------------

def get_monthly_flight_distribution(airspace: Optional[str] = None, region: Optional[str] = None) -> pd.DataFrame:
    """
    Retrieve monthly aggregate flight volume across the network.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(columns=["month", "flights"])

    reg = _resolve_region(airspace, region)
    db = get_db()

    try:
        df = temp_analytics.get_monthly_flight_activity(db, region=reg)
        if not df.empty:
            df["flights"] = df["operated_flights"]
            df["month_num"] = df["month"]
        return df
    except Exception as e:
        logger.error(f"Error fetching monthly flight distribution for {reg}: {e}")
        return pd.DataFrame(columns=["month", "flights"])


def get_weekday_flight_distribution(airspace: Optional[str] = None, region: Optional[str] = None) -> pd.DataFrame:
    """
    Retrieve network-wide flight operations distribution by day of week.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame(columns=["day_name", "day_of_week", "flights"])

    reg = _resolve_region(airspace, region)
    db = get_db()

    try:
        res = temp_analytics.get_weekday_activity(db, region=reg)
        days = res.get("days", [])
        df = pd.DataFrame(days)
        if not df.empty:
            df["flights"] = df["flight_count"]
        return df
    except Exception as e:
        logger.error(f"Error fetching weekday flight distribution for {reg}: {e}")
        return pd.DataFrame(columns=["day_name", "day_of_week", "flights"])


def get_month_weekday_matrix(airspace: Optional[str] = None, region: Optional[str] = None) -> pd.DataFrame:
    """
    Cross-tabulate flight counts by Month vs. Day of Week for heatmap visualization.
    """
    is_conn, _ = check_connection()
    if not is_conn:
        return pd.DataFrame()

    reg = _resolve_region(airspace, region)
    db = get_db()
    month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

    try:
        if reg == "INDIA":
            pipeline = [
                {"$unwind": "$days_of_week"},
                {"$group": {
                    "_id": {"month": "$month", "dow": "$days_of_week"},
                    "flights": {"$sum": 1}
                }},
                {"$sort": {"_id.month": 1}}
            ]
            res = list(db.flights_in.aggregate(pipeline))
            name_to_abbr = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
            rows = []
            for item in res:
                m = item["_id"]["month"]
                d = item["_id"]["dow"]
                rows.append({
                    "Month": month_names.get(m, f"M{m}"),
                    "Weekday": name_to_abbr.get(d, str(d)),
                    "Flights": item["flights"]
                })
        else:
            pipeline = [
                {"$match": {"$or": [{"is_route_eligible": True}, {"is_eligible_for_route_analysis": True}]}},
                {"$group": {
                    "_id": {"month": "$month", "dow": "$day_of_week"},
                    "flights": {"$sum": 1}
                }},
                {"$sort": {"_id.month": 1, "_id.dow": 1}}
            ]
            res = list(db.flights.aggregate(pipeline))
            rows = []
            for item in res:
                m = item["_id"]["month"]
                d = item["_id"]["dow"]
                rows.append({
                    "Month": month_names.get(m, f"M{m}"),
                    "Weekday": day_names.get(d, f"D{d}"),
                    "Flights": item["flights"]
                })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        pivot_df = df.pivot(index="Weekday", columns="Month", values="Flights").fillna(0)
        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        pivot_df = pivot_df.reindex([d for d in weekday_order if d in pivot_df.index])
        return pivot_df
    except Exception as e:
        logger.error(f"Error fetching month-weekday matrix for {reg}: {e}")
        return pd.DataFrame()
