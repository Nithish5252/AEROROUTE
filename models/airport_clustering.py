# ============================================================
# AeroRoute -- Airport K-Means Clustering Model
# File : models/airport_clustering.py
# Usage: python -m models.airport_clustering [--k 4] [--save-db]
# ============================================================

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
import pymongo
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from config.settings import settings
from models.feature_pipeline import (
    ALL_FEATURE_COLS,
    AirportFeatureTransformer,
    prepare_clustering_dataset,
)
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("airport_clustering")


class AirportClusteringModel:
    """
    Production-grade K-Means clustering model for commercial airports.
    
    Transforms skewed flight volumes and degree connectivity via log1p,
    standardizes features, fits reproducible K-Means, orders clusters
    monotonically by operational activity, and generates data-driven
    statistical summaries.
    """

    def __init__(
        self,
        k: int = 4,
        random_state: int = 42,
        n_init: int = 10,
        max_iter: int = 300,
    ):
        self.k = k
        self.random_state = random_state
        self.n_init = n_init
        self.max_iter = max_iter

        self.kmeans: Optional[KMeans] = None
        self.transformer: Optional[AirportFeatureTransformer] = None
        self.pca: Optional[PCA] = None
        self.is_fitted: bool = False
        self.cluster_order_map: Dict[int, int] = {}
        self.metrics: Dict[str, Any] = {}

    def fit(
        self,
        raw_df: pd.DataFrame,
        X_scaled: np.ndarray,
        transformer: AirportFeatureTransformer,
    ) -> "AirportClusteringModel":
        """
        Fit K-Means clustering model and 2D PCA on scaled features.
        Re-indexes cluster IDs monotonically by median total flight volume
        so Cluster 0 represents the lowest activity tier and Cluster k-1
        represents the highest activity tier (national super-hubs).
        """
        logger.info(f"Fitting K-Means model with k={self.k}, random_state={self.random_state}...")
        self.transformer = transformer

        raw_km = KMeans(
            n_clusters=self.k,
            random_state=self.random_state,
            n_init=self.n_init,
            max_iter=self.max_iter,
        )
        raw_labels = raw_km.fit_predict(X_scaled)

        # 1. Monotonic cluster ordering: Map raw cluster labels to sorted tiers by median total_flights
        temp_df = pd.DataFrame({"raw_cluster": raw_labels, "total_flights": raw_df["total_flights"].values})
        median_activity = temp_df.groupby("raw_cluster")["total_flights"].median().sort_values()
        # Sorted order: index 0 has lowest median flights, index k-1 has highest median flights
        sorted_raw_ids = list(median_activity.index)
        self.cluster_order_map = {raw_id: new_id for new_id, raw_id in enumerate(sorted_raw_ids)}

        # Apply monotonic ordering to labels
        ordered_labels = np.array([self.cluster_order_map[label] for label in raw_labels])

        # 2. Re-order cluster centers to match ordered labels
        ordered_centers = np.zeros_like(raw_km.cluster_centers_)
        for raw_id, new_id in self.cluster_order_map.items():
            ordered_centers[new_id] = raw_km.cluster_centers_[raw_id]

        self.kmeans = raw_km
        self.kmeans.cluster_centers_ = ordered_centers
        self.kmeans.labels_ = ordered_labels

        # 3. Fit 2D PCA for dimensionality reduction and plotting
        self.pca = PCA(n_components=2, random_state=self.random_state)
        self.pca.fit(X_scaled)

        # 4. Compute evaluation metrics on fitted model
        sil = float(silhouette_score(X_scaled, ordered_labels))
        ch = float(calinski_harabasz_score(X_scaled, ordered_labels))
        db = float(davies_bouldin_score(X_scaled, ordered_labels))
        inertia = float(raw_km.inertia_)

        self.metrics = {
            "k": self.k,
            "random_state": self.random_state,
            "inertia": round(inertia, 2),
            "silhouette_score": round(sil, 4),
            "calinski_harabasz_score": round(ch, 2),
            "davies_bouldin_score": round(db, 4),
            "pca_explained_variance_ratio": [
                round(float(v), 4) for v in self.pca.explained_variance_ratio_
            ],
            "pca_cumulative_variance": round(float(np.sum(self.pca.explained_variance_ratio_)), 4),
        }

        self.is_fitted = True
        logger.info(
            f"Fitted AirportClusteringModel (k={self.k}): Inertia={self.metrics['inertia']}, "
            f"Silhouette={self.metrics['silhouette_score']}, Davies-Bouldin={self.metrics['davies_bouldin_score']}."
        )
        return self

    def predict(self, X_scaled: np.ndarray) -> np.ndarray:
        """Predict cluster assignments for scaled features."""
        if not self.is_fitted or self.kmeans is None:
            raise RuntimeError("Model is not fitted! Call fit() before predict().")
        raw_labels = self.kmeans.predict(X_scaled)
        return np.array([self.cluster_order_map.get(lbl, lbl) for lbl in raw_labels])

    def generate_cluster_assignments_df(
        self,
        raw_df: pd.DataFrame,
        X_scaled: np.ndarray,
    ) -> pd.DataFrame:
        """
        Generate comprehensive DataFrame joining airport metadata, raw features,
        transformed features, assigned cluster ID, data-driven label, and PCA coordinates.
        """
        if not self.is_fitted or self.kmeans is None or self.pca is None:
            raise RuntimeError("Model is not fitted!")

        df = raw_df.copy()
        df["cluster_id"] = self.kmeans.labels_

        # PCA 2D coordinates
        pca_coords = self.pca.transform(X_scaled)
        df["pca_x"] = np.round(pca_coords[:, 0], 4)
        df["pca_y"] = np.round(pca_coords[:, 1], 4)

        # Assign data-driven operational cluster labels
        labels_map = self._derive_data_driven_labels(df)
        df["cluster_label"] = df["cluster_id"].map(labels_map)

        return df

    def _derive_data_driven_labels(self, df: pd.DataFrame) -> Dict[int, str]:
        """
        Generate empirical, data-driven cluster category names based purely on
        observed median flight counts and network degree.
        Avoids unsupported commercial/financial claims.
        """
        labels = {}
        for c in range(self.k):
            sub = df[df["cluster_id"] == c]
            med_flights = sub["total_flights"].median()
            med_dest = sub["distinct_destinations"].median()
            med_betw = sub["betweenness_centrality"].median()

            if self.k == 4:
                if c == 3:
                    labels[c] = "National Super-Hub (Mega-Scale Interconnector)"
                elif c == 2:
                    labels[c] = "Major Commercial Hub (High-Density Multi-Region)"
                elif c == 1:
                    labels[c] = "Regional Connection Airport (Mid-Density Spoke Network)"
                else:
                    labels[c] = "Regional Feeder / Spoke (Low-Volume Destination)"
            elif self.k == 5:
                if c == 4:
                    labels[c] = "National Super-Hub (Mega-Scale Interconnector)"
                elif c == 3:
                    labels[c] = "Primary Commercial Hub (High-Density Nationwide Reach)"
                elif c == 2:
                    labels[c] = "Focus City / Medium Commercial Hub"
                elif c == 1:
                    labels[c] = "Small Regional Commercial Airport"
                else:
                    labels[c] = "Regional Feeder / Low-Volume Spoke"
            else:
                # Dynamic generic label based on median operational flight volume
                labels[c] = f"Cluster {c} (Median Flights: {int(med_flights):,}, Median Dests: {int(med_dest)})"

        return labels

    def generate_cluster_profiles(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Generate detailed, interpretable statistical profiles for each cluster:
          - Size & percentage of network
          - Feature medians (unscaled, human-readable)
          - Feature means and standard deviations
          - Top representative/exemplar airports
          - Grounded operational profile summary
        """
        profiles = []
        total_airports = len(df)
        labels_map = self._derive_data_driven_labels(df)

        for c in range(self.k):
            sub = df[df["cluster_id"] == c]
            size = len(sub)
            pct = round((size / total_airports) * 100, 2)

            top_airports = (
                sub.sort_values(by="total_flights", ascending=False)
                .head(8)[["iata", "name", "city", "state", "total_flights", "distinct_destinations", "betweenness_centrality"]]
                .to_dict(orient="records")
            )

            # Clean float values in top airports
            for a in top_airports:
                a["total_flights"] = int(a["total_flights"])
                a["distinct_destinations"] = int(a["distinct_destinations"])
                a["betweenness_centrality"] = round(float(a["betweenness_centrality"]), 6)

            medians = {
                "total_flights": int(sub["total_flights"].median()),
                "outgoing_flights": int(sub["outgoing_flights"].median()),
                "incoming_flights": int(sub["incoming_flights"].median()),
                "distinct_destinations": int(sub["distinct_destinations"].median()),
                "distinct_origins": int(sub["distinct_origins"].median()),
                "distinct_connections": int(sub["distinct_connections"].median()),
                "betweenness_centrality": round(float(sub["betweenness_centrality"].median()), 6),
                "pagerank": round(float(sub["pagerank"].median()), 6),
            }

            means = {
                "total_flights": round(float(sub["total_flights"].mean()), 2),
                "distinct_destinations": round(float(sub["distinct_destinations"].mean()), 2),
                "betweenness_centrality": round(float(sub["betweenness_centrality"].mean()), 6),
                "pagerank": round(float(sub["pagerank"].mean()), 6),
            }

            # Generate natural language summary grounded purely in observed features
            label = labels_map.get(c, f"Cluster {c}")
            summary = (
                f"{label} comprises {size} airports ({pct}% of active commercial network). "
                f"Airports in this tier exhibit a median of {medians['total_flights']:,} total flights "
                f"(mean: {means['total_flights']:,}) and serve a median of {medians['distinct_destinations']} "
                f"direct outbound destinations. Network centrality shows a median betweenness of "
                f"{medians['betweenness_centrality']} and PageRank of {medians['pagerank']}."
            )

            profiles.append({
                "cluster_id": c,
                "label": label,
                "size": size,
                "percentage_of_network": pct,
                "feature_medians": medians,
                "feature_means": means,
                "operational_summary": summary,
                "representative_airports": top_airports,
            })

        return profiles

    def save_artifacts(
        self,
        region: Optional[str] = None,
        models_dir: Optional[Path] = None,
        exports_dir: Optional[Path] = None,
        assigned_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Path]:
        """
        Save all trained artifacts and export files to disk:
          - models/kmeans_model[_<region>].joblib
          - models/feature_transformer[_<region>].joblib
          - models/pca_model[_<region>].joblib
          - models/model_metadata[_<region>].json
          - exports/airport_clusters[_<region>].json
          - exports/cluster_profiles[_<region>].json
        """
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted! Cannot save artifacts.")

        reg = (region or settings.DATASET_REGION).upper()
        if models_dir is None:
            models_dir = settings.MODELS_DIR
        if exports_dir is None:
            exports_dir = settings.EXPORTS_DIR

        models_dir.mkdir(parents=True, exist_ok=True)
        exports_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = {}
        suffix = f"_{reg.lower()}"

        # 1. Save KMeans model
        km_path = models_dir / f"kmeans_model{suffix}.joblib"
        joblib.dump(self.kmeans, km_path)
        saved_paths["kmeans_model"] = km_path
        joblib.dump(self.kmeans, models_dir / "kmeans_model.joblib")

        # 2. Save Feature Transformer
        if self.transformer:
            tf_path = models_dir / f"feature_transformer{suffix}.joblib"
            joblib.dump(self.transformer, tf_path)
            saved_paths["feature_transformer"] = tf_path
            joblib.dump(self.transformer, models_dir / "feature_transformer.joblib")

        # 3. Save PCA model
        if self.pca:
            pca_path = models_dir / f"pca_model{suffix}.joblib"
            joblib.dump(self.pca, pca_path)
            saved_paths["pca_model"] = pca_path
            joblib.dump(self.pca, models_dir / "pca_model.joblib")

        # 4. Save Model Configuration and Metadata
        limitations = (
            [
                "Clusters represent published scheduled movement frequency and NetworkX graph centrality.",
                "Based on approved DGCA domestic airline timetable filings (2018–2025).",
                "Does not reflect actual delays, cancellations, or passenger load factors.",
            ]
            if reg == "INDIA"
            else [
                "Clusters represent operational flight movement density and graph network topology.",
                "Does not forecast passenger demand, ticket pricing, load factors, or airline profitability.",
                "Airport coverage is bounded to commercial flights recorded in the validated DOT dataset sample.",
            ]
        )
        metadata = {
            "region": reg,
            "algorithm": "KMeans",
            "k": self.k,
            "random_state": self.random_state,
            "n_init": self.n_init,
            "max_iter": self.max_iter,
            "fitted_at_utc": datetime.now(timezone.utc).isoformat(),
            "feature_columns": ALL_FEATURE_COLS,
            "metrics": self.metrics,
            "cluster_order_map": {str(k): int(v) for k, v in self.cluster_order_map.items()},
            "limitations": limitations,
        }
        meta_path = models_dir / f"model_metadata{suffix}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        with open(models_dir / "model_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        saved_paths["metadata"] = meta_path

        # 5. Export Cluster Assignments and Profiles
        if assigned_df is not None:
            clusters_export_path = exports_dir / f"airport_clusters{suffix}.json"
            records = assigned_df.replace({np.nan: None}).to_dict(orient="records")
            with open(clusters_export_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            with open(exports_dir / "airport_clusters.json", "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            saved_paths["airport_clusters"] = clusters_export_path

            profiles_export_path = exports_dir / f"cluster_profiles{suffix}.json"
            profiles = self.generate_cluster_profiles(assigned_df)
            with open(profiles_export_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
            with open(exports_dir / "cluster_profiles.json", "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
            saved_paths["cluster_profiles"] = profiles_export_path

        logger.info(f"[{reg}] Successfully saved model artifacts to {models_dir} and exports to {exports_dir}.")
        return saved_paths

    def update_mongodb_airports(
        self,
        assigned_df: pd.DataFrame,
        region: Optional[str] = None,
        db: Optional[pymongo.database.Database] = None,
    ) -> int:
        """
        Idempotently update MongoDB airports collection with cluster assignments
        and 2D PCA coordinates for seamless downstream dashboard visualization.
        """
        reg = (region or settings.DATASET_REGION).upper()
        target_col = settings.get_airports_collection(reg)
        if db is None:
            db = get_db()

        logger.info(f"Updating MongoDB '{target_col}' collection with cluster assignments...")
        updated_count = 0
        bulk_ops = []

        for _, row in assigned_df.iterrows():
            iata = str(row["iata"])
            update_fields = {
                "cluster_id": int(row["cluster_id"]),
                "cluster_label": str(row["cluster_label"]),
                "pca_x": float(row["pca_x"]),
                "pca_y": float(row["pca_y"]),
                "total_flights": float(row["total_flights"]),
                "distinct_destinations": float(row["distinct_destinations"]),
                "betweenness_centrality": float(row["betweenness_centrality"]),
                "pagerank": float(row["pagerank"]),
                "clustering_updated_at": datetime.now(timezone.utc).isoformat(),
            }
            bulk_ops.append(
                pymongo.UpdateOne({"iata": iata}, {"$set": update_fields}, upsert=False)
            )

        if bulk_ops:
            result = db[target_col].bulk_write(bulk_ops, ordered=False)
            updated_count = result.modified_count
            logger.info(f"Updated {updated_count} airport documents in '{target_col}' with cluster assignments.")

        return updated_count


def run_airport_clustering_pipeline(
    k: Optional[int] = None,
    random_state: Optional[int] = None,
    region: Optional[str] = None,
    save_to_mongodb: bool = True,
    models_dir: Optional[Path] = None,
    exports_dir: Optional[Path] = None,
) -> Tuple[AirportClusteringModel, pd.DataFrame, List[Dict[str, Any]]]:
    """
    Main driver executing the end-to-end airport clustering pipeline.
    """
    reg = (region or settings.DATASET_REGION).upper()
    if k is None:
        k = settings.KMEANS_K  # defaults to 4
    if random_state is None:
        random_state = settings.RANDOM_STATE

    logger.info(f"=== Starting AeroRoute Airport Clustering Pipeline [{reg}] (k={k}, random_state={random_state}) ===")

    # 1. Prepare raw features and scaled matrix
    db = get_db()
    raw_df, X_scaled, feat_names, transformer = prepare_clustering_dataset(db, region=reg)

    # 2. Fit clustering model
    model = AirportClusteringModel(k=k, random_state=random_state)
    model.fit(raw_df, X_scaled, transformer)

    # 3. Generate assigned DataFrame
    assigned_df = model.generate_cluster_assignments_df(raw_df, X_scaled)

    # 4. Generate cluster profiles
    profiles = model.generate_cluster_profiles(assigned_df)

    # 5. Persist artifacts
    model.save_artifacts(
        region=reg,
        models_dir=models_dir,
        exports_dir=exports_dir,
        assigned_df=assigned_df,
    )

    # 6. Update MongoDB if requested
    if save_to_mongodb:
        model.update_mongodb_airports(assigned_df, region=reg, db=db)

    # 7. Print Terminal Summary
    print("\n" + "=" * 90)
    print(f" AEROROUTE -- K-MEANS AIRPORT CLUSTERING COMPLETE [{reg}] (k={k})")
    print("=" * 90)
    print(f" Samples: {len(raw_df)} | Features: {len(feat_names)} | Random State: {random_state}")
    print(f" Inertia: {model.metrics['inertia']} | Silhouette: {model.metrics['silhouette_score']} | Davies-Bouldin: {model.metrics['davies_bouldin_score']}")
    print("-" * 90)

    for p in profiles:
        print(f"\n[Tier {p['cluster_id']}] {p['label']}")
        print(f"  Count: {p['size']} airports ({p['percentage_of_network']}%)")
        print(f"  Operational Medians -> Flights: {p['feature_medians']['total_flights']:,} | Dests: {p['feature_medians']['distinct_destinations']} | Centrality: {p['feature_medians']['betweenness_centrality']}")
        ex_iatas = [a["iata"] for a in p["representative_airports"][:5]]
        print(f"  Exemplar Hubs: {', '.join(ex_iatas)}")

    print("\n" + "=" * 90 + "\n")
    return model, assigned_df, profiles


def main():
    parser = argparse.ArgumentParser(description="AeroRoute K-Means Airport Clustering Model")
    parser.add_argument("--k", type=int, default=4, help="Number of clusters (default: 4)")
    parser.add_argument("--random-state", type=int, default=42, help="Random state seed (default: 42)")
    parser.add_argument("--region", type=str, default=None, choices=["INDIA", "US", "india", "us"], help="Regional scope (default: DATASET_REGION)")
    parser.add_argument("--no-db", action="store_true", help="Skip updating MongoDB airports collection")

    args = parser.parse_args()
    run_airport_clustering_pipeline(
        k=args.k,
        random_state=args.random_state,
        region=args.region,
        save_to_mongodb=not args.no_db,
    )


if __name__ == "__main__":
    main()
