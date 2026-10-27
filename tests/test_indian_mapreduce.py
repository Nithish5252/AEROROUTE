# ============================================================
# AeroRoute -- Test Suite: Indian MongoDB MapReduce Adaptation
# File : tests/test_indian_mapreduce.py
# Phase: Phase 3 Verification & Validation Tests
# ============================================================

import unittest
import pytest
import pymongo
from config.settings import settings
from src.mapreduce.indian_jobs import (
    INDIAN_JOB_A_MAPPER, INDIAN_JOB_A_REDUCER, INDIAN_JOB_A_FINALIZE,
    INDIAN_JOB_B_MAPPER, INDIAN_JOB_B_REDUCER, INDIAN_JOB_B_FINALIZE,
    INDIAN_JOB_C_MAPPER, INDIAN_JOB_C_REDUCER, INDIAN_JOB_C_FINALIZE,
    INDIAN_JOB_D_MAPPER, INDIAN_JOB_D_REDUCER, INDIAN_JOB_D_FINALIZE,
    INDIAN_JOB_E_MAPPER, INDIAN_JOB_E_REDUCER, INDIAN_JOB_E_FINALIZE,
    INDIAN_MAPREDUCE_QUERY_FILTER,
)
from src.utils.db import get_db
from scripts.run_indian_mapreduce import run_pipeline


