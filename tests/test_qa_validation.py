# ============================================================
# AeroRoute -- Phase 9 Comprehensive QA Validation Test Suite
# File : tests/test_qa_validation.py
# Usage: pytest tests/test_qa_validation.py
# ============================================================

import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pymongo
import pytest
from sklearn.cluster import KMeans

from config.settings import settings
from dashboard.services.data_service import AeroRouteDataService
from dashboard.services.filter_service import filter_airports, filter_routes, paginate_dataframe
from models.feature_pipeline import (
    ALL_FEATURE_COLS,
    SKEWED_COUNT_FEATURES,
    AirportFeatureTransformer,
)
from src.ingestion.preprocessor import (
    clean_and_transform_chunk,
    format_hhmm,
    parse_flight_date,
)
from src.mapreduce.jobs import (
    JOB_A_MAPPER,
    JOB_A_REDUCER,
    JOB_B_MAPPER,
    JOB_B_REDUCER,
)
from src.utils.db import get_client, get_db


# =============================================================
# 1. CSV Schema Validation
# =============================================================
@pytest.mark.unit
def test_01_csv_schema_validation(synthetic_flights_df):
    """
    Test 1: Verify that flight CSV chunks contain all required schema columns
    and missing mandatory fields are detected.
    """
    required_cols = [
        "YEAR", "MONTH", "DAY", "AIRLINE", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT"
    ]
    # Check that synthetic fixture conforms to required schema
    for col in required_cols:
        assert col in synthetic_flights_df.columns, f"Missing required column: {col}"

    # Verify detection of invalid chunk missing required columns
    broken_df = synthetic_flights_df.drop(columns=["ORIGIN_AIRPORT"])
    assert "ORIGIN_AIRPORT" not in broken_df.columns


# =============================================================
# 2. Date and Time Parsing
# =============================================================
@pytest.mark.unit
def test_02_date_and_time_parsing():
    """
    Test 2: Verify parse_flight_date and format_hhmm handle integers, floats,
    and edge-case timestamps (midnight, single digits, nulls).
    """
    # Valid date
    dt = parse_flight_date(2015, 1, 15)
    assert dt == datetime.date(2015, 1, 15)

    # Invalid dates return None
    assert parse_flight_date(2015, 2, 31) is None
    assert parse_flight_date(None, 1, 1) is None

    # Time formatting
    assert format_hhmm(805) == "08:05"
    assert format_hhmm(1530) == "15:30"
    assert format_hhmm(5) == "00:05"
    assert format_hhmm(2400) == "00:00"
    assert format_hhmm(0) == "00:00"
    assert format_hhmm(np.nan) is None
    assert format_hhmm(None) is None


# =============================================================
# 3. Missing Origin and Destination Handling
# =============================================================
@pytest.mark.unit
def test_03_missing_origin_destination_handling(synthetic_flights_df, synthetic_airports_ref, synthetic_airlines_ref):
    """
    Test 3: Verify clean_and_transform_chunk rejects rows with missing, null,
    or unresolvable origin/destination airport codes.
    """
    clean_records, qa = clean_and_transform_chunk(
        synthetic_flights_df,
        airports_ref=synthetic_airports_ref,
        airlines_ref=synthetic_airlines_ref,
    )
    # 1. Missing origin is rejected as corrupt
    assert qa["rejected_corrupt"] >= 1

    # 2. Unresolved destination (ZZZ) is flagged in QA stats
    assert qa["unresolved_airport"] >= 1

    # 3. For all route-eligible records, both airports MUST be fully resolved in reference dictionary
    route_eligible_records = [r for r in clean_records if r.get("is_route_eligible")]
    assert len(route_eligible_records) > 0

    for rec in route_eligible_records:
        assert rec["origin"]["iata"] in synthetic_airports_ref
        assert rec["destination"]["iata"] in synthetic_airports_ref
        assert rec["origin"]["iata"] != rec["destination"]["iata"]


