# ============================================================
# AeroRoute -- Phase 8 Dashboard Unit Test Suite
# File : tests/test_dashboard.py
# Usage: python -m unittest tests/test_dashboard.py
# ============================================================

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import unittest
import pandas as pd
import plotly.graph_objects as go

from dashboard.components.charts import (
    create_donut_chart,
    create_horizontal_bar_chart,
    create_scatter_plot,
    create_us_airport_map,
    get_aviation_layout,
)
from dashboard.services.data_service import AeroRouteDataService
from dashboard.services.filter_service import (
    filter_airports,
    filter_routes,
    paginate_dataframe,
)


class TestDashboardFiltersAndPagination(unittest.TestCase):
    """Unit tests for route filtering, airport filtering, and pagination logic."""

    def setUp(self):
        self.routes_df = pd.DataFrame([
            {"route_key": "ATL->ORD", "origin": "ATL", "destination": "ORD", "flight_count": 250},
            {"route_key": "ORD->ATL", "origin": "ORD", "destination": "ATL", "flight_count": 248},
            {"route_key": "LAX->SFO", "origin": "LAX", "destination": "SFO", "flight_count": 210},
            {"route_key": "SFO->LAX", "origin": "SFO", "destination": "LAX", "flight_count": 208},
            {"route_key": "JFK->MIA", "origin": "JFK", "destination": "MIA", "flight_count": 95},
            {"route_key": "MIA->JFK", "origin": "MIA", "destination": "JFK", "flight_count": 94},
            {"route_key": "DEN->SLC", "origin": "DEN", "destination": "SLC", "flight_count": 30},
        ])

        self.airports_df = pd.DataFrame([
            {"iata": "ATL", "name": "Hartsfield-Jackson", "city": "Atlanta", "state": "GA", "total_flights": 12000, "distinct_destinations": 160, "cluster_id": 3, "betweenness_centrality": 0.17},
            {"iata": "ORD", "name": "O'Hare", "city": "Chicago", "state": "IL", "total_flights": 9200, "distinct_destinations": 150, "cluster_id": 3, "betweenness_centrality": 0.15},
            {"iata": "LAX", "name": "Los Angeles Intl", "city": "Los Angeles", "state": "CA", "total_flights": 7500, "distinct_destinations": 78, "cluster_id": 2, "betweenness_centrality": 0.03},
            {"iata": "SFO", "name": "San Francisco Intl", "city": "San Francisco", "state": "CA", "total_flights": 5600, "distinct_destinations": 75, "cluster_id": 2, "betweenness_centrality": 0.04},
            {"iata": "ABQ", "name": "Albuquerque Sunport", "city": "Albuquerque", "state": "NM", "total_flights": 700, "distinct_destinations": 21, "cluster_id": 1, "betweenness_centrality": 0.0001},
            {"iata": "MGM", "name": "Montgomery Regional", "city": "Montgomery", "state": "AL", "total_flights": 50, "distinct_destinations": 2, "cluster_id": 0, "betweenness_centrality": 0.0},
        ])

    def test_filter_routes_by_search_query(self):
        """Verify case-insensitive search across origin, destination, and route_key."""
        # Query matching origin
        res_atl = filter_routes(self.routes_df, search_query="atl")
        self.assertEqual(len(res_atl), 2)  # ATL->ORD and ORD->ATL

        # Query matching corridor substring
        res_lax_sfo = filter_routes(self.routes_df, search_query="lax->sfo")
        self.assertEqual(len(res_lax_sfo), 1)
        self.assertEqual(res_lax_sfo.iloc[0]["route_key"], "LAX->SFO")

        # Query matching destination
        res_slc = filter_routes(self.routes_df, search_query="slc")
        self.assertEqual(len(res_slc), 1)
        self.assertEqual(res_slc.iloc[0]["destination"], "SLC")

    def test_filter_routes_by_min_flights(self):
        """Verify filtering out corridors below flight count threshold."""
        res_high = filter_routes(self.routes_df, min_flights=200)
        self.assertEqual(len(res_high), 4)  # 250, 248, 210, 208

        res_none = filter_routes(self.routes_df, min_flights=500)
        self.assertTrue(res_none.empty)

    def test_filter_routes_sorting(self):
        """Verify sorting descending, ascending, and alphabetical."""
        desc = filter_routes(self.routes_df, sort_by="Flights (High to Low)")
        self.assertEqual(desc.iloc[0]["flight_count"], 250)
        self.assertEqual(desc.iloc[-1]["flight_count"], 30)

        asc = filter_routes(self.routes_df, sort_by="Flights (Low to High)")
        self.assertEqual(asc.iloc[0]["flight_count"], 30)

        alpha = filter_routes(self.routes_df, sort_by="Route Key (A-Z)")
        self.assertEqual(alpha.iloc[0]["route_key"], "ATL->ORD")

    def test_filter_airports_by_state_and_cluster(self):
        """Verify filtering airports by state and operational cluster tier."""
        # State filter
        ca_airports = filter_airports(self.airports_df, selected_states=["CA"])
        self.assertEqual(len(ca_airports), 2)
        self.assertTrue(all(ca_airports["state"] == "CA"))

        # Cluster tier filter
        super_hubs = filter_airports(self.airports_df, selected_clusters=[3])
        self.assertEqual(len(super_hubs), 2)
        self.assertEqual(set(super_hubs["iata"]), {"ATL", "ORD"})

        # Multi-state and multi-cluster
        combo = filter_airports(self.airports_df, selected_states=["CA", "GA"], selected_clusters=[2, 3])
        self.assertEqual(len(combo), 3)  # ATL (GA, tier 3), LAX (CA, tier 2), SFO (CA, tier 2)

    def test_paginate_dataframe_bounds(self):
        """Verify pagination boundary conditions, clamping, and page count calculations."""
        # Test empty DataFrame
        empty_df = pd.DataFrame()
        page_df, total_r, total_p = paginate_dataframe(empty_df, page_number=1, page_size=10)
        self.assertEqual(len(page_df), 0)
        self.assertEqual(total_r, 0)
        self.assertEqual(total_p, 1)

        # Test normal page slicing
        large_df = pd.DataFrame({"id": range(45)})
        # Page 1 (0 to 9)
        p1, tot_rows, tot_pages = paginate_dataframe(large_df, page_number=1, page_size=10)
        self.assertEqual(len(p1), 10)
        self.assertEqual(p1.iloc[0]["id"], 0)
        self.assertEqual(tot_pages, 5)

        # Page 5 (last page: 40 to 44 -> 5 items)
        p5, _, _ = paginate_dataframe(large_df, page_number=5, page_size=10)
        self.assertEqual(len(p5), 5)
        self.assertEqual(p5.iloc[0]["id"], 40)

        # Out-of-bounds high page number clamps to last page
        p_clamp_high, _, _ = paginate_dataframe(large_df, page_number=999, page_size=10)
        self.assertEqual(len(p_clamp_high), 5)
        self.assertEqual(p_clamp_high.iloc[0]["id"], 40)

        # Out-of-bounds low page number clamps to page 1
        p_clamp_low, _, _ = paginate_dataframe(large_df, page_number=-5, page_size=10)
        self.assertEqual(len(p_clamp_low), 10)
        self.assertEqual(p_clamp_low.iloc[0]["id"], 0)


