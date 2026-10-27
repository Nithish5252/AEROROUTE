# ============================================================
# AeroRoute -- OpenSky Network Live ADS-B Telemetry Service
# File : src/services/opensky_service.py
# ============================================================

import os
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

logger = logging.getLogger("aeroroute.opensky_service")

# Regional Bounding Boxes (geographic prefilters, not exact FIR legal boundaries)
BOUNDING_BOXES = {
    "INDIA": {
        "lamin": 6.0,   # Southern tip (Kanyakumari / Indian Ocean approach)
        "lamax": 37.0,  # Northern Kashmir
        "lomin": 68.0,  # Western Gujarat / Arabian Sea
        "lomax": 98.0,  # Eastern Arunachal Pradesh / Assam
        "label": "Indian Subcontinent Airspace Prefilter",
    },
    "US": {
        "lamin": 24.0,  # Southern Florida / Texas
        "lamax": 50.0,  # Northern US border
        "lomin": -125.0,# Pacific Coast
        "lomax": -66.0, # Atlantic Coast
        "label": "Continental US Airspace Prefilter",
    },
}

# Airline ICAO 3-letter callsign prefix lookup
AIRLINE_CALLSIGN_MAP = {
    # Indian Commercial Operators
    "IGO": {"name": "IndiGo", "code": "6E", "country": "India"},
    "AIC": {"name": "Air India", "code": "AI", "country": "India"},
    "VTI": {"name": "Vistara", "code": "UK", "country": "India"},
    "SEJ": {"name": "SpiceJet", "code": "SG", "country": "India"},
    "AKJ": {"name": "Akasa Air", "code": "QP", "country": "India"},
    "AXB": {"name": "Air India Express", "code": "IX", "country": "India"},
    "IAD": {"name": "AIX Connect", "code": "I5", "country": "India"},
    "LLR": {"name": "Alliance Air", "code": "9I", "country": "India"},
    # International & Gulf Carriers
    "UAE": {"name": "Emirates", "code": "EK", "country": "UAE"},
    "QTR": {"name": "Qatar Airways", "code": "QR", "country": "Qatar"},
    "ETD": {"name": "Etihad Airways", "code": "EY", "country": "UAE"},
    "SIA": {"name": "Singapore Airlines", "code": "SQ", "country": "Singapore"},
    "BAW": {"name": "British Airways", "code": "BA", "country": "UK"},
    "DLH": {"name": "Lufthansa", "code": "LH", "country": "Germany"},
    "FDB": {"name": "flydubai", "code": "FZ", "country": "UAE"},
    "OMA": {"name": "Oman Air", "code": "WY", "country": "Oman"},
    # Major US Carriers
    "AAL": {"name": "American Airlines", "code": "AA", "country": "USA"},
    "DAL": {"name": "Delta Air Lines", "code": "DL", "country": "USA"},
    "UAL": {"name": "United Airlines", "code": "UA", "country": "USA"},
    "SWA": {"name": "Southwest Airlines", "code": "WN", "country": "USA"},
}

CARDINAL_DIRECTIONS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
]


def _heading_to_cardinal(deg: Optional[float]) -> str:
    if deg is None:
        return "UNK"
    try:
        ix = int((float(deg) + 11.25) / 22.5) % 16
        return CARDINAL_DIRECTIONS[ix]
    except Exception:
        return "UNK"


