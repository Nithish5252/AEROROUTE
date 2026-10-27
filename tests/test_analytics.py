# ============================================================
# AeroRoute -- Unit Tests: Big Data Analytics & Network Modeling
# File : tests/test_analytics.py
# Usage: python tests/test_analytics.py
#        python -m unittest tests/test_analytics.py
# ============================================================

import unittest
import networkx as nx
import numpy as np
import pandas as pd

from analytics.utils import (
    compute_asymmetry_index,
    compute_hhi,
    compute_normalized_hhi,
    interpret_hhi,
)
from analytics.network_analysis import (
    compute_centrality_metrics,
    compute_network_summary_statistics,
)


class TestAnalyticsModules(unittest.TestCase):
    """
    Test analytics algorithms using isolated synthetic fixtures.
    Validates statistical properties, graph calculations, and boundary conditions.
    """

    def test_hhi_computation_monopoly(self):
        """Test HHI for a monopoly (100% share) equals 10,000."""
        monopoly = [100.0]
        self.assertEqual(compute_hhi(monopoly, is_percentage=True), 10000.0)

    def test_hhi_computation_equal_split(self):
        """Test HHI for an equal 5-firm split equals 2,000."""
        # 5 firms with 20% each -> 5 * 20^2 = 2,000
        five_equal = [20.0, 20.0, 20.0, 20.0, 20.0]
        self.assertEqual(compute_hhi(five_equal, is_percentage=True), 2000.0)

        # Raw volume equivalent: 5 firms with 100 flights each
        raw_volumes = [100, 100, 100, 100, 100]
        self.assertEqual(compute_hhi(raw_volumes, is_percentage=False), 2000.0)

    def test_hhi_edge_cases(self):
        """Test HHI handles empty lists, single items, and zeros gracefully."""
        self.assertEqual(compute_hhi([]), 0.0)
        self.assertEqual(compute_hhi([0, 0, 0]), 0.0)
        self.assertEqual(compute_normalized_hhi([100]), 1.0)

    def test_asymmetry_index_balanced(self):
        """Test asymmetry index for equal bidirectional volume is 0.0."""
        # 100 flights each way
        self.assertEqual(compute_asymmetry_index(100, 100), 0.0)

    def test_asymmetry_index_one_way(self):
        """Test asymmetry index for completely one-way route is 1.0."""
        # 100 flights A->B, 0 flights B->A
        self.assertEqual(compute_asymmetry_index(100, 0), 1.0)
        self.assertEqual(compute_asymmetry_index(0, 50), 1.0)

    def test_asymmetry_index_partial(self):
        """Test asymmetry index for 75/25 split equals 0.5."""
        # |75 - 25| / (75 + 25) = 50 / 100 = 0.5
        self.assertEqual(compute_asymmetry_index(75, 25), 0.5)

    def test_synthetic_networkx_graph_centrality(self):
        """
        Test graph algorithms on a synthetic 4-node Hub-and-Spoke network:
        Hub 'H' connects bidirectionally to 'S1', 'S2', 'S3'.
        No direct flights between spokes.
        """
        G = nx.DiGraph()
        nodes = ["H", "S1", "S2", "S3"]
        for n in nodes:
            G.add_node(n, name=f"Airport {n}", city="City", state="ST", lat=0.0, lon=0.0)

        # Add bidirectional edges
        spokes = ["S1", "S2", "S3"]
        for s in spokes:
            G.add_edge("H", s, weight=100.0)
            G.add_edge(s, "H", weight=100.0)

        # 1. Check summary stats
        stats = compute_network_summary_statistics(G)
        self.assertEqual(stats["node_count"], 4)
        self.assertEqual(stats["directed_edge_count"], 6)  # 3 pairs * 2 = 6
        self.assertEqual(stats["reciprocity"], 1.0)        # Perfectly reciprocal
        self.assertEqual(stats["total_network_flight_volume"], 600)

        # 2. Check centrality metrics
        centrality_df = compute_centrality_metrics(G)
        hub_row = centrality_df[centrality_df["iata"] == "H"].iloc[0]
        spoke_row = centrality_df[centrality_df["iata"] == "S1"].iloc[0]

        # Hub must have in-degree 3, out-degree 3, total strength 600
        self.assertEqual(hub_row["in_degree"], 3)
        self.assertEqual(hub_row["out_degree"], 3)
        self.assertEqual(hub_row["weighted_degree_strength"], 600)

        # Spokes must have in-degree 1, out-degree 1, total strength 200
        self.assertEqual(spoke_row["in_degree"], 1)
        self.assertEqual(spoke_row["out_degree"], 1)
        self.assertEqual(spoke_row["weighted_degree_strength"], 200)

        # Hub 'H' must have highest betweenness centrality (it bridges all spoke pairs)
        self.assertGreater(hub_row["betweenness_centrality"], spoke_row["betweenness_centrality"])
        self.assertEqual(spoke_row["betweenness_centrality"], 0.0)

    def test_temporal_anomaly_detection_logic(self):
        """Test Z-score statistical outlier detection on synthetic monthly series."""
        # 11 baseline months of ~100 flights, 1 spike month of 400 flights
        counts = [100, 102, 98, 101, 99, 100, 103, 97, 101, 100, 100, 400]
        mean_v = np.mean(counts)
        std_v = np.std(counts)
        z_scores = [(x - mean_v) / std_v for x in counts]

        # The spike month must have Z > 2.0
        self.assertGreater(z_scores[-1], 2.0)
        # All baseline months must have |Z| < 1.0
        for z in z_scores[:-1]:
            self.assertLess(abs(z), 1.0)

    def test_domain_integrity_no_passenger_assumptions(self):
        """
        Verify that analytical schemas strictly track flight counts and operational metrics,
        without inventing unverifiable passenger counts, load factors, or ticket revenues.
        """
        forbidden_terms = ["passenger", "ticket_price", "revenue", "profit", "seat_capacity"]
        G = nx.DiGraph()
        G.add_node("ATL", name="Atlanta", city="Atlanta", state="GA", lat=33.6, lon=-84.4)
        G.add_node("ORD", name="Chicago", city="Chicago", state="IL", lat=41.9, lon=-87.9)
        G.add_edge("ATL", "ORD", weight=150.0)

        centrality_df = compute_centrality_metrics(G)
        columns = [c.lower() for c in centrality_df.columns]

        for term in forbidden_terms:
            self.assertNotIn(term, columns, f"Forbidden non-existent BTS metric found: {term}")


if __name__ == "__main__":
    unittest.main()
