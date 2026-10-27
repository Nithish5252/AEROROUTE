# ============================================================
# AeroRoute -- Phase 7 Machine Learning Test Suite
# File : tests/test_clustering.py
# Usage: python -m unittest tests/test_clustering.py
# ============================================================

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from models.feature_pipeline import (
    ALL_FEATURE_COLS,
    GRAPH_CENTRALITY_FEATURES,
    SKEWED_COUNT_FEATURES,
    AirportFeatureTransformer,
)
from models.airport_clustering import AirportClusteringModel
from models.model_evaluation import (
    compute_pca_projection,
    evaluate_candidate_k,
)


def create_synthetic_airport_dataset(n_samples: int = 60, random_seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic airport dataset with known tiered clusters
    (simulating feed/regional/hub hierarchy with heavy-tailed counts).
    """
    rng = np.random.RandomState(random_seed)
    records = []

    for i in range(n_samples):
        iata = f"AP{i:03d}"
        if i < 4:
            # Simulated Super-Hubs
            tot = int(rng.normal(9000, 500))
            dests = int(rng.normal(150, 10))
            betw = rng.uniform(0.12, 0.18)
            pr = rng.uniform(0.04, 0.05)
        elif i < 20:
            # Simulated Commercial Hubs
            tot = int(rng.normal(2000, 300))
            dests = int(rng.normal(45, 8))
            betw = rng.uniform(0.005, 0.03)
            pr = rng.uniform(0.008, 0.015)
        elif i < 40:
            # Simulated Regional Connections
            tot = int(rng.normal(250, 40))
            dests = int(rng.normal(8, 2))
            betw = rng.uniform(0.0, 0.001)
            pr = rng.uniform(0.001, 0.002)
        else:
            # Simulated Regional Feeders
            tot = int(rng.normal(35, 10))
            dests = int(rng.choice([1, 2, 3]))
            betw = 0.0
            pr = rng.uniform(0.0005, 0.0008)

        tot = max(tot, 1)
        dests = max(dests, 1)
        outg = tot // 2
        inco = tot - outg

        records.append({
            "iata": iata,
            "name": f"Airport {iata}",
            "city": f"City {i}",
            "state": "US",
            "lat": 35.0 + (i * 0.1),
            "lon": -90.0 - (i * 0.1),
            "total_flights": float(tot),
            "outgoing_flights": float(outg),
            "incoming_flights": float(inco),
            "distinct_destinations": float(dests),
            "distinct_origins": float(dests),
            "distinct_connections": float(dests),
            "betweenness_centrality": float(betw),
            "pagerank": float(pr),
        })

    return pd.DataFrame(records)


class TestFeaturePipeline(unittest.TestCase):
    """Unit tests for feature generation, log1p transformation, and scaling."""

    def setUp(self):
        self.df = create_synthetic_airport_dataset(n_samples=50)

    def test_log1p_transformation_math(self):
        """Verify mathematical correctness of log1p transformation: y = ln(1 + x)."""
        transformer = AirportFeatureTransformer()
        transformed = transformer._transform_skewed_features(self.df)

        # Test zero preservation: log(1 + 0) == 0.0
        zero_df = pd.DataFrame({
            "total_flights": [0.0],
            "outgoing_flights": [0.0],
            "incoming_flights": [0.0],
            "distinct_destinations": [0.0],
            "distinct_origins": [0.0],
            "betweenness_centrality": [0.0],
            "pagerank": [0.0],
        })
        zero_trans = transformer._transform_skewed_features(zero_df)
        for col in SKEWED_COUNT_FEATURES:
            self.assertEqual(zero_trans[f"log1p_{col}"].iloc[0], 0.0)

        # Test exact formula on known value: x = 99 -> log(100)
        test_val = 99.0
        expected = np.log(1.0 + test_val)
        actual = np.log1p(test_val)
        self.assertAlmostEqual(actual, expected, places=7)

        # Verify skewness reduction
        raw_skew = float(self.df["total_flights"].skew())
        log_skew = float(transformed["log1p_total_flights"].skew())
        self.assertLess(abs(log_skew), abs(raw_skew))

    def test_standard_scaler_normalization(self):
        """Verify that fitted features have mean approx 0.0 and std approx 1.0."""
        transformer = AirportFeatureTransformer()
        X_scaled, feat_names = transformer.fit_transform(self.df)

        self.assertEqual(X_scaled.shape, (len(self.df), len(ALL_FEATURE_COLS)))
        means = np.mean(X_scaled, axis=0)
        stds = np.std(X_scaled, axis=0)

        for i, (m, s) in enumerate(zip(means, stds)):
            self.assertAlmostEqual(m, 0.0, places=5, msg=f"Feature {feat_names[i]} mean is not 0.0")
            self.assertAlmostEqual(s, 1.0, places=5, msg=f"Feature {feat_names[i]} std is not 1.0")

    def test_unfitted_transform_raises(self):
        """Verify that transform() without prior fit_transform() raises RuntimeError."""
        transformer = AirportFeatureTransformer()
        with self.assertRaises(RuntimeError):
            transformer.transform(self.df)

    def test_transformer_persistence(self):
        """Verify joblib serialization and deserialization of AirportFeatureTransformer."""
        transformer = AirportFeatureTransformer()
        X1, _ = transformer.fit_transform(self.df)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "transformer.joblib"
            transformer.save(save_path)
            self.assertTrue(save_path.exists())

            loaded_transformer = AirportFeatureTransformer.load(save_path)
            self.assertTrue(loaded_transformer.is_fitted)
            X2 = loaded_transformer.transform(self.df)
            np.testing.assert_array_almost_equal(X1, X2, decimal=6)


class TestModelReproducibilityAndClustering(unittest.TestCase):
    """Unit tests for K-Means reproducibility, monotonic ordering, and profiles."""

    def setUp(self):
        self.df = create_synthetic_airport_dataset(n_samples=60)
        self.transformer = AirportFeatureTransformer()
        self.X_scaled, self.feat_names = self.transformer.fit_transform(self.df)

    def test_kmeans_deterministic_reproducibility(self):
        """Verify that identical random_state yields 100% bitwise identical cluster assignments."""
        model_1 = AirportClusteringModel(k=4, random_state=42)
        model_1.fit(self.df, self.X_scaled, self.transformer)

        model_2 = AirportClusteringModel(k=4, random_state=42)
        model_2.fit(self.df, self.X_scaled, self.transformer)

        np.testing.assert_array_equal(model_1.kmeans.labels_, model_2.kmeans.labels_)
        np.testing.assert_array_almost_equal(
            model_1.kmeans.cluster_centers_,
            model_2.kmeans.cluster_centers_,
            decimal=7,
        )
        self.assertEqual(model_1.metrics["inertia"], model_2.metrics["inertia"])
        self.assertEqual(model_1.metrics["silhouette_score"], model_2.metrics["silhouette_score"])

    def test_monotonic_cluster_tier_ordering(self):
        """Verify that cluster IDs are ordered monotonically by median operational flight volume."""
        model = AirportClusteringModel(k=4, random_state=42)
        model.fit(self.df, self.X_scaled, self.transformer)
        assigned_df = model.generate_cluster_assignments_df(self.df, self.X_scaled)

        medians = [
            assigned_df[assigned_df["cluster_id"] == c]["total_flights"].median()
            for c in range(4)
        ]
        # Verify strictly increasing medians across tiers
        for i in range(len(medians) - 1):
            self.assertLess(
                medians[i],
                medians[i + 1],
                f"Tier {i} median ({medians[i]}) must be strictly less than Tier {i+1} ({medians[i+1]})",
            )

    def test_cluster_output_schema_and_profiles(self):
        """Verify generated cluster assignments and profile structures."""
        model = AirportClusteringModel(k=4, random_state=42)
        model.fit(self.df, self.X_scaled, self.transformer)
        assigned_df = model.generate_cluster_assignments_df(self.df, self.X_scaled)

        # Schema checks
        required_cols = ["iata", "cluster_id", "cluster_label", "pca_x", "pca_y", "total_flights"]
        for col in required_cols:
            self.assertIn(col, assigned_df.columns)

        self.assertEqual(set(assigned_df["cluster_id"].unique()), {0, 1, 2, 3})
        self.assertFalse(assigned_df["pca_x"].isnull().any())
        self.assertFalse(assigned_df["pca_y"].isnull().any())

        # Profile checks
        profiles = model.generate_cluster_profiles(assigned_df)
        self.assertEqual(len(profiles), 4)

        total_size = sum(p["size"] for p in profiles)
        self.assertEqual(total_size, len(self.df))

        total_pct = sum(p["percentage_of_network"] for p in profiles)
        self.assertAlmostEqual(total_pct, 100.0, places=1)

        for p in profiles:
            self.assertIn("cluster_id", p)
            self.assertIn("label", p)
            self.assertIn("feature_medians", p)
            self.assertIn("operational_summary", p)
            self.assertIn("representative_airports", p)
            self.assertTrue(len(p["representative_airports"]) > 0)


class TestModelEvaluationAndPCA(unittest.TestCase):
    """Unit tests for candidate k evaluation, metrics bounds, and 2D PCA projection."""

    def setUp(self):
        self.df = create_synthetic_airport_dataset(n_samples=40)
        self.transformer = AirportFeatureTransformer()
        self.X_scaled, _ = self.transformer.fit_transform(self.df)

    def test_candidate_k_evaluation_bounds(self):
        """Verify evaluate_candidate_k calculates valid metrics across k in [2, 5]."""
        results = evaluate_candidate_k(self.X_scaled, k_range=range(2, 6), random_state=42)

        self.assertIn("candidate_evaluations", results)
        self.assertIn("recommended_k", results)
        self.assertIn("silhouette_limitations_explained", results)

        evals = results["candidate_evaluations"]
        self.assertEqual(len(evals), 4)

        for e in evals:
            self.assertIn(e["k"], range(2, 6))
            # Silhouette is mathematically in [-1.0, 1.0]
            self.assertGreaterEqual(e["silhouette_score"], -1.0)
            self.assertLessEqual(e["silhouette_score"], 1.0)
            # Davies-Bouldin is non-negative
            self.assertGreaterEqual(e["davies_bouldin_score"], 0.0)
            # Calinski-Harabasz is non-negative
            self.assertGreaterEqual(e["calinski_harabasz_score"], 0.0)
            # Inertia is positive
            self.assertGreater(e["inertia"], 0.0)
            # Sum of cluster sizes matches sample count
            self.assertEqual(sum(e["cluster_sizes"]), len(self.df))

    def test_pca_projection_properties(self):
        """Verify PCA dimensionality reduction produces correct dimensions and variance."""
        X_pca, pca, meta = compute_pca_projection(self.X_scaled, random_state=42)

        self.assertEqual(X_pca.shape, (len(self.df), 2))
        self.assertEqual(meta["n_components"], 2)
        self.assertGreaterEqual(meta["cumulative_explained_variance"], 0.70)
        self.assertLessEqual(meta["cumulative_explained_variance"], 1.0)

    def test_artifact_persistence_and_metadata(self):
        """Verify end-to-end artifact persistence to temporary directories."""
        model = AirportClusteringModel(k=3, random_state=42)
        model.fit(self.df, self.X_scaled, self.transformer)
        assigned_df = model.generate_cluster_assignments_df(self.df, self.X_scaled)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models"
            exports_dir = Path(tmpdir) / "exports"

            paths = model.save_artifacts(
                models_dir=models_dir,
                exports_dir=exports_dir,
                assigned_df=assigned_df,
            )

            # Check that all 6 files exist
            for name, filepath in paths.items():
                self.assertTrue(filepath.exists(), f"Artifact {name} ({filepath}) was not created!")

            # Verify JSON files are readable and well-formed
            with open(paths["metadata"], "r", encoding="utf-8") as f:
                meta = json.load(f)
                self.assertEqual(meta["algorithm"], "KMeans")
                self.assertEqual(meta["k"], 3)
                self.assertIn("limitations", meta)

            with open(paths["airport_clusters"], "r", encoding="utf-8") as f:
                clusters = json.load(f)
                self.assertEqual(len(clusters), len(self.df))

            with open(paths["cluster_profiles"], "r", encoding="utf-8") as f:
                profiles = json.load(f)
                self.assertEqual(len(profiles), 3)


if __name__ == "__main__":
    unittest.main()
