# ============================================================
# AeroRoute -- Indian Domestic Aviation Ingestion Test Suite
# File : tests/test_indian_ingestion.py
# Phase: Phase 2 Validation Tests
# ============================================================

import datetime
from pathlib import Path
import pandas as pd
import pytest
import pymongo

from config.settings import settings
from src.ingestion.indian_reference_data import (
    INDIAN_STATION_MAP,
    INDIAN_AIRLINES_MAP,
    get_airport_by_station,
    get_airline_by_name,
)
from src.ingestion.indian_preprocessor import (
    haversine_distance,
    format_time_hhmm,
    parse_iso_date,
    parse_days_of_week,
    clean_and_transform_indian_chunk,
    build_indian_airports_documents,
    build_indian_airlines_documents,
)
from src.utils.db import get_db


# ----------------------------------------------------------------------
# 1. Indian Reference Data Unit Tests
# ----------------------------------------------------------------------
@pytest.mark.unit
class TestIndianReferenceData:
    """Test suite verifying Indian aviation reference data integrity."""

    def test_station_map_coverage(self):
        """Verify all 110 stations in the dataset are mapped without None."""
        assert len(INDIAN_STATION_MAP) == 110
        for name, meta in INDIAN_STATION_MAP.items():
            assert meta["iata"] is not None and len(meta["iata"]) == 3
            assert meta["icao"] is not None and len(meta["icao"]) == 4
            assert meta["name"] is not None
            assert meta["city"] is not None
            assert meta["state"] is not None
            # Latitude and Longitude bounding box for Indian subcontinent
            assert 8.0 <= meta["lat"] <= 36.0, f"Latitude out of bounds for {name}: {meta['lat']}"
            assert 68.0 <= meta["lon"] <= 98.0, f"Longitude out of bounds for {name}: {meta['lon']}"

    def test_unique_airports_and_aliases(self):
        """Verify that 107 unique IATAs represent the 110 raw station names with aliases."""
        unique_iatas = set(m["iata"] for m in INDIAN_STATION_MAP.values())
        assert len(unique_iatas) == 107
        
        # Verify known aliases resolve to identical IATA
        assert get_airport_by_station("Kannur")["iata"] == "CNN"
        assert get_airport_by_station("Kannur International Airport")["iata"] == "CNN"
        assert get_airport_by_station("Nagpur")["iata"] == "NAG"
        assert get_airport_by_station("MIHAN")["iata"] == "NAG"
        assert get_airport_by_station("Shirdi")["iata"] == "SAG"
        assert get_airport_by_station("Shirdi Airport")["iata"] == "SAG"

    def test_airline_map_coverage(self):
        """Verify all 14 Indian airlines are mapped with proper IATA codes."""
        assert len(INDIAN_AIRLINES_MAP) == 14
        expected_codes = {"9W", "IX", "AI", "UK", "6E", "2T", "I7", "QP", "SG", "G8", "S2", "9I", "S9", "S5"}
        found_codes = set(m["airline_code"] for m in INDIAN_AIRLINES_MAP.values())
        assert found_codes == expected_codes

    def test_build_airports_documents_deduplication(self):
        """Verify that build_indian_airports_documents produces 107 docs with station_aliases."""
        docs = build_indian_airports_documents()
        assert len(docs) == 107
        doc_map = {d["iata"]: d for d in docs}
        assert "CNN" in doc_map
        assert set(doc_map["CNN"]["station_aliases"]) == {"Kannur", "Kannur International Airport"}
        assert "NAG" in doc_map
        assert set(doc_map["NAG"]["station_aliases"]) == {"Nagpur", "MIHAN"}
        assert "SAG" in doc_map
        assert set(doc_map["SAG"]["station_aliases"]) == {"Shirdi", "Shirdi Airport"}


