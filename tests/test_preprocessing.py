# ============================================================
# AeroRoute -- Unit Tests for Data Preprocessing & Quality Control
# File : tests/test_preprocessing.py
# Usage: python tests/test_preprocessing.py
#        python -m unittest tests/test_preprocessing.py
# ============================================================

import datetime
import unittest
import numpy as np
import pandas as pd

from src.ingestion.preprocessor import (
    CANCELLATION_REASONS,
    format_hhmm,
    parse_flight_date,
    clean_and_transform_chunk,
)

class TestAeroRoutePreprocessing(unittest.TestCase):
    def setUp(self):
        # Synthetic reference lookup dictionaries
        self.airlines_ref = {
            "AA": "American Airlines Inc.",
            "DL": "Delta Air Lines Inc.",
            "UA": "United Air Lines Inc.",
            "WN": "Southwest Airlines Co.",
        }
        self.airports_ref = {
            "JFK": {
                "iata": "JFK",
                "name": "John F Kennedy International Airport",
                "city": "New York",
                "state": "NY",
                "country": "USA",
                "lat": 40.6398,
                "lon": -73.7789,
            },
            "LAX": {
                "iata": "LAX",
                "name": "Los Angeles International Airport",
                "city": "Los Angeles",
                "state": "CA",
                "country": "USA",
                "lat": 33.9425,
                "lon": -118.4081,
            },
            "ORD": {
                "iata": "ORD",
                "name": "Chicago O'Hare International Airport",
                "city": "Chicago",
                "state": "IL",
                "country": "USA",
                "lat": 41.9742,
                "lon": -87.9073,
            },
        }

    def test_hhmm_formatting(self):
        """Test parsing of HHMM integer/float timestamps into HH:MM strings."""
        self.assertEqual(format_hhmm(800), "08:00")
        self.assertEqual(format_hhmm(1430.0), "14:30")
        self.assertEqual(format_hhmm(45), "00:45")
        self.assertEqual(format_hhmm(0), "00:00")
        self.assertEqual(format_hhmm(2400), "00:00")
        self.assertIsNone(format_hhmm(None))
        self.assertIsNone(format_hhmm(np.nan))
        self.assertIsNone(format_hhmm(2599))  # Out of range
        self.assertIsNone(format_hhmm(-50))   # Negative

    def test_date_parsing(self):
        """Test safe date parsing."""
        d = parse_flight_date(2015, 1, 15)
        self.assertEqual(d, datetime.date(2015, 1, 15))
        self.assertIsNone(parse_flight_date(2015, 13, 1))
        self.assertIsNone(parse_flight_date(2015, 2, 30))
        self.assertIsNone(parse_flight_date("bad", "date", 1))

    def test_normal_flight_processing(self):
        """Test a standard valid flight transforms and classifies accurately."""
        synthetic_df = pd.DataFrame([{
            "YEAR": 2015, "MONTH": 3, "DAY": 10, "DAY_OF_WEEK": 2,
            "AIRLINE": "AA", "FLIGHT_NUMBER": 100, "TAIL_NUMBER": "N123AA",
            "ORIGIN_AIRPORT": "JFK", "DESTINATION_AIRPORT": "LAX",
            "SCHEDULED_DEPARTURE": 830, "DEPARTURE_TIME": 835, "DEPARTURE_DELAY": 5.0,
            "TAXI_OUT": 12.0, "WHEELS_OFF": 847, "SCHEDULED_TIME": 360.0,
            "ELAPSED_TIME": 355.0, "AIR_TIME": 335.0, "DISTANCE": 2475,
            "WHEELS_ON": 1122, "TAXI_IN": 8.0, "SCHEDULED_ARRIVAL": 1130,
            "ARRIVAL_TIME": 1130, "ARRIVAL_DELAY": 0.0,
            "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": np.nan,
            "AIR_SYSTEM_DELAY": np.nan, "SECURITY_DELAY": np.nan,
            "AIRLINE_DELAY": np.nan, "LATE_AIRCRAFT_DELAY": np.nan, "WEATHER_DELAY": np.nan,
        }])

        docs, stats = clean_and_transform_chunk(
            synthetic_df, self.airports_ref, self.airlines_ref
        )

        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(stats["read"], 1)
        self.assertEqual(stats["valid"], 1)
        self.assertEqual(stats["route_eligible"], 1)
        self.assertEqual(stats["cancelled"], 0)

        self.assertTrue(doc["is_valid_record"])
        self.assertTrue(doc["is_route_eligible"])
        self.assertFalse(doc["is_cancelled"])
        self.assertEqual(doc["eligibility_reason"], "ELIGIBLE")
        self.assertEqual(doc["route_key"], "JFK->LAX")
        self.assertEqual(doc["airline_name"], "American Airlines Inc.")
        self.assertEqual(doc["scheduled_departure_formatted"], "08:30")
        self.assertEqual(doc["origin"]["city"], "New York")
        self.assertEqual(doc["destination"]["city"], "Los Angeles")
        self.assertIsNotNone(doc["delay_breakdown"])
        self.assertEqual(doc["delay_breakdown"]["airline"], 0.0)

    def test_cancelled_flight_handling(self):
        """Test cancelled flights are preserved with cancellation details and excluded from route analysis."""
        synthetic_df = pd.DataFrame([{
            "YEAR": 2015, "MONTH": 2, "DAY": 1, "DAY_OF_WEEK": 7,
            "AIRLINE": "DL", "FLIGHT_NUMBER": 250, "TAIL_NUMBER": "N456DL",
            "ORIGIN_AIRPORT": "ORD", "DESTINATION_AIRPORT": "LAX",
            "SCHEDULED_DEPARTURE": 1000, "DEPARTURE_TIME": np.nan, "DEPARTURE_DELAY": np.nan,
            "TAXI_OUT": np.nan, "WHEELS_OFF": np.nan, "SCHEDULED_TIME": 270.0,
            "ELAPSED_TIME": np.nan, "AIR_TIME": np.nan, "DISTANCE": 1744,
            "WHEELS_ON": np.nan, "TAXI_IN": np.nan, "SCHEDULED_ARRIVAL": 1230,
            "ARRIVAL_TIME": np.nan, "ARRIVAL_DELAY": np.nan,
            "DIVERTED": 0, "CANCELLED": 1, "CANCELLATION_REASON": "B",
            "AIR_SYSTEM_DELAY": np.nan, "SECURITY_DELAY": np.nan,
            "AIRLINE_DELAY": np.nan, "LATE_AIRCRAFT_DELAY": np.nan, "WEATHER_DELAY": np.nan,
        }])

        docs, stats = clean_and_transform_chunk(
            synthetic_df, self.airports_ref, self.airlines_ref
        )

        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(stats["cancelled"], 1)
        self.assertEqual(stats["cancellation_reason_B"], 1)
        self.assertEqual(stats["route_eligible"], 0)
        self.assertEqual(stats["route_ineligible"], 1)

        self.assertTrue(doc["is_valid_record"])
        self.assertTrue(doc["is_cancelled"])
        self.assertFalse(doc["is_route_eligible"])
        self.assertEqual(doc["eligibility_reason"], "CANCELLED_FLIGHT")
        self.assertEqual(doc["cancellation_reason"], "B")
        self.assertEqual(doc["cancellation_description"], "Weather")
        self.assertIsNone(doc["delay_breakdown"])
        self.assertIsNone(doc["departure_time"])

    def test_numeric_dot_airport_code_handling(self):
        """Test that October 2015 numeric DOT airport codes are preserved but marked ineligible for route analysis."""
        synthetic_df = pd.DataFrame([{
            "YEAR": 2015, "MONTH": 10, "DAY": 5, "DAY_OF_WEEK": 1,
            "AIRLINE": "UA", "FLIGHT_NUMBER": 555, "TAIL_NUMBER": "N789UA",
            "ORIGIN_AIRPORT": "14747", "DESTINATION_AIRPORT": "11298",  # Numeric BTS IDs
            "SCHEDULED_DEPARTURE": 1200, "DEPARTURE_TIME": 1205, "DEPARTURE_DELAY": 5.0,
            "TAXI_OUT": 15.0, "WHEELS_OFF": 1220, "SCHEDULED_TIME": 200.0,
            "ELAPSED_TIME": 195.0, "AIR_TIME": 170.0, "DISTANCE": 1660,
            "WHEELS_ON": 1710, "TAXI_IN": 10.0, "SCHEDULED_ARRIVAL": 1720,
            "ARRIVAL_TIME": 1720, "ARRIVAL_DELAY": 0.0,
            "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": np.nan,
            "AIR_SYSTEM_DELAY": np.nan, "SECURITY_DELAY": np.nan,
            "AIRLINE_DELAY": np.nan, "LATE_AIRCRAFT_DELAY": np.nan, "WEATHER_DELAY": np.nan,
        }])

        docs, stats = clean_and_transform_chunk(
            synthetic_df, self.airports_ref, self.airlines_ref
        )

        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(stats["unresolved_airport"], 1)
        self.assertEqual(stats["route_eligible"], 0)
        self.assertEqual(stats["route_ineligible"], 1)

        self.assertTrue(doc["is_valid_record"])
        self.assertFalse(doc["is_route_eligible"])
        self.assertEqual(doc["eligibility_reason"], "NUMERIC_DOT_AIRPORT_ID")
        self.assertIsNone(doc["origin"]["lat"])

    def test_corrupt_records_rejected(self):
        """Test that records with negative distance, origin==destination, or corrupt date are dropped."""
        corrupt_df = pd.DataFrame([
            # Bad distance <= 0
            {
                "YEAR": 2015, "MONTH": 1, "DAY": 1, "AIRLINE": "AA", "FLIGHT_NUMBER": 1,
                "ORIGIN_AIRPORT": "JFK", "DESTINATION_AIRPORT": "LAX", "DISTANCE": -50,
                "SCHEDULED_DEPARTURE": 800, "CANCELLED": 0, "DIVERTED": 0,
            },
            # Origin equals Destination
            {
                "YEAR": 2015, "MONTH": 1, "DAY": 1, "AIRLINE": "AA", "FLIGHT_NUMBER": 2,
                "ORIGIN_AIRPORT": "JFK", "DESTINATION_AIRPORT": "JFK", "DISTANCE": 100,
                "SCHEDULED_DEPARTURE": 900, "CANCELLED": 0, "DIVERTED": 0,
            },
            # Invalid date
            {
                "YEAR": 2015, "MONTH": 14, "DAY": 40, "AIRLINE": "AA", "FLIGHT_NUMBER": 3,
                "ORIGIN_AIRPORT": "JFK", "DESTINATION_AIRPORT": "LAX", "DISTANCE": 1000,
                "SCHEDULED_DEPARTURE": 1000, "CANCELLED": 0, "DIVERTED": 0,
            },
        ])

        docs, stats = clean_and_transform_chunk(
            corrupt_df, self.airports_ref, self.airlines_ref
        )

        self.assertEqual(len(docs), 0)
        self.assertEqual(stats["rejected_corrupt"], 3)
        self.assertEqual(stats["valid"], 0)

    def test_duplicate_record_handling(self):
        """Test that identical duplicate natural key flights within or across chunks are caught."""
        dup_df = pd.DataFrame([
            {
                "YEAR": 2015, "MONTH": 5, "DAY": 1, "DAY_OF_WEEK": 5,
                "AIRLINE": "WN", "FLIGHT_NUMBER": 999, "ORIGIN_AIRPORT": "LAX",
                "DESTINATION_AIRPORT": "ORD", "DISTANCE": 1744, "SCHEDULED_DEPARTURE": 700,
                "CANCELLED": 0, "DIVERTED": 0,
            },
            {
                "YEAR": 2015, "MONTH": 5, "DAY": 1, "DAY_OF_WEEK": 5,
                "AIRLINE": "WN", "FLIGHT_NUMBER": 999, "ORIGIN_AIRPORT": "LAX",
                "DESTINATION_AIRPORT": "ORD", "DISTANCE": 1744, "SCHEDULED_DEPARTURE": 700,
                "CANCELLED": 0, "DIVERTED": 0,
            },
        ])

        seen_keys = set()
        docs, stats = clean_and_transform_chunk(
            dup_df, self.airports_ref, self.airlines_ref, seen_keys=seen_keys
        )

        self.assertEqual(len(docs), 1)
        self.assertEqual(stats["exact_duplicates"], 1)
        self.assertEqual(stats["valid"], 1)

if __name__ == "__main__":
    unittest.main()
