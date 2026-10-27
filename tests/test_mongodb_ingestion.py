# ============================================================
# AeroRoute -- Unit & Integration Tests: MongoDB Database & Ingestion
# File : tests/test_mongodb_ingestion.py
# Usage: python tests/test_mongodb_ingestion.py
#        python -m unittest tests/test_mongodb_ingestion.py
# ============================================================

import datetime
import unittest
import uuid
import pymongo
from pymongo.errors import ServerSelectionTimeoutError

from config.settings import settings
from src.utils.db import (
    get_client,
    get_db,
    get_collection_stats,
    record_pipeline_start,
    record_pipeline_end,
)
from scripts.load_mongodb import (
    bulk_insert_sub_batches,
    verify_ingestion_counts,
)


class TestMongoDBIngestion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.test_col_name = f"test_flights_{uuid.uuid4().hex[:6]}"
        cls.test_col = cls.db[cls.test_col_name]
        # Create unique index on flight_id for duplicate testing
        cls.test_col.create_index("flight_id", unique=True)

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary test collection
        cls.db[cls.test_col_name].drop()

    def test_database_connection_handling(self):
        """Test MongoDB client connection and server ping."""
        client = get_client()
        server_info = client.server_info()
        self.assertIsNotNone(server_info)
        self.assertIn("version", server_info)
        # Verify aeroroutedb handle is accessible
        db = get_db()
        self.assertEqual(db.name, settings.MONGO_DB_NAME)

    def test_invalid_connection_timeout(self):
        """Test connection failure fast timeout with invalid port."""
        bad_client = pymongo.MongoClient(
            "mongodb://localhost:27999/",
            serverSelectionTimeoutMS=500,
        )
        with self.assertRaises(ServerSelectionTimeoutError):
            bad_client.server_info()

    def test_bulk_insertion_sub_batches(self):
        """Test bulk write sub-batching with PyMongo."""
        sample_docs = [
            {
                "flight_id": f"TEST_FLIGHT_BATCH_{i}",
                "flight_date": datetime.datetime(2015, 1, 1),
                "airline_code": "AA",
                "route_key": "JFK->LAX",
                "is_route_eligible": True,
            }
            for i in range(25)
        ]

        inserted = bulk_insert_sub_batches(self.test_col, sample_docs, batch_size=10, idempotent_mode=False)
        self.assertEqual(inserted, 25)
        self.assertEqual(self.test_col.count_documents({"flight_id": {"$regex": "^TEST_FLIGHT_BATCH_"}}), 25)

    def test_rerun_safety_and_duplicate_prevention(self):
        """Test that re-running insertion does not create duplicate documents."""
        initial_count = self.test_col.count_documents({})

        duplicate_payload = [
            {
                "flight_id": f"TEST_IDEMPOTENT_FLIGHT_{i}",
                "route_key": "ORD->DFW",
                "is_route_eligible": True,
            }
            for i in range(5)
        ]

        # First run: inserts 5 documents
        bulk_insert_sub_batches(self.test_col, duplicate_payload, batch_size=5, idempotent_mode=True)
        count_after_first = self.test_col.count_documents({})
        self.assertEqual(count_after_first, initial_count + 5)

        # Second run (exact re-run simulation): should not increase count
        bulk_insert_sub_batches(self.test_col, duplicate_payload, batch_size=5, idempotent_mode=True)
        count_after_second = self.test_col.count_documents({})
        self.assertEqual(count_after_second, count_after_first, "Duplicate ingestion detected on rerun!")

    def test_document_count_verification(self):
        """Test post-ingestion document count verification helper."""
        expected = {
            self.test_col_name: self.test_col.count_documents({}),
        }
        self.assertTrue(verify_ingestion_counts(self.db, expected))

        bad_expected = {
            self.test_col_name: 999999,  # Intentional count mismatch
        }
        self.assertFalse(verify_ingestion_counts(self.db, bad_expected))

    def test_pipeline_runs_metadata_recording(self):
        """Test recording run metadata in pipeline_runs collection."""
        test_run_id = f"test_run_{uuid.uuid4().hex[:8]}"
        config = {"chunk_size": 50000, "drop": True}

        # 1. Start record
        record_pipeline_start(test_run_id, "test_script.py", config)
        run_doc = self.db[settings.PIPELINE_RUNS_COLLECTION].find_one({"run_id": test_run_id})
        self.assertIsNotNone(run_doc)
        self.assertEqual(run_doc["status"], "RUNNING")
        self.assertIsNotNone(run_doc["started_at"])

        # 2. End record
        metrics = {"total_inserted": 1000, "valid_records": 1000}
        record_pipeline_end(test_run_id, "SUCCESS", metrics, duration_seconds=5.2)

        updated_doc = self.db[settings.PIPELINE_RUNS_COLLECTION].find_one({"run_id": test_run_id})
        self.assertEqual(updated_doc["status"], "SUCCESS")
        self.assertEqual(updated_doc["duration_seconds"], 5.2)
        self.assertEqual(updated_doc["metrics"]["total_inserted"], 1000)
        self.assertIn("storage_stats", updated_doc)

        # Cleanup test run document
        self.db[settings.PIPELINE_RUNS_COLLECTION].delete_one({"run_id": test_run_id})

    def test_collection_stats_retrieval(self):
        """Test WiredTiger storage stats retrieval."""
        stats = get_collection_stats(self.test_col_name)
        self.assertIn("count", stats)
        self.assertIn("storage_size_bytes", stats)
        self.assertIn("total_index_size_bytes", stats)
        self.assertGreater(stats["count"], 0)


if __name__ == "__main__":
    unittest.main()
