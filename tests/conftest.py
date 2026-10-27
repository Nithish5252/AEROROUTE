# ============================================================
# AeroRoute -- Pytest Fixtures & Shared Test Configuration
# File : tests/conftest.py
# ============================================================

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

from pathlib import Path
from typing import Any, Dict, Generator
import pandas as pd
import pymongo
import pytest

from config.settings import settings
from src.utils.db import get_client, get_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# -------------------------------------------------------------
# Synthetic Unit Test Fixture (Clearly Labeled)
# -------------------------------------------------------------
SYNTHETIC_TEST_FIXTURE_DO_NOT_USE_AS_FINDINGS = [
    # 1. Valid operated flights (ATL -> ORD)
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 1, "DAY_OF_WEEK": 4,
        "AIRLINE": "DL", "FLIGHT_NUMBER": 101, "TAIL_NUMBER": "N101DA",
        "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ORD",
        "SCHEDULED_DEPARTURE": 800, "DEPARTURE_TIME": 805, "DEPARTURE_DELAY": 5.0,
        "SCHEDULED_TIME": 120, "ELAPSED_TIME": 118, "AIR_TIME": 98, "DISTANCE": 606,
        "SCHEDULED_ARRIVAL": 900, "ARRIVAL_TIME": 903, "ARRIVAL_DELAY": 3.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 1, "DAY_OF_WEEK": 4,
        "AIRLINE": "DL", "FLIGHT_NUMBER": 102, "TAIL_NUMBER": "N102DA",
        "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ORD",
        "SCHEDULED_DEPARTURE": 1200, "DEPARTURE_TIME": 1202, "DEPARTURE_DELAY": 2.0,
        "SCHEDULED_TIME": 120, "ELAPSED_TIME": 119, "AIR_TIME": 99, "DISTANCE": 606,
        "SCHEDULED_ARRIVAL": 1300, "ARRIVAL_TIME": 1301, "ARRIVAL_DELAY": 1.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
    # 2. Reverse direction (ORD -> ATL) - tests directed separation
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 1, "DAY_OF_WEEK": 4,
        "AIRLINE": "UA", "FLIGHT_NUMBER": 201, "TAIL_NUMBER": "N201UA",
        "ORIGIN_AIRPORT": "ORD", "DESTINATION_AIRPORT": "ATL",
        "SCHEDULED_DEPARTURE": 1400, "DEPARTURE_TIME": 1400, "DEPARTURE_DELAY": 0.0,
        "SCHEDULED_TIME": 120, "ELAPSED_TIME": 115, "AIR_TIME": 95, "DISTANCE": 606,
        "SCHEDULED_ARRIVAL": 1700, "ARRIVAL_TIME": 1655, "ARRIVAL_DELAY": -5.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
    # 3. Third corridor (LAX -> SFO)
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 2, "DAY_OF_WEEK": 5,
        "AIRLINE": "AA", "FLIGHT_NUMBER": 301, "TAIL_NUMBER": "N301AA",
        "ORIGIN_AIRPORT": "LAX", "DESTINATION_AIRPORT": "SFO",
        "SCHEDULED_DEPARTURE": 930, "DEPARTURE_TIME": 935, "DEPARTURE_DELAY": 5.0,
        "SCHEDULED_TIME": 85, "ELAPSED_TIME": 80, "AIR_TIME": 55, "DISTANCE": 337,
        "SCHEDULED_ARRIVAL": 1055, "ARRIVAL_TIME": 1055, "ARRIVAL_DELAY": 0.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
    # 4. Cancelled flight (Weather B)
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 2, "DAY_OF_WEEK": 5,
        "AIRLINE": "AA", "FLIGHT_NUMBER": 302, "TAIL_NUMBER": "N302AA",
        "ORIGIN_AIRPORT": "LAX", "DESTINATION_AIRPORT": "SFO",
        "SCHEDULED_DEPARTURE": 1600, "DEPARTURE_TIME": None, "DEPARTURE_DELAY": None,
        "SCHEDULED_TIME": 85, "ELAPSED_TIME": None, "AIR_TIME": None, "DISTANCE": 337,
        "SCHEDULED_ARRIVAL": 1725, "ARRIVAL_TIME": None, "ARRIVAL_DELAY": None,
        "DIVERTED": 0, "CANCELLED": 1, "CANCELLATION_REASON": "B",
    },
    # 5. Invalid records for QA rejection testing
    # - Missing origin
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 3, "DAY_OF_WEEK": 6,
        "AIRLINE": "WN", "FLIGHT_NUMBER": 401, "TAIL_NUMBER": "N401WN",
        "ORIGIN_AIRPORT": None, "DESTINATION_AIRPORT": "ORD",
        "SCHEDULED_DEPARTURE": 700, "DEPARTURE_TIME": 700, "DEPARTURE_DELAY": 0.0,
        "SCHEDULED_TIME": 100, "ELAPSED_TIME": 100, "AIR_TIME": 80, "DISTANCE": 500,
        "SCHEDULED_ARRIVAL": 840, "ARRIVAL_TIME": 840, "ARRIVAL_DELAY": 0.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
    # - Circular route (ATL -> ATL)
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 3, "DAY_OF_WEEK": 6,
        "AIRLINE": "DL", "FLIGHT_NUMBER": 402, "TAIL_NUMBER": "N402DA",
        "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ATL",
        "SCHEDULED_DEPARTURE": 900, "DEPARTURE_TIME": 900, "DEPARTURE_DELAY": 0.0,
        "SCHEDULED_TIME": 60, "ELAPSED_TIME": 60, "AIR_TIME": 40, "DISTANCE": 0,
        "SCHEDULED_ARRIVAL": 1000, "ARRIVAL_TIME": 1000, "ARRIVAL_DELAY": 0.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
    # - Unresolvable airport (ZZZ)
    {
        "YEAR": 2015, "MONTH": 1, "DAY": 3, "DAY_OF_WEEK": 6,
        "AIRLINE": "DL", "FLIGHT_NUMBER": 403, "TAIL_NUMBER": "N403DA",
        "ORIGIN_AIRPORT": "ATL", "DESTINATION_AIRPORT": "ZZZ",
        "SCHEDULED_DEPARTURE": 1100, "DEPARTURE_TIME": 1100, "DEPARTURE_DELAY": 0.0,
        "SCHEDULED_TIME": 120, "ELAPSED_TIME": 120, "AIR_TIME": 100, "DISTANCE": 500,
        "SCHEDULED_ARRIVAL": 1300, "ARRIVAL_TIME": 1300, "ARRIVAL_DELAY": 0.0,
        "DIVERTED": 0, "CANCELLED": 0, "CANCELLATION_REASON": None,
    },
]


