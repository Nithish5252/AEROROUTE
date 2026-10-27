# ============================================================
# AeroRoute -- Central Configuration Loader
# File : config/settings.py
# Usage: from config.settings import settings
# ============================================================
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from the project root (one level up from config/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    # MongoDB
    MONGO_URI: str       = os.getenv("MONGO_URI",      "mongodb://localhost:27017/")
    MONGO_DB_NAME: str   = os.getenv("MONGO_DB_NAME",  "aeroroutedb")

    # Data paths
    RAW_DATA_DIR: Path   = Path(os.getenv("RAW_DATA_DIR",   str(_PROJECT_ROOT / ".." / "archive")))
    FLIGHTS_CSV: Path    = Path(os.getenv("FLIGHTS_CSV",    str(_PROJECT_ROOT / ".." / "archive" / "flights.csv")))
    AIRPORTS_CSV: Path   = Path(os.getenv("AIRPORTS_CSV",   str(_PROJECT_ROOT / ".." / "archive" / "airports.csv")))
    AIRLINES_CSV: Path   = Path(os.getenv("AIRLINES_CSV",   str(_PROJECT_ROOT / ".." / "archive" / "airlines.csv")))
    PROCESSED_DIR: Path  = Path(os.getenv("PROCESSED_DIR",  str(_PROJECT_ROOT / "data" / "processed")))
    EXPORTS_DIR: Path    = Path(os.getenv("EXPORTS_DIR",    str(_PROJECT_ROOT / "data" / "exports")))

    # Ingestion
    CHUNK_SIZE: int      = int(os.getenv("CHUNK_SIZE",  "50000"))
    LOG_LEVEL: str       = os.getenv("LOG_LEVEL",       "INFO")

    # Indian Aviation Data Paths (Phase 2)
    INDIAN_RAW_DATA_DIR: Path  = Path(os.getenv("INDIAN_RAW_DATA_DIR",  str(_PROJECT_ROOT / "data" / "raw" / "indian_aviation")))
    INDIAN_CLEAN_CSV: Path     = Path(os.getenv("INDIAN_CLEAN_CSV",     str(_PROJECT_ROOT / "data" / "raw" / "indian_aviation" / "Air-Clean.csv")))
    INDIAN_RAW_CSV: Path       = Path(os.getenv("INDIAN_RAW_CSV",       str(_PROJECT_ROOT / "data" / "raw" / "indian_aviation" / "Air_full-Raw.csv")))
    INDIAN_REFERENCE_DIR: Path = Path(os.getenv("INDIAN_REFERENCE_DIR", str(_PROJECT_ROOT / "data" / "reference")))

    # Collection names (Original US - preserved)
    FLIGHTS_COLLECTION: str              = os.getenv("FLIGHTS_COLLECTION",        "flights")
    AIRPORTS_COLLECTION: str             = os.getenv("AIRPORTS_COLLECTION",       "airports")
    AIRLINES_COLLECTION: str             = os.getenv("AIRLINES_COLLECTION",       "airlines")
    PIPELINE_RUNS_COLLECTION: str        = os.getenv("PIPELINE_RUNS_COLLECTION",   "pipeline_runs")
    BATCH_SIZE: int                      = int(os.getenv("BATCH_SIZE",            "10000"))

    # Separate Indian Collection Names (Directive 3)
    INDIAN_FLIGHTS_COLLECTION: str       = os.getenv("INDIAN_FLIGHTS_COLLECTION",  "flights_in")
    INDIAN_AIRPORTS_COLLECTION: str      = os.getenv("INDIAN_AIRPORTS_COLLECTION", "airports_in")
    INDIAN_AIRLINES_COLLECTION: str      = os.getenv("INDIAN_AIRLINES_COLLECTION", "airlines_in")

    # MapReduce output collections (US Baseline)
    MR_ROUTE_ACTIVITY: str               = os.getenv("MR_ROUTE_ACTIVITY",       "mr_route_activity")
    MR_AIRPORT_OUTGOING: str             = os.getenv("MR_AIRPORT_OUTGOING",     "mr_airport_outgoing")
    MR_AIRPORT_INCOMING: str             = os.getenv("MR_AIRPORT_INCOMING",     "mr_airport_incoming")
    MR_MONTHLY_ROUTE: str                = os.getenv("MR_MONTHLY_ROUTE",        "mr_monthly_route")
    MR_AIRPORT_CONNECTIVITY: str         = os.getenv("MR_AIRPORT_CONNECTIVITY", "mr_airport_connectivity")

    # Dedicated Indian MapReduce Output Collections (Phase 3 Directive 2)
    INDIAN_MR_ROUTE_ACTIVITY: str        = os.getenv("INDIAN_MR_ROUTE_ACTIVITY",        "mr_route_activity_in")
    INDIAN_MR_AIRPORT_OUTGOING: str      = os.getenv("INDIAN_MR_AIRPORT_OUTGOING",      "mr_airport_outgoing_in")
    INDIAN_MR_AIRPORT_INCOMING: str      = os.getenv("INDIAN_MR_AIRPORT_INCOMING",      "mr_airport_incoming_in")
    INDIAN_MR_MONTHLY_ROUTE: str         = os.getenv("INDIAN_MR_MONTHLY_ROUTE",         "mr_monthly_route_in")
    INDIAN_MR_AIRPORT_CONNECTIVITY: str  = os.getenv("INDIAN_MR_AIRPORT_CONNECTIVITY",  "mr_airport_connectivity_in")

    # Convenience alias properties matching *_IN naming convention
    MR_ROUTE_ACTIVITY_IN: str            = "mr_route_activity_in"
    MR_AIRPORT_OUTGOING_IN: str          = "mr_airport_outgoing_in"
    MR_AIRPORT_INCOMING_IN: str          = "mr_airport_incoming_in"
    MR_MONTHLY_ROUTE_IN: str             = "mr_monthly_route_in"
    MR_AIRPORT_CONNECTIVITY_IN: str      = "mr_airport_connectivity_in"
    FLIGHTS_COLLECTION_IN: str           = "flights_in"
    AIRPORTS_COLLECTION_IN: str          = "airports_in"
    AIRLINES_COLLECTION_IN: str          = "airlines_in"

    # ML settings
    KMEANS_K: int        = int(os.getenv("KMEANS_K",     "5"))
    RANDOM_STATE: int    = int(os.getenv("RANDOM_STATE", "42"))
    MODELS_DIR: Path     = Path(os.getenv("MODELS_DIR",   str(_PROJECT_ROOT / "data" / "models")))

    # Dashboard & Regional Settings
    STREAMLIT_PORT: int  = int(os.getenv("STREAMLIT_PORT", "8501"))
    DATASET_REGION: str  = os.getenv("DATASET_REGION", "INDIA").upper()

    def get_flights_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_FLIGHTS_COLLECTION if r in ("INDIA", "IN") else self.FLIGHTS_COLLECTION

    def get_airports_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_AIRPORTS_COLLECTION if r in ("INDIA", "IN") else self.AIRPORTS_COLLECTION

    def get_airlines_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_AIRLINES_COLLECTION if r in ("INDIA", "IN") else self.AIRLINES_COLLECTION

    def get_mr_route_activity_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_MR_ROUTE_ACTIVITY if r in ("INDIA", "IN") else self.MR_ROUTE_ACTIVITY

    def get_mr_airport_outgoing_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_MR_AIRPORT_OUTGOING if r in ("INDIA", "IN") else self.MR_AIRPORT_OUTGOING

    def get_mr_airport_incoming_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_MR_AIRPORT_INCOMING if r in ("INDIA", "IN") else self.MR_AIRPORT_INCOMING

    def get_mr_monthly_route_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_MR_MONTHLY_ROUTE if r in ("INDIA", "IN") else self.MR_MONTHLY_ROUTE

    def get_mr_airport_connectivity_collection(self, region: Optional[str] = None) -> str:
        r = (region or self.DATASET_REGION).upper()
        return self.INDIAN_MR_AIRPORT_CONNECTIVITY if r in ("INDIA", "IN") else self.MR_AIRPORT_CONNECTIVITY


settings = Settings()
