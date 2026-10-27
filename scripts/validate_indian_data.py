# ============================================================
# AeroRoute -- Indian Domestic Aviation Data Quality & Integrity Validator
# File : scripts/validate_indian_data.py
# Usage: python scripts/validate_indian_data.py [--report-path REPORT_PATH]
# ============================================================

import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymongo
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("validate_indian_data")


class IndianDataQualityValidator:
    """
    Automated QA validation auditor for Indian domestic aviation staging collections.
    Enforces 100% data hygiene, coordinate resolution, and non-fabrication guarantees.
    """

    def __init__(self, db: pymongo.database.Database, report_path: Path):
        self.db = db
        self.report_path = report_path
        self.results: List[Dict[str, Any]] = []
        self.passed_count = 0
        self.failed_count = 0

    def record_check(self, category: str, test_name: str, passed: bool, details: str):
        entry = {
            "check_id": len(self.results) + 1,
            "category": category,
            "test_name": test_name,
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }
        self.results.append(entry)
        if passed:
            self.passed_count += 1
            logger.info(f"[PASS] {category} -> {test_name}: {details}")
        else:
            self.failed_count += 1
            logger.error(f"[FAIL] {category} -> {test_name}: {details}")

    def validate_all(self):
        self.validate_collection_presence()
        self.validate_original_us_data_preserved()
        self.validate_reference_tables()
        self.validate_coordinate_integrity()
        self.validate_self_loop_prevention()
        self.validate_distance_domain_rules()
        self.validate_temporal_bounds()
        self.validate_scheduled_time_integrity()
        self.validate_non_fabrication_guarantees()
        self.validate_database_indexes()
        self.save_report()

    def validate_collection_presence(self):
        col_names = self.db.list_collection_names()
        for c in [settings.INDIAN_FLIGHTS_COLLECTION, settings.INDIAN_AIRPORTS_COLLECTION, settings.INDIAN_AIRLINES_COLLECTION]:
            exists = c in col_names
            count = self.db[c].count_documents({}) if exists else 0
            self.record_check(
                "COLLECTION_PRESENCE",
                f"Collection '{c}' populated",
                exists and count > 0,
                f"Count: {count:,} documents"
            )

    def validate_original_us_data_preserved(self):
        """Directive 2: Guarantee original US dataset collections are completely untouched."""
        us_flights = self.db[settings.FLIGHTS_COLLECTION].count_documents({})
        us_airports = self.db[settings.AIRPORTS_COLLECTION].count_documents({})
        us_airlines = self.db[settings.AIRLINES_COLLECTION].count_documents({})

        self.record_check(
            "US_PRESERVATION",
            "Original US 'flights' collection preserved",
            us_flights == 100000,
            f"Expected: 100,000 | Found: {us_flights:,}"
        )
        self.record_check(
            "US_PRESERVATION",
            "Original US 'airports' collection preserved",
            us_airports == 322,
            f"Expected: 322 | Found: {us_airports:,}"
        )
        self.record_check(
            "US_PRESERVATION",
            "Original US 'airlines' collection preserved",
            us_airlines == 14,
            f"Expected: 14 | Found: {us_airlines:,}"
        )

    def validate_reference_tables(self):
        ap_count = self.db[settings.INDIAN_AIRPORTS_COLLECTION].count_documents({})
        al_count = self.db[settings.INDIAN_AIRLINES_COLLECTION].count_documents({})
        self.record_check(
            "REFERENCE_DATA",
            "Indian Airports registry count (Unique IATA stations)",
            ap_count == 107,
            f"Expected: 107 unique IATA stations (resolving 110 raw dataset station names) | Found: {ap_count}"
        )
        self.record_check(
            "REFERENCE_DATA",
            "Indian Airlines registry count",
            al_count == 14,
            f"Expected: 14 | Found: {al_count}"
        )

    def validate_coordinate_integrity(self):
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        missing_coords = flights.count_documents({
            "is_route_eligible": True,
            "$or": [
                {"origin.lat": None}, {"origin.lon": None},
                {"destination.lat": None}, {"destination.lon": None},
            ]
        })
        self.record_check(
            "COORDINATE_INTEGRITY",
            "100% of route-eligible flights have verified coordinates",
            missing_coords == 0,
            f"Missing coordinates count: {missing_coords}"
        )

    def validate_self_loop_prevention(self):
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        self_loops = flights.count_documents({
            "$expr": {"$eq": ["$origin.iata", "$destination.iata"]}
        })
        self.record_check(
            "TOPOLOGY_INTEGRITY",
            "Zero self-loop routes (origin == destination)",
            self_loops == 0,
            f"Self-loops count: {self_loops}"
        )

    def validate_distance_domain_rules(self):
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        bad_dist = flights.count_documents({
            "$or": [{"distance_km": {"$lte": 0}}, {"distance_km": None}]
        })
        self.record_check(
            "DOMAIN_RULES",
            "All flights have positive Haversine distance (> 0 km)",
            bad_dist == 0,
            f"Invalid distance count: {bad_dist}"
        )

    def validate_temporal_bounds(self):
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        bad_year = flights.count_documents({
            "$or": [{"year": {"$lt": 2018}}, {"year": {"$gt": 2025}}]
        })
        bad_month = flights.count_documents({
            "$or": [{"month": {"$lt": 1}}, {"month": {"$gt": 12}}]
        })
        self.record_check(
            "TEMPORAL_INTEGRITY",
            "All schedule validity years within [2018, 2025]",
            bad_year == 0,
            f"Out-of-bounds year count: {bad_year}"
        )
        self.record_check(
            "TEMPORAL_INTEGRITY",
            "All schedule validity months within [1, 12]",
            bad_month == 0,
            f"Out-of-bounds month count: {bad_month}"
        )

    def validate_scheduled_time_integrity(self):
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        bad_dep = flights.count_documents({
            "$or": [{"scheduled_departure": {"$lt": 0}}, {"scheduled_departure": {"$gt": 1439}}]
        })
        bad_arr = flights.count_documents({
            "$or": [{"scheduled_arrival": {"$lt": 0}}, {"scheduled_arrival": {"$gt": 1439}}]
        })
        self.record_check(
            "SCHEDULE_TIMING",
            "Scheduled departure minutes within 24-hr [0, 1439]",
            bad_dep == 0,
            f"Invalid departure minute count: {bad_dep}"
        )
        self.record_check(
            "SCHEDULE_TIMING",
            "Scheduled arrival minutes within 24-hr [0, 1439]",
            bad_arr == 0,
            f"Invalid arrival minute count: {bad_arr}"
        )

    def validate_non_fabrication_guarantees(self):
        """Directive 6: Explicitly verify no fabricated delays, cancellations, or operated flights."""
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]

        # 1. record_type is strictly SCHEDULED_SERVICE
        bad_type = flights.count_documents({"record_type": {"$ne": "SCHEDULED_SERVICE"}})
        self.record_check(
            "DATA_PROVENANCE",
            "Record type strictly marked SCHEDULED_SERVICE",
            bad_type == 0,
            f"Non-scheduled record count: {bad_type}"
        )

        # 2. Zero fabricated departure delays
        fab_dep_delay = flights.count_documents({"departure_delay": {"$ne": None}})
        self.record_check(
            "NON_FABRICATION",
            "Zero fabricated departure delays (departure_delay is null)",
            fab_dep_delay == 0,
            f"Fabricated departure delay count: {fab_dep_delay}"
        )

        # 3. Zero fabricated arrival delays
        fab_arr_delay = flights.count_documents({"arrival_delay": {"$ne": None}})
        self.record_check(
            "NON_FABRICATION",
            "Zero fabricated arrival delays (arrival_delay is null)",
            fab_arr_delay == 0,
            f"Fabricated arrival delay count: {fab_arr_delay}"
        )

        # 4. Zero fabricated delay breakdowns
        fab_breakdown = flights.count_documents({"delay_breakdown": {"$ne": None}})
        self.record_check(
            "NON_FABRICATION",
            "Zero fabricated delay breakdowns (delay_breakdown is null)",
            fab_breakdown == 0,
            f"Fabricated delay breakdown count: {fab_breakdown}"
        )

    def validate_database_indexes(self):
        flights = self.db[settings.INDIAN_FLIGHTS_COLLECTION]
        indexes = flights.index_information()
        keys_set = set(indexes.keys())
        for info in indexes.values():
            sig = "_".join(f"{f}_{d}" for f, d in info.get("key", []))
            keys_set.add(sig)

        required = [
            ("flight_id_1", "uniq_flight_id"),
            ("route_key_1", "idx_route_key"),
            ("origin.iata_1", "idx_origin_iata"),
            ("destination.iata_1", "idx_dest_iata"),
            ("airline_code_1", "idx_airline_code"),
            ("is_route_eligible_1", "idx_is_route_eligible"),
        ]
        for def_name, custom_name in required:
            exists = (def_name in keys_set) or (custom_name in keys_set)
            self.record_check(
                "INDEX_INTEGRITY",
                f"Index on '{def_name.replace('_1', '')}' present",
                exists,
                "Present" if exists else "Missing"
            )

    def save_report(self):
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_collection": settings.INDIAN_FLIGHTS_COLLECTION,
            "total_checks": len(self.results),
            "passed_checks": self.passed_count,
            "failed_checks": self.failed_count,
            "score_percentage": round((self.passed_count / len(self.results)) * 100, 2),
            "verdict": "PASSED" if self.failed_count == 0 else "FAILED",
            "checks": self.results,
        }
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print("\n" + "=" * 80)
        print("  AEROROUTE -- INDIAN DATA QUALITY & INTEGRITY VALIDATION AUDIT")
        print("=" * 80)
        print(f" Total Checks Evaluated : {len(self.results)}")
        print(f" Passed                 : {self.passed_count}")
        print(f" Failed                 : {self.failed_count}")
        print(f" Quality Score          : {report['score_percentage']}%")
        print(f" Overall Verdict        : {report['verdict']}")
        print(f" Machine-Readable Report: {self.report_path}")
        print("=" * 80)


def run_validation(report_path: Path):
    db = get_db()
    validator = IndianDataQualityValidator(db, report_path)
    validator.validate_all()
    if validator.failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indian Aviation Data Quality Validator")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "indian_data_quality_report.json",
        help="Destination JSON report file"
    )
    args = parser.parse_args()
    run_validation(args.report_path)