@pytest.fixture(scope="session")
def synthetic_flights_df() -> pd.DataFrame:
    """
    Returns a small synthetic DataFrame strictly labeled as a test fixture.
    Never to be presented as real dataset findings.
    """
    return pd.DataFrame(SYNTHETIC_TEST_FIXTURE_DO_NOT_USE_AS_FINDINGS)


@pytest.fixture(scope="session")
def synthetic_airports_ref() -> Dict[str, Dict[str, Any]]:
    """Known synthetic airport reference dictionary for validation testing."""
    return {
        "ATL": {"iata": "ATL", "name": "Hartsfield-Jackson", "city": "Atlanta", "state": "GA", "country": "USA", "lat": 33.6407, "lon": -84.4277},
        "ORD": {"iata": "ORD", "name": "Chicago O'Hare", "city": "Chicago", "state": "IL", "country": "USA", "lat": 41.9742, "lon": -87.9073},
        "LAX": {"iata": "LAX", "name": "Los Angeles Intl", "city": "Los Angeles", "state": "CA", "country": "USA", "lat": 33.9425, "lon": -118.4081},
        "SFO": {"iata": "SFO", "name": "San Francisco Intl", "city": "San Francisco", "state": "CA", "country": "USA", "lat": 37.6190, "lon": -122.3748},
    }


@pytest.fixture(scope="session")
def synthetic_airlines_ref() -> Dict[str, str]:
    """Known synthetic airline reference dictionary."""
    return {
        "DL": "Delta Air Lines Inc.",
        "UA": "United Air Lines Inc.",
        "AA": "American Airlines Inc.",
        "WN": "Southwest Airlines Co.",
    }


@pytest.fixture(scope="session")
def mongo_db() -> pymongo.database.Database:
    """
    Yields the local aeroroutedb test database connection.
    Gracefully skips tests requiring MongoDB if the service is unreachable.
    """
    try:
        client = get_client()
        client.admin.command("ping")
        return client[settings.MONGO_DB_NAME]
    except Exception as e:
        pytest.skip(f"MongoDB Community Server is not reachable at {settings.MONGO_URI} ({e})")


@pytest.fixture(scope="session")
def real_sample_chunk() -> pd.DataFrame:
    """
    Reads a small 100-row slice of the actual Kaggle flights.csv dataset
    for real end-to-end integration validation when available.
    """
    csv_path = settings.FLIGHTS_CSV
    if not csv_path.exists():
        # Check archive directory
        csv_path = PROJECT_ROOT.parent / "archive" / "flights.csv"

    if csv_path.exists():
        try:
            return pd.read_csv(csv_path, nrows=100)
        except Exception:
            pass

    # Fallback to small slice of valid synthetic data if raw CSV missing
    return pd.DataFrame(SYNTHETIC_TEST_FIXTURE_DO_NOT_USE_AS_FINDINGS[:4])
