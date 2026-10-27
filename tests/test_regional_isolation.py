# ============================================================
# AeroRoute -- Test Suite: Regional Data Isolation
# File : tests/test_regional_isolation.py
# Phase: Phase 8 Testing & Regional Isolation Verification
# ============================================================

import pytest
from src.utils.db import get_db
from config.settings import settings
from dashboard.services.database import get_collection_counts
from dashboard.services.analytics_service import get_top_directed_routes


class TestRegionalDataIsolation:
    """
    Verify complete strict isolation between Indian and US datasets.
    Zero cross-contamination; separate collections; preserved counts.
    """

    def test_settings_collection_resolution(self):
        # India resolution
        assert settings.get_flights_collection("INDIA") == "flights_in"
        assert settings.get_airports_collection("INDIA") == "airports_in"
        assert settings.get_mr_route_activity_collection("INDIA") == "mr_route_activity_in"
        assert settings.get_mr_airport_outgoing_collection("INDIA") == "mr_airport_outgoing_in"
        assert settings.get_mr_airport_incoming_collection("INDIA") == "mr_airport_incoming_in"
        assert settings.get_mr_monthly_route_collection("INDIA") == "mr_monthly_route_in"
        assert settings.get_mr_airport_connectivity_collection("INDIA") == "mr_airport_connectivity_in"

        # US resolution
        assert settings.get_flights_collection("US") == "flights"
        assert settings.get_airports_collection("US") == "airports"
        assert settings.get_mr_route_activity_collection("US") == "mr_route_activity"
        assert settings.get_mr_airport_outgoing_collection("US") == "mr_airport_outgoing"
        assert settings.get_mr_airport_incoming_collection("US") == "mr_airport_incoming"
        assert settings.get_mr_monthly_route_collection("US") == "mr_monthly_route"
        assert settings.get_mr_airport_connectivity_collection("US") == "mr_airport_connectivity"

    def test_collection_counts_isolation(self):
        in_counts = get_collection_counts("INDIA")
        us_counts = get_collection_counts("US")

        # India counts
        assert in_counts["flights"] == 33023
        assert in_counts["airports"] == 107
        assert in_counts["airlines"] == 14
        assert in_counts["mr_route_activity"] == 1381

        # US counts
        assert us_counts["flights"] == 100000
        assert us_counts["airports"] == 322
        assert us_counts["airlines"] == 14
        assert us_counts["mr_route_activity"] == 4129

        # Ensure Indian counts != US counts
        assert in_counts["flights"] != us_counts["flights"]
        assert in_counts["airports"] != us_counts["airports"]
        assert in_counts["mr_route_activity"] != us_counts["mr_route_activity"]

    def test_distinct_route_query_isolation(self):
        # Query top routes for India
        in_routes_df = get_top_directed_routes(limit=5, region="INDIA")
        in_origins = set(in_routes_df["origin"].tolist())
        # All top Indian hubs should be Indian IATAs
        assert any(hub in in_origins for hub in ["DEL", "BOM", "BLR", "HYD", "CCU"])
        # Should NOT contain US hubs like ATL, ORD, DFW, LAX
        assert not any(hub in in_origins for hub in ["ATL", "ORD", "DFW", "LAX"])

        # Query top routes for US
        us_routes_df = get_top_directed_routes(limit=5, region="US")
        us_origins = set(us_routes_df["origin"].tolist())
        assert any(hub in us_origins for hub in ["ATL", "ORD", "DFW", "LAX", "DEN", "SFO"])
        # Should NOT contain Indian hubs like DEL, BOM
        assert not any(hub in us_origins for hub in ["DEL", "BOM", "BLR", "HYD"])

    def test_database_document_fields_isolation(self):
        db = get_db()

        # Check an Indian flight document
        in_flight = db["flights_in"].find_one({"is_route_eligible": True})
        assert in_flight is not None
        assert "operating_days_count" in in_flight
        assert "timetable_entry_id" in in_flight or "flight_number" in in_flight
        assert in_flight["origin"]["country"] == "India"
        assert in_flight["destination"]["country"] == "India"

        # Check a US flight document
        us_flight = db["flights"].find_one({"is_route_eligible": True})
        assert us_flight is not None
        assert "year" in us_flight
        assert "month" in us_flight
        assert "origin_airport" in us_flight or "origin" in us_flight
