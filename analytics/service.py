# ============================================================
# AeroRoute -- Central Analytics Service & Exporter
# File : analytics/service.py
# Usage: python -m analytics.service
#        python analytics/service.py
# ============================================================

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymongo
from analytics.airport_analysis import run_full_airport_analysis
from analytics.network_analysis import run_full_network_analysis
from analytics.route_analysis import run_full_route_analysis
from analytics.temporal_analysis import run_full_temporal_analysis
from analytics.utils import safe_export_json
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("analytics_service")


class AeroRouteAnalyticsService:
    """
    Unified analytics facade providing orchestrated access and caching
    for Route, Airport, Temporal, and Network Graph intelligence.
    """

    def __init__(self, db: Optional[pymongo.database.Database] = None):
        self.db = db if db is not None else get_db()
        self._route_cache: Optional[Dict[str, Any]] = None
        self._airport_cache: Optional[Dict[str, Any]] = None
        self._temporal_cache: Optional[Dict[str, Any]] = None
        self._network_cache: Optional[Dict[str, Any]] = None

    def get_route_intelligence(self, refresh: bool = False, export: bool = False) -> Dict[str, Any]:
        """Fetch route intelligence summary, frequency distribution, and top pairs."""
        if self._route_cache is None or refresh:
            self._route_cache = run_full_route_analysis(self.db, export=export)
        return self._route_cache

    def get_airport_intelligence(self, refresh: bool = False, export: bool = False) -> Dict[str, Any]:
        """Fetch airport volume rankings, distinct connections, and hub profiles."""
        if self._airport_cache is None or refresh:
            self._airport_cache = run_full_airport_analysis(self.db, export=export)
        return self._airport_cache

    def get_temporal_intelligence(self, refresh: bool = False, export: bool = False) -> Dict[str, Any]:
        """Fetch monthly volume, weekday distribution, and volatility anomalies."""
        if self._temporal_cache is None or refresh:
            self._temporal_cache = run_full_temporal_analysis(self.db, export=export)
        return self._temporal_cache

    def get_network_intelligence(self, refresh: bool = False, export: bool = False) -> Dict[str, Any]:
        """Fetch graph summary statistics, centrality metrics, and hub rankings."""
        if self._network_cache is None or refresh:
            self._network_cache = run_full_network_analysis(self.db, export=export)
        return self._network_cache

    def run_all_analytics(self, export: bool = True) -> Dict[str, Any]:
        """
        Execute full Phase 6 analytics pipeline across all four domains.
        Saves all machine-readable artifacts to data/exports/ for downstream consumption.
        """
        start_time = time.time()
        logger.info("=======================================================")
        logger.info("  AeroRoute -- Executing Complete Phase 6 Analytics Suite")
        logger.info("=======================================================")

        route_res = self.get_route_intelligence(refresh=True, export=export)
        airport_res = self.get_airport_intelligence(refresh=True, export=export)
        temporal_res = self.get_temporal_intelligence(refresh=True, export=export)
        network_res = self.get_network_intelligence(refresh=True, export=export)

        elapsed = time.time() - start_time

        master_summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "execution_duration_seconds": round(elapsed, 2),
            "route_intelligence_summary": route_res.get("summary", {}),
            "network_topology_summary": network_res.get("network_summary", {}),
            "temporal_activity_summary": temporal_res.get("weekday_activity", {}).get("summary", {}),
            "top_hub_by_betweenness": network_res.get("top_10_betweenness_hubs", [{}])[0],
            "top_hub_by_traffic": airport_res.get("top_activity_airports", [{}])[0],
        }

        if export:
            master_export_path = settings.EXPORTS_DIR / "analytics_master_summary.json"
            safe_export_json(master_summary, master_export_path)

        logger.info(f"Phase 6 Analytics completed in {elapsed:.2f} seconds.")
        return master_summary


def main():
    service = AeroRouteAnalyticsService()
    summary = service.run_all_analytics(export=True)

    print("\n" + "=" * 78)
    print("  AEROROUTE BIG DATA ANALYTICS MASTER SUMMARY (PHASE 6)")
    print("=" * 78)
    print(f"  Execution Wall Time      : {summary['execution_duration_seconds']}s")
    r_sum = summary["route_intelligence_summary"]
    print(f"  Total Directed Routes    : {r_sum.get('total_directed_routes'):,}")
    print(f"  Route HHI Concentration  : {r_sum.get('hhi')} ({r_sum.get('concentration_category')})")
    n_sum = summary["network_topology_summary"]
    print(f"  Network Topology Nodes   : {n_sum.get('node_count'):,} airports")
    print(f"  Network Directed Edges   : {n_sum.get('directed_edge_count'):,} corridors")
    print(f"  Network Reciprocity      : {n_sum.get('reciprocity')} (High Two-Way Symmetry)")
    top_traffic = summary["top_hub_by_traffic"]
    print(f"  Busiest Airport Hub      : {top_traffic.get('iata')} ({top_traffic.get('city')}, {top_traffic.get('state')}) - {top_traffic.get('total_flights'):,} flights")
    top_betweenness = summary["top_hub_by_betweenness"]
    print(f"  Key Network Bridge Hub   : {top_betweenness.get('iata')} (Betweenness: {top_betweenness.get('betweenness_centrality')})")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