@pytest.mark.mongodb
class TestIndianMapReduceJobs(unittest.TestCase):
    """Test suite verifying all five Indian MapReduce jobs and domain constraints."""

    def setUp(self):
        self.db = get_db()
        self.flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        if self.flights.count_documents({}) == 0:
            self.skipTest("Collection flights_in must be populated")

    def test_job_a_directed_route_activity(self):
        """Test Job A creates directed route activity distinguishing services & frequency."""
        out_col = "test_mr_in_job_a"
        self.flights.map_reduce(
            INDIAN_JOB_A_MAPPER,
            INDIAN_JOB_A_REDUCER,
            out={"replace": out_col},
            finalize=INDIAN_JOB_A_FINALIZE,
            query=INDIAN_MAPREDUCE_QUERY_FILTER,
            limit=1000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample = col.find_one()
        self.assertIsNotNone(sample)
        self.assertIn("->", sample["_id"])

        val = sample["value"]
        self.assertIn("timetable_services", val)
        self.assertIn("weekly_frequency", val)
        self.assertIn("estimated_monthly_departures", val)
        self.assertIn("distance_km", val)
        self.assertIn("airlines", val)
        self.assertIn("carrier_count", val)
        self.assertEqual(val["data_source"], "DGCA_Airline_Timetables_2018_2025")
        self.assertEqual(val["metric_type"], "SCHEDULED_ROUTE_CAPACITY")
        self.assertEqual(val["carrier_count"], len(val["airlines"]))
        col.drop()

    def test_job_b_airport_outgoing_activity(self):
        """Test Job B outputs airport-level scheduled outgoing metrics."""
        out_col = "test_mr_in_job_b"
        self.flights.map_reduce(
            INDIAN_JOB_B_MAPPER,
            INDIAN_JOB_B_REDUCER,
            out={"replace": out_col},
            finalize=INDIAN_JOB_B_FINALIZE,
            query=INDIAN_MAPREDUCE_QUERY_FILTER,
            limit=1000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample = col.find_one()
        self.assertIsNotNone(sample)
        self.assertEqual(len(sample["_id"]), 3)  # 3-char IATA

        val = sample["value"]
        self.assertIn("outgoing_timetable_services", val)
        self.assertIn("outgoing_weekly_frequency", val)
        self.assertIn("estimated_monthly_departures", val)
        self.assertIn("out_degree_destinations", val)
        self.assertIn("destinations", val)
        self.assertEqual(val["out_degree_destinations"], len(val["destinations"]))
        col.drop()

    def test_job_c_airport_incoming_activity(self):
        """Test Job C outputs airport-level scheduled incoming metrics."""
        out_col = "test_mr_in_job_c"
        self.flights.map_reduce(
            INDIAN_JOB_C_MAPPER,
            INDIAN_JOB_C_REDUCER,
            out={"replace": out_col},
            finalize=INDIAN_JOB_C_FINALIZE,
            query=INDIAN_MAPREDUCE_QUERY_FILTER,
            limit=1000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample = col.find_one()
        self.assertIsNotNone(sample)
        self.assertEqual(len(sample["_id"]), 3)

        val = sample["value"]
        self.assertIn("incoming_timetable_services", val)
        self.assertIn("incoming_weekly_frequency", val)
        self.assertIn("estimated_monthly_arrivals", val)
        self.assertIn("in_degree_origins", val)
        self.assertIn("origins", val)
        self.assertEqual(val["in_degree_origins"], len(val["origins"]))
        col.drop()

    def test_job_d_monthly_route_seasonality(self):
        """Test Job D outputs monthly route coverage with structured key and non-operational labels."""
        out_col = "test_mr_in_job_d"
        self.flights.map_reduce(
            INDIAN_JOB_D_MAPPER,
            INDIAN_JOB_D_REDUCER,
            out={"replace": out_col},
            finalize=INDIAN_JOB_D_FINALIZE,
            query=INDIAN_MAPREDUCE_QUERY_FILTER,
            limit=500,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample = col.find_one()
        self.assertIsNotNone(sample)
        key = sample["_id"]
        self.assertIn("year_month", key)
        self.assertIn("origin", key)
        self.assertIn("destination", key)
        self.assertIn("route_key", key)

        val = sample["value"]
        self.assertIn("active_timetable_services", val)
        self.assertIn("weekly_frequency", val)
        self.assertIn("metric_description", val)
        # Verify explicit non-operational documentation in payload
        self.assertIn("Does not represent operated flight events", val["metric_description"])
        col.drop()

    def test_job_e_airport_connectivity_summary(self):
        """Test Job E generates degree and scheduled movement metrics without inflation."""
        out_col = "test_mr_in_job_e"
        self.flights.map_reduce(
            INDIAN_JOB_E_MAPPER,
            INDIAN_JOB_E_REDUCER,
            out={"replace": out_col},
            finalize=INDIAN_JOB_E_FINALIZE,
            query=INDIAN_MAPREDUCE_QUERY_FILTER,
            limit=1000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample = col.find_one()
        self.assertIsNotNone(sample)
        v = sample["value"]

        # Mathematical constraints:
        self.assertEqual(v["total_schedules"], v["outgoing_schedules"] + v["incoming_schedules"])
        self.assertEqual(v["total_weekly_frequency"], v["outgoing_weekly_frequency"] + v["incoming_weekly_frequency"])
        self.assertEqual(v["distinct_connections"], len(v["neighbor_airports"]))
        self.assertLessEqual(v["distinct_connections"], v["out_degree"] + v["in_degree"])
        self.assertLessEqual(v["distinct_connections"], 107)  # cannot exceed total Indian airports
        col.drop()

    def test_empty_input_handling(self):
        """Verify MapReduce on empty collection handles 0 records cleanly."""
        empty_col = "test_empty_flights"
        self.db[empty_col].drop()
        self.db[empty_col].insert_one({"_id": "dummy", "is_route_eligible": False})

        out_col = "test_mr_empty_out"
        self.db[empty_col].map_reduce(
            INDIAN_JOB_A_MAPPER,
            INDIAN_JOB_A_REDUCER,
            out={"replace": out_col},
            query={"is_route_eligible": True},
        )
        self.assertEqual(self.db[out_col].count_documents({}), 0)

        self.db[empty_col].drop()
        self.db[out_col].drop()

    def test_missing_optional_fields_resilience(self):
        """Verify mapper gracefully handles documents with missing optional fields."""
        temp_col = "test_missing_fields_flights"
        self.db[temp_col].drop()
        self.db[temp_col].insert_one({
            "_id": "sparse_1",
            "is_route_eligible": True,
            "origin": {"iata": "DEL"},
            "destination": {"iata": "BOM"},
            "route_key": "DEL->BOM",
            # missing operating_days_count, distance_km, airline_code
        })

        out_col = "test_mr_sparse_out"
        self.db[temp_col].map_reduce(
            INDIAN_JOB_A_MAPPER,
            INDIAN_JOB_A_REDUCER,
            out={"replace": out_col},
            finalize=INDIAN_JOB_A_FINALIZE,
            query={"is_route_eligible": True},
        )
        doc = self.db[out_col].find_one({"_id": "DEL->BOM"})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["value"]["timetable_services"], 1)
        self.assertEqual(doc["value"]["weekly_frequency"], 1)  # default
        self.assertEqual(doc["value"]["airlines"], ["UNKNOWN"])

        self.db[temp_col].drop()
        self.db[out_col].drop()

    def test_duplicate_route_records_handling(self):
        """Verify multiple schedule filings for the same route accumulate frequency without degree inflation."""
        temp_col = "test_dup_routes_flights"
        self.db[temp_col].drop()
        # Insert 3 schedules for DEL->BOM
        docs = [
            {
                "_id": f"dup_{i}",
                "is_route_eligible": True,
                "origin": {"iata": "DEL"},
                "destination": {"iata": "BOM"},
                "route_key": "DEL->BOM",
                "operating_days_count": 7,
                "airline_code": "6E",
            }
            for i in range(3)
        ]
        self.db[temp_col].insert_many(docs)

        # Test Job A
        out_a = "test_mr_dup_a"
        self.db[temp_col].map_reduce(
            INDIAN_JOB_A_MAPPER,
            INDIAN_JOB_A_REDUCER,
            out={"replace": out_a},
            finalize=INDIAN_JOB_A_FINALIZE,
            query={"is_route_eligible": True},
        )
        doc_a = self.db[out_a].find_one({"_id": "DEL->BOM"})
        self.assertIsNotNone(doc_a)
        self.assertEqual(doc_a["value"]["timetable_services"], 3)
        self.assertEqual(doc_a["value"]["weekly_frequency"], 21)
        self.assertEqual(self.db[out_a].count_documents({}), 1)

        # Test Job E (degree must NOT be 3; distinct connections must be 1)
        out_e = "test_mr_dup_e"
        self.db[temp_col].map_reduce(
            INDIAN_JOB_E_MAPPER,
            INDIAN_JOB_E_REDUCER,
            out={"replace": out_e},
            finalize=INDIAN_JOB_E_FINALIZE,
            query={"is_route_eligible": True},
        )
        doc_e = self.db[out_e].find_one({"_id": "DEL"})
        self.assertIsNotNone(doc_e)
        self.assertEqual(doc_e["value"]["out_degree"], 1)  # BOM only
        self.assertEqual(doc_e["value"]["distinct_connections"], 1)
        self.assertEqual(doc_e["value"]["outgoing_schedules"], 3)
        self.assertEqual(doc_e["value"]["outgoing_weekly_frequency"], 21)

        self.db[temp_col].drop()
        self.db[out_a].drop()
        self.db[out_e].drop()

    def test_route_directionality_separation(self):
        """Verify that directed routes DEL->BOM and BOM->DEL are strictly separated."""
        doc_forward = self.db[settings.INDIAN_MR_ROUTE_ACTIVITY].find_one({"_id": "DEL->BOM"})
        doc_reverse = self.db[settings.INDIAN_MR_ROUTE_ACTIVITY].find_one({"_id": "BOM->DEL"})

        self.assertIsNotNone(doc_forward, "DEL->BOM should exist in mr_route_activity_in")
        self.assertIsNotNone(doc_reverse, "BOM->DEL should exist in mr_route_activity_in")
        self.assertNotEqual(doc_forward["_id"], doc_reverse["_id"])
        # Verify frequencies differ or are measured per directed edge
        self.assertGreater(doc_forward["value"]["weekly_frequency"], 0)
        self.assertGreater(doc_reverse["value"]["weekly_frequency"], 0)

    def test_repeatable_execution_no_stale_duplicates(self):
        """Verify executing pipeline multiple times replaces collections cleanly without duplication."""
        col_a = self.db[settings.INDIAN_MR_ROUTE_ACTIVITY]
        count_before = col_a.count_documents({})
        self.assertGreater(count_before, 0)

        # Re-run Job A
        self.flights.map_reduce(
            INDIAN_JOB_A_MAPPER,
            INDIAN_JOB_A_REDUCER,
            out={"replace": settings.INDIAN_MR_ROUTE_ACTIVITY},
            finalize=INDIAN_JOB_A_FINALIZE,
            query=INDIAN_MAPREDUCE_QUERY_FILTER,
        )
        count_after = col_a.count_documents({})
        self.assertEqual(count_before, count_after, "Repeat execution should result in exact identical count")

    def test_us_collections_strictly_preserved(self):
        """Strictly verify all original US collections and US MapReduce outputs are untouched."""
        self.assertEqual(self.db[settings.FLIGHTS_COLLECTION].count_documents({}), 100000)
        self.assertEqual(self.db[settings.AIRPORTS_COLLECTION].count_documents({}), 322)
        self.assertEqual(self.db[settings.AIRLINES_COLLECTION].count_documents({}), 14)
        self.assertEqual(self.db[settings.MR_ROUTE_ACTIVITY].count_documents({}), 4129)
        self.assertEqual(self.db[settings.MR_AIRPORT_OUTGOING].count_documents({}), 312)
        self.assertEqual(self.db[settings.MR_AIRPORT_INCOMING].count_documents({}), 312)
        self.assertEqual(self.db[settings.MR_MONTHLY_ROUTE].count_documents({}), 4129)
        self.assertEqual(self.db[settings.MR_AIRPORT_CONNECTIVITY].count_documents({}), 312)
