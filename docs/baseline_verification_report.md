# AeroRoute: Phase 0 Baseline Verification Report

**Date:** 2026-10-27T00:03:00+05:30  
**Status:** VERIFIED & HEALTHY  

---

## 1. Environment & Dependencies
- **OS:** Windows 11
- **Python:** 3.12.10 (AMD64)
- **PyMongo:** 3.13.0
- **Streamlit:** 1.39.0
- **Plotly:** 5.24.1
- **NetworkX:** 3.3
- **Scikit-learn:** 1.5.2
- **Pandas:** 2.2.3
- **NumPy:** 1.26.4
- **Database:** Local MongoDB Community Server 4.4 (`mongodb://localhost:27017/aeroroutedb`)

---

## 2. Live Database Baseline Verification

| Collection Name | Document Count | Domain / Purpose |
| :--- | :--- | :--- |
| `flights` | 100,000 | US Domestic Historical Flights (Preserved Baseline) |
| `airports` | 322 | US Operational Airports (Preserved Baseline) |
| `airlines` | 14 | US Commercial Carriers (Preserved Baseline) |
| `mr_route_activity` | 4,129 | US Directed Route Frequencies (Preserved Baseline) |
| `mr_airport_outgoing` | 312 | US Outgoing Airport Flights (Preserved Baseline) |
| `mr_airport_incoming` | 312 | US Incoming Airport Flights (Preserved Baseline) |
| `mr_monthly_route` | 4,129 | US Monthly Route Activity (Preserved Baseline) |
| `mr_airport_connectivity` | 312 | US Node Centrality & Graph Connectivity (Preserved) |
| `flights_in` | 33,023 | Indian Domestic Timetable Scheduled Services |
| `airports_in` | 107 | Indian Airports (110 Dataset Station Aliases Resolved) |
| `airlines_in` | 14 | Indian Commercial Domestic Carriers |
| `mr_route_activity_in` | 1,381 | Indian Directed Route Services & Weekly Frequency |
| `mr_airport_outgoing_in` | 100 | Indian Outgoing Hub Frequency & Destinations |
| `mr_airport_incoming_in` | 107 | Indian Incoming Hub Frequency & Origins |
| `mr_monthly_route_in` | 62,234 | Indian Monthly Schedule Coverage (84 Months: 2018–2025) |
| `mr_airport_connectivity_in` | 107 | Indian Topological Connectivity & Centrality |
| `pipeline_runs` | 3 | Historical Audit Trail |

---

## 3. Test Suite Baseline
- **Execution Command:** `pytest`
- **Result:** **110 Passed, 0 Failed** in 3.92s across all 12 test files.
- **Pre-existing Failures:** None.

---

## 4. Phase 0 Conclusion
The baseline is completely sound, reproducible, and ready for continuous execution through Phases 4 through 10.