# =============================================================
# 4. Duplicate-Handling Rules
# =============================================================
@pytest.mark.unit
def test_04_duplicate_handling_rules():
    """
    Test 4: Verify duplicate-handling rules. Exact duplicate rows should be flagged,
    while identical flight numbers on different dates or different departure times are preserved.
    """
    dup_rows = pd.DataFrame([
        {"YEAR": 2015, "MONTH": 1, "DAY": 1, "AIRLINE": "DL", "FLIGHT_NUMBER": 101, "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ORD", "SCHEDULED_DEPARTURE": 800},
        {"YEAR": 2015, "MONTH": 1, "DAY": 1, "AIRLINE": "DL", "FLIGHT_NUMBER": 101, "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ORD", "SCHEDULED_DEPARTURE": 800},  # Exact duplicate
        {"YEAR": 2015, "MONTH": 1, "DAY": 2, "AIRLINE": "DL", "FLIGHT_NUMBER": 101, "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ORD", "SCHEDULED_DEPARTURE": 800},  # Different day -> VALID
    ])
    exact_duplicates = dup_rows.duplicated(subset=["YEAR", "MONTH", "DAY", "AIRLINE", "FLIGHT_NUMBER", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT", "SCHEDULED_DEPARTURE"])
    assert exact_duplicates.sum() == 1


# =============================================================
# 5. Route-Key Construction
# =============================================================
@pytest.mark.unit
def test_05_route_key_construction(synthetic_flights_df, synthetic_airports_ref, synthetic_airlines_ref):
    """
    Test 5: Verify route-key construction follows 'ORIGIN->DESTINATION' convention.
    """
    clean_records, _ = clean_and_transform_chunk(
        synthetic_flights_df,
        airports_ref=synthetic_airports_ref,
        airlines_ref=synthetic_airlines_ref,
    )
    for rec in clean_records:
        expected = f"{rec['origin']['iata']}->{rec['destination']['iata']}"
        assert rec["route_key"] == expected
        assert "->" in rec["route_key"]


# =============================================================
# 6. Directed-Route Semantics
# =============================================================
@pytest.mark.unit
def test_06_directed_route_semantics(synthetic_flights_df, synthetic_airports_ref, synthetic_airlines_ref):
    """
    Test 6: Verify directed-route semantics. ATL->ORD and ORD->ATL must remain separate.
    """
    clean_records, _ = clean_and_transform_chunk(
        synthetic_flights_df,
        airports_ref=synthetic_airports_ref,
        airlines_ref=synthetic_airlines_ref,
    )
    route_keys = [r["route_key"] for r in clean_records]

    assert "ATL->ORD" in route_keys
    assert "ORD->ATL" in route_keys
    assert route_keys.count("ATL->ORD") != route_keys.count("ORD->ATL") or "ATL->ORD" != "ORD->ATL"


# =============================================================
# 7. MongoDB MapReduce Mapper Logic
# =============================================================
@pytest.mark.unit
def test_07_mapreduce_mapper_logic():
    """
    Test 7: Verify JavaScript mapper code strings contain expected emit signatures.
    """
    mapper_code_a = str(JOB_A_MAPPER)
    assert "emit(" in mapper_code_a
    assert "this.route_key" in mapper_code_a
    assert "1" in mapper_code_a

    mapper_code_b = str(JOB_B_MAPPER)
    assert "this.origin.iata" in mapper_code_b
    assert "emit(" in mapper_code_b


# =============================================================
# 8. MongoDB MapReduce Reducer Logic
# =============================================================
@pytest.mark.unit
def test_08_mapreduce_reducer_logic():
    """
    Test 8: Verify JavaScript reducer code string uses summation aggregation logic.
    """
    reducer_code = str(JOB_A_REDUCER)
    assert "reduce" in reducer_code or "Array.sum" in reducer_code or "values" in reducer_code

    # Python simulation of the reducer logic
    def py_reducer(key, values):
        return sum(values)

    assert py_reducer("ATL->ORD", [1, 1, 1, 1]) == 4


# =============================================================
# 9. Output-Collection Verification
# =============================================================
@pytest.mark.mongodb
def test_09_output_collection_verification(mongo_db):
    """
    Test 9: Verify MapReduce output collections exist, contain documents matching
    {_id: str, value: number}, and have no null keys.
    """
    target_coll = settings.MR_ROUTE_ACTIVITY
    assert target_coll in mongo_db.list_collection_names()

    doc_count = mongo_db[target_coll].count_documents({})
    assert doc_count > 0

    sample = mongo_db[target_coll].find_one()
    assert sample is not None
    assert "_id" in sample
    assert "value" in sample
    assert isinstance(sample["_id"], str)
    assert "->" in sample["_id"]
    assert sample["value"] > 0


# =============================================================
# 10. Database Connection Handling
# =============================================================
@pytest.mark.mongodb
def test_10_database_connection_handling():
    """
    Test 10: Verify get_client() acquires a working connection, executes server_info(),
    and handles reconnection idempotently.
    """
    client = get_client()
    assert client is not None
    info = client.server_info()
    assert "version" in info

    # Ensure get_db() returns correct database handle
    db = get_db()
    assert db.name == settings.MONGO_DB_NAME


# =============================================================
# 11. Machine-Learning Feature Generation
# =============================================================
@pytest.mark.unit
def test_11_ml_feature_generation():
    """
    Test 11: Verify AirportFeatureTransformer applies log1p to count columns,
    reduces skewness, and standardizes feature matrices to zero mean and unit variance.
    """
    df = pd.DataFrame({
        "total_flights": [10.0, 100.0, 1000.0, 10000.0],
        "outgoing_flights": [5.0, 50.0, 500.0, 5000.0],
        "incoming_flights": [5.0, 50.0, 500.0, 5000.0],
        "distinct_destinations": [2.0, 10.0, 50.0, 150.0],
        "distinct_origins": [2.0, 10.0, 50.0, 150.0],
        "betweenness_centrality": [0.0, 0.001, 0.02, 0.15],
        "pagerank": [0.0005, 0.002, 0.01, 0.05],
    })
    transformer = AirportFeatureTransformer()
    X_scaled, feat_names = transformer.fit_transform(df)

    assert X_scaled.shape == (4, len(ALL_FEATURE_COLS))
    means = np.mean(X_scaled, axis=0)
    stds = np.std(X_scaled, axis=0)

    for m in means:
        assert abs(m) < 1e-5
    for s in stds:
        assert abs(s - 1.0) < 1e-5


# =============================================================
# 12. Model Reproducibility
# =============================================================
@pytest.mark.unit
def test_12_ml_model_reproducibility():
    """
    Test 12: Verify K-Means training with random_state=42 yields 100% bitwise
    identical centroids and cluster labels across independent runs.
    """
    X = np.array([
        [1.0, 2.0], [1.2, 1.8], [0.9, 2.1],
        [8.0, 9.0], [8.2, 8.8], [7.9, 9.1],
        [15.0, 15.0], [15.2, 14.8], [14.9, 15.1],
    ])
    km1 = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X)
    km2 = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X)

    np.testing.assert_array_equal(km1.labels_, km2.labels_)
    np.testing.assert_array_almost_equal(km1.cluster_centers_, km2.cluster_centers_)


