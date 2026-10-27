# ============================================================
# AeroRoute -- Phase 3: Data Quality & Integrity Validation
# File : scripts/validate_data.py
# Usage: python scripts/validate_data.py [--quick]
# ============================================================

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymongo
from config.settings import settings
from src.utils.db import get_client, get_db
from src.utils.logger import get_logger

logger = get_logger("validate_data")


class QAValidator:
    def __init__(self, db: pymongo.database.Database, report_path: Path):
        self.db = db
        self.report_path = report_path
        self.results = []
        self.total_checks = 0
        self.passed_checks = 0
        self.failed_checks = 0

    def record_check(self, category: str, test_name: str, passed: bool, details: str):
        self.total_checks += 1
        if passed:
            self.passed_checks += 1
            status = "PASS"
        else:
            self.failed_checks += 1
            status = "FAIL"

        self.results.append({
            "category": category,
            "test_name": test_name,
            "status": status,
            "passed": passed,
            "details": details,
        })
        log_msg = f"[{status}] {category} -> {test_name}: {details}"
        if passed:
            logger.info(log_msg)
        else:
            logger.error(log_msg)

    def validate_collections_exist(self):
        col_names = self.db.list_collection_names()
        for expected in [settings.AIRLINES_COLLECTION, settings.AIRPORTS_COLLECTION, settings.FLIGHTS_COLLECTION]:
            exists = expected in col_names
            count = self.db[expected].count_documents({}) if exists else 0
            self.record_check(
                "COLLECTION_PRESENCE",
                f"Collection '{expected}' exists and populated",
                exists and count > 0,
                f"Count: {count:,} documents",
            )

    def validate_reference_tables(self):
        # Airlines check: expected 14 major carriers
        al_count = self.db[settings.AIRLINES_COLLECTION].count_documents({})
        self.record_check(
            "REFERENCE_DATA",
            "Airlines lookup table count",
            al_count == 14,
            f"Expected: 14 | Found: {al_count}",
        )

        # Airports check: expected 322 reference airports
        ap_count = self.db[settings.AIRPORTS_COLLECTION].count_documents({})
        self.record_check(
            "REFERENCE_DATA",
            "Airports lookup table count",
            ap_count == 322,
            f"Expected: 322 | Found: {ap_count}",
        )

        # Airports geo-coordinates check
        missing_coords = self.db[settings.AIRPORTS_COLLECTION].count_documents({
            "$or": [{"lat": None}, {"lon": None}]
        })
        self.record_check(
            "REFERENCE_DATA",
            "Airports without coordinates",
            missing_coords <= 5,  # only tiny territories may lack lat/lon
            f"Airports without coordinates: {missing_coords}",
        )

    def validate_cohort_separation(self):
        """
        Verify the three core cohorts:
        1. All valid recorded flight entries
        2. Records eligible for operated-route activity analysis
        3. Cancelled flight records
        """
        flights = self.db[settings.FLIGHTS_COLLECTION]

        # Check 1: Zero cancelled flights are marked route-eligible
        cancelled_and_eligible = flights.count_documents({
            "is_route_eligible": True,
            "is_cancelled": True,
        })
        self.record_check(
            "COHORT_INTEGRITY",
            "Cancelled flights quarantined from route analysis",
            cancelled_and_eligible == 0,
            f"Found {cancelled_and_eligible} cancelled flights flagged as route-eligible (Expected: 0)",
        )

        # Check 2: Zero route-eligible flights have unresolved coordinates
        eligible_missing_coords = flights.count_documents({
            "is_route_eligible": True,
            "$or": [
                {"origin.lat": None}, {"origin.lon": None},
                {"destination.lat": None}, {"destination.lon": None},
            ]
        })
        self.record_check(
            "COHORT_INTEGRITY",
            "Route-eligible flights have complete coordinates",
            eligible_missing_coords == 0,
            f"Found {eligible_missing_coords} route-eligible flights missing coordinates (Expected: 0)",
        )

        # Check 3: Zero route-eligible flights have numeric (non-IATA) airport codes
        numeric_routes = flights.count_documents({
            "is_route_eligible": True,
            "$or": [
                {"origin.iata": {"$regex": "^[0-9]"}},
                {"destination.iata": {"$regex": "^[0-9]"}},
            ]
        })
        self.record_check(
            "COHORT_INTEGRITY",
            "Numeric DOT airport IDs prevented from route analysis",
            numeric_routes == 0,
            f"Found {numeric_routes} numeric route-eligible records (Expected: 0)",
        )

        # Check 4: Zero self-loop flights in route analysis (origin != destination)
        self_loops = flights.count_documents({
            "is_route_eligible": True,
            "$expr": {"$eq": ["$origin.iata", "$destination.iata"]},
        })
        self.record_check(
            "COHORT_INTEGRITY",
            "Self-loop routes prevented from route analysis",
            self_loops == 0,
            f"Found {self_loops} self-loop records in route analysis (Expected: 0)",
        )

        # Check 5: Cancelled flights have valid cancellation reason
        invalid_reasons = flights.count_documents({
            "is_cancelled": True,
            "cancellation_reason": {"$nin": ["A", "B", "C", "D", "UNKNOWN"]},
        })
        self.record_check(
            "COHORT_INTEGRITY",
            "Cancelled flights preserve valid cancellation reason",
            invalid_reasons == 0,
            f"Found {invalid_reasons} cancelled flights with invalid reason (Expected: 0)",
        )

    def validate_schema_and_domain_rules(self):
        flights = self.db[settings.FLIGHTS_COLLECTION]

        # Check distance > 0
        invalid_dist = flights.count_documents({
            "$or": [{"distance": {"$lte": 0}}, {"distance": None}]
        })
        self.record_check(
            "DOMAIN_RULES",
            "All flights have positive distance (> 0)",
            invalid_dist == 0,
            f"Found {invalid_dist} records with non-positive distance (Expected: 0)",
        )

        # Check valid year == 2015
        bad_year = flights.count_documents({
            "year": {"$ne": 2015}
        })
        self.record_check(
            "DOMAIN_RULES",
            "All flights are in calendar year 2015",
            bad_year == 0,
            f"Found {bad_year} records with year != 2015 (Expected: 0)",
        )

        # Check month between 1 and 12
        bad_month = flights.count_documents({
            "$or": [{"month": {"$lt": 1}}, {"month": {"$gt": 12}}]
        })
        self.record_check(
            "DOMAIN_RULES",
            "All flight months within [1, 12]",
            bad_month == 0,
            f"Found {bad_month} records with month out of bounds (Expected: 0)",
        )

    def validate_database_indexes(self):
        flights = self.db[settings.FLIGHTS_COLLECTION]
        existing_indexes = flights.index_information()
        existing_keys = set(existing_indexes.keys())
        for info in existing_indexes.values():
            key_sig = "_".join(f"{field}_{direction}" for field, direction in info.get("key", []))
            existing_keys.add(key_sig)

        required_keys = ["flight_id_1", "route_key_1", "origin.iata_1", "destination.iata_1", "is_route_eligible_1"]

        for idx_key in required_keys:
            exists = idx_key in existing_keys
            self.record_check(
                "INDEX_INTEGRITY",
                f"Index '{idx_key}' present on flights",
                exists,
                "Indexed" if exists else "Missing",
            )

    def validate_quality_report_file(self):
        exists = self.report_path.exists()
        valid_json = False
        status_val = "NOT_FOUND"

        if exists:
            try:
                with open(self.report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid_json = True
                status_val = data.get("pipeline_health_status", "UNKNOWN")
            except Exception as e:
                status_val = f"CORRUPT: {e}"

        self.record_check(
            "REPORT_INTEGRITY",
            "Machine-readable Data Quality Report exists and valid",
            exists and valid_json and status_val in ["PASSED", "PASSED_WITH_WARNINGS"],
            f"File: {self.report_path.name} | Status: {status_val}",
        )

    def print_summary_table(self):
        print("\n" + "=" * 78)
        print("  AEROROUTE DATA QUALITY & INTEGRITY VALIDATION AUDIT")
        print("=" * 78)
        print(f" {'#':<3} | {'STATUS':<6} | {'CATEGORY':<20} | {'TEST DESCRIPTION':<40}")
        print("-" * 78)

        for i, res in enumerate(self.results, 1):
            mark = "PASS" if res["passed"] else "FAIL"
            color_mark = f"[OK]   " if res["passed"] else f"[FAIL] "
            print(f" {i:<3} | {color_mark:<6} | {res['category']:<20} | {res['test_name'][:40]:<40}")
            if not res["passed"]:
                print(f"     `--> Details: {res['details']}")

        print("-" * 78)
        pass_rate = (self.passed_checks / max(self.total_checks, 1)) * 100
        print(f"  Total Checks: {self.total_checks} | Passed: {self.passed_checks} | Failed: {self.failed_checks} | Score: {pass_rate:.1f}%")

        if self.failed_checks == 0:
            print("  VERDICT: ALL QUALITY ASSERTIONS PASSED. Pipeline is ready for Phase 4.")
        else:
            print(f"  VERDICT: {self.failed_checks} CHECK(S) FAILED. Inspect logs before proceeding.")
        print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description="AeroRoute Data Quality & Integrity Validation Script")
    parser.add_argument("--report-path", type=str, default="", help="Path to data_quality_report.json")
    args = parser.parse_args()

    report_path = Path(args.report_path) if args.report_path else settings.PROCESSED_DIR / "data_quality_report.json"

    logger.info("Connecting to MongoDB for validation...")
    try:
        db = get_db()
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)

    validator = QAValidator(db, report_path)
    validator.validate_collections_exist()
    validator.validate_reference_tables()
    validator.validate_cohort_separation()
    validator.validate_schema_and_domain_rules()
    validator.validate_database_indexes()
    validator.validate_quality_report_file()
    validator.print_summary_table()

    if validator.failed_checks > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
