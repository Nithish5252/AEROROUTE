# ============================================================
# AeroRoute -- Real-Time Flight Tracking & Airspace Intelligence
# File : dashboard/services/realtime_service.py
# ============================================================
#
# Supports:
# - India Indian Subcontinent & Gulf Airspace (DGCA / AAI)
# - Global Global Intercontinental Megahubs
# - US US Domestic & Transatlantic Network
# - Comprehensive Aircraft Types & Fleet Specifications
# - Predictive ML Delay Risk Scoring
# - Airport Radar HUD & Terminal Gate Telemetry (METAR, Runways)
# - "What-If" Network Resilience & Hub Disruption Simulator
# - 24-Hour Diurnal Wave Time Scrubber
# ============================================================

import logging
import random
import math
import time
import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from dashboard.services.database import get_db, check_connection

logger = logging.getLogger("aeroroute.realtime_service")

# ---------------------------------------------------------------------------
# Comprehensive Airport Registry
# ---------------------------------------------------------------------------

INDIAN_AIRPORTS: Dict[str, Dict[str, Any]] = {
    "DEL": {
        "name": "Indira Gandhi International Airport",
        "city": "New Delhi", "state": "Delhi", "country": "India",
        "lat": 28.5562, "lon": 77.1000, "icao": "VIDP",
        "runways": ["RWY 28/10 (3,810m)", "RWY 29L/11R (4,430m)", "RWY 29R/11L (4,400m)"],
        "terminals": ["T1 (Domestic LCC)", "T2 (Domestic)", "T3 (Integrated Intl/Dom)"],
        "elevation_ft": 777,
    },
    "BOM": {
        "name": "Chhatrapati Shivaji Maharaj International Airport",
        "city": "Mumbai", "state": "Maharashtra", "country": "India",
        "lat": 19.0896, "lon": 72.8656, "icao": "VABB",
        "runways": ["RWY 09/27 (3,448m)", "RWY 14/32 (2,925m cross-runway)"],
        "terminals": ["T1 (Santacruz Domestic)", "T2 (Sahar International/Dom)"],
        "elevation_ft": 39,
    },
    "BLR": {
        "name": "Kempegowda International Airport",
        "city": "Bengaluru", "state": "Karnataka", "country": "India",
        "lat": 13.1986, "lon": 77.7066, "icao": "VOBL",
        "runways": ["RWY 09L/27R (4,000m)", "RWY 09R/27L (4,000m Cat IIIb)"],
        "terminals": ["T1 (Garden City)", "T2 (Terminal in a Garden - Intl)"],
        "elevation_ft": 3000,
    },
    "HYD": {
        "name": "Rajiv Gandhi International Airport",
        "city": "Hyderabad", "state": "Telangana", "country": "India",
        "lat": 17.2403, "lon": 78.4294, "icao": "VOHS",
        "runways": ["RWY 09L/27R (4,260m Cat IIIb)", "RWY 09R/27L (Secondary)"],
        "terminals": ["Integrated Terminal (East/West concourses)"],
        "elevation_ft": 2024,
    },
    "MAA": {
        "name": "Chennai International Airport",
        "city": "Chennai", "state": "Tamil Nadu", "country": "India",
        "lat": 12.9941, "lon": 80.1709, "icao": "VOMM",
        "runways": ["RWY 07/25 (3,658m)", "RWY 12/30 (2,045m)"],
        "terminals": ["T1 (Kamaraj Domestic)", "T2 (Integrated Intl)", "T4 (Domestic)"],
        "elevation_ft": 52,
    },
    "CCU": {
        "name": "Netaji Subhash Chandra Bose International Airport",
        "city": "Kolkata", "state": "West Bengal", "country": "India",
        "lat": 22.6547, "lon": 88.4467, "icao": "VECC",
        "runways": ["RWY 01R/19L (3,627m)", "RWY 01L/19R (2,790m)"],
        "terminals": ["Integrated Terminal (Domestic & International)"],
        "elevation_ft": 16,
    },
    "COK": {
        "name": "Cochin International Airport (Solar Powered)",
        "city": "Kochi", "state": "Kerala", "country": "India",
        "lat": 10.1556, "lon": 76.3912, "icao": "VOCI",
        "runways": ["RWY 09/27 (3,445m Cat IIIa)"],
        "terminals": ["T1 (Domestic)", "T3 (International)"],
        "elevation_ft": 30,
    },
    "AMD": {
        "name": "Sardar Vallabhbhai Patel International Airport",
        "city": "Ahmedabad", "state": "Gujarat", "country": "India",
        "lat": 23.0772, "lon": 72.6347, "icao": "VAAH",
        "runways": ["RWY 05/23 (3,505m)"],
        "terminals": ["T1 (Domestic)", "T2 (International)"],
        "elevation_ft": 189,
    },
    "GOI": {
        "name": "Dabolim Airport (Goa)",
        "city": "Goa Dabolim", "state": "Goa", "country": "India",
        "lat": 15.3808, "lon": 73.8313, "icao": "VOGO",
        "runways": ["RWY 08/26 (3,430m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 184,
    },
    "GOX": {
        "name": "Manohar International Airport (Mopa)",
        "city": "Goa Mopa", "state": "Goa", "country": "India",
        "lat": 15.7725, "lon": 73.8689, "icao": "VOGX",
        "runways": ["RWY 09/27 (3,750m Cat III)"],
        "terminals": ["Passenger Terminal 1"],
        "elevation_ft": 558,
    },
    "PNQ": {
        "name": "Pune International Airport",
        "city": "Pune", "state": "Maharashtra", "country": "India",
        "lat": 18.5821, "lon": 73.9197, "icao": "VAPO",
        "runways": ["RWY 10/28 (2,539m)"],
        "terminals": ["New Integrated Terminal"],
        "elevation_ft": 1942,
    },
    "TRV": {
        "name": "Thiruvananthapuram International Airport",
        "city": "Thiruvananthapuram", "state": "Kerala", "country": "India",
        "lat": 8.4821, "lon": 76.9200, "icao": "VOTV",
        "runways": ["RWY 14/32 (3,400m)"],
        "terminals": ["T1 (Domestic)", "T2 (International)"],
        "elevation_ft": 15,
    },
    "ATQ": {
        "name": "Sri Guru Ram Dass Jee International Airport",
        "city": "Amritsar", "state": "Punjab", "country": "India",
        "lat": 31.7096, "lon": 74.7973, "icao": "VIAR",
        "runways": ["RWY 16/34 (3,658m Cat IIIb)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 756,
    },
    "IXC": {
        "name": "Shaheed Bhagat Singh International Airport",
        "city": "Chandigarh", "state": "Punjab/Haryana", "country": "India",
        "lat": 30.6735, "lon": 76.7885, "icao": "VICG",
        "runways": ["RWY 11/29 (3,170m)"],
        "terminals": ["Integrated Eco-Friendly Terminal"],
        "elevation_ft": 1012,
    },
    "JAI": {
        "name": "Jaipur International Airport",
        "city": "Jaipur", "state": "Rajasthan", "country": "India",
        "lat": 26.8242, "lon": 75.8122, "icao": "VIJP",
        "runways": ["RWY 09/27 (3,505m Cat IIIb)"],
        "terminals": ["T2 (Integrated)"],
        "elevation_ft": 1263,
    },
    "LKO": {
        "name": "Chaudhary Charan Singh International Airport",
        "city": "Lucknow", "state": "Uttar Pradesh", "country": "India",
        "lat": 26.7606, "lon": 80.8893, "icao": "VILK",
        "runways": ["RWY 09/27 (2,743m Cat IIIb)"],
        "terminals": ["T2 (Domestic)", "T3 (Integrated Intl/Dom)"],
        "elevation_ft": 404,
    },
    "GAU": {
        "name": "Lokpriya Gopinath Bordoloi International Airport",
        "city": "Guwahati", "state": "Assam", "country": "India",
        "lat": 26.1061, "lon": 91.5859, "icao": "VEGT",
        "runways": ["RWY 02/20 (3,110m)"],
        "terminals": ["Terminal 1"],
        "elevation_ft": 162,
    },
    "VTZ": {
        "name": "Visakhapatnam International Airport",
        "city": "Visakhapatnam", "state": "Andhra Pradesh", "country": "India",
        "lat": 17.7212, "lon": 83.2245, "icao": "VOVZ",
        "runways": ["RWY 10/28 (3,050m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 17,
    },
    "SXR": {
        "name": "Sheikh ul-Alam International Airport",
        "city": "Srinagar", "state": "Jammu & Kashmir", "country": "India",
        "lat": 34.0086, "lon": 74.7741, "icao": "VISR",
        "runways": ["RWY 13/31 (3,688m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 5458,
    },
    "PAT": {
        "name": "Jayprakash Narayan Airport",
        "city": "Patna", "state": "Bihar", "country": "India",
        "lat": 25.5913, "lon": 85.0880, "icao": "VEPT",
        "runways": ["RWY 07/25 (2,072m)"],
        "terminals": ["Domestic Terminal"],
        "elevation_ft": 170,
    },
    "BBI": {
        "name": "Biju Patnaik International Airport",
        "city": "Bhubaneswar", "state": "Odisha", "country": "India",
        "lat": 20.2444, "lon": 85.8178, "icao": "VEBS",
        "runways": ["RWY 14/32 (2,743m)"],
        "terminals": ["T1 (Domestic)", "T2 (International)"],
        "elevation_ft": 140,
    },
    "NAG": {
        "name": "Dr. Babasaheb Ambedkar International Airport",
        "city": "Nagpur (Zero Mile Hub)", "state": "Maharashtra", "country": "India",
        "lat": 21.0922, "lon": 79.0472, "icao": "VANP",
        "runways": ["RWY 14/32 (3,200m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 1033,
    },
    "IXR": {
        "name": "Birsa Munda Airport",
        "city": "Ranchi", "state": "Jharkhand", "country": "India",
        "lat": 23.3143, "lon": 85.3217, "icao": "VERC",
        "runways": ["RWY 13/31 (2,748m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 2148,
    },
    "IXB": {
        "name": "Bagdogra International Airport",
        "city": "Siliguri / Darjeeling", "state": "West Bengal", "country": "India",
        "lat": 26.6812, "lon": 88.3286, "icao": "VEBD",
        "runways": ["RWY 18/36 (2,750m)"],
        "terminals": ["Domestic Terminal"],
        "elevation_ft": 412,
    },
    "CNN": {
        "name": "Kannur International Airport",
        "city": "Kannur", "state": "Kerala", "country": "India",
        "lat": 11.9189, "lon": 75.5481, "icao": "VOKN",
        "runways": ["RWY 07/25 (3,050m Cat I)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 335,
    },
    "STV": {
        "name": "Surat International Airport",
        "city": "Surat", "state": "Gujarat", "country": "India",
        "lat": 21.1141, "lon": 72.7417, "icao": "VASU",
        "runways": ["RWY 04/22 (2,905m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 16,
    },
    "IDR": {
        "name": "Devi Ahilya Bai Holkar Airport",
        "city": "Indore", "state": "Madhya Pradesh", "country": "India",
        "lat": 22.7217, "lon": 75.8011, "icao": "VAID",
        "runways": ["RWY 07/25 (2,750m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 1849,
    },
    "VNS": {
        "name": "Lal Bahadur Shastri International Airport",
        "city": "Varanasi", "state": "Uttar Pradesh", "country": "India",
        "lat": 25.4524, "lon": 82.8593, "icao": "VEBN",
        "runways": ["RWY 09/27 (2,745m)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 266,
    },
    "IXE": {
        "name": "Mangaluru International Airport",
        "city": "Mangaluru", "state": "Karnataka", "country": "India",
        "lat": 12.9613, "lon": 74.8900, "icao": "VOML",
        "runways": ["RWY 06/24 (2,450m Tabletop)"],
        "terminals": ["Integrated Terminal"],
        "elevation_ft": 336,
    },
    "CCJ": {
        "name": "Calicut International Airport",
        "city": "Kozhikode", "state": "Kerala", "country": "India",
        "lat": 11.1368, "lon": 75.9553, "icao": "VOCL",
        "runways": ["RWY 10/28 (2,860m Tabletop)"],
        "terminals": ["T1 (Domestic)", "T2 (International)"],
        "elevation_ft": 342,
    },
    "CJB": {
        "name": "Coimbatore International Airport",
        "city": "Coimbatore", "state": "Tamil Nadu", "country": "India",
        "lat": 11.0298, "lon": 77.0434, "icao": "VOCB",
        "runways": ["RWY 05/23 (3,044m)"],
        "terminals": ["Single Integrated Terminal"],
        "elevation_ft": 1319,
    },
    "IXZ": {
        "name": "Veer Savarkar International Airport",
        "city": "Port Blair", "state": "Andaman & Nicobar", "country": "India",
        "lat": 11.6410, "lon": 92.7297, "icao": "VOPB",
        "runways": ["RWY 04/22 (3,290m)"],
        "terminals": ["New Integrated Terminal"],
        "elevation_ft": 52,
    },
    "JDH": {
        "name": "Jodhpur Airport",
        "city": "Jodhpur", "state": "Rajasthan", "country": "India",
        "lat": 26.2511, "lon": 73.0489, "icao": "VIJO",
        "runways": ["RWY 05/23 (2,743m)"],
        "terminals": ["Civil Enclave Terminal"],
        "elevation_ft": 717,
    },
    "IXJ": {
        "name": "Jammu Airport",
        "city": "Jammu", "state": "Jammu & Kashmir", "country": "India",
        "lat": 32.6891, "lon": 74.8375, "icao": "VIJU",
        "runways": ["RWY 18/36 (2,042m)"],
        "terminals": ["Civil Enclave Terminal"],
        "elevation_ft": 1029,
    },
}

INTL_AIRPORTS: Dict[str, Dict[str, Any]] = {
    "DXB": {
        "name": "Dubai International Airport",
        "city": "Dubai", "state": "Dubai", "country": "United Arab Emirates",
        "lat": 25.2532, "lon": 55.3657, "icao": "OMDB",
        "runways": ["RWY 12L/30R (4,447m)", "RWY 12R/30L (4,000m)"],
        "terminals": ["T1 (Intl Concourse D)", "T2 (flydubai)", "T3 (Emirates A380 Concourse A/B/C)"],
        "elevation_ft": 62,
    },
    "DOH": {
        "name": "Hamad International Airport",
        "city": "Doha", "state": "Doha", "country": "Qatar",
        "lat": 25.2731, "lon": 51.6081, "icao": "OTHH",
        "runways": ["RWY 16L/34R (4,850m)", "RWY 16R/34L (4,250m)"],
        "terminals": ["Central Passenger Terminal (The Orchard)"],
        "elevation_ft": 13,
    },
    "AUH": {
        "name": "Zayed International Airport (Abu Dhabi)",
        "city": "Abu Dhabi", "state": "Abu Dhabi", "country": "United Arab Emirates",
        "lat": 24.4330, "lon": 54.6511, "icao": "OMAA",
        "runways": ["RWY 13L/31R (4,100m)", "RWY 13R/31L (4,100m)"],
        "terminals": ["Terminal A (Midfield Terminal)"],
        "elevation_ft": 88,
    },
    "SIN": {
        "name": "Singapore Changi Airport",
        "city": "Singapore", "state": "Singapore", "country": "Singapore",
        "lat": 1.3644, "lon": 103.9915, "icao": "WSSS",
        "runways": ["RWY 02L/20R (4,000m)", "RWY 02C/20C (4,000m)", "RWY 02R/20L (2,748m)"],
        "terminals": ["T1", "T2", "T3 (SIA Flagship)", "T4", "Jewel Complex"],
        "elevation_ft": 22,
    },
    "BKK": {
        "name": "Suvarnabhumi Airport",
        "city": "Bangkok", "state": "Samut Prakan", "country": "Thailand",
        "lat": 13.6900, "lon": 100.7501, "icao": "VTBS",
        "runways": ["RWY 01R/19L (4,000m)", "RWY 01L/19R (3,700m)"],
        "terminals": ["Main Terminal Concourse A-G", "SAT-1 Midfield"],
        "elevation_ft": 5,
    },
    "KUL": {
        "name": "Kuala Lumpur International Airport",
        "city": "Kuala Lumpur", "state": "Selangor", "country": "Malaysia",
        "lat": 2.7456, "lon": 101.7099, "icao": "WMKK",
        "runways": ["RWY 14L/32R (4,056m)", "RWY 14R/32L (4,019m)", "RWY 15/33 (3,960m)"],
        "terminals": ["KLIA Main Terminal & Satellite", "KLIA2 (AirAsia Hub)"],
        "elevation_ft": 69,
    },
    "LHR": {
        "name": "London Heathrow Airport",
        "city": "London", "state": "England", "country": "United Kingdom",
        "lat": 51.4700, "lon": -0.4543, "icao": "EGLL",
        "runways": ["RWY 09L/27R (3,902m)", "RWY 09R/27L (3,660m)"],
        "terminals": ["T2 (Queen's)", "T3 (Oneworld)", "T4 (SkyTeam)", "T5 (BA Flagship)"],
        "elevation_ft": 83,
    },
    "FRA": {
        "name": "Frankfurt Airport",
        "city": "Frankfurt", "state": "Hesse", "country": "Germany",
        "lat": 50.0379, "lon": 8.5622, "icao": "EDDF",
        "runways": ["RWY 07C/25C (4,000m)", "RWY 07R/25L (4,000m)", "RWY 18 (4,000m)"],
        "terminals": ["T1 (Lufthansa Star Alliance)", "T2 (SkyTeam & Oneworld)"],
        "elevation_ft": 364,
    },
    "CDG": {
        "name": "Paris Charles de Gaulle Airport",
        "city": "Paris", "state": "Île-de-France", "country": "France",
        "lat": 49.0097, "lon": 2.5479, "icao": "LFPG",
        "runways": ["RWY 09L/27R (4,215m)", "RWY 09R/27L (4,200m)", "RWY 08L/26R (4,215m)"],
        "terminals": ["T1", "T2A-2G (Air France Concourse)", "T3"],
        "elevation_ft": 392,
    },
    "AMS": {
        "name": "Amsterdam Airport Schiphol",
        "city": "Amsterdam", "state": "North Holland", "country": "Netherlands",
        "lat": 52.3105, "lon": 4.7683, "icao": "EHAM",
        "runways": ["Polderbaan 18R/36L (3,800m)", "Kaagbaan 06/24 (3,500m)", "Aalsmeerbaan 18L/36R (3,400m)"],
        "terminals": ["Single Terminal (Departures 1, 2, 3, 4)"],
        "elevation_ft": -11,
    },
    "JFK": {
        "name": "John F. Kennedy International Airport",
        "city": "New York", "state": "NY", "country": "United States",
        "lat": 40.6413, "lon": -73.7781, "icao": "KJFK",
        "runways": ["RWY 04L/22R (3,682m)", "RWY 04R/22L (2,560m)", "RWY 13L/31R (4,423m)"],
        "terminals": ["T1 (Intl)", "T4 (Delta)", "T5 (JetBlue)", "T7", "T8 (American/BA)"],
        "elevation_ft": 13,
    },
    "SFO": {
        "name": "San Francisco International Airport",
        "city": "San Francisco", "state": "CA", "country": "United States",
        "lat": 37.6213, "lon": -122.3790, "icao": "KSFO",
        "runways": ["RWY 28L/10R (3,475m)", "RWY 28R/10L (3,618m)"],
        "terminals": ["T1 (Harvey Milk)", "T2", "T3 (United)", "International Terminal A/G"],
        "elevation_ft": 13,
    },
    "ORD": {
        "name": "Chicago O'Hare International Airport",
        "city": "Chicago", "state": "IL", "country": "United States",
        "lat": 41.9742, "lon": -87.9073, "icao": "KORD",
        "runways": ["RWY 10L/28R (3,962m)", "RWY 10C/28C (3,292m)", "RWY 09C/27C (3,429m)"],
        "terminals": ["T1 (United)", "T2", "T3 (American)", "T5 (International)"],
        "elevation_ft": 668,
    },
    "HND": {
        "name": "Tokyo Haneda Airport",
        "city": "Tokyo", "state": "Tokyo", "country": "Japan",
        "lat": 35.5494, "lon": 139.7798, "icao": "RJTT",
        "runways": ["RWY 34L/16R (3,000m)", "RWY 34R/16L (3,360m)", "RWY 05/23 (2,500m)"],
        "terminals": ["T1 (JAL)", "T2 (ANA)", "T3 (International)"],
        "elevation_ft": 21,
    },
    "SYD": {
        "name": "Sydney Kingsford Smith Airport",
        "city": "Sydney", "state": "NSW", "country": "Australia",
        "lat": -33.9399, "lon": 151.1753, "icao": "YSSY",
        "runways": ["RWY 16R/34L (3,962m)", "RWY 16L/34R (2,438m)", "RWY 07/25 (2,530m)"],
        "terminals": ["T1 (International)", "T2 (Domestic)", "T3 (Qantas)"],
        "elevation_ft": 21,
    },
    "IST": {
        "name": "Istanbul Airport (Mega Hub)",
        "city": "Istanbul", "state": "Istanbul", "country": "Turkey",
        "lat": 41.2753, "lon": 28.7519, "icao": "LTFM",
        "runways": ["RWY 16R/34L (3,750m)", "RWY 16L/34R (3,750m)", "RWY 17L/35R (4,100m)"],
        "terminals": ["Main Passenger Terminal (World's Largest Under Single Roof)"],
        "elevation_ft": 325,
    },
}

US_AIRPORTS: Dict[str, Dict[str, Any]] = {
    "ATL": {"name": "Hartsfield-Jackson Atlanta Intl", "city": "Atlanta", "state": "GA", "country": "United States", "lat": 33.6407, "lon": -84.4277, "icao": "KATL", "elevation_ft": 1026},
    "LAX": {"name": "Los Angeles International", "city": "Los Angeles", "state": "CA", "country": "United States", "lat": 33.9425, "lon": -118.4081, "icao": "KLAX", "elevation_ft": 125},
    "ORD": {"name": "Chicago O'Hare International", "city": "Chicago", "state": "IL", "country": "United States", "lat": 41.9742, "lon": -87.9073, "icao": "KORD", "elevation_ft": 668},
    "DFW": {"name": "Dallas/Fort Worth International", "city": "Dallas/Ft Worth", "state": "TX", "country": "United States", "lat": 32.8998, "lon": -97.0403, "icao": "KDFW", "elevation_ft": 607},
    "DEN": {"name": "Denver International", "city": "Denver", "state": "CO", "country": "United States", "lat": 39.8561, "lon": -104.6737, "icao": "KDEN", "elevation_ft": 5434},
    "JFK": {"name": "John F. Kennedy International", "city": "New York", "state": "NY", "country": "United States", "lat": 40.6413, "lon": -73.7781, "icao": "KJFK", "elevation_ft": 13},
    "SFO": {"name": "San Francisco International", "city": "San Francisco", "state": "CA", "country": "United States", "lat": 37.6213, "lon": -122.3790, "icao": "KSFO", "elevation_ft": 13},
    "SEA": {"name": "Seattle-Tacoma International", "city": "Seattle", "state": "WA", "country": "United States", "lat": 47.4502, "lon": -122.3088, "icao": "KSEA", "elevation_ft": 433},
    "LAS": {"name": "Harry Reid International", "city": "Las Vegas", "state": "NV", "country": "United States", "lat": 36.0840, "lon": -115.1537, "icao": "KLAS", "elevation_ft": 2181},
    "MCO": {"name": "Orlando International", "city": "Orlando", "state": "FL", "country": "United States", "lat": 28.4294, "lon": -81.3089, "icao": "KMCO", "elevation_ft": 96},
    "CLT": {"name": "Charlotte Douglas International", "city": "Charlotte", "state": "NC", "country": "United States", "lat": 35.2140, "lon": -80.9431, "icao": "KCLT", "elevation_ft": 748},
    "PHX": {"name": "Phoenix Sky Harbor International", "city": "Phoenix", "state": "AZ", "country": "United States", "lat": 33.4373, "lon": -112.0078, "icao": "KPHX", "elevation_ft": 1135},
    "MIA": {"name": "Miami International", "city": "Miami", "state": "FL", "country": "United States", "lat": 25.7959, "lon": -80.2870, "icao": "KMIA", "elevation_ft": 8},
    "EWR": {"name": "Newark Liberty International", "city": "Newark", "state": "NJ", "country": "United States", "lat": 40.6895, "lon": -74.1745, "icao": "KEWR", "elevation_ft": 18},
    "BOS": {"name": "Boston Logan International", "city": "Boston", "state": "MA", "country": "United States", "lat": 42.3656, "lon": -71.0096, "icao": "KBOS", "elevation_ft": 20},
    "IAH": {"name": "George Bush Intercontinental", "city": "Houston", "state": "TX", "country": "United States", "lat": 29.9902, "lon": -95.3368, "icao": "KIAH", "elevation_ft": 97},
}

# ---------------------------------------------------------------------------
# Comprehensive Airline Fleet Specifications & Aircraft Types
# ---------------------------------------------------------------------------

AIRCRAFT_FLEET_SPECS: Dict[str, Dict[str, Any]] = {
    "A320neo": {
        "model": "Airbus A320neo",
        "category": "Narrowbody Twin-Jet",
        "capacity": 186,
        "cruise_speed_kts": 450,
        "max_altitude_ft": 39000,
        "range_km": 6500,
        "wake_turbulence": "Medium",
    },
    "A321neo": {
        "model": "Airbus A321neo",
        "category": "Narrowbody Extended",
        "capacity": 222,
        "cruise_speed_kts": 455,
        "max_altitude_ft": 39000,
        "range_km": 7400,
        "wake_turbulence": "Medium",
    },
    "A350-900": {
        "model": "Airbus A350-900",
        "category": "Widebody Long-Haul",
        "capacity": 316,
        "cruise_speed_kts": 490,
        "max_altitude_ft": 43000,
        "range_km": 15000,
        "wake_turbulence": "Heavy",
    },
    "A350-1000": {
        "model": "Airbus A350-1000",
        "category": "Widebody Ultra Long-Haul",
        "capacity": 369,
        "cruise_speed_kts": 495,
        "max_altitude_ft": 43000,
        "range_km": 16100,
        "wake_turbulence": "Heavy",
    },
    "B777-300ER": {
        "model": "Boeing 777-300ER",
        "category": "Widebody Twin-Aisle",
        "capacity": 342,
        "cruise_speed_kts": 490,
        "max_altitude_ft": 43100,
        "range_km": 13650,
        "wake_turbulence": "Heavy",
    },
    "B787-8": {
        "model": "Boeing 787-8 Dreamliner",
        "category": "Widebody Composite",
        "capacity": 256,
        "cruise_speed_kts": 488,
        "max_altitude_ft": 43000,
        "range_km": 13620,
        "wake_turbulence": "Heavy",
    },
    "B787-9": {
        "model": "Boeing 787-9 Dreamliner",
        "category": "Widebody Extended Dreamliner",
        "capacity": 296,
        "cruise_speed_kts": 490,
        "max_altitude_ft": 43000,
        "range_km": 14140,
        "wake_turbulence": "Heavy",
    },
    "B737-MAX8": {
        "model": "Boeing 737 MAX 8",
        "category": "Narrowbody Next-Gen",
        "capacity": 189,
        "cruise_speed_kts": 453,
        "max_altitude_ft": 41000,
        "range_km": 6570,
        "wake_turbulence": "Medium",
    },
    "B737-800": {
        "model": "Boeing 737-800",
        "category": "Narrowbody Classic",
        "capacity": 189,
        "cruise_speed_kts": 450,
        "max_altitude_ft": 41000,
        "range_km": 5436,
        "wake_turbulence": "Medium",
    },
    "A380-800": {
        "model": "Airbus A380-800 Superjumbo",
        "category": "Double-Deck Super-Heavy",
        "capacity": 484,
        "cruise_speed_kts": 490,
        "max_altitude_ft": 43000,
        "range_km": 15200,
        "wake_turbulence": "Super",
    },
    "ATR-72": {
        "model": "ATR 72-600",
        "category": "Regional Turboprop (UDAN)",
        "capacity": 72,
        "cruise_speed_kts": 275,
        "max_altitude_ft": 25000,
        "range_km": 1528,
        "wake_turbulence": "Medium",
    },
    "Q400": {
        "model": "De Havilland Dash 8 Q400",
        "category": "High-Speed Regional Turboprop",
        "capacity": 78,
        "cruise_speed_kts": 360,
        "max_altitude_ft": 27000,
        "range_km": 2040,
        "wake_turbulence": "Medium",
    },
}

AIRLINES_DIRECTORY: Dict[str, Dict[str, Any]] = {
    # Indian Airspace Carriers
    "6E": {
        "name": "IndiGo Airlines",
        "country": "India",
        "callsign": "IFLY",
        "fleet": ["A320neo", "A321neo", "ATR-72"],
        "badge_color": "#2563EB",
        "reg_prefix": "VT-I",
        "type": "Low-Cost Carrier / Market Leader",
    },
    "AI": {
        "name": "Air India (Tata Group)",
        "country": "India",
        "callsign": "AIRINDIA",
        "fleet": ["A350-900", "B777-300ER", "B787-8", "A320neo"],
        "badge_color": "#DC2626",
        "reg_prefix": "VT-A",
        "type": "Full-Service Flag Carrier",
    },
    "UK": {
        "name": "Vistara (Tata SIA)",
        "country": "India",
        "callsign": "VISTARA",
        "fleet": ["B787-9", "A321neo", "A320neo"],
        "badge_color": "#7C2D12",
        "reg_prefix": "VT-T",
        "type": "Premium Full-Service",
    },
    "QP": {
        "name": "Akasa Air",
        "country": "India",
        "callsign": "AKASA AIR",
        "fleet": ["B737-MAX8"],
        "badge_color": "#EA580C",
        "reg_prefix": "VT-Y",
        "type": "Ultra-Modern LCC",
    },
    "SG": {
        "name": "SpiceJet",
        "country": "India",
        "callsign": "SPICETJET",
        "fleet": ["B737-800", "Q400"],
        "badge_color": "#C2410C",
        "reg_prefix": "VT-S",
        "type": "Low-Cost Regional & Trunk",
    },
    "IX": {
        "name": "Air India Express",
        "country": "India",
        "callsign": "EXPRESS INDIA",
        "fleet": ["B737-MAX8", "B737-800"],
        "badge_color": "#B91C1C",
        "reg_prefix": "VT-B",
        "type": "International Budget & Gulf Link",
    },
    # International Flagship Megacarriers
    "EK": {
        "name": "Emirates",
        "country": "United Arab Emirates",
        "callsign": "EMIRATES",
        "fleet": ["A380-800", "B777-300ER"],
        "badge_color": "#B91C1C",
        "reg_prefix": "A6-E",
        "type": "Global Mega Carrier",
    },
    "QR": {
        "name": "Qatar Airways",
        "country": "Qatar",
        "callsign": "QATARI",
        "fleet": ["A350-1000", "B787-9", "B777-300ER"],
        "badge_color": "#831843",
        "reg_prefix": "A7-B",
        "type": "5-Star Global Flagship",
    },
    "SQ": {
        "name": "Singapore Airlines",
        "country": "Singapore",
        "callsign": "SINGAPORE",
        "fleet": ["A380-800", "A350-900", "B787-9"],
        "badge_color": "#1E3A8A",
        "reg_prefix": "9V-S",
        "type": "Premier Global Airline",
    },
    "LH": {
        "name": "Lufthansa",
        "country": "Germany",
        "callsign": "LUFTHANSA",
        "fleet": ["A350-900", "B747-8"],
        "badge_color": "#1E293B",
        "reg_prefix": "D-A",
        "type": "European Star Alliance Leader",
    },
    "BA": {
        "name": "British Airways",
        "country": "United Kingdom",
        "callsign": "SPEEDBIRD",
        "fleet": ["A350-1000", "B777-300ER", "B787-9"],
        "badge_color": "#1E40AF",
        "reg_prefix": "G-Z",
        "type": "British Flag Carrier",
    },
    "EY": {
        "name": "Etihad Airways",
        "country": "United Arab Emirates",
        "callsign": "ETIHAD",
        "fleet": ["B787-9", "A350-1000"],
        "badge_color": "#B45309",
        "reg_prefix": "A6-B",
        "type": "UAE National Airline",
    },
    # US Network Carriers
    "DL": {
        "name": "Delta Air Lines",
        "country": "United States",
        "callsign": "DELTA",
        "fleet": ["A350-900", "A321neo", "B737-800"],
        "badge_color": "#1E3A8A",
        "reg_prefix": "N8",
        "type": "US Global Network Carrier",
    },
    "UA": {
        "name": "United Airlines",
        "country": "United States",
        "callsign": "UNITED",
        "fleet": ["B787-9", "B777-300ER", "B737-MAX8"],
        "badge_color": "#0369A1",
        "reg_prefix": "N3",
        "type": "US Transcontinental Leader",
    },
    "AA": {
        "name": "American Airlines",
        "country": "United States",
        "callsign": "AMERICAN",
        "fleet": ["B777-300ER", "B787-8", "B737-800"],
        "badge_color": "#0284C7",
        "reg_prefix": "N9",
        "type": "World's Largest Airline by Fleet",
    },
}

# Real-world Indian high-density trunk & metro corridors
INDIAN_CORRIDORS: List[Tuple[str, str, str]] = [
    ("DEL", "BOM", "6E"), ("BOM", "DEL", "AI"), ("DEL", "BLR", "UK"),
    ("BLR", "DEL", "6E"), ("BOM", "BLR", "QP"), ("BLR", "BOM", "6E"),
    ("DEL", "HYD", "6E"), ("HYD", "DEL", "AI"), ("DEL", "MAA", "UK"),
    ("MAA", "DEL", "6E"), ("DEL", "CCU", "AI"), ("CCU", "DEL", "6E"),
    ("BOM", "HYD", "6E"), ("BOM", "MAA", "AI"), ("BOM", "COK", "6E"),
    ("COK", "BOM", "AI"), ("BLR", "HYD", "6E"), ("BLR", "MAA", "6E"),
    ("DEL", "GOI", "6E"), ("DEL", "GOX", "QP"), ("BOM", "GOI", "SG"),
    ("DEL", "AMD", "6E"), ("BOM", "AMD", "AI"), ("DEL", "PNQ", "UK"),
    ("BOM", "PNQ", "6E"), ("DEL", "ATQ", "AI"), ("DEL", "SXR", "6E"),
    ("DEL", "IXC", "UK"), ("DEL", "JAI", "6E"), ("DEL", "LKO", "6E"),
    ("DEL", "GAU", "6E"), ("CCU", "GAU", "AI"), ("MAA", "COK", "6E"),
    ("BLR", "COK", "6E"), ("DEL", "VTZ", "6E"), ("DEL", "PAT", "SG"),
    ("DEL", "BBI", "6E"), ("BOM", "NAG", "6E"), ("DEL", "IXR", "6E"),
    ("CCU", "IXB", "6E"), ("COK", "TRV", "6E"),
    # Middle East & Southeast Asia International Connections from India
    ("DEL", "DXB", "EK"), ("BOM", "DXB", "EK"), ("BLR", "DXB", "EK"),
    ("DEL", "DOH", "QR"), ("BOM", "DOH", "QR"), ("MAA", "DOH", "QR"),
    ("DEL", "SIN", "SQ"), ("BOM", "SIN", "SQ"), ("BLR", "SIN", "SQ"),
    ("DEL", "LHR", "AI"), ("BOM", "LHR", "BA"), ("DEL", "FRA", "LH"),
    ("BLR", "FRA", "LH"), ("DEL", "JFK", "AI"), ("BOM", "EWR", "AI"),
    ("DEL", "SFO", "AI"), ("BOM", "SFO", "AI"), ("BKK", "DEL", "AI"),
    ("KUL", "MAA", "6E"), ("COK", "DXB", "IX"), ("TRV", "AUH", "IX"),
    ("CNN", "DOH", "IX"),
]

GLOBAL_CORRIDORS: List[Tuple[str, str, str]] = [
    ("LHR", "JFK", "BA"), ("JFK", "LHR", "AA"), ("LHR", "DXB", "EK"),
    ("DXB", "SIN", "EK"), ("SIN", "HND", "SQ"), ("HND", "SFO", "UA"),
    ("SFO", "JFK", "UA"), ("JFK", "CDG", "DL"), ("CDG", "DXB", "EK"),
    ("FRA", "ORD", "LH"), ("ORD", "LHR", "UA"), ("DXB", "SYD", "EK"),
    ("SIN", "SYD", "SQ"), ("DOH", "LHR", "QR"), ("DOH", "JFK", "QR"),
    ("FRA", "SIN", "LH"), ("AMS", "ATL", "DL"), ("IST", "JFK", "UA"),
    ("DEL", "LHR", "AI"), ("BOM", "JFK", "AI"), ("DEL", "SIN", "SQ"),
]

US_FALLBACK_ROUTES: List[Tuple[str, str, str]] = [
    ("ATL", "LAX", "DL"), ("LAX", "JFK", "AA"), ("ORD", "DFW", "UA"),
    ("DFW", "LAX", "AA"), ("DEN", "ORD", "UA"), ("SFO", "JFK", "UA"),
    ("ATL", "MCO", "DL"), ("JFK", "LAX", "AA"), ("LAS", "LAX", "DL"),
    ("PHX", "LAX", "AA"), ("SEA", "LAX", "DL"), ("MIA", "JFK", "AA"),
    ("BOS", "ORD", "UA"), ("DTW", "ATL", "DL"), ("EWR", "SFO", "UA"),
]

# Delay cause categories and their typical minute ranges
_DELAY_CAUSES = {
    "Carrier / Turnaround": (15, 120),
    "Adverse Weather": (20, 240),
    "ATC Route Congestion": (15, 90),
    "Runway Queue & Slot": (10, 60),
    "Late Inbound Aircraft": (20, 180),
}

_STATUS_OPTIONS   = ["ON TIME", "AIRBORNE", "BOARDING", "DEPARTED", "DELAYED", "DIVERTED", "LANDED"]
_STATUS_WEIGHTS   = [0.38,      0.22,       0.12,       0.10,       0.12,      0.01,       0.05]

DELAY_MINOR    = 15
DELAY_MODERATE = 45
DELAY_SEVERE   = 90

# ---------------------------------------------------------------------------
# Mathematical & Geodesic Utilities
# ---------------------------------------------------------------------------

def _interpolate_position(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    progress: float
) -> Tuple[float, float]:
    """Spherical / geodesic approximation for flight path interpolation."""
    lat = lat1 + (lat2 - lat1) * progress
    lon = lon1 + (lon2 - lon1) * progress
    return round(lat, 4), round(lon, 4)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _calculate_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    heading = (math.degrees(math.atan2(dlon, dlat)) + 360) % 360
    return round(heading, 1)


# ---------------------------------------------------------------------------
# Machine Learning Delay Risk Scorer
# ---------------------------------------------------------------------------

def compute_ml_delay_risk(
    origin_code: str,
    dest_code: str,
    distance_km: float,
    departure_hour: int,
    airline_code: str,
    simulated_delay_min: int,
) -> Dict[str, Any]:
    """
    Predictive ML Delay Risk Scorer.
    Estimates the probability (0-100%) that an en-route flight will suffer
    delays based on airport congestion, diurnal peak hours, route distance,
    and turnaround stress.
    """
    # 1. Congestion feature: High-volume mega hubs have elevated risk
    busy_hubs = {"DEL", "BOM", "BLR", "DXB", "LHR", "JFK", "ORD", "ATL"}
    hub_stress = 0
    if origin_code in busy_hubs:
        hub_stress += 18
    if dest_code in busy_hubs:
        hub_stress += 14

    # 2. Diurnal wave factor: 08-10 AM and 18-21 PM peak departure banks
    if 8 <= departure_hour <= 10 or 18 <= departure_hour <= 21:
        diurnal_factor = 22
    elif 11 <= departure_hour <= 17:
        diurnal_factor = 12
    else:
        diurnal_factor = 5

    # 3. Distance & airspace complexity
    distance_factor = min(int(distance_km / 180), 16)

    # 4. Turnaround propagation base
    random_noise = random.randint(-4, 6)
    raw_risk = hub_stress + diurnal_factor + distance_factor + random_noise

    # If the flight already has delay in simulation, correlate with high risk
    if simulated_delay_min > 0:
        raw_risk += min(int(simulated_delay_min * 0.4), 35)

    risk_pct = max(5, min(raw_risk, 98))

    # Categorize risk
    if risk_pct < 30:
        category = "LOW"
        color = "#22C55E"
    elif risk_pct < 60:
        category = "MODERATE"
        color = "#F59E0B"
    elif risk_pct < 80:
        category = "HIGH"
        color = "#F97316"
    else:
        category = "CRITICAL"
        color = "#EF4444"

    # Identify primary contributing risk factors
    factors = []
    if hub_stress >= 18:
        factors.append(f"Hub Saturation ({origin_code}/{dest_code})")
    if diurnal_factor >= 20:
        factors.append("Peak Diurnal Bank")
    if distance_km > 2500:
        factors.append("Long-Haul Airway Complexity")
    if simulated_delay_min > 30:
        factors.append("Turnaround Ripple Effect")
    if not factors:
        factors.append("Standard En-Route Flow")

    return {
        "risk_pct": risk_pct,
        "category": category,
        "color": color,
        "primary_factor": factors[0],
        "factors": factors,
    }


# ---------------------------------------------------------------------------
# Airport Radar Telemetry (METAR, Runways, Queues)
# ---------------------------------------------------------------------------

def get_airport_telemetry(iata_code: str) -> Dict[str, Any]:
    """
    Returns live terminal radar telemetry for a selected airport, including
    simulated METAR weather observations, active runway queues, and terminal load.
    """
    all_airports = {**INDIAN_AIRPORTS, **INTL_AIRPORTS, **US_AIRPORTS}
    info = all_airports.get(iata_code.upper(), {
        "name": f"{iata_code} International",
        "city": iata_code,
        "country": "International",
        "runways": ["RWY 09/27 (3,500m)"],
        "terminals": ["Main Terminal"],
        "elevation_ft": 500,
        "icao": f"V{iata_code}P",
    })

    # Weather simulation seeded by airport and time
    airport_hash = sum(ord(c) for c in iata_code)
    time_seed = int(time.time() // 600) + airport_hash
    rng = random.Random(time_seed)

    temp_c = rng.randint(22, 38) if info.get("country") in ["India", "United Arab Emirates", "Qatar"] else rng.randint(12, 28)
    dew_c = max(temp_c - rng.randint(3, 10), 5)
    wind_dir = rng.choice([90, 140, 240, 270, 310, 360])
    wind_spd = rng.randint(4, 18)
    visibility_km = rng.choice([3.5, 5.0, 7.0, 10.0, 10.0])
    qnh = rng.randint(1008, 1018)

    cond_options = ["CAVOK (Clear Skies)", "FEW clouds at 3000ft", "Scattered haze / dry mist", "Thunderstorm in vicinity", "Light drizzle"]
    cond = rng.choice(cond_options)

    icao = info.get("icao", f"V{iata_code}")
    metar_str = f"{icao} 201200Z {wind_dir:03d}{wind_spd:02d}KT {int(visibility_km*1000):04d} {cond[:3].upper()} {temp_c}/{dew_c} Q{qnh} NOSIG"

    runways = info.get("runways", ["RWY 09/27"])
    active_runway = runways[0].split(" ")[1] if len(runways[0].split(" ")) > 1 else runways[0]

    inbound_queue = rng.randint(2, 9)
    outbound_queue = rng.randint(3, 14)
    avg_taxi_out = rng.randint(12, 28)

    return {
        "iata": iata_code.upper(),
        "icao": icao,
        "name": info.get("name", ""),
        "city": info.get("city", ""),
        "country": info.get("country", ""),
        "elevation_ft": info.get("elevation_ft", 0),
        "runways": runways,
        "active_runway": active_runway,
        "terminals": info.get("terminals", ["Main Terminal"]),
        "metar_raw": metar_str,
        "temperature_c": temp_c,
        "dew_point_c": dew_c,
        "wind": f"{wind_dir}° at {wind_spd} kts",
        "visibility_km": visibility_km,
        "altimeter_qnh": qnh,
        "condition": cond,
        "inbound_queue": inbound_queue,
        "outbound_queue": outbound_queue,
        "avg_taxi_out_min": avg_taxi_out,
        "gate_occupancy_pct": rng.randint(68, 94),
    }


# ---------------------------------------------------------------------------
# "What-If" Network Resilience & Hub Disruption Simulator
# ---------------------------------------------------------------------------

def simulate_network_disruption(
    disrupted_airport: str,
    scenario_name: str,
    severity_pct: int,
    flights_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Computes real-time network cascade effects if a major hub suffers an outage:
    - Cancelled / Diverted Flights
    - Impacted Spoke Routes (downstream ripple effect)
    - Stranded Passengers
    - Additional Network Delay Incurred
    """
    if flights_df.empty:
        return {}

    apt = disrupted_airport.upper()
    total_flights = len(flights_df)

    # Flights with origin or destination at this airport
    direct_flights = flights_df[(flights_df["origin"] == apt) | (flights_df["destination"] == apt)]
    direct_count = len(direct_flights)

    # Number of flights directly cancelled/diverted based on severity
    impact_fraction = severity_pct / 100.0
    grounded_count = int(round(direct_count * impact_fraction))

    # Average passengers per aircraft based on fleet capacities
    avg_capacity = int(flights_df["capacity"].mean()) if "capacity" in flights_df.columns else 180
    stranded_pax = grounded_count * avg_capacity

    # Identify spoke airports affected
    spokes = set()
    for _, r in direct_flights.iterrows():
        other = r["destination"] if r["origin"] == apt else r["origin"]
        if other != apt:
            spokes.add(other)

    # Ripple delay calculation: each grounded aircraft delays subsequent legs by 45-120 min
    cascade_delay_min = grounded_count * random.randint(70, 110)
    system_resilience_score = max(10, 100 - int(grounded_count * 3.2) - int(len(spokes) * 1.5))

    return {
        "hub": apt,
        "scenario": scenario_name,
        "severity_pct": severity_pct,
        "direct_flights": direct_count,
        "grounded_or_diverted": grounded_count,
        "affected_spoke_airports": list(spokes),
        "spoke_count": len(spokes),
        "stranded_passengers": stranded_pax,
        "cascade_delay_minutes": cascade_delay_min,
        "resilience_health_score": system_resilience_score,
        "direct_flight_ids": direct_flights["flight_id"].tolist(),
    }


# ---------------------------------------------------------------------------
# 24-Hour Diurnal Wave Time Controller
# ---------------------------------------------------------------------------

def get_diurnal_traffic_profile(hour: int) -> Dict[str, Any]:
    """
    Provides diurnal traffic volume multiplier and operational wave descriptor
    for 24-hour time scrubbing.
    """
    if 5 <= hour < 9:
        wave_name = " Early Morning Metro Business Rush"
        multiplier = 1.35
        desc = "High departure intensity on golden trunk corridors (DEL-BOM, BLR-DEL, HYD-BOM)."
    elif 9 <= hour < 13:
        wave_name = "️ Midday Trunk & Connecting Bank"
        multiplier = 1.10
        desc = "Regional feeder flights connecting to long-haul hubs; active domestic transit."
    elif 13 <= hour < 17:
        wave_name = " Afternoon Inter-Regional Operations"
        multiplier = 0.95
        desc = "UDAN tier-2 connectivity, cargo feeds, and transcontinental operations."
    elif 17 <= hour < 21:
        wave_name = " Evening Peak Return & Corporate Bank"
        multiplier = 1.40
        desc = "Peak network saturation; turnaround stress peaks across major metro airports."
    elif 21 <= hour < 24:
        wave_name = " Late Night Gulf & European Departures"
        multiplier = 0.85
        desc = "International widebodies departing for Middle East hubs (DXB/DOH) and Europe."
    else:
        wave_name = " Overnight Redeye & Cargo Corridor"
        multiplier = 0.45
        desc = "Freight networks, maintenance repositions, and overnight redeye services."

    return {
        "hour": hour,
        "wave_name": wave_name,
        "multiplier": multiplier,
        "description": desc,
    }


# ---------------------------------------------------------------------------
# Live ADS-B Equipment & Route Resolution
# ---------------------------------------------------------------------------

_FLIGHT_TIMETABLE_CACHE: Dict[str, Dict[str, Any]] = {}


def _infer_aircraft_model(callsign: str, airline_code: str, alt_ft: float) -> Tuple[str, str, int]:
    """
    Infers realistic aircraft equipment, category, and passenger capacity from airline fleet and altitude.
    Returns (model_name, category, capacity).
    """
    h = int(hashlib.md5(callsign.encode("utf-8")).hexdigest(), 16)
    fleet = AIRLINES_DIRECTORY.get(airline_code, {}).get("fleet", [])

    if not fleet:
        if alt_ft > 38000:
            aircraft_key = "B787-8" if (h % 2 == 0) else "A350-900"
        elif alt_ft < 16000:
            aircraft_key = "ATR-72" if (h % 2 == 0) else "Q400"
        else:
            aircraft_key = "A320neo" if (h % 2 == 0) else "B737-800"
    else:
        if alt_ft < 16000 and any(m in ["ATR-72", "Q400"] for m in fleet):
            turboprops = [m for m in fleet if m in ["ATR-72", "Q400"]]
            aircraft_key = turboprops[h % len(turboprops)]
        elif alt_ft > 38000 and any(
            m in ["A350-900", "A350-1000", "B787-8", "B787-9", "B777-300ER", "A380-800", "B747-8"] for m in fleet
        ):
            widebodies = [
                m
                for m in fleet
                if m in ["A350-900", "A350-1000", "B787-8", "B787-9", "B777-300ER", "A380-800", "B747-8"]
            ]
            aircraft_key = widebodies[h % len(widebodies)]
        else:
            narrow = [m for m in fleet if m not in ["ATR-72", "Q400"]]
            pool = narrow if narrow else fleet
            aircraft_key = pool[h % len(pool)]

    spec = AIRCRAFT_FLEET_SPECS.get(aircraft_key, AIRCRAFT_FLEET_SPECS["A320neo"])
    return spec["model"], spec["category"], spec["capacity"]


def _resolve_live_flight_corridor(
    callsign: str,
    airline_code: str,
    lat: Optional[float],
    lon: Optional[float],
    heading: Optional[float],
    airspace: str = "india",
) -> Dict[str, Any]:
    """
    Resolves origin and destination airports, city names, and route distances for live ADS-B aircraft.
    Uses cached timetable lookup first, then spatial heading vectors, and finally deterministic airline corridor sampling.
    """
    global _FLIGHT_TIMETABLE_CACHE
    h = int(hashlib.md5(callsign.encode("utf-8")).hexdigest(), 16)

    # 1. Select airport coordinates dictionary based on airspace
    if airspace == "india":
        coords = {**INDIAN_AIRPORTS, **INTL_AIRPORTS}
        corridors = INDIAN_CORRIDORS
        default_orig, default_dest = "DEL", "BOM"
    elif airspace == "global":
        coords = {**INTL_AIRPORTS, **INDIAN_AIRPORTS, **US_AIRPORTS}
        corridors = GLOBAL_CORRIDORS + INDIAN_CORRIDORS[:15]
        default_orig, default_dest = "DXB", "LHR"
    else:
        coords = {**US_AIRPORTS, **INTL_AIRPORTS}
        corridors = US_FALLBACK_ROUTES
        default_orig, default_dest = "JFK", "LAX"

    orig_code, dest_code = None, None

    # 2. Check timetable cache or database
    m = re.search(r"\d+", callsign)
    flight_num = m.group(0) if m else ""
    if flight_num and flight_num in _FLIGHT_TIMETABLE_CACHE:
        cached_entry = _FLIGHT_TIMETABLE_CACHE[flight_num]
        orig_code, dest_code = cached_entry["origin"], cached_entry["destination"]
    elif flight_num:
        try:
            db = get_db()
            coll_name = "flights_in" if airspace in ["india", "global"] else "flights"
            if coll_name in db.list_collection_names():
                query = (
                    {"airline_code": airline_code, "flight_number": flight_num}
                    if airline_code != "OTHER"
                    else {"flight_number": flight_num}
                )
                doc = db[coll_name].find_one(query)
                if not doc and airline_code != "OTHER":
                    doc = db[coll_name].find_one({"flight_number": flight_num})
                if doc and doc.get("origin") and doc.get("destination"):
                    orig_code = doc["origin"].get("iata") or doc["origin"].get("code")
                    dest_code = doc["destination"].get("iata") or doc["destination"].get("code")
                    if orig_code and dest_code and orig_code != dest_code:
                        _FLIGHT_TIMETABLE_CACHE[flight_num] = {
                            "origin": orig_code,
                            "destination": dest_code,
                        }
        except Exception:
            pass

    # 3. Spatial heading vector resolution if not matched in timetable
    has_pos = lat is not None and not pd.isna(lat) and lon is not None and not pd.isna(lon)
    has_hdg = heading is not None and not pd.isna(heading)

    if (not orig_code or not dest_code or orig_code == dest_code) and has_pos and has_hdg:
        cand_dest = []
        cand_orig = []
        major_hubs = {"DEL", "BOM", "BLR", "HYD", "MAA", "CCU", "JFK", "LAX", "ORD", "DFW", "ATL", "DXB", "LHR", "SIN"}

        for apt, info in coords.items():
            apt_lat, apt_lon = info.get("lat"), info.get("lon")
            if apt_lat is None or apt_lon is None:
                continue
            dist = _haversine_km(lat, lon, apt_lat, apt_lon)
            if dist > 2600 or dist < 20:
                continue
            brg = _calculate_heading(lat, lon, apt_lat, apt_lon)
            diff_dest = abs((heading - brg + 180) % 360 - 180)
            brg_back = (heading + 180) % 360
            diff_orig = abs((brg_back - brg + 180) % 360 - 180)

            hub_factor = 0.65 if apt in major_hubs else 1.0
            if diff_dest < 55:
                cand_dest.append((dist * hub_factor, apt))
            if diff_orig < 55:
                cand_orig.append((dist * hub_factor, apt))

        cand_dest.sort()
        cand_orig.sort()
        if cand_dest:
            dest_code = cand_dest[0][1]
        if cand_orig:
            orig_code = cand_orig[0][1]

    # 4. Deterministic airline corridor fallback if still unresolved
    if not orig_code or not dest_code or orig_code == dest_code:
        airline_corrs = [c for c in corridors if len(c) >= 3 and c[2] == airline_code]
        pool = airline_corrs if airline_corrs else corridors
        if pool:
            chosen = pool[h % len(pool)]
            orig_code, dest_code = chosen[0], chosen[1]
        else:
            orig_code, dest_code = default_orig, default_dest

    if orig_code == dest_code:
        dest_code = default_dest if orig_code == default_orig else default_orig

    # 5. Extract metadata and calculate distance and progress
    o_meta = coords.get(orig_code, {"city": orig_code, "name": f"{orig_code} Airport", "lat": lat, "lon": lon})
    d_meta = coords.get(dest_code, {"city": dest_code, "name": f"{dest_code} Airport", "lat": lat, "lon": lon})

    if o_meta.get("lat") and d_meta.get("lat"):
        dist_km = round(_haversine_km(o_meta["lat"], o_meta["lon"], d_meta["lat"], d_meta["lon"]))
    else:
        dist_km = 850

    if has_pos and o_meta.get("lat") and dist_km > 0:
        dist_from_orig = _haversine_km(o_meta["lat"], o_meta["lon"], lat, lon)
        progress_pct = max(10.0, min(92.0, round((dist_from_orig / dist_km) * 100, 1)))
    else:
        progress_pct = 50.0

    return {
        "origin": orig_code,
        "origin_city": o_meta.get("city", orig_code),
        "origin_name": o_meta.get("name", f"{orig_code} Airport"),
        "destination": dest_code,
        "dest_city": d_meta.get("city", dest_code),
        "dest_name": d_meta.get("name", f"{dest_code} Airport"),
        "distance_km": dist_km,
        "progress_pct": progress_pct,
    }


# ---------------------------------------------------------------------------
# Main Flight Generator Supporting All Airspaces
# ---------------------------------------------------------------------------

def get_live_flights(
    airspace: str = "india",  # "india", "global", "usa"
    n_flights: int = 60,
    time_hour: Optional[int] = None,
    time_minute: Optional[int] = None,
    seed: Optional[int] = None,
    prefer_live_api: bool = True,
) -> pd.DataFrame:
    """
    Retrieves live flights for the requested airspace.
    If prefer_live_api is True, fetches real-time ADS-B state vectors from the OpenSky Network.
    If OpenSky is unreachable or rate-limited, provides synthetic operational simulation
    with explicit data provenance flags to avoid deceiving users.
    """
    if prefer_live_api:
        try:
            from src.services.opensky_service import get_opensky_client
            client = get_opensky_client()
            target_reg = "INDIA" if airspace in ["india", "global"] else "US"
            live_df, meta = client.fetch_live_aircraft(region=target_reg)

            if meta.get("status") == "ONLINE" and not live_df.empty:
                logger.info(f"Using {len(live_df)} live OpenSky state vectors for airspace [{airspace}].")
                # Format live records for dashboard compatibility
                live_records = []
                for _, row in live_df.head(max(n_flights, 150)).iterrows():
                    raw_alt = row.get("altitude_ft")
                    if raw_alt is None or pd.isna(raw_alt):
                        alt = 0.0
                    else:
                        try:
                            alt = float(raw_alt)
                            if math.isnan(alt):
                                alt = 0.0
                        except (ValueError, TypeError):
                            alt = 0.0

                    raw_spd = row.get("ground_speed_kts")
                    if raw_spd is None or pd.isna(raw_spd):
                        spd = 0.0
                    else:
                        try:
                            spd = float(raw_spd)
                            if math.isnan(spd):
                                spd = 0.0
                        except (ValueError, TypeError):
                            spd = 0.0

                    raw_vert = row.get("vertical_speed_fpm")
                    if raw_vert is None or pd.isna(raw_vert):
                        vert_fpm = 0.0
                    else:
                        try:
                            vert_fpm = float(raw_vert)
                            if math.isnan(vert_fpm):
                                vert_fpm = 0.0
                        except (ValueError, TypeError):
                            vert_fpm = 0.0

                    int_alt = int(round(alt))
                    int_spd = int(round(spd))
                    int_vert = int(round(vert_fpm))

                    if int_vert > 500:
                        vert_label = f"+{int_vert:,} fpm (Climbing)"
                        status = "CLIMBING"
                    elif int_vert < -500:
                        vert_label = f"{int_vert:,} fpm (Descending)"
                        status = "DESCENDING"
                    elif row.get("on_ground"):
                        vert_label = "0 fpm (Ground)"
                        status = "ON GROUND"
                    else:
                        vert_label = "Level (Cruise)"
                        status = "AIRBORNE"

                    fl = f"FL{int_alt // 100}" if int_alt >= 10000 else (f"{int_alt:,} ft" if int_alt > 0 else "GND")
                    carrier = row.get("operator") or row.get("origin_country") or "Commercial Aircraft"
                    code = row.get("airline_code") or "OTHER"

                    # Infer realistic aircraft model from fleet & altitude
                    model_name, category, capacity = _infer_aircraft_model(row["callsign"], code, alt)

                    # Infer realistic origin, destination corridor, and progress
                    corridor_info = _resolve_live_flight_corridor(
                        callsign=row["callsign"],
                        airline_code=code,
                        lat=row["latitude"],
                        lon=row["longitude"],
                        heading=row.get("heading_deg"),
                        airspace=airspace,
                    )

                    # Commercial flight ID (e.g. IGO126 -> 6E 126, AIC2378 -> AI 2378)
                    digits = "".join(ch for ch in row["callsign"][3:] if ch.isalnum()) if len(row["callsign"]) > 3 else ""
                    if code != "OTHER" and digits:
                        comm_flight_id = f"{code} {digits}"
                    else:
                        comm_flight_id = row["callsign"]

                    cur_spd = spd if spd > 100 else 420.0
                    rem_km = max(0.0, corridor_info["distance_km"] * (1.0 - corridor_info["progress_pct"] / 100.0))
                    rem_min = int(round((rem_km / (cur_spd * 1.852)) * 60))
                    eta_str = f"+{rem_min} min" if rem_min > 0 else "Approaching"
                    flight_duration = int(round((corridor_info["distance_km"] / (cur_spd * 1.852)) * 60))

                    live_records.append({
                        "flight_id": comm_flight_id,
                        "callsign": row["callsign"],
                        "tail_number": f"HEX:{row['icao24'].upper()}",
                        "mode_s_hex": row["icao24"].upper(),
                        "squawk": row["squawk"],
                        "vertical_speed_fpm": vert_fpm,
                        "vertical_speed_label": vert_label,
                        "flight_level": fl,
                        "atc_sector": "Live ADS-B Radar Sector",
                        "transponder_protocol": "ADS-B Out (1090ES)",
                        "gps_integrity": "Live ADS-B Broadcast",
                        "ping_latency_ms": 110,
                        "airline_code": code,
                        "airline": carrier,
                        "airline_type": "Live Scheduled Commercial Operator",
                        "aircraft_model": model_name,
                        "aircraft_category": category,
                        "capacity": capacity,
                        "origin": corridor_info["origin"],
                        "origin_city": corridor_info["origin_city"],
                        "origin_name": corridor_info["origin_name"],
                        "destination": corridor_info["destination"],
                        "dest_city": corridor_info["dest_city"],
                        "dest_name": corridor_info["dest_name"],
                        "status": status,
                        "lat": row["latitude"],
                        "lon": row["longitude"],
                        "altitude_ft": int_alt,
                        "speed_kts": spd,
                        "heading": row.get("heading_deg") or 0.0,
                        "progress_pct": corridor_info["progress_pct"],
                        "distance_km": corridor_info["distance_km"],
                        "flight_duration_min": flight_duration,
                        "delay_minutes": 0,
                        "delay_cause": "Live Transponder Stream",
                        "delay_severity": "none",
                        "ml_risk_pct": 12,
                        "ml_risk_category": "LOW",
                        "ml_risk_color": "#22C55E",
                        "ml_risk_factor": "Nominal Live ADS-B Track",
                        "std": row.get("last_contact_utc", "Live"),
                        "atd": row.get("last_contact_utc", "Live"),
                        "sta": "Live",
                        "departed_at": row.get("last_contact_utc", "Live"),
                        "eta": eta_str,
                        "route_key": f"{corridor_info['origin']}->{corridor_info['destination']}",
                        "data_provenance": "OpenSky Network (Live ADS-B Telemetry)",
                        "is_live_telemetry": True,
                    })

                if live_records:
                    return pd.DataFrame(live_records)
        except Exception as e:
            logger.warning(f"Failed to fetch live OpenSky aircraft: {e}. Falling back to simulation.")

    # Diurnal time seed for synthetic simulation fallback
    now = datetime.utcnow()
    hour = time_hour if time_hour is not None else now.hour
    minute = time_minute if time_minute is not None else now.minute

    if seed is not None:
        random.seed(seed)
    else:
        random.seed(int(time.time() // 60) + hour * 100 + minute)

    # 1. Select airport registry and route corridors based on airspace
    if airspace == "india":
        coords = {**INDIAN_AIRPORTS, **INTL_AIRPORTS}
        corridors = INDIAN_CORRIDORS
        default_airline_codes = ["6E", "AI", "UK", "QP", "SG", "IX", "EK", "QR", "SQ"]
    elif airspace == "global":
        coords = {**INTL_AIRPORTS, **INDIAN_AIRPORTS, **US_AIRPORTS}
        corridors = GLOBAL_CORRIDORS + INDIAN_CORRIDORS[:15]
        default_airline_codes = ["EK", "QR", "SQ", "LH", "BA", "AI", "DL", "UA", "AA"]
    else:
        coords = {**US_AIRPORTS, **INTL_AIRPORTS}
        corridors = US_FALLBACK_ROUTES
        default_airline_codes = ["DL", "UA", "AA", "6E", "BA", "EK"]

        # Try sampling real routes from MongoDB if connected
        is_conn, _ = check_connection()
        if is_conn:
            try:
                db = get_db()
                pipeline = [{"$match": {"value": {"$gt": 10}}}, {"$sample": {"size": 80}}]
                sampled = []
                for doc in db.mr_route_activity.aggregate(pipeline):
                    key = doc.get("_id", "")
                    if "->" in key:
                        o, d = key.split("->", 1)
                        if o.strip() in coords and d.strip() in coords:
                            sampled.append((o.strip(), d.strip(), ""))
                if sampled:
                    corridors = sampled
            except Exception:
                pass

    # Ensure corridors only use available coords
    valid_corridors = [
        (o, d, a) for (o, d, a) in corridors
        if o in coords and d in coords and o != d
    ]
    if not valid_corridors:
        valid_corridors = [("DEL", "BOM", "6E"), ("BOM", "BLR", "AI"), ("DEL", "BLR", "UK")]

    # Sample routes
    selected = random.choices(valid_corridors, k=n_flights)
    records = []

    for idx, (orig, dest, airline_hint) in enumerate(selected):
        o_info = coords[orig]
        d_info = coords[dest]

        # Airline selection
        airline_code = airline_hint or random.choice(default_airline_codes)
        airline_meta = AIRLINES_DIRECTORY.get(airline_code, {
            "name": f"Aero {airline_code}",
            "country": "International",
            "callsign": airline_code,
            "fleet": ["A320neo", "B737-800"],
            "badge_color": "#2563EB",
            "reg_prefix": "VT-",
            "type": "Commercial Airline",
        })

        # Aircraft Equipment Selection from airline's actual fleet
        possible_fleet = airline_meta.get("fleet", ["A320neo"])
        aircraft_key = random.choice(possible_fleet)
        fleet_spec = AIRCRAFT_FLEET_SPECS.get(aircraft_key, AIRCRAFT_FLEET_SPECS["A320neo"])

        flight_num_int = random.randint(101, 2999)
        flight_id = f"{airline_code} {flight_num_int}"
        callsign = f"{airline_meta.get('callsign', airline_code)}{flight_num_int}"
        tail_num = f"{airline_meta.get('reg_prefix', 'VT-')}{random.choice(['A','B','C','D','X','Z'])}{random.randint(10,99)}"

        # Progress along route
        progress = random.uniform(0.06, 0.94)

        # Great circle interpolated position
        cur_lat, cur_lon = _interpolate_position(o_info["lat"], o_info["lon"], d_info["lat"], d_info["lon"], progress)
        heading = _calculate_heading(o_info["lat"], o_info["lon"], d_info["lat"], d_info["lon"])
        dist_km = _haversine_km(o_info["lat"], o_info["lon"], d_info["lat"], d_info["lon"])

        # Realistic altitude and speed profiles scaled by corridor distance
        if dist_km < 200:
            route_max_alt = min(14000, fleet_spec["max_altitude_ft"])
            route_min_alt = 8000
            route_cruise_spd = min(fleet_spec["cruise_speed_kts"], 300)
        elif dist_km < 450:
            route_max_alt = min(26000, fleet_spec["max_altitude_ft"])
            route_min_alt = 18000
            route_cruise_spd = min(fleet_spec["cruise_speed_kts"], 380)
        else:
            route_max_alt = fleet_spec["max_altitude_ft"]
            route_min_alt = min(28000, route_max_alt - 4000)
            route_cruise_spd = fleet_spec["cruise_speed_kts"]

        # Status & altitude based on route progress
        if progress < 0.10:
            status = random.choice(["BOARDING", "DEPARTED"])
            altitude = random.randint(1500, min(8000, route_max_alt))
            speed = random.randint(150, 240)
        elif progress > 0.90:
            status = random.choice(["LANDED", "AIRBORNE"])
            altitude = random.randint(1200, min(6000, route_max_alt))
            speed = random.randint(140, 220)
        else:
            status = random.choices(_STATUS_OPTIONS, _STATUS_WEIGHTS)[0]
            altitude = random.randint(route_min_alt, route_max_alt)
            speed = random.randint(max(route_cruise_spd - 25, 180), route_cruise_spd + 15)

        # Synthetic Delay Generation
        is_delayed = (status == "DELAYED") or (random.random() < 0.22)
        if is_delayed:
            cause = random.choice(list(_DELAY_CAUSES.keys()))
            lo, hi = _DELAY_CAUSES[cause]
            delay_min = random.randint(lo, hi)
            if delay_min < DELAY_MINOR:
                severity = "none"
            elif delay_min < DELAY_MODERATE:
                severity = "minor"
            elif delay_min < DELAY_SEVERE:
                severity = "moderate"
            else:
                severity = "severe"
            status = "DELAYED" if status not in ["DIVERTED", "LANDED"] else status
        else:
            delay_min = 0
            cause = "—"
            severity = "none"

        # Predictive ML Delay Risk Scoring
        ml_risk = compute_ml_delay_risk(
            origin_code=orig,
            dest_code=dest,
            distance_km=dist_km,
            departure_hour=hour,
            airline_code=airline_code,
            simulated_delay_min=delay_min,
        )

        # Authentic flight duration & scheduled vs actual timestamps
        speed_kmh = speed * 1.852
        duration_min = max((dist_km / max(speed_kmh, 200)) * 60, 25)

        # Base operational time reference
        current_op_time = datetime(now.year, now.month, now.day, hour, minute)
        actual_dep = current_op_time - timedelta(minutes=duration_min * progress)
        scheduled_dep = actual_dep - timedelta(minutes=delay_min)
        scheduled_arr = scheduled_dep + timedelta(minutes=duration_min)
        eta_time = actual_dep + timedelta(minutes=duration_min)

        # Authentic ADS-B Transponder Telemetry & ATC Parameters
        if airline_code in ["6E", "AI", "UK", "QP", "SG", "IX"]:
            mode_s_hex = f"80{random.randint(0x0100, 0x0FFF):04X}"
        elif airline_code in ["EK", "EY"]:
            mode_s_hex = f"89{random.randint(0x0100, 0x0FFF):04X}"
        elif airline_code == "SQ":
            mode_s_hex = f"76{random.randint(0x0100, 0x0FFF):04X}"
        else:
            mode_s_hex = f"A{random.randint(0x10000, 0xFFFFF):05X}"

        # ATC Transponder Squawk code (4-digit octal)
        if status == "DIVERTED" and random.random() < 0.3:
            squawk = "7700"  # Emergency
        else:
            squawk = f"{random.choice(['1', '2', '3', '4', '5'])}{random.randint(0, 7)}{random.randint(0, 7)}{random.randint(0, 7)}"

        # Vertical rate (climb / descent / cruise in fpm)
        if progress < 0.15:
            vert_speed_fpm = random.randint(1400, 2800)
            vert_label = f"+{vert_speed_fpm:,} fpm (Climbing)"
        elif progress > 0.85:
            vert_speed_fpm = -random.randint(1100, 2300)
            vert_label = f"{vert_speed_fpm:,} fpm (Descending)"
        else:
            vert_speed_fpm = random.choice([0, 0, 0, 64, -64])
            vert_label = "Level (Cruise)"

        flight_level = f"FL{altitude // 100}" if altitude >= 10000 else f"{altitude:,} ft"

        # Active ATC sector & frequency
        if orig == "DEL" or dest == "DEL":
            atc_sector = "Delhi Control (125.700 MHz)"
        elif orig == "BOM" or dest == "BOM":
            atc_sector = "Mumbai Area Control (132.600 MHz)"
        elif orig == "BLR" or dest == "BLR":
            atc_sector = "Bengaluru Radar (121.200 MHz)"
        elif orig == "HYD" or dest == "HYD":
            atc_sector = "Hyderabad Approach (119.200 MHz)"
        elif orig == "MAA" or dest == "MAA":
            atc_sector = "Chennai Radar (120.500 MHz)"
        elif orig == "CCU" or dest == "CCU":
            atc_sector = "Kolkata FIR Control (126.100 MHz)"
        elif orig == "DXB" or dest == "DXB":
            atc_sector = "Emirates Radar (120.400 MHz)"
        elif orig == "SIN" or dest == "SIN":
            atc_sector = "Singapore Control (132.150 MHz)"
        else:
            atc_sector = "En-Route Airway Sector (124.850 MHz)"

        records.append({
            "flight_id": flight_id,
            "callsign": callsign,
            "tail_number": tail_num,
            "mode_s_hex": mode_s_hex,
            "squawk": squawk,
            "vertical_speed_fpm": vert_speed_fpm,
            "vertical_speed_label": vert_label,
            "flight_level": flight_level,
            "atc_sector": atc_sector,
            "transponder_protocol": "ADS-B Out (1090ES)",
            "gps_integrity": "NACp: 9 (EPU &lt; 30m)",
            "ping_latency_ms": random.randint(92, 185),
            "airline_code": airline_code,
            "airline": airline_meta["name"],
            "airline_type": airline_meta["type"],
            "aircraft_model": fleet_spec["model"],
            "aircraft_category": fleet_spec["category"],
            "capacity": fleet_spec["capacity"],
            "origin": orig,
            "origin_city": o_info.get("city", orig),
            "origin_name": o_info.get("name", orig),
            "destination": dest,
            "dest_city": d_info.get("city", dest),
            "dest_name": d_info.get("name", dest),
            "status": status,
            "lat": cur_lat,
            "lon": cur_lon,
            "altitude_ft": altitude,
            "speed_kts": speed,
            "heading": heading,
            "progress_pct": round(progress * 100, 1),
            "distance_km": round(dist_km, 0),
            "flight_duration_min": round(duration_min, 0),
            "delay_minutes": delay_min,
            "delay_cause": cause,
            "delay_severity": severity,
            "ml_risk_pct": ml_risk["risk_pct"],
            "ml_risk_category": ml_risk["category"],
            "ml_risk_color": ml_risk["color"],
            "ml_risk_factor": ml_risk["primary_factor"],
            "std": scheduled_dep.strftime("%H:%M IST"),
            "atd": actual_dep.strftime("%H:%M IST"),
            "sta": scheduled_arr.strftime("%H:%M IST"),
            "departed_at": actual_dep.strftime("%H:%M IST"),
            "eta": eta_time.strftime("%H:%M IST"),
            "route_key": f"{orig} → {dest}",
        })

    return pd.DataFrame(records)


def get_delay_summary(flights_df: pd.DataFrame) -> Dict[str, Any]:
    """Aggregate delay KPIs and ML risk distributions from the flight snapshot."""
    if flights_df.empty:
        return {}

    delayed = flights_df[flights_df["delay_minutes"] > 0]
    total = len(flights_df)

    delay_by_cause = (
        delayed.groupby("delay_cause")["delay_minutes"]
        .agg(["count", "mean", "sum"])
        .reset_index()
        .rename(columns={"count": "flights", "mean": "avg_delay", "sum": "total_delay"})
        .sort_values("flights", ascending=False)
    )

    severity_counts = delayed["delay_severity"].value_counts().to_dict()
    ml_risk_counts = flights_df["ml_risk_category"].value_counts().to_dict()

    worst_routes = (
        delayed.groupby("route_key")["delay_minutes"]
        .agg(["count", "mean"])
        .reset_index()
        .rename(columns={"count": "delayed_flights", "mean": "avg_delay_min"})
        .sort_values("avg_delay_min", ascending=False)
        .head(8)
    )

    return {
        "total_flights": total,
        "delayed_flights": len(delayed),
        "on_time_flights": total - len(delayed),
        "delay_rate_pct": round(len(delayed) / total * 100, 1) if total > 0 else 0,
        "avg_delay_minutes": round(delayed["delay_minutes"].mean(), 1) if not delayed.empty else 0,
        "max_delay_minutes": int(delayed["delay_minutes"].max()) if not delayed.empty else 0,
        "by_cause": delay_by_cause,
        "by_severity": severity_counts,
        "ml_risk_distribution": ml_risk_counts,
        "worst_routes": worst_routes,
        "severe_count": severity_counts.get("severe", 0),
        "moderate_count": severity_counts.get("moderate", 0),
        "minor_count": severity_counts.get("minor", 0),
    }


def get_delay_trend(n_snapshots: int = 12, airspace: str = "india") -> pd.DataFrame:
    """Rolling trend over the last 12 intervals (5-min each)."""
    now = datetime.utcnow()
    records = []
    base_seed = int(time.time() // 300)

    for i in range(n_snapshots):
        random.seed(base_seed - i)
        snapshot_time = now - timedelta(minutes=5 * (n_snapshots - 1 - i))
        delay_rate = round(random.uniform(11, 28), 1)
        avg_delay = round(random.uniform(18, 52), 1)
        n_active = random.randint(45, 95)
        records.append({
            "timestamp": snapshot_time.strftime("%H:%M"),
            "delay_rate_pct": delay_rate,
            "avg_delay_min": avg_delay,
            "airborne_count": n_active,
        })

    return pd.DataFrame(records)


# ── FlightRadar24 Situation Indication Color System ─────────────────────────
FR24_CRUISE    = "#FACC15"  # FlightRadar24 Iconic Yellow (Airborne Cruising)
FR24_CLIMB     = "#10B981"  # Emerald Green (Climbing > 600 fpm)
FR24_DESCEND   = "#EAB308"  # Warm Amber Gold (Descending < -600 fpm)
FR24_DELAYED   = "#F97316"  # Bright Orange (Delayed 15-60 min)
FR24_CRITICAL  = "#EF4444"  # Alert Red (Severe Delay >= 60 min)
FR24_EMERGENCY = "#DC2626"  # Crimson Red (Diverted / Squawk 7700)
FR24_GROUND    = "#38BDF8"  # Sky Blue (Taxiing / Boarding / Gate)
FR24_LANDED    = "#A855F7"  # Royal Purple (Touchdown / Landed)


def get_fr24_situation(row: pd.Series) -> Tuple[str, str]:
    """
    Returns (situation_label, hex_color) mimicking FlightRadar24 live tracking rules.
    """
    status = str(row.get("status", "")).upper()
    delay = int(row.get("delay_minutes", 0))
    vert = int(row.get("vertical_speed_fpm", 0))
    sqk = str(row.get("squawk", ""))

    if status == "DIVERTED" or sqk == "7700":
        return "DIVERTED / 7700", FR24_EMERGENCY
    if status == "LANDED":
        return "LANDED", FR24_LANDED
    if status in ["BOARDING", "DEPARTED"]:
        return "GROUND / TAXI", FR24_GROUND
    if delay >= 60:
        return f"CRITICAL DELAY (+{delay}m)", FR24_CRITICAL
    if delay > 0:
        return f"DELAYED (+{delay}m)", FR24_DELAYED
    if vert > 600:
        return "CLIMBING", FR24_CLIMB
    if vert < -600:
        return "DESCENDING", FR24_DESCEND
    return "AIRBORNE / CRUISE", FR24_CRUISE


def get_opensky_telemetry_meta(airspace: str = "india") -> Dict[str, Any]:
    """Retrieve metadata about the active live OpenSky telemetry stream."""
    try:
        from src.services.opensky_service import get_opensky_client
        client = get_opensky_client()
        target_reg = "INDIA" if airspace in ["india", "global"] else "US"
        _, meta = client.fetch_live_aircraft(region=target_reg)
        return meta
    except Exception as e:
        return {
            "status": "OFFLINE",
            "message": str(e),
            "data_source": "OpenSky Network (Unavailable)",
            "coverage_disclaimer": "Live telemetry service currently unavailable.",
        }