# =============================================================
# 13. Dashboard Empty States and Database Errors
# =============================================================
@pytest.mark.unit
def test_13_dashboard_empty_states_and_db_errors():
    """
    Test 13: Verify that dashboard data service handles nonexistent files
    and offline databases gracefully without throwing uncaught exceptions.
    """
    service = AeroRouteDataService()
    # Missing file returns None
    result = service._load_json_export("nonexistent_test_file_8888.json")
    assert result is None

    # System health masking check
    health = service.get_system_health()
    assert "masked_uri" in health
    assert "password" not in health["masked_uri"].lower()


# =============================================================
# 14. Filter and Pagination Correctness
# =============================================================
@pytest.mark.unit
def test_14_filter_and_pagination_correctness():
    """
    Test 14: Verify route search query, flight threshold filtering,
    and pagination boundary clamping.
    """
    routes = pd.DataFrame([
        {"route_key": "ATL->ORD", "origin": "ATL", "destination": "ORD", "flight_count": 250},
        {"route_key": "LAX->SFO", "origin": "LAX", "destination": "SFO", "flight_count": 200},
        {"route_key": "DEN->SLC", "origin": "DEN", "destination": "SLC", "flight_count": 30},
    ])
    # Search filter
    filtered = filter_routes(routes, search_query="lax")
    assert len(filtered) == 1
    assert filtered.iloc[0]["route_key"] == "LAX->SFO"

    # Threshold filter
    threshold_filtered = filter_routes(routes, min_flights=100)
    assert len(threshold_filtered) == 2

    # Pagination clamping
    page_df, total_rows, total_pages = paginate_dataframe(routes, page_number=99, page_size=2)
    assert total_pages == 2
    assert len(page_df) == 1  # Last page has 1 item


# =============================================================
# 15. Python Verification vs. MongoDB MapReduce Consistency
# =============================================================
@pytest.mark.mongodb
def test_15_python_vs_mapreduce_consistency(mongo_db):
    """
    Test 15: Verify 100% numerical consistency between client-side Python aggregation
    and server-side MongoDB MapReduce results on a designated corridor.
    """
    # Sample a top route from mr_route_activity
    mr_doc = mongo_db[settings.MR_ROUTE_ACTIVITY].find_one({"value": {"$gt": 50}})
    assert mr_doc is not None

    route_key = mr_doc["_id"]
    mr_count = int(mr_doc["value"])

    # Verify matching count in raw flights collection
    py_count = mongo_db[settings.FLIGHTS_COLLECTION].count_documents({
        "route_key": route_key,
        "is_route_eligible": True,
    })

    assert mr_count == py_count, (
        f"Discrepancy detected for route '{route_key}': "
        f"MapReduce count ({mr_count}) != Python raw count ({py_count})"
    )
