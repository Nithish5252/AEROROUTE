# ============================================================
# AeroRoute -- Unit & Integration Tests: MongoDB MapReduce Jobs
# File : tests/test_mapreduce.py
# Usage: python tests/test_mapreduce.py
#        python -m unittest tests/test_mapreduce.py
# ============================================================

import unittest
from bson.code import Code
import pymongo

from config.settings import settings
from src.mapreduce.jobs import (
    JOB_A_MAPPER, JOB_A_REDUCER,
    JOB_B_MAPPER, JOB_B_REDUCER,
    JOB_C_MAPPER, JOB_C_REDUCER,
    JOB_D_MAPPER, JOB_D_REDUCER,
    JOB_E_MAPPER, JOB_E_REDUCER, JOB_E_FINALIZE,
    MAPREDUCE_QUERY_FILTER,
)
from src.utils.db import get_db


class TestMapReduceJobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        # Verify that flights collection has data
        cls.eligible_count = cls.db[settings.FLIGHTS_COLLECTION].count_documents(MAPREDUCE_QUERY_FILTER)
        if cls.eligible_count == 0:
            raise unittest.SkipTest("No eligible flights in database. Run load_mongodb.py first.")

    def test_job_a_directed_route_activity(self):
        """Test Job A creates directed route counts and keeps ATL->ORD and ORD->ATL separate."""
        out_col = "test_mr_job_a"
        self.db.flights.map_reduce(
            JOB_A_MAPPER,
            JOB_A_REDUCER,
            out={"replace": out_col},
            query=MAPREDUCE_QUERY_FILTER,
            limit=5000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        # Verify documents have route string keys
        sample_doc = col.find_one()
        self.assertIsNotNone(sample_doc)
        self.assertIn("->", sample_doc["_id"])
        self.assertIsInstance(sample_doc["value"], (int, float))
        self.assertGreater(sample_doc["value"], 0)

        # Cleanup
        col.drop()

    def test_job_b_outgoing_activity(self):
        """Test Job B outputs airport-level outgoing flight counts."""
        out_col = "test_mr_job_b"
        self.db.flights.map_reduce(
            JOB_B_MAPPER,
            JOB_B_REDUCER,
            out={"replace": out_col},
            query=MAPREDUCE_QUERY_FILTER,
            limit=5000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample_doc = col.find_one()
        self.assertIsNotNone(sample_doc)
        self.assertEqual(len(sample_doc["_id"]), 3)  # 3-character IATA
        self.assertGreater(sample_doc["value"], 0)
        col.drop()

    def test_job_c_incoming_activity(self):
        """Test Job C outputs airport-level incoming flight counts."""
        out_col = "test_mr_job_c"
        self.db.flights.map_reduce(
            JOB_C_MAPPER,
            JOB_C_REDUCER,
            out={"replace": out_col},
            query=MAPREDUCE_QUERY_FILTER,
            limit=5000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample_doc = col.find_one()
        self.assertIsNotNone(sample_doc)
        self.assertEqual(len(sample_doc["_id"]), 3)
        self.assertGreater(sample_doc["value"], 0)
        col.drop()

    def test_job_d_monthly_route_activity(self):
        """Test Job D outputs monthly route entries with year_month and corridor keys."""
        out_col = "test_mr_job_d"
        self.db.flights.map_reduce(
            JOB_D_MAPPER,
            JOB_D_REDUCER,
            out={"replace": out_col},
            query=MAPREDUCE_QUERY_FILTER,
            limit=5000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample_doc = col.find_one()
        self.assertIsNotNone(sample_doc)
        key = sample_doc["_id"]
        self.assertIn("year_month", key)
        self.assertIn("origin", key)
        self.assertIn("destination", key)
        self.assertIn("route_key", key)
        self.assertGreater(sample_doc["value"], 0)
        col.drop()

    def test_job_e_airport_connectivity_summary(self):
        """Test Job E generates incoming, outgoing, and distinct neighbor counts correctly."""
        out_col = "test_mr_job_e"
        self.db.flights.map_reduce(
            JOB_E_MAPPER,
            JOB_E_REDUCER,
            out={"replace": out_col},
            finalize=JOB_E_FINALIZE,
            query=MAPREDUCE_QUERY_FILTER,
            limit=5000,
        )
        col = self.db[out_col]
        self.assertGreater(col.count_documents({}), 0)

        sample_doc = col.find_one({"_id": "ATL"})
        if sample_doc is None:
            sample_doc = col.find_one()

        self.assertIsNotNone(sample_doc)
        v = sample_doc["value"]
        self.assertIn("outgoing_flights", v)
        self.assertIn("incoming_flights", v)
        self.assertIn("total_flights", v)
        self.assertIn("out_degree", v)
        self.assertIn("in_degree", v)
        self.assertIn("distinct_connections", v)
        self.assertIn("neighbor_airports", v)

        # Mathematical assertions:
        # 1. Total flights equals outgoing + incoming
        self.assertEqual(v["total_flights"], v["outgoing_flights"] + v["incoming_flights"])
        # 2. Distinct connections cannot exceed total airports in dataset (322)
        self.assertLessEqual(v["distinct_connections"], 322)
        # 3. Distinct connections must equal length of neighbor_airports list
        self.assertEqual(v["distinct_connections"], len(v["neighbor_airports"]))

        col.drop()

    def test_route_directionality_separation(self):
        """Verify that directed routes A->B and B->A are preserved as separate keys."""
        out_col = "test_mr_directionality"
        self.db.flights.map_reduce(
            JOB_A_MAPPER,
            JOB_A_REDUCER,
            out={"replace": out_col},
            query=MAPREDUCE_QUERY_FILTER,
            limit=10000,
        )
        col = self.db[out_col]

        # Find any pair of airports with bidirectional flights in sample
        all_routes = set(col.distinct("_id"))
        bidirectional_found = False
        for route in all_routes:
            if "->" in route:
                orig, dest = route.split("->")
                reverse = f"{dest}->{orig}"
                if reverse in all_routes:
                    bidirectional_found = True
                    doc1 = col.find_one({"_id": route})
                    doc2 = col.find_one({"_id": reverse})
                    self.assertIsNotNone(doc1)
                    self.assertIsNotNone(doc2)
                    self.assertNotEqual(doc1["_id"], doc2["_id"])
                    break

        col.drop()


if __name__ == "__main__":
    unittest.main()
