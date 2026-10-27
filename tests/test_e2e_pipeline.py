# ============================================================
# AeroRoute -- End-to-End Pipeline Integration Test
# File : tests/test_e2e_pipeline.py
# Usage: pytest tests/test_e2e_pipeline.py
# ============================================================

import uuid
import pandas as pd
import pymongo
import pytest
from bson.code import Code
from sklearn.cluster import KMeans

from config.settings import settings
from models.feature_pipeline import AirportFeatureTransformer
from src.ingestion.preprocessor import clean_and_transform_chunk
from src.mapreduce.jobs import JOB_A_MAPPER, JOB_A_REDUCER
from src.utils.db import get_db


@pytest.mark.e2e
@pytest.mark.mongodb
def test_e2e_flight_data_pipeline(real_sample_chunk, synthetic_airports_ref, synthetic_airlines_ref, mongo_db):
    """
    End-to-End Pipeline Test using real subset of flight data:
      1. Preprocessing & Quality Filtering
      2. MongoDB Staging & Bulk Insertion into temporary test collection
      3. Server-Side MapReduce Job A Execution
      4. Python vs. MapReduce Aggregation Consistency Assertion
      5. ML Feature Transformation & Clustering Validation
      6. Idempotent Test Collection Teardown
    """
    test_id = uuid.uuid4().hex[:8]
    test_flights_coll = f"e2e_flights_{test_id}"
    test_mr_coll = f"e2e_mr_routes_{test_id}"

    try:
        # Step 1: Preprocessing
        # Enrich airports_ref with any origin/dest in real_sample_chunk so records are valid
        enhanced_airports = dict(synthetic_airports_ref)
        for _, row in real_sample_chunk.iterrows():
            orig = str(row.get("ORIGIN_AIRPORT", ""))
            dest = str(row.get("DESTINATION_AIRPORT", ""))
            if len(orig) == 3 and orig not in enhanced_airports:
                enhanced_airports[orig] = {"iata": orig, "name": f"Airport {orig}", "city": "Test", "state": "US", "country": "USA", "lat": 35.0, "lon": -90.0}
            if len(dest) == 3 and dest not in enhanced_airports:
                enhanced_airports[dest] = {"iata": dest, "name": f"Airport {dest}", "city": "Test", "state": "US", "country": "USA", "lat": 35.0, "lon": -90.0}

        cleaned_records, qa = clean_and_transform_chunk(
            real_sample_chunk,
            airports_ref=enhanced_airports,
            airlines_ref=synthetic_airlines_ref,
        )

        assert len(cleaned_records) > 0, "No records survived preprocessing!"

        # Step 2: Insert into isolated test collection
        mongo_db[test_flights_coll].insert_many(cleaned_records)
        assert mongo_db[test_flights_coll].count_documents({}) == len(cleaned_records)

        # Step 3: Run Server-Side MapReduce Job A on the test collection
        mongo_db[test_flights_coll].map_reduce(
            JOB_A_MAPPER,
            JOB_A_REDUCER,
            out=test_mr_coll,
            query={"is_route_eligible": True},
        )

        mr_results = list(mongo_db[test_mr_coll].find())
        assert len(mr_results) > 0, "MapReduce output collection is empty!"

        # Step 4: Python Verification Calculation Consistency
        # Filter route-eligible records and compute Pandas groupby
        eligible_records = [r for r in cleaned_records if r.get("is_route_eligible")]
        py_df = pd.DataFrame(eligible_records)
        py_counts = py_df.groupby("route_key").size().to_dict()

        # Verify each MapReduce document matches Python groupby exactly
        for doc in mr_results:
            rk = doc["_id"]
            mr_val = int(doc["value"])
            assert rk in py_counts, f"MapReduce route {rk} missing from Python calculation!"
            assert mr_val == py_counts[rk], (
                f"Discrepancy in route {rk}: MapReduce={mr_val} != Python={py_counts[rk]}"
            )

        # Step 5: Machine Learning Clustering Pipeline on Test Data
        # Build small feature matrix from test results
        test_feature_records = []
        for doc in mr_results:
            parts = doc["_id"].split("->")
            orig = parts[0]
            test_feature_records.append({
                "iata": orig,
                "total_flights": float(doc["value"]),
                "outgoing_flights": float(doc["value"]),
                "incoming_flights": float(doc["value"]),
                "distinct_destinations": 1.0,
                "distinct_origins": 1.0,
                "betweenness_centrality": 0.0,
                "pagerank": 0.001,
            })

        if len(test_feature_records) >= 3:
            test_ml_df = pd.DataFrame(test_feature_records)
            transformer = AirportFeatureTransformer()
            X_scaled, feat_names = transformer.fit_transform(test_ml_df)
            assert X_scaled.shape[1] == 7

            km = KMeans(n_clusters=2, random_state=42, n_init=5)
            labels = km.fit_predict(X_scaled)
            assert len(labels) == len(test_ml_df)
            assert set(labels).issubset({0, 1})

    finally:
        # Step 6: Idempotent Cleanup of temporary test collections
        mongo_db[test_flights_coll].drop()
        mongo_db[test_mr_coll].drop()