class OpenSkyClient:
    """
    Production client for the OpenSky Network live ADS-B state vector API.
    Enforces caching, rate limits, credential isolation, and bounded geographic filtering.
    """

    def __init__(self, cache_ttl_seconds: int = 20, timeout_seconds: int = 8):
        self.base_url = "https://opensky-network.org/api/states/all"
        self.cache_ttl = cache_ttl_seconds
        self.timeout = timeout_seconds

        # Read credentials strictly from environment
        self.username = os.getenv("OPENSKY_USERNAME")
        self.password = os.getenv("OPENSKY_PASSWORD")

        # In-memory regional cache: { "INDIA": {"timestamp": float, "data": DataFrame, "meta": dict} }
        self._cache: Dict[str, Dict[str, Any]] = {}

    def is_authenticated(self) -> bool:
        """Return True if credentials are configured in environment variables."""
        return bool(self.username and self.password)

    def fetch_live_aircraft(
        self,
        region: str = "INDIA",
        force_refresh: bool = False,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Fetch real-time state vectors within the region's bounding box.
        Returns:
            (DataFrame of live aircraft, metadata dict with status and provenance)
        """
        reg = region.upper()
        if reg not in BOUNDING_BOXES:
            reg = "INDIA"

        bbox = BOUNDING_BOXES[reg]
        now_ts = time.time()

        # Check Cache
        cached = self._cache.get(reg)
        if not force_refresh and cached:
            age = now_ts - cached["timestamp"]
            if age < self.cache_ttl:
                meta = dict(cached["meta"])
                meta["is_cached"] = True
                meta["cache_age_seconds"] = round(age, 1)
                return cached["data"].copy(), meta

        # Construct API parameters
        params = {
            "lamin": bbox["lamin"],
            "lamax": bbox["lamax"],
            "lomin": bbox["lomin"],
            "lomax": bbox["lomax"],
        }

        auth = None
        if self.is_authenticated():
            auth = (self.username, self.password)

        meta: Dict[str, Any] = {
            "region": reg,
            "data_source": "OpenSky Network (Live ADS-B Telemetry)",
            "api_endpoint": self.base_url,
            "bounding_box": bbox,
            "is_authenticated": self.is_authenticated(),
            "fetch_time_utc": datetime.now(timezone.utc).isoformat(),
            "is_cached": False,
            "status": "OFFLINE",
            "message": "",
            "coverage_disclaimer": (
                "Positions derived from terrestrial ADS-B/Mode-S receivers. "
                "Coverage density varies across flight information regions. "
                "Bounding box represents a geographic filter and does not constitute exact FIR legal borders."
            ),
        }

        try:
            resp = requests.get(
                self.base_url,
                params=params,
                auth=auth,
                timeout=self.timeout,
                headers={"User-Agent": "AeroRoute-Platform/2.0"},
            )

            if resp.status_code == 200:
                payload = resp.json()
                states = payload.get("states") or []
                records = self._parse_state_vectors(states, now_ts)

                df = pd.DataFrame(records)
                meta["status"] = "ONLINE"
                meta["total_states_received"] = len(states)
                meta["valid_airborne_count"] = len(df[df["on_ground"] == False]) if not df.empty else 0
                meta["on_ground_count"] = len(df[df["on_ground"] == True]) if not df.empty else 0
                meta["message"] = f"Successfully received {len(df)} live aircraft state vectors."

                # Update cache
                self._cache[reg] = {
                    "timestamp": now_ts,
                    "data": df,
                    "meta": meta,
                }
                return df, meta

            elif resp.status_code == 429:
                meta["status"] = "RATE_LIMITED"
                meta["message"] = "OpenSky API rate limit reached. Waiting for backoff interval."
                logger.warning("OpenSky API 429 Rate Limit encountered.")
                if cached:
                    return cached["data"].copy(), meta
                return pd.DataFrame(), meta

            elif resp.status_code == 401:
                meta["status"] = "AUTH_FAILED"
                meta["message"] = "Invalid OpenSky credentials provided in environment."
                logger.error("OpenSky API 401 Unauthorized.")
                return pd.DataFrame(), meta

            else:
                meta["status"] = "HTTP_ERROR"
                meta["message"] = f"OpenSky returned HTTP {resp.status_code}."
                if cached:
                    return cached["data"].copy(), meta
                return pd.DataFrame(), meta

        except requests.exceptions.Timeout:
            meta["status"] = "TIMEOUT"
            meta["message"] = "OpenSky API request timed out (> 8s). Using cached telemetry if available."
            logger.warning("OpenSky request timed out.")
            if cached:
                return cached["data"].copy(), meta
            return pd.DataFrame(), meta

        except Exception as e:
            meta["status"] = "CONNECTION_ERROR"
            meta["message"] = f"Network connection error: {str(e)}"
            logger.error(f"OpenSky request failed: {e}")
            if cached:
                return cached["data"].copy(), meta
            return pd.DataFrame(), meta

    def _parse_state_vectors(self, states: List[List[Any]], current_ts: float) -> List[Dict[str, Any]]:
        """
        Parse raw OpenSky 17-element state vectors into clean, typed records.
        Filters out null coordinates and stale records (> 300 seconds without contact).
        """
        parsed = []
        for s in states:
            if len(s) < 17:
                continue

            icao24 = s[0]
            callsign = (s[1] or "").strip()
            origin_country = s[2]
            time_position = s[3]
            last_contact = s[4]
            lon = s[5]
            lat = s[6]
            baro_alt_m = s[7]
            on_ground = bool(s[8])
            velocity_ms = s[9]
            true_track_deg = s[10]
            vertical_rate_ms = s[11]
            geo_alt_m = s[13]
            squawk = s[14]

            # 1. Geographic validation
            if lat is None or lon is None:
                continue
            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                continue

            # 2. Staleness filter: drop positions not seen in the last 300 seconds
            if last_contact and (current_ts - last_contact > 300):
                continue

            # 3. Units conversion
            altitude_ft = round(baro_alt_m * 3.28084) if baro_alt_m is not None else (
                round(geo_alt_m * 3.28084) if geo_alt_m is not None else None
            )
            speed_kts = round(velocity_ms * 1.94384) if velocity_ms is not None else None
            vertical_fpm = round(vertical_rate_ms * 196.85) if vertical_rate_ms is not None else 0

            # 4. Resolve airline and display callsign
            flight_display = callsign if callsign else f"ICAO:{icao24.upper()}"
            operator_name = origin_country
            airline_code = "OTHER"

            if len(callsign) >= 3:
                prefix = callsign[:3].upper()
                if prefix in AIRLINE_CALLSIGN_MAP:
                    carrier_info = AIRLINE_CALLSIGN_MAP[prefix]
                    operator_name = carrier_info["name"]
                    airline_code = carrier_info["code"]

            # 5. Determine operational state
            if on_ground:
                situation = "ON GROUND"
            elif vertical_fpm > 500:
                situation = "CLIMBING"
            elif vertical_fpm < -500:
                situation = "DESCENDING"
            else:
                situation = "AIRBORNE / CRUISE"

            parsed.append({
                "icao24": icao24,
                "callsign": flight_display,
                "raw_callsign": callsign,
                "operator": operator_name,
                "airline_code": airline_code,
                "origin_country": origin_country,
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "altitude_ft": altitude_ft,
                "altitude_display": f"{altitude_ft:,} ft" if altitude_ft is not None else "N/A",
                "ground_speed_kts": speed_kts,
                "speed_display": f"{speed_kts} kts" if speed_kts is not None else "N/A",
                "heading_deg": round(true_track_deg, 1) if true_track_deg is not None else None,
                "heading_cardinal": _heading_to_cardinal(true_track_deg),
                "vertical_speed_fpm": vertical_fpm,
                "on_ground": on_ground,
                "squawk": squawk or "—",
                "situation": situation,
                "last_contact_utc": datetime.fromtimestamp(last_contact, timezone.utc).strftime("%H:%M:%S UTC") if last_contact else "N/A",
                "data_provenance": "OpenSky Network (ADS-B)",
            })

        return parsed


# Singleton client instance
_opensky_client = None

def get_opensky_client() -> OpenSkyClient:
    global _opensky_client
    if _opensky_client is None:
        _opensky_client = OpenSkyClient()
    return _opensky_client