# ----------------------------------------------------------------------
# 2. Indian Preprocessor Helper Unit Tests
# ----------------------------------------------------------------------
@pytest.mark.unit
class TestIndianPreprocessorHelpers:
    """Test suite verifying mathematical, temporal, and parsing helpers."""

    def test_haversine_distance_del_bom(self):
        """Verify DEL (28.5665, 77.1031) to BOM (19.0896, 72.8656) is ~1137 km."""
        del_meta = get_airport_by_station("Delhi")
        bom_meta = get_airport_by_station("Mumbai")
        dist = haversine_distance(del_meta["lat"], del_meta["lon"], bom_meta["lat"], bom_meta["lon"])
        assert 1130.0 <= dist <= 1160.0, f"Unexpected DEL-BOM distance: {dist}"

    def test_haversine_zero_distance(self):
        """Verify identical coordinates produce 0.0 distance."""
        dist = haversine_distance(28.5665, 77.1031, 28.5665, 77.1031)
        assert dist == 0.0

    def test_format_time_hhmm(self):
        """Verify 24-hr time parsing and minute calculation."""
        t_str, mins = format_time_hhmm("06:30")
        assert t_str == "06:30"
        assert mins == 390

        t_str, mins = format_time_hhmm("23:59")
        assert t_str == "23:59"
        assert mins == 1439

        t_str, mins = format_time_hhmm("00:00")
        assert t_str == "00:00"
        assert mins == 0

        # Invalid cases
        assert format_time_hhmm(None) == (None, None)
        assert format_time_hhmm("") == (None, None)
        assert format_time_hhmm("invalid") == (None, None)
        assert format_time_hhmm("25:00") == (None, None)

    def test_parse_iso_date(self):
        """Verify ISO date parsing."""
        d = parse_iso_date("2022-10-30")
        assert d == datetime.date(2022, 10, 30)
        assert parse_iso_date(None) is None
        assert parse_iso_date("bad-date") is None

    def test_parse_days_of_week(self):
        """Verify day-of-week parsing and frequency calculation."""
        days_str, freq, booleans = parse_days_of_week("Daily")
        assert freq == 7
        assert all(booleans.values())

        days_str, freq, booleans = parse_days_of_week("Monday,Wednesday,Friday")
        assert freq == 3
        assert booleans["monday"] is True
        assert booleans["tuesday"] is False
        assert booleans["wednesday"] is True
        assert booleans["thursday"] is False
        assert booleans["friday"] is True
        assert booleans["saturday"] is False
        assert booleans["sunday"] is False


# ----------------------------------------------------------------------
# 3. Chunk Transformation & Non-Fabrication Unit Tests
# ----------------------------------------------------------------------
@pytest.mark.unit
class TestIndianChunkTransformation:
    """Test suite verifying transformation pipeline, data provenance, and non-fabrication."""

    def test_transform_valid_sample(self):
        """Verify normal conversion of a valid schedule record."""
        df_sample = pd.DataFrame([
            {
                "airline": "Air India",
                "flightNumber": "AI 887",
                "origin": "Delhi",
                "destination": "Mumbai",
                "scheduledDepartureTime": "07:00",
                "scheduledArrivalTime": "09:15",
                "validFrom": "2022-10-30",
                "validTo": "2023-03-25",
                "daysOfWeek": "Daily",
                "timezone": "IST",
                "lastUpdated": "2022-10-15",
            }
        ])

        seen = set()
        docs, stats = clean_and_transform_indian_chunk(df_sample, seen, dataset_mode="clean")
        assert len(docs) == 1
        assert stats["valid"] == 1
        assert stats["rejected_corrupt"] == 0

        doc = docs[0]
        assert doc["airline_code"] == "AI"
        assert doc["flight_number"] == "AI 887"
        assert doc["origin"]["iata"] == "DEL"
        assert doc["destination"]["iata"] == "BOM"
        assert doc["scheduled_departure_formatted"] == "07:00"
        assert doc["scheduled_departure"] == 420
        assert doc["scheduled_arrival_formatted"] == "09:15"
        assert doc["scheduled_arrival"] == 555
        assert doc["distance_km"] > 1130.0
        assert doc["operating_days_count"] == 7
        assert doc["is_route_eligible"] is True

        # STRICT NON-FABRICATION ASSERTIONS
        assert doc["record_type"] == "SCHEDULED_SERVICE"
        assert doc["departure_delay"] is None
        assert doc["arrival_delay"] is None
        assert doc["delay_breakdown"] is None
        assert doc["is_cancelled"] is False
        assert doc["is_diverted"] is False

    def test_rejection_of_corrupt_records(self):
        """Verify invalid or unresolvable stations/times are rejected without fabrication."""
        df_corrupt = pd.DataFrame([
            # Missing departure time
            {
                "airline": "IndiGo", "flightNumber": "6E 101",
                "origin": "Delhi", "destination": "Mumbai",
                "scheduledDepartureTime": None, "scheduledArrivalTime": "09:00",
                "validFrom": "2022-10-30", "validTo": "2023-03-25",
            },
            # Unknown station
            {
                "airline": "IndiGo", "flightNumber": "6E 102",
                "origin": "Atlantis", "destination": "Mumbai",
                "scheduledDepartureTime": "07:00", "scheduledArrivalTime": "09:00",
                "validFrom": "2022-10-30", "validTo": "2023-03-25",
            },
            # Self-loop
            {
                "airline": "IndiGo", "flightNumber": "6E 103",
                "origin": "Delhi", "destination": "Delhi",
                "scheduledDepartureTime": "07:00", "scheduledArrivalTime": "08:00",
                "validFrom": "2022-10-30", "validTo": "2023-03-25",
            },
        ])

        seen = set()
        docs, stats = clean_and_transform_indian_chunk(df_corrupt, seen, dataset_mode="clean")
        assert len(docs) == 0
        assert stats["valid"] == 0
        assert stats["rejected_missing_time"] == 1
        assert stats["rejected_unresolved_station"] == 1
        assert stats["rejected_self_loop"] == 1

    def test_duplicate_filtering(self):
        """Verify identical schedule filings within a chunk are deduplicated."""
        record = {
            "airline": "SpiceJet",
            "flightNumber": "SG 123",
            "origin": "Delhi",
            "destination": "Bengaluru",
            "scheduledDepartureTime": "10:00",
            "scheduledArrivalTime": "12:45",
            "validFrom": "2022-10-30",
            "validTo": "2023-03-25",
            "daysOfWeek": "Daily",
        }
        df_dup = pd.DataFrame([record, record])
        seen = set()
        docs, stats = clean_and_transform_indian_chunk(df_dup, seen, dataset_mode="clean")
        assert len(docs) == 1
        assert stats["valid"] == 1
        assert stats["exact_duplicates"] == 1


