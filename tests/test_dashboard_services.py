# ============================================================
# AeroRoute -- Test Suite: Dashboard Services
# File : tests/test_dashboard_services.py
# ============================================================

import pytest
import pandas as pd

from dashboard.services.database import check_connection, get_collection_counts
from dashboard.services.mapreduce_service import (
    get_mapreduce_job_definitions,
    get_job_telemetry,
    verify_job_integrity,
)
from dashboard.services.analytics_service import (
    get_top_directed_routes,
    get_route_spotlight,
    get_route_concentration_metrics,
    get_top_airports,
    get_monthly_flight_distribution,
    get_weekday_flight_distribution,
)
from dashboard.services.ml_service import (
    get_clustering_metadata,
    get_cluster_profiles_summary,
    get_cluster_results_dataframe,
)


def test_database_connection_check():
    """Verify check_connection returns a boolean and status message."""
    is_conn, msg = check_connection()
    assert isinstance(is_conn, bool)
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_database_collection_counts():
    """Verify collection counts dict contains all expected collections."""
    counts = get_collection_counts()
    assert isinstance(counts, dict)
    expected_cols = [
        "flights",
        "airports",
        "airlines",
        "mr_route_activity",
        "mr_airport_outgoing",
        "mr_airport_incoming",
        "mr_monthly_route",
        "mr_airport_connectivity",
        "pipeline_runs",
    ]
    for col in expected_cols:
        assert col in counts
        assert isinstance(counts[col], int)
        assert counts[col] >= 0


def test_mapreduce_job_definitions():
    """Verify all 5 MapReduce jobs have complete definitions and valid JS code."""
    jobs = get_mapreduce_job_definitions()
    assert len(jobs) == 5
    for jid in ["job_a", "job_b", "job_c", "job_d", "job_e"]:
        assert jid in jobs
        job = jobs[jid]
        assert "name" in job
        assert "purpose" in job
        assert "mapper_code" in job
        assert "reducer_code" in job
        assert "input_collection" in job
        assert "output_collection" in job
        assert "emit(" in job["mapper_code"]
        assert "function" in job["reducer_code"]


def test_mapreduce_job_telemetry_structure():
    """Verify telemetry returns document count, sample records, and verification status."""
    telemetry = get_job_telemetry("job_a")
    assert isinstance(telemetry, dict)
    assert "document_count" in telemetry
    assert "sample_records" in telemetry
    assert "verification_status" in telemetry
    assert isinstance(telemetry["sample_records"], list)


def test_analytics_top_routes_dataframe():
    """Verify get_top_directed_routes returns a valid DataFrame."""
    df = get_top_directed_routes(limit=5)
    assert isinstance(df, pd.DataFrame)
    expected_cols = ["route_key", "origin", "destination", "flights"]
    for c in expected_cols:
        assert c in df.columns


def test_analytics_top_airports():
    """Verify get_top_airports returns valid DataFrame for all ranking modes."""
    for mode in ["total", "outgoing", "incoming"]:
        df = get_top_airports(by=mode, limit=5)
        assert isinstance(df, pd.DataFrame)
        assert "airport" in df.columns


def test_analytics_temporal_distributions():
    """Verify monthly and weekday distribution return structured DataFrames."""
    m_df = get_monthly_flight_distribution()
    assert isinstance(m_df, pd.DataFrame)
    assert "flights" in m_df.columns

    w_df = get_weekday_flight_distribution()
    assert isinstance(w_df, pd.DataFrame)
    assert "flights" in w_df.columns


def test_ml_service_metadata():
    """Verify ML metadata provides k=4, feature list, and evaluation metrics."""
    meta = get_clustering_metadata()
    assert meta.get("k") == 4
    assert meta.get("random_state") == 42
    assert "features" in meta
    assert len(meta["features"]) in [5, 7]
    eval_metrics = meta.get("evaluation_metrics", {})
    assert "davies_bouldin_index" in eval_metrics
    assert "inertia" in eval_metrics
    assert "pca_explained_variance_2d" in eval_metrics


def test_ml_service_cluster_profiles():
    """Verify cluster profiles summarize the 4 discovered tiers."""
    profiles = get_cluster_profiles_summary()
    assert isinstance(profiles, pd.DataFrame)
    if not profiles.empty:
        assert "Cluster ID" in profiles.columns
        assert "Archetype Name" in profiles.columns
        assert len(profiles) <= 4
