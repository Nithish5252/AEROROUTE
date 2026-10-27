# ============================================================
# AeroRoute -- Indian MapReduce Output Quality & Integrity Audit
# File : scripts/validate_indian_mapreduce.py
# Usage: python scripts/validate_indian_mapreduce.py
# ============================================================

import datetime
import json
import re
import sys
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymongo
from config.settings import settings
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("validate_indian_mapreduce")


class IndianMapReduceValidator:
    def __init__(self):
        self.db = get_db()
        self.checks: List[Dict[str, Any]] = []
        self.output_file = settings.PROCESSED_DIR / "indian_mapreduce_quality_report.json"

    def record_check(self, category: str, test_name: str, passed: bool, details: str):
        status = "PASS" if passed else "FAIL"
        entry = {
            "check_id": len(self.checks) + 1,
            "category": category,
            "test_name": test_name,
            "passed": passed,
            "status": status,
            "details": details,
        }
        self.checks.append(entry)
        if passed:
            logger.info(f"[PASS] {category} -> {test_name}: {details}")
        else:
            logger.error(f"[FAIL] {category} -> {test_name}: {details}")

    def validate_us_preservation(self):
        """Directive 3: Verify all original US collections and MapReduce outputs are untouched."""
        us_flights = self.db[settings.FLIGHTS_COLLECTION].count_documents({})
        us_airports = self.db[settings.AIRPORTS_COLLECTION].count_documents({})
        us_airlines = self.db[settings.AIRLINES_COLLECTION].count_documents({})
        us_mr_route = self.db[settings.MR_ROUTE_ACTIVITY].count_documents({})
        us_mr_out = self.db[settings.MR_AIRPORT_OUTGOING].count_documents({})
        us_mr_in = self.db[settings.MR_AIRPORT_INCOMING].count_documents({})
        us_mr_month = self.db[settings.MR_MONTHLY_ROUTE].count_documents({})
        us_mr_conn = self.db[settings.MR_AIRPORT_CONNECTIVITY].count_documents({})

        self.record_check("US_PRESERVATION", "US 'flights' collection preserved", us_flights == 100000, f"Expected: 100,000 | Found: {us_flights:,}")
        self.record_check("US_PRESERVATION", "US 'airports' collection preserved", us_airports == 322, f"Expected: 322 | Found: {us_airports:,}")
        self.record_check("US_PRESERVATION", "US 'airlines' collection preserved", us_airlines == 14, f"Expected: 14 | Found: {us_airlines:,}")
        self.record_check("US_PRESERVATION", "US 'mr_route_activity' preserved", us_mr_route == 4129, f"Expected: 4,129 | Found: {us_mr_route:,}")
        self.record_check("US_PRESERVATION", "US 'mr_airport_outgoing' preserved", us_mr_out == 312, f"Expected: 312 | Found: {us_mr_out:,}")
        self.record_check("US_PRESERVATION", "US 'mr_airport_incoming' preserved", us_mr_in == 312, f"Expected: 312 | Found: {us_mr_in:,}")
        self.record_check("US_PRESERVATION", "US 'mr_monthly_route' preserved", us_mr_month == 4129, f"Expected: 4,129 | Found: {us_mr_month:,}")
        self.record_check("US_PRESERVATION", "US 'mr_airport_connectivity' preserved", us_mr_conn == 312, f"Expected: 312 | Found: {us_mr_conn:,}")

    def validate_indian_collections_populated(self):
        """Directive 2: Verify dedicated Indian MapReduce collections exist and are populated."""
        mr_a = self.db[settings.INDIAN_MR_ROUTE_ACTIVITY].count_documents({})
        mr_b = self.db[settings.INDIAN_MR_AIRPORT_OUTGOING].count_documents({})
        mr_c = self.db[settings.INDIAN_MR_AIRPORT_INCOMING].count_documents({})
        mr_d = self.db[settings.INDIAN_MR_MONTHLY_ROUTE].count_documents({})
        mr_e = self.db[settings.INDIAN_MR_AIRPORT_CONNECTIVITY].count_documents({})

        self.record_check("COLLECTION_PRESENCE", "Collection 'mr_route_activity_in' populated", mr_a == 1381, f"Found: {mr_a:,} routes (Expected: 1,381)")
        self.record_check("COLLECTION_PRESENCE", "Collection 'mr_airport_outgoing_in' populated", mr_b == 100, f"Found: {mr_b:,} origin airports (Expected: 100)")
        self.record_check("COLLECTION_PRESENCE", "Collection 'mr_airport_incoming_in' populated", mr_c == 107, f"Found: {mr_c:,} destination airports (Expected: 107)")
        self.record_check("COLLECTION_PRESENCE", "Collection 'mr_monthly_route_in' populated", mr_d == 62234, f"Found: {mr_d:,} monthly route entries (Expected: 62,234)")
        self.record_check("COLLECTION_PRESENCE", "Collection 'mr_airport_connectivity_in' populated", mr_e == 107, f"Found: {mr_e:,} network airports (Expected: 107)")

    def validate_schema_and_types(self):
        """Directive 4 & 5: Check data types, non-fabrication flags, and required schema attributes."""
        # 1. Job A
        col_a = self.db[settings.INDIAN_MR_ROUTE_ACTIVITY]
        bad_a = col_a.count_documents({
            "$or": [
                {"value.timetable_services": {"$exists": False}},
                {"value.weekly_frequency": {"$exists": False}},
                {"value.distance_km": {"$exists": False}},
                {"value.data_source": {"$ne": "DGCA_Airline_Timetables_2018_2025"}},
                {"value.metric_type": {"$ne": "SCHEDULED_ROUTE_CAPACITY"}},
            ]
        })
        self.record_check("SCHEMA_INTEGRITY", "Job A output fields and data source integrity", bad_a == 0, f"Non-conforming docs: {bad_a}")

        # 2. Job B
        col_b = self.db[settings.INDIAN_MR_AIRPORT_OUTGOING]
        bad_b = col_b.count_documents({
            "$or": [
                {"value.outgoing_timetable_services": {"$exists": False}},
                {"value.outgoing_weekly_frequency": {"$exists": False}},
                {"value.destinations": {"$exists": False}},
            ]
        })
        self.record_check("SCHEMA_INTEGRITY", "Job B output fields and data types", bad_b == 0, f"Non-conforming docs: {bad_b}")

        # 3. Job C
        col_c = self.db[settings.INDIAN_MR_AIRPORT_INCOMING]
        bad_c = col_c.count_documents({
            "$or": [
                {"value.incoming_timetable_services": {"$exists": False}},
                {"value.incoming_weekly_frequency": {"$exists": False}},
                {"value.origins": {"$exists": False}},
            ]
        })
        self.record_check("SCHEMA_INTEGRITY", "Job C output fields and data types", bad_c == 0, f"Non-conforming docs: {bad_c}")

        # 4. Job D
        col_d = self.db[settings.INDIAN_MR_MONTHLY_ROUTE]
        bad_d = col_d.count_documents({
            "$or": [
                {"_id.year_month": {"$not": {"$regex": r"^\d{4}-\d{2}$"}}},
                {"_id.route_key": {"$not": {"$regex": r"^[A-Z]{3}->[A-Z]{3}$"}}},
                {"value.active_timetable_services": {"$exists": False}},
                {"value.metric_description": {"$not": {"$regex": "Does not represent operated flight events"}}},
            ]
        })
        self.record_check("SCHEMA_INTEGRITY", "Job D composite key & non-operational documentation", bad_d == 0, f"Non-conforming docs: {bad_d}")

        # 5. Job E
        col_e = self.db[settings.INDIAN_MR_AIRPORT_CONNECTIVITY]
        bad_e = col_e.count_documents({
            "$or": [
                {"value.distinct_connections": {"$exists": False}},
                {"value.out_degree": {"$exists": False}},
                {"value.in_degree": {"$exists": False}},
                {"value.total_weekly_frequency": {"$exists": False}},
                {"value.neighbor_airports": {"$exists": False}},
            ]
        })
        self.record_check("SCHEMA_INTEGRITY", "Job E graph connectivity & degree fields", bad_e == 0, f"Non-conforming docs: {bad_e}")

    def validate_referential_integrity(self):
        """Directive 7: Verify all airport identifiers reference valid airports in airports_in."""
        valid_iatas = set(self.db[settings.INDIAN_AIRPORTS_COLLECTION].distinct("iata"))
        assert len(valid_iatas) == 107, "Expected 107 airports in airports_in"

        # Check Job B origins
        job_b_airports = set(self.db[settings.INDIAN_MR_AIRPORT_OUTGOING].distinct("_id"))
        unresolved_b = job_b_airports - valid_iatas
        self.record_check("REFERENTIAL_INTEGRITY", "Job B origin airports exist in airports_in", len(unresolved_b) == 0, f"Unresolved origins: {unresolved_b}")

        # Check Job C destinations
        job_c_airports = set(self.db[settings.INDIAN_MR_AIRPORT_INCOMING].distinct("_id"))
        unresolved_c = job_c_airports - valid_iatas
        self.record_check("REFERENTIAL_INTEGRITY", "Job C destination airports exist in airports_in", len(unresolved_c) == 0, f"Unresolved destinations: {unresolved_c}")

        # Check Job E connectivity airports
        job_e_airports = set(self.db[settings.INDIAN_MR_AIRPORT_CONNECTIVITY].distinct("_id"))
        unresolved_e = job_e_airports - valid_iatas
        self.record_check("REFERENTIAL_INTEGRITY", "Job E connectivity nodes exist in airports_in", len(unresolved_e) == 0, f"Unresolved nodes: {unresolved_e}")

    def validate_numerical_and_graph_consistency(self):
        """Directive 4 & 7: Verify mathematical and graph-theoretical balance."""
        # 1. Total timetable services balance:
        # Sum of Job A timetable services should match total valid flights in flights_in (33,023)
        pipeline_a = [{"$group": {"_id": None, "total": {"$sum": "$value.timetable_services"}}}]
        agg_a = list(self.db[settings.INDIAN_MR_ROUTE_ACTIVITY].aggregate(pipeline_a))
        sum_services_a = int(agg_a[0]["total"]) if agg_a else 0
        total_flights_in = self.db[settings.INDIAN_FLIGHTS_COLLECTION].count_documents({"is_route_eligible": True})

        self.record_check(
            "NUMERICAL_CONSISTENCY",
            "Job A total timetable services == flights_in total",
            sum_services_a == total_flights_in == 33023,
            f"Job A sum: {sum_services_a:,} | Collection total: {total_flights_in:,}"
        )

        # 2. Outgoing services sum == Incoming services sum == 33,023
        pipeline_b = [{"$group": {"_id": None, "total": {"$sum": "$value.outgoing_timetable_services"}}}]
        agg_b = list(self.db[settings.INDIAN_MR_AIRPORT_OUTGOING].aggregate(pipeline_b))
        sum_services_b = int(agg_b[0]["total"]) if agg_b else 0

        pipeline_c = [{"$group": {"_id": None, "total": {"$sum": "$value.incoming_timetable_services"}}}]
        agg_c = list(self.db[settings.INDIAN_MR_AIRPORT_INCOMING].aggregate(pipeline_c))
        sum_services_c = int(agg_c[0]["total"]) if agg_c else 0

        self.record_check(
            "NUMERICAL_CONSISTENCY",
            "Job B Outgoing == Job C Incoming == 33,023 timetable services",
            sum_services_b == sum_services_c == 33023,
            f"Outgoing sum: {sum_services_b:,} | Incoming sum: {sum_services_c:,}"
        )

        # 3. Weekly flight frequencies balance
        pipeline_freq_b = [{"$group": {"_id": None, "total": {"$sum": "$value.outgoing_weekly_frequency"}}}]
        agg_freq_b = list(self.db[settings.INDIAN_MR_AIRPORT_OUTGOING].aggregate(pipeline_freq_b))
        freq_b = int(agg_freq_b[0]["total"]) if agg_freq_b else 0

        pipeline_freq_c = [{"$group": {"_id": None, "total": {"$sum": "$value.incoming_weekly_frequency"}}}]
        agg_freq_c = list(self.db[settings.INDIAN_MR_AIRPORT_INCOMING].aggregate(pipeline_freq_c))
        freq_c = int(agg_freq_c[0]["total"]) if agg_freq_c else 0

        self.record_check(
            "NUMERICAL_CONSISTENCY",
            "Job B Outgoing Weekly Freq == Job C Incoming Weekly Freq",
            freq_b == freq_c and freq_b > 0,
            f"Outgoing weekly freq: {freq_b:,} | Incoming weekly freq: {freq_c:,}"
        )

        # 4. Job E Graph Connectivity: Undirected Degree <= Out-Degree + In-Degree
        invalid_graph = self.db[settings.INDIAN_MR_AIRPORT_CONNECTIVITY].count_documents({
            "$expr": {
                "$gt": ["$value.distinct_connections", {"$add": ["$value.out_degree", "$value.in_degree"]}]
            }
        })
        self.record_check(
            "GRAPH_SEMANTICS",
            "Undirected distinct connections <= (out_degree + in_degree)",
            invalid_graph == 0,
            f"Violations count: {invalid_graph}"
        )

    def run_all_checks(self) -> Dict[str, Any]:
        logger.info("Executing comprehensive Phase 3 Indian MapReduce validation audit...")
        self.validate_us_preservation()
        self.validate_indian_collections_populated()
        self.validate_schema_and_types()
        self.validate_referential_integrity()
        self.validate_numerical_and_graph_consistency()

        passed_count = sum(1 for c in self.checks if c["passed"])
        total_count = len(self.checks)
        score = round((passed_count / total_count) * 100.0, 1) if total_count > 0 else 0.0
        verdict = "PASSED" if passed_count == total_count else "FAILED"

        report = {
            "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
            "target_pipeline": "INDIAN_MAPREDUCE_PHASE_3",
            "total_checks": total_count,
            "passed_checks": passed_count,
            "failed_checks": total_count - passed_count,
            "score_percentage": score,
            "verdict": verdict,
            "checks": self.checks,
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print("\n" + "=" * 80)
        print("  AEROROUTE -- INDIAN MAPREDUCE QUALITY & INTEGRITY VALIDATION AUDIT")
        print("=" * 80)
        print(f" Total Checks Evaluated : {total_count}")
        print(f" Passed                 : {passed_count}")
        print(f" Failed                 : {total_count - passed_count}")
        print(f" Quality Score          : {score}%")
        print(f" Overall Verdict        : {verdict}")
        print(f" Machine-Readable Report: {self.output_file}")
        print("=" * 80 + "\n")

        return report


if __name__ == "__main__":
    validator = IndianMapReduceValidator()
    report = validator.run_all_checks()
    if report["verdict"] != "PASSED":
        sys.exit(1)