# ----------------------------------------------------------------------
# 4. MongoDB Database Integration & Preservation Tests
# ----------------------------------------------------------------------
@pytest.mark.mongodb
class TestIndianMongoDBIntegration:
    """Integration test suite against the live MongoDB instance."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = get_db()

    def test_original_us_collections_untouched(self):
        """Strictly verify original US collections have not been modified or dropped."""
        assert self.db[settings.FLIGHTS_COLLECTION].count_documents({}) == 100000
        assert self.db[settings.AIRPORTS_COLLECTION].count_documents({}) == 322
        assert self.db[settings.AIRLINES_COLLECTION].count_documents({}) == 14

    def test_indian_collections_populated(self):
        """Verify Indian collections contain expected records."""
        flight_count = self.db[settings.INDIAN_FLIGHTS_COLLECTION].count_documents({})
        airport_count = self.db[settings.INDIAN_AIRPORTS_COLLECTION].count_documents({})
        airline_count = self.db[settings.INDIAN_AIRLINES_COLLECTION].count_documents({})

        assert flight_count == 33023
        assert airport_count == 107
        assert airline_count == 14

    def test_indian_airports_geospatial_index(self):
        """Verify 2dsphere geospatial index is present and operational on airports_in."""
        indexes = self.db[settings.INDIAN_AIRPORTS_COLLECTION].index_information()
        assert "idx_airport_location_2dsphere" in indexes
        assert indexes["idx_airport_location_2dsphere"]["key"] == [("location", "2dsphere")]

    def test_indian_flights_no_fabrication_in_db(self):
        """Query flights_in to guarantee 0 documents have fabricated delay or operated fields."""
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]

        # 1. 100% must have record_type == "SCHEDULED_SERVICE"
        invalid_type = flights.count_documents({"record_type": {"$ne": "SCHEDULED_SERVICE"}})
        assert invalid_type == 0, f"Found {invalid_type} documents without SCHEDULED_SERVICE type"

        # 2. 100% must have null departure and arrival delays
        fab_dep = flights.count_documents({"departure_delay": {"$ne": None}})
        assert fab_dep == 0, f"Found {fab_dep} documents with fabricated departure_delay"

        fab_arr = flights.count_documents({"arrival_delay": {"$ne": None}})
        assert fab_arr == 0, f"Found {fab_arr} documents with fabricated arrival_delay"

        fab_breakdown = flights.count_documents({"delay_breakdown": {"$ne": None}})
        assert fab_breakdown == 0, f"Found {fab_breakdown} documents with fabricated delay_breakdown"

    def test_pipeline_audit_run_logged(self):
        """Verify that load_indian_data logged an audit document in pipeline_runs."""
        run = self.db["pipeline_runs"].find_one({"run_id": {"$regex": "^RUN_IN_"}})
        assert run is not None
        assert run["status"] == "COMPLETED"
        assert run["stats"]["valid"] == 33023
        assert run["target_collection"] == settings.INDIAN_FLIGHTS_COLLECTION
