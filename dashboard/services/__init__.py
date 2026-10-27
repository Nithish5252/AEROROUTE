# ============================================================
# AeroRoute -- Dashboard Services Package
# File : dashboard/services/__init__.py
# ============================================================

from dashboard.services.database import (
    get_mongo_client,
    get_db,
    get_collection,
    check_connection,
    get_collection_counts,
)
from dashboard.services.mapreduce_service import (
    get_mapreduce_job_definitions,
    get_job_telemetry,
    verify_job_integrity,
    get_all_mapreduce_statuses,
)
from dashboard.services.analytics_service import (
    get_route_spotlight,
    get_top_directed_routes,
    get_route_concentration_metrics,
    get_route_detail,
    get_monthly_route_activity,
    get_weekday_route_activity,
    get_top_airports,
    get_airport_profile,
    get_airport_network_graph,
    get_airport_centrality_metrics,
    get_monthly_flight_distribution,
    get_weekday_flight_distribution,
    get_month_weekday_matrix,
)
from dashboard.services.ml_service import (
    get_clustering_metadata,
    get_cluster_results_dataframe,
    get_cluster_profiles_summary,
    get_pca_projection_data,
)

__all__ = [
    "get_mongo_client",
    "get_db",
    "get_collection",
    "check_connection",
    "get_collection_counts",
    "get_mapreduce_job_definitions",
    "get_job_telemetry",
    "verify_job_integrity",
    "get_all_mapreduce_statuses",
    "get_route_spotlight",
    "get_top_directed_routes",
    "get_route_concentration_metrics",
    "get_route_detail",
    "get_monthly_route_activity",
    "get_weekday_route_activity",
    "get_top_airports",
    "get_airport_profile",
    "get_airport_network_graph",
    "get_airport_centrality_metrics",
    "get_monthly_flight_distribution",
    "get_weekday_flight_distribution",
    "get_month_weekday_matrix",
    "get_clustering_metadata",
    "get_cluster_results_dataframe",
    "get_cluster_profiles_summary",
    "get_pca_projection_data",
]
