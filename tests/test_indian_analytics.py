# ============================================================
# AeroRoute -- Test Suite: Indian Aviation Analytics
# File : tests/test_indian_analytics.py
# Phase: Phase 8 Testing & Analytics Regression Verification
# ============================================================

import pytest
import pandas as pd
import networkx as nx

from src.utils.db import get_db
from analytics.route_analysis import (
    get_busiest_directed_routes,
    get_route_concentration_metrics,
    get_most_active_airport_pairs,
)
from analytics.airport_analysis import (
    get_airports_ranked_by_outgoing,
    get_airports_ranked_by_incoming,
    get_airport_profile,
    get_total_observed_airport_activity,
)
from analytics.network_analysis import (
    build_airport_directed_graph,
    compute_centrality_metrics,
    compute_network_summary_statistics,
)
from dashboard.services.analytics_service import (
    get_route_spotlight,
    get_top_directed_routes,
    get_monthly_flight_distribution,
    get_weekday_flight_distribution,
)
from dashboard.services.ml_service import (
    get_clustering_metadata,
    get_cluster_profiles_summary,
    get_pca_projection_data,
)


class TestIndianRouteAnalytics:
    """Validate Indian corridor ranking, bidirectional spotlighting, and HHI concentration."""

    def test_busiest_routes_india(self):
        db = get_db()
        df = get_busiest_directed_routes(db, limit=10, region="INDIA")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10
        assert "route_key" in df.columns
        assert "flight_count" in df.columns
        top_corridors = df["route_key"].tolist()
        assert any(c in top_corridors for c in ["DEL->BOM", "BOM->DEL", "BLR->DEL", "DEL->BLR"])

    def test_top_directed_routes_dashboard(self):
        df = get_top_directed_routes(limit=10, region="INDIA")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10
        assert "route_key" in df.columns
        assert "flights" in df.columns

    def test_route_spotlight_bidirectional_india(self):
        spotlight = get_route_spotlight(origin="DEL", dest="BOM", region="INDIA")
        assert isinstance(spotlight, dict)
        assert spotlight.get("origin") == "DEL"
        assert spotlight.get("dest") == "BOM"
        assert spotlight.get("volume", 0) > 0
        assert spotlight.get("reverse_volume", 0) > 0
        assert "asymmetry_delta" in spotlight

    def test_route_concentration_hhi_india(self):
        db = get_db()
        hhi_data = get_route_concentration_metrics(db, region="INDIA")
        assert isinstance(hhi_data, dict)
        assert "hhi" in hhi_data
        assert "concentration_category" in hhi_data
        # Indian network is unconcentrated / highly competitive, raw HHI < 100
        assert 0.0 <= hhi_data["hhi"] <= 100.0


class TestIndianAirportAnalytics:
    """Validate Indian airport profiles, hub activity, and degree statistics."""

    def test_delhi_profile(self):
        db = get_db()
        profile = get_airport_profile(db, "DEL", region="INDIA")
        assert isinstance(profile, dict)
        assert profile.get("iata") == "DEL"
        assert profile.get("total_flights") > 1000
        assert "top_destinations" in profile or "coordinates" in profile

    def test_top_outgoing_airports_india(self):
        db = get_db()
        df = get_airports_ranked_by_outgoing(db, limit=5, region="INDIA")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "iata" in df.columns
        top_iatas = df["iata"].tolist()
        assert "DEL" in top_iatas
        assert "BOM" in top_iatas

    def test_top_incoming_airports_india(self):
        db = get_db()
        df = get_airports_ranked_by_incoming(db, limit=5, region="INDIA")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "iata" in df.columns
        top_iatas = df["iata"].tolist()
        assert "DEL" in top_iatas
        assert "BOM" in top_iatas


class TestIndianNetworkTopology:
    """Validate Indian graph structure, centrality metrics, and reciprocity."""

    def test_graph_construction_india(self):
        db = get_db()
        G = build_airport_directed_graph(db, region="INDIA")
        assert isinstance(G, nx.DiGraph)
        assert G.number_of_nodes() >= 90
        assert G.number_of_edges() >= 500
        assert G.has_node("DEL")
        assert G.has_node("BOM")

    def test_centrality_metrics_india(self):
        db = get_db()
        G = build_airport_directed_graph(db, region="INDIA")
        df = compute_centrality_metrics(G)
        assert isinstance(df, pd.DataFrame)
        assert "iata" in df.columns
        assert "betweenness_centrality" in df.columns
        assert "pagerank" in df.columns
        top_nodes = df.sort_values(by="pagerank", ascending=False)["iata"].head(3).tolist()
        assert any(hub in top_nodes for hub in ["DEL", "BOM", "BLR"])

    def test_network_reciprocity_india(self):
        db = get_db()
        G = build_airport_directed_graph(db, region="INDIA")
        stats = compute_network_summary_statistics(G)
        assert isinstance(stats, dict)
        assert "reciprocity" in stats
        assert 0.80 <= stats["reciprocity"] <= 1.0


class TestIndianTemporalAnalytics:
    """Validate Indian seasonal and day-of-week distributions."""

    def test_monthly_distribution_india(self):
        df = get_monthly_flight_distribution(region="INDIA")
        assert isinstance(df, pd.DataFrame)
        assert len(df) <= 12
        assert "month" in df.columns
        assert "flights" in df.columns

    def test_weekday_distribution_india(self):
        df = get_weekday_flight_distribution(region="INDIA")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 7
        assert "day_name" in df.columns
        assert "flights" in df.columns


class TestIndianMachineLearningArtifacts:
    """Validate Indian K-Means artifacts, profiles, and PCA projections."""

    def test_clustering_metadata_india(self):
        meta = get_clustering_metadata(region="INDIA")
        assert meta["region"] == "INDIA"
        assert meta["k"] == 4
        assert meta["random_state"] == 42
        assert len(meta["features"]) in [5, 7]
        assert "davies_bouldin_index" in meta["evaluation_metrics"]

    def test_cluster_profiles_india(self):
        profiles = get_cluster_profiles_summary(region="INDIA")
        assert isinstance(profiles, pd.DataFrame)
        assert not profiles.empty
        assert len(profiles) <= 4

    def test_pca_projection_india(self):
        pca_df = get_pca_projection_data(region="INDIA")
        assert isinstance(pca_df, pd.DataFrame)
        assert not pca_df.empty
        assert "pca_x" in pca_df.columns
        assert "pca_y" in pca_df.columns
        assert "cluster" in pca_df.columns