class TestDashboardDataServiceAndErrorHandling(unittest.TestCase):
    """Unit tests for data service resilience, graceful error handling, and security masking."""

    def test_nonexistent_export_returns_none(self):
        """Verify that attempting to load a missing export file returns None without throwing."""
        ds = AeroRouteDataService()
        result = ds._load_json_export("definitely_nonexistent_export_9999.json")
        self.assertIsNone(result)

    def test_system_health_masks_credentials(self):
        """Verify that get_system_health masks database URIs and does not expose passwords."""
        ds = AeroRouteDataService()
        health = ds.get_system_health()

        self.assertIn("masked_uri", health)
        self.assertNotIn("password", health["masked_uri"].lower())
        self.assertIn("database_name", health)
        self.assertIn("exports_status", health)
        self.assertIn("models_status", health)

    def test_mapreduce_unknown_job_handling(self):
        """Verify graceful error dictionary returned when an unknown job name is requested."""
        ds = AeroRouteDataService()
        res = ds.get_mapreduce_job_details("Job Z: Nonexistent Fake Job")
        self.assertIn("error", res)


class TestPlotlyChartBuilders(unittest.TestCase):
    """Unit tests for Plotly chart builders and aviation theme properties."""

    def setUp(self):
        self.sample_df = pd.DataFrame([
            {"route_key": "ATL->ORD", "flight_count": 250},
            {"route_key": "ORD->ATL", "flight_count": 248},
        ])

        self.geo_df = pd.DataFrame([
            {"iata": "ATL", "lat": 33.6407, "lon": -84.4277, "total_flights": 12000, "cluster_label": "Super-Hub", "distinct_destinations": 160},
            {"iata": "ORD", "lat": 41.9742, "lon": -87.9073, "total_flights": 9200, "cluster_label": "Super-Hub", "distinct_destinations": 150},
        ])

    def test_aviation_layout_tokens(self):
        """Verify dark theme color and typography tokens in base layout."""
        layout = get_aviation_layout(title="Test Chart", height=350)
        self.assertIn("paper_bgcolor", layout)
        self.assertIn("plot_bgcolor", layout)
        self.assertEqual(layout["height"], 350)

    def test_horizontal_bar_chart_generation(self):
        """Verify create_horizontal_bar_chart constructs a valid Plotly Figure."""
        fig = create_horizontal_bar_chart(self.sample_df, x_col="flight_count", y_col="route_key", title="Top Corridors")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 1)
        self.assertEqual(fig.data[0].orientation, "h")

    def test_donut_chart_generation(self):
        """Verify create_donut_chart creates a pie trace with hole parameter."""
        fig = create_donut_chart(self.sample_df, names_col="route_key", values_col="flight_count")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.data[0].hole, 0.55)

    def test_us_airport_map_with_valid_coordinates(self):
        """Verify create_us_airport_map constructs a scattergeo figure with USA scope."""
        fig = create_us_airport_map(self.geo_df, color_col="cluster_label", size_col="total_flights")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(fig.layout.geo.scope, "usa")

    def test_us_airport_map_with_missing_coordinates(self):
        """Verify create_us_airport_map handles empty or NaN coordinate DataFrame gracefully."""
        nan_df = pd.DataFrame([{"iata": "XYZ", "lat": None, "lon": None, "total_flights": 10}])
        fig = create_us_airport_map(nan_df)
        self.assertIsInstance(fig, go.Figure)


if __name__ == "__main__":
    unittest.main()
