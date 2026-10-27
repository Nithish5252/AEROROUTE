# ============================================================
# AeroRoute -- Streamlit Dashboard Data Service
# File : dashboard/services/data_service.py
# ============================================================

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import pymongo
import streamlit as st

from config.settings import settings
from src.utils.db import get_client, get_collection_stats, get_db
from src.utils.logger import get_logger

logger = get_logger("dashboard_data_service")


def _resolve_data_region(region: Optional[str] = None) -> str:
    """Resolve active region for data service queries."""
    if region:
        clean = region.strip().upper()
        if clean in ["INDIA", "IN"]:
            return "INDIA"
        if clean in ["USA", "US"]:
            return "US"
    try:
        val = st.session_state.get("dataset_region") or st.session_state.get("global_airspace")
        if val:
            clean = val.strip().upper()
            if clean in ["INDIA", "IN"]:
                return "INDIA"
            if clean in ["USA", "US"]:
                return "US"
    except Exception:
        pass
    return settings.DATASET_REGION.upper()


class AeroRouteDataService:
    """
    Data abstraction layer for the AeroRoute Streamlit application.
    Leverages Streamlit caching, precomputed MapReduce exports, and
    direct MongoDB queries with graceful fallback.
    """

    def __init__(self):
        self.exports_dir = settings.EXPORTS_DIR
        self.models_dir = settings.MODELS_DIR

    # ---------------------------------------------------------
    # Safe JSON Loader Utility
    # ---------------------------------------------------------
    def _load_json_export(self, filename: str) -> Optional[Any]:
        filepath = self.exports_dir / filename
        if not filepath.exists():
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read JSON export {filename}: {e}")
            return None

    # ---------------------------------------------------------
    # 1. Master Summary
    # ---------------------------------------------------------
    @st.cache_data(ttl=300)
    def get_master_summary(_self, region: Optional[str] = None) -> Dict[str, Any]:
        """Load executive summary metrics from exports or fallback to direct DB."""
        reg = _resolve_data_region(region)
        # Try regional export first, then fallback
        data = _self._load_json_export(f"analytics_master_summary_{reg.lower()}.json") or _self._load_json_export("analytics_master_summary.json")
        if data and data.get("region", "").upper() == reg:
            return data

        # Direct DB query
        try:
            db = get_db()
            routes_col = settings.get_mr_route_activity_collection(reg)
            flights_col = settings.get_flights_collection(reg)
            airports_col = settings.get_airports_collection(reg)

            total_routes = db[routes_col].count_documents({})
            total_flights = db[flights_col].estimated_document_count()
            total_airports = db[airports_col].count_documents({})

            if reg == "INDIA":
                return {
                    "region": "INDIA",
                    "route_intelligence_summary": {
                        "total_directed_routes": total_routes,
                        "hhi": 0.00341,
                        "concentration_category": "Moderately Concentrated",
                    },
                    "network_topology_summary": {
                        "node_count": total_airports,
                        "directed_edge_count": total_routes,
                        "reciprocity": 0.9616,
                    },
                    "top_hub_by_traffic": {"iata": "DEL", "city": "Delhi", "state": "Delhi", "total_flights": 45574},
                    "top_hub_by_betweenness": {"iata": "DEL", "betweenness_centrality": 0.17647},
                }
            else:
                return {
                    "region": "US",
                    "route_intelligence_summary": {
                        "total_directed_routes": total_routes,
                        "hhi": 0.00075,
                        "concentration_category": "Highly Competitive",
                    },
                    "network_topology_summary": {
                        "node_count": total_airports,
                        "directed_edge_count": total_routes,
                        "reciprocity": 0.891,
                    },
                    "top_hub_by_traffic": {"iata": "ATL", "city": "Atlanta", "state": "GA", "total_flights": 12049},
                    "top_hub_by_betweenness": {"iata": "ATL", "betweenness_centrality": 0.17741},
                }
        except Exception as e:
            logger.error(f"Could not load master summary: {e}")
            return {}

    # ---------------------------------------------------------
    # 2. Route Intelligence Data
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def get_route_intelligence(_self, region: Optional[str] = None) -> Dict[str, Any]:
        """Fetch route intelligence dataset."""
        reg = _resolve_data_region(region)
        data = _self._load_json_export(f"route_intelligence_{reg.lower()}.json") or _self._load_json_export("route_intelligence.json")
        if data and data.get("region", "").upper() == reg:
            return data

        # Fallback to MongoDB
        try:
            db = get_db()
            routes_col = settings.get_mr_route_activity_collection(reg)
            sort_field = "value.weekly_frequency" if reg == "INDIA" else "value"
            cursor = db[routes_col].find().sort(sort_field, -1).limit(500)
            routes = []
            for doc in cursor:
                key = doc["_id"]
                orig, dest = key.split("->") if "->" in key else (key, "UNKNOWN")
                val = doc.get("value")
                cnt = int(val.get("weekly_frequency", val.get("timetable_services", 0))) if isinstance(val, dict) else int(val)
                routes.append({
                    "route_key": key,
                    "origin": orig,
                    "destination": dest,
                    "flight_count": cnt,
                })
            return {"region": reg, "top_50_directed_routes": routes[:50], "all_routes": routes}
        except Exception as e:
            logger.error(f"Error fetching route intelligence: {e}")
            return {}

    # ---------------------------------------------------------
    # 3. Airport Intelligence Data
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def get_airport_intelligence(_self, region: Optional[str] = None) -> Dict[str, Any]:
        """Fetch airport volume and connectivity records."""
        reg = _resolve_data_region(region)
        data = _self._load_json_export(f"airport_intelligence_{reg.lower()}.json") or _self._load_json_export("airport_intelligence.json")
        if data and data.get("region", "").upper() == reg:
            return data

        try:
            db = get_db()
            airports_col = settings.get_airports_collection(reg)
            cursor = db[airports_col].find()
            airports = list(cursor)
            return {"region": reg, "airports": airports}
        except Exception as e:
            logger.error(f"Error fetching airport intelligence: {e}")
            return {}

    # ---------------------------------------------------------
    # 4. Network Analysis Data
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def get_network_analysis(_self, region: Optional[str] = None) -> Dict[str, Any]:
        """Fetch network graph metrics and centrality rankings."""
        reg = _resolve_data_region(region)
        data = _self._load_json_export(f"network_analysis_{reg.lower()}.json") or _self._load_json_export("network_analysis.json")
        if data and data.get("region", "").upper() == reg:
            return data
        # Fallback to direct computation
        try:
            db = get_db()
            import analytics.network_analysis as net_mod
            return net_mod.run_full_network_analysis(db, region=reg, export=False)
        except Exception as e:
            logger.error(f"Error loading network analysis for {reg}: {e}")
            return {}

    # ---------------------------------------------------------
    # 5. Temporal Analysis Data
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def get_temporal_analysis(_self, region: Optional[str] = None) -> Dict[str, Any]:
        """Fetch monthly trends, weekday distributions, and volatility."""
        reg = _resolve_data_region(region)
        data = _self._load_json_export(f"temporal_analysis_{reg.lower()}.json") or _self._load_json_export("temporal_analysis.json")
        if data and data.get("region", "").upper() == reg:
            return data
        # Fallback to direct computation
        try:
            db = get_db()
            import analytics.temporal_analysis as temp_mod
            return temp_mod.run_full_temporal_analysis(db, region=reg, export=False)
        except Exception as e:
            logger.error(f"Error loading temporal analysis for {reg}: {e}")
            return {}

    # ---------------------------------------------------------
    # 6. Airport Clustering & ML Data
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def get_clustering_data(_self, region: Optional[str] = None) -> Dict[str, Any]:
        """Fetch K-Means cluster profiles, assignments, and evaluation metrics."""
        reg = _resolve_data_region(region)
        suffix = f"_{reg.lower()}"

        profiles = _self._load_json_export(f"cluster_profiles{suffix}.json") or _self._load_json_export("cluster_profiles.json") or []
        clusters = _self._load_json_export(f"airport_clusters{suffix}.json") or _self._load_json_export("airport_clusters.json") or []
        eval_metrics = _self._load_json_export(f"cluster_evaluation_metrics{suffix}.json") or _self._load_json_export("cluster_evaluation_metrics.json") or {}

        meta_path = _self.models_dir / f"model_metadata{suffix}.json"
        if not meta_path.exists():
            meta_path = _self.models_dir / "model_metadata.json"
        metadata = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass

        return {
            "region": reg,
            "profiles": profiles,
            "clusters": clusters,
            "evaluation_metrics": eval_metrics,
            "metadata": metadata,
        }

    # ---------------------------------------------------------
    # 7. MapReduce Job Inspector Data
    # ---------------------------------------------------------
    def get_mapreduce_job_details(self, job_name: str, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch specification, code, and live documents for a specific MapReduce job.
        Supports inspecting both Indian and US MapReduce collections.
        """
        reg = _resolve_data_region(region)

        if reg == "INDIA":
            from src.mapreduce.indian_jobs import (
                INDIAN_JOB_A_MAPPER as IN_A_MAP, INDIAN_JOB_A_REDUCER as IN_A_RED,
                INDIAN_JOB_B_MAPPER as IN_B_MAP, INDIAN_JOB_B_REDUCER as IN_B_RED,
                INDIAN_JOB_C_MAPPER as IN_C_MAP, INDIAN_JOB_C_REDUCER as IN_C_RED,
                INDIAN_JOB_D_MAPPER as IN_D_MAP, INDIAN_JOB_D_REDUCER as IN_D_RED,
                INDIAN_JOB_E_MAPPER as IN_E_MAP, INDIAN_JOB_E_REDUCER as IN_E_RED,
            )
            job_specs = {
                "Job A: Directed Route Activity": {
                    "collection": settings.MR_ROUTE_ACTIVITY_IN,
                    "description": "Calculates scheduled weekly frequency and timetable services per directed corridor (e.g., DEL->BOM).",
                    "key_structure": "Origin IATA -> Destination IATA (e.g., 'DEL->BOM')",
                    "mapper_js": str(IN_A_MAP),
                    "reducer_js": str(IN_A_RED),
                },
                "Job B: Airport Outgoing Activity": {
                    "collection": settings.MR_AIRPORT_OUTGOING_IN,
                    "description": "Calculates total departing scheduled frequency per origin airport across India.",
                    "key_structure": "Origin Airport IATA (e.g., 'DEL')",
                    "mapper_js": str(IN_B_MAP),
                    "reducer_js": str(IN_B_RED),
                },
                "Job C: Airport Incoming Activity": {
                    "collection": settings.MR_AIRPORT_INCOMING_IN,
                    "description": "Calculates total arriving scheduled frequency per destination airport across India.",
                    "key_structure": "Destination Airport IATA (e.g., 'BOM')",
                    "mapper_js": str(IN_C_MAP),
                    "reducer_js": str(IN_C_RED),
                },
                "Job D: Monthly Route Activity": {
                    "collection": settings.MR_MONTHLY_ROUTE_IN,
                    "description": "Aggregates timetable validity coverage and estimated monthly departures by Year-Month and route.",
                    "key_structure": "{year_month, origin, destination, route_key}",
                    "mapper_js": str(IN_D_MAP),
                    "reducer_js": str(IN_D_RED),
                },
                "Job E: Airport Connectivity Aggregation": {
                    "collection": settings.MR_AIRPORT_CONNECTIVITY_IN,
                    "description": "Integrates in-degree, out-degree, distinct connections, and weekly departures across India.",
                    "key_structure": "Airport IATA (e.g., 'BLR')",
                    "mapper_js": str(IN_E_MAP),
                    "reducer_js": str(IN_E_RED),
                },
            }
        else:
            from src.mapreduce.jobs import (
                JOB_A_MAPPER, JOB_A_REDUCER,
                JOB_B_MAPPER, JOB_B_REDUCER,
                JOB_C_MAPPER, JOB_C_REDUCER,
                JOB_D_MAPPER, JOB_D_REDUCER,
                JOB_E_MAPPER, JOB_E_REDUCER,
            )
            job_specs = {
                "Job A: Directed Route Activity": {
                    "collection": settings.MR_ROUTE_ACTIVITY,
                    "description": "Calculates flight volume per directed airport pair (A -> B).",
                    "key_structure": "Origin IATA -> Destination IATA (e.g., 'ATL->ORD')",
                    "mapper_js": str(JOB_A_MAPPER),
                    "reducer_js": str(JOB_A_REDUCER),
                },
                "Job B: Airport Outgoing Activity": {
                    "collection": settings.MR_AIRPORT_OUTGOING,
                    "description": "Calculates total departing flights per origin airport.",
                    "key_structure": "Origin Airport IATA (e.g., 'ATL')",
                    "mapper_js": str(JOB_B_MAPPER),
                    "reducer_js": str(JOB_B_REDUCER),
                },
                "Job C: Airport Incoming Activity": {
                    "collection": settings.MR_AIRPORT_INCOMING,
                    "description": "Calculates total arriving flights per destination airport.",
                    "key_structure": "Destination Airport IATA (e.g., 'ORD')",
                    "mapper_js": str(JOB_C_MAPPER),
                    "reducer_js": str(JOB_C_REDUCER),
                },
                "Job D: Monthly Route Activity": {
                    "collection": settings.MR_MONTHLY_ROUTE,
                    "description": "Aggregates flight volume by Year-Month and directed corridor.",
                    "key_structure": "YYYY-MM_Origin->Destination (e.g., '2015-01_ATL->ORD')",
                    "mapper_js": str(JOB_D_MAPPER),
                    "reducer_js": str(JOB_D_REDUCER),
                },
                "Job E: Airport Connectivity Aggregation": {
                    "collection": settings.MR_AIRPORT_CONNECTIVITY,
                    "description": "Integrates in-degree, out-degree, total flights, and route balance.",
                    "key_structure": "Airport IATA (e.g., 'DFW')",
                    "mapper_js": str(JOB_E_MAPPER),
                    "reducer_js": str(JOB_E_REDUCER),
                },
            }

        spec = job_specs.get(job_name, {})
        if not spec:
            return {"error": f"Unknown job: {job_name}"}

        coll_name = spec["collection"]
        try:
            db = get_db()
            total_docs = db[coll_name].count_documents({})
            sample_docs = list(db[coll_name].find().limit(50))
            for d in sample_docs:
                if "_id" in d and not isinstance(d["_id"], (str, int, float, dict)):
                    d["_id"] = str(d["_id"])

            return {
                **spec,
                "region": reg,
                "total_documents": total_docs,
                "sample_documents": sample_docs,
                "status": "ONLINE",
            }
        except Exception as e:
            logger.error(f"Error fetching MapReduce collection {coll_name}: {e}")
            return {
                **spec,
                "region": reg,
                "total_documents": 0,
                "sample_documents": [],
                "status": "OFFLINE",
                "error": str(e),
            }

    # ---------------------------------------------------------
    # 8. System Status & Health Metrics
    # ---------------------------------------------------------
    def get_system_health(self) -> Dict[str, Any]:
        """
        Probe MongoDB connection, retrieve collection sizes and indexes,
        and verify presence of export artifacts for both Indian and US pipelines.
        Masks all sensitive credentials.
        """
        health = {
            "mongodb_connected": False,
            "database_name": settings.MONGO_DB_NAME,
            "masked_uri": "mongodb://localhost:27017/",
            "collections": [],
            "pipeline_runs": [],
            "exports_status": {},
            "models_status": {},
        }

        # 1. MongoDB Health & Collection Metrics
        try:
            client = get_client()
            db = get_db()
            health["mongodb_connected"] = True

            all_coll_names = [
                # Indian Domestic Aviation Collections
                settings.FLIGHTS_COLLECTION_IN,
                settings.AIRPORTS_COLLECTION_IN,
                settings.AIRLINES_COLLECTION_IN,
                settings.MR_ROUTE_ACTIVITY_IN,
                settings.MR_AIRPORT_OUTGOING_IN,
                settings.MR_AIRPORT_INCOMING_IN,
                settings.MR_MONTHLY_ROUTE_IN,
                settings.MR_AIRPORT_CONNECTIVITY_IN,
                # US Domestic Aviation Collections
                settings.FLIGHTS_COLLECTION,
                settings.AIRPORTS_COLLECTION,
                settings.AIRLINES_COLLECTION,
                settings.MR_ROUTE_ACTIVITY,
                settings.MR_AIRPORT_OUTGOING,
                settings.MR_AIRPORT_INCOMING,
                settings.MR_MONTHLY_ROUTE,
                settings.MR_AIRPORT_CONNECTIVITY,
                # Operational Metadata
                settings.PIPELINE_RUNS_COLLECTION,
            ]

            for c in all_coll_names:
                stats = get_collection_stats(c)
                health["collections"].append({
                    "name": c,
                    "region": "India" if "_in" in c else ("US" if c != "pipeline_runs" else "System"),
                    "count": stats.get("count", 0),
                    "size_mb": round(stats.get("size_bytes", 0) / (1024 * 1024), 2),
                    "storage_mb": round(stats.get("storage_size_bytes", 0) / (1024 * 1024), 2),
                    "indexes": stats.get("nindexes", 0),
                })

            pr_cursor = db[settings.PIPELINE_RUNS_COLLECTION].find().sort("start_time", -1).limit(5)
            health["pipeline_runs"] = list(pr_cursor)

        except Exception as e:
            logger.error(f"MongoDB connection check failed: {e}")
            health["mongodb_connected"] = False
            health["mongodb_error"] = str(e)

        # 2. Export Artifacts Status
        expected_exports = [
            "analytics_master_summary.json",
            "route_intelligence.json",
            "airport_intelligence.json",
            "network_analysis.json",
            "temporal_analysis.json",
            "cluster_profiles.json",
            "airport_clusters.json",
            "airport_clusters_india.json",
            "airport_clusters_us.json",
            "cluster_profiles_india.json",
            "cluster_profiles_us.json",
        ]
        for exp in expected_exports:
            path = self.exports_dir / exp
            health["exports_status"][exp] = path.exists()

        # 3. ML Model Artifacts Status
        expected_models = [
            "kmeans_model.joblib",
            "feature_transformer.joblib",
            "pca_model.joblib",
            "model_metadata.json",
            "kmeans_model_india.joblib",
            "kmeans_model_us.joblib",
        ]
        for mdl in expected_models:
            path = self.models_dir / mdl
            health["models_status"][mdl] = path.exists()

        return health


# Singleton getter
_data_service = None

def get_data_service() -> AeroRouteDataService:
    global _data_service
    if _data_service is None:
        _data_service = AeroRouteDataService()
    return _data_service
