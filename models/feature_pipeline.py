# ============================================================
# AeroRoute -- Feature Generation & Transformation Pipeline
# File : models/feature_pipeline.py
# ============================================================

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
import pymongo
from sklearn.preprocessing import StandardScaler

from analytics.network_analysis import (
    build_airport_directed_graph,
    compute_centrality_metrics,
)
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("feature_pipeline")

# Features subject to log1p transformation due to heavy-tailed power-law distribution
SKEWED_COUNT_FEATURES = [
    "total_flights",
    "outgoing_flights",
    "incoming_flights",
    "distinct_destinations",
    "distinct_origins",
]

# Graph centrality features (already bounded or normalized, but scaled)
GRAPH_CENTRALITY_FEATURES = [
    "betweenness_centrality",
    "pagerank",
]

ALL_FEATURE_COLS = SKEWED_COUNT_FEATURES + GRAPH_CENTRALITY_FEATURES


def extract_airport_raw_features(
    db: pymongo.database.Database,
    region: Optional[str] = None,
) -> pd.DataFrame:
    """
    Extract raw airport connectivity and network centrality features from MongoDB and NetworkX.
    Filters strictly for airports with observed flight activity.
    """
    reg = (region or settings.DATASET_REGION).upper()
    conn_col = settings.get_mr_airport_connectivity_collection(reg)
    logger.info(f"Extracting airport features for region [{reg}] from '{conn_col}' and NetworkX...")

    # 1. Fetch connectivity data from mr_airport_connectivity
    conn_cursor = db[conn_col].find()
    conn_map = {}
    for doc in conn_cursor:
        iata = doc["_id"]
        val = doc.get("value", {})
        # Support both Indian timetable schema and US operated flight schema
        out_vol = float(val.get("outgoing_weekly_frequency", val.get("outgoing_flights", 0)))
        in_vol = float(val.get("incoming_weekly_frequency", val.get("incoming_flights", 0)))
        tot_vol = float(val.get("total_weekly_frequency", val.get("total_flights", 0)))

        conn_map[iata] = {
            "outgoing_flights": out_vol,
            "incoming_flights": in_vol,
            "total_flights": tot_vol,
            "distinct_destinations": float(val.get("out_degree", 0)),
            "distinct_origins": float(val.get("in_degree", 0)),
            "distinct_connections": float(val.get("distinct_connections", 0)),
        }

    if not conn_map:
        logger.error(f"No connectivity records found in '{conn_col}'!")
        return pd.DataFrame()

    # 2. Build graph and compute network centrality metrics
    G = build_airport_directed_graph(db, region=reg)
    centrality_df = compute_centrality_metrics(G)
    centrality_map = {}
    for _, row in centrality_df.iterrows():
        centrality_map[row["iata"]] = {
            "betweenness_centrality": float(row.get("betweenness_centrality", 0.0)),
            "pagerank": float(row.get("pagerank", 0.0)),
            "name": row.get("name", "Unknown"),
            "city": row.get("city", "Unknown"),
            "state": row.get("state", "NA"),
            "lat": row.get("lat"),
            "lon": row.get("lon"),
        }

    # 3. Join records into a unified DataFrame
    records = []
    for iata, c_data in conn_map.items():
        cent = centrality_map.get(iata, {})
        records.append({
            "iata": iata,
            "name": cent.get("name", "Unknown Airport"),
            "city": cent.get("city", "Unknown City"),
            "state": cent.get("state", "NA"),
            "lat": cent.get("lat"),
            "lon": cent.get("lon"),
            "total_flights": c_data["total_flights"],
            "outgoing_flights": c_data["outgoing_flights"],
            "incoming_flights": c_data["incoming_flights"],
            "distinct_destinations": c_data["distinct_destinations"],
            "distinct_origins": c_data["distinct_origins"],
            "distinct_connections": c_data["distinct_connections"],
            "betweenness_centrality": cent.get("betweenness_centrality", 0.0),
            "pagerank": cent.get("pagerank", 0.0),
        })

    df = pd.DataFrame(records)
    logger.info(f"[{reg}] Extracted {len(df)} airport records with {len(ALL_FEATURE_COLS)} features.")
    return df


class AirportFeatureTransformer:
    """
    Reproducible feature preprocessing pipeline for airport clustering:
      1. Log1p transformation of heavy-tailed flight counts and connection degrees.
      2. StandardScaler standardization across all transformed features.
    """

    def __init__(self):
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_names: List[str] = []

    def fit_transform(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Fit scaler on DataFrame and return scaled feature matrix and feature names.
        """
        X_df = self._transform_skewed_features(df)
        self.feature_names = list(X_df.columns)
        X_scaled = self.scaler.fit_transform(X_df)
        self.is_fitted = True
        logger.info(f"Fitted AirportFeatureTransformer on {len(df)} samples across {len(self.feature_names)} features.")
        return X_scaled, self.feature_names

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transform new data using the already fitted scaler.
        """
        if not self.is_fitted:
            raise RuntimeError("Transformer has not been fitted yet! Call fit_transform first.")
        X_df = self._transform_skewed_features(df)
        return self.scaler.transform(X_df)

    def _transform_skewed_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply log1p transformation to heavy-tailed count columns.
        Keeps bounded/normalized centrality features unchanged before standardization.
        """
        transformed_df = pd.DataFrame(index=df.index)

        # Apply log1p: y = log(1 + x)
        for col in SKEWED_COUNT_FEATURES:
            if col in df.columns:
                transformed_df[f"log1p_{col}"] = np.log1p(df[col].astype(float))

        # Copy centrality features directly
        for col in GRAPH_CENTRALITY_FEATURES:
            if col in df.columns:
                transformed_df[col] = df[col].astype(float)

        return transformed_df

    def save(self, filepath: Path) -> Path:
        """Save fitted transformer to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, filepath)
        logger.info(f"Saved feature transformer to: {filepath}")
        return filepath

    @classmethod
    def load(cls, filepath: Path) -> "AirportFeatureTransformer":
        """Load fitted transformer from disk."""
        transformer = joblib.load(filepath)
        logger.info(f"Loaded feature transformer from: {filepath}")
        return transformer


def prepare_clustering_dataset(
    db: Optional[pymongo.database.Database] = None,
    region: Optional[str] = None,
) -> Tuple[pd.DataFrame, np.ndarray, List[str], AirportFeatureTransformer]:
    """
    Convenience function extracting raw airport features and transforming them.
    Returns:
        (raw_df, X_scaled, feature_names, transformer)
    """
    if db is None:
        db = get_db()

    raw_df = extract_airport_raw_features(db, region=region)
    if raw_df.empty:
        raise ValueError("Cannot prepare dataset: extracted airport feature DataFrame is empty!")

    transformer = AirportFeatureTransformer()
    X_scaled, feature_names = transformer.fit_transform(raw_df)

    return raw_df, X_scaled, feature_names, transformer
