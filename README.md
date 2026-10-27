# AeroRoute: Dual-Airspace Aviation Intelligence Platform

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![MongoDB 4.4](https://img.shields.io/badge/MongoDB-4.4%20WiredTiger-green.svg)](https://www.mongodb.com/)
[![Streamlit 1.39](https://img.shields.io/badge/Streamlit-1.39-red.svg)](https://streamlit.io/)
[![Tests Passing](https://img.shields.io/badge/Tests-129%2F129%20Passed-brightgreen.svg)](docs/final_acceptance_audit.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AeroRoute** is a production-grade aviation intelligence and big data analytics platform featuring a dual-airspace architecture covering **Indian Civil Aviation** and **US Domestic Airspace**. 

The platform integrates large-scale chunked ingestion, server-side MongoDB V8 MapReduce pipelines, graph-theoretic network analysis (NetworkX), unsupervised machine learning for airport archetype discovery (K-Means & PCA), a modern multi-page Streamlit dashboard, and real-time ADS-B aircraft tracking.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Raw Data Sources (CSVs)        |
                      |  - DGCA Indian Timetable Services     |
                      |  - BTS US Domestic Flight Sample      |
                      +-------------------+-------------------+
                                          |
                                          v Chunked ETL Pipeline
                      +---------------------------------------+
                      |         MongoDB WiredTiger DB         |
                      |  Collections: flights, airports, ...  |
                      +-------------------+-------------------+
                                          |
                                          v Server-Side MapReduce
                      +---------------------------------------+
                      |     5 Server-Side MapReduce Jobs      |
                      |  (Jobs A, B, C, D, E -> mr_* colls)   |
                      +-------------------+-------------------+
                                          |
                         +----------------+----------------+
                         |                                 |
                         v                                 v
          +-----------------------------+   +-----------------------------+
          |  Graph & Network Analytics  |   |    Unsupervised ML Model    |
          |  - Directed Corridors       |   |  - Centrality & Density Feat|
          |  - Degree Centrality        |   |  - K-Means (k=4) Archetypes |
          |  - NetworkX Topological Map |   |  - PCA Explained Variance   |
          +--------------+--------------+   +--------------+--------------+
                         |                                 |
                         +----------------+----------------+
                                          |
                                          v
                      +---------------------------------------+
                      |     Streamlit Analytics Dashboard     |
                      |     - 8 Specialized Pages             |
                      |     - Dual-Airspace Regional Switcher |
                      |     - OpenSky ADS-B Live Flight Radar |
                      +---------------------------------------+
```

---

## Key Capabilities

### 1. Dual-Airspace Regional Architecture
- **India Airspace**: 33,023 scheduled timetable services across 107 commercial airports, 14 carriers, and 1,381 directed flight corridors (183,324 flights/week).
- **US Domestic Airspace**: 100,000 baseline domestic flights, 322 commercial airports, 14 airlines, and 4,129 directed flight corridors.
- Zero cross-contamination between regional collections (`flights` vs `flights_in`, `airports` vs `airports_in`, etc.).

### 2. Server-Side MongoDB MapReduce (Jobs A through E)
Five dedicated V8 JavaScript MapReduce jobs compute full network aggregation directly on the database engine:
- **Job A (`mr_route_activity`)**: Directed corridor frequencies, passenger capacity, and airline breakdown.
- **Job B (`mr_airport_outgoing`)**: Outbound departure frequency and unique destination counts.
- **Job C (`mr_airport_incoming`)**: Inbound arrival frequency and origin connectivity.
- **Job D (`mr_monthly_route`)**: Monthly and seasonal corridor time-series trends.
- **Job E (`mr_airport_connectivity`)**: Bidirectional topological degree and connectivity census.

### 3. Unsupervised Machine Learning (K-Means & PCA)
- **Feature Engineering**: Standardized metrics including in-degree, out-degree, total weekly movements, network hub centrality, and average fleet capacity.
- **K-Means Clustering**: Uncovers 4 distinct operational archetypes:
  1. *Super-Hubs* (e.g., DEL, BOM)
  2. *Primary Connectors* (e.g., BLR, HYD, MAA, CCU)
  3. *Regional Feeders* (e.g., PNQ, GOI, COK)
  4. *Local Spokes* (Point-to-point regional airstrips)
- **Dimensionality Reduction**: Principal Component Analysis (PCA) capturing **95.60% cumulative explained variance**.

### 4. Interactive Streamlit Dashboard (Dark Aviation UI)
Eight specialized analytical modules styled with custom CSS and typography:
1. **Network Pulse**: Executive KPIs, corridor rankings, and regional network density.
2. **Route Explorer**: Filterable corridor analytics, airline market shares, and weekly schedules.
3. **Connectivity Map**: Geospatial network topologies with interactive Folium and Plotly visualizations.
4. **Time Radar**: Monthly seasonality, weekly departure profiles, and temporal flight distribution.
5. **MapReduce Lab**: Interactive MapReduce job inspector with execution statistics and schema viewer.
6. **Network Roles**: 2D PCA scatter plots, cluster radar profiles, and feature importance.
7. **Pipeline Health**: Diagnostic health checks, MongoDB connection status, and QA audit census.
8. **Live Tracker**: Real-time ADS-B live aircraft radar powered by OpenSky Network API with dynamic heading chevrons and vertical altitude profiles.

### 5. Automated Verification & Quality Assurance
- **129/129 tests passing** (`pytest`) covering:
  - Unit tests for preprocessing, date parsing, and route key generation.
  - Integration tests for MongoDB ingestion chunking and idempotent reruns.
  - MapReduce mathematical consistency and edge-case resilience.
  - ML reproducibility, deterministic seed checks, and cluster bounds.
  - Regional data isolation audits.

---

## Project Structure

```
aeroroutedb/
├── analytics/                      # Network graph & statistical calculation modules
│   ├── network_analysis.py         # NetworkX directed graph metrics
│   ├── route_intelligence.py       # Corridor analysis & market concentration
│   └── temporal_analysis.py        # Seasonality & frequency profiling
├── config/                         # System configuration and path settings
│   └── settings.py                 # Pydantic/Environment settings
├── dashboard/                      # Multi-page Streamlit application
│   ├── app.py                      # Dashboard entry point
│   ├── components/                 # UI cards, navigation, and theme utilities
│   ├── pages/                      # 8 analytical dashboard pages
│   └── services/                   # Data service layer and MongoDB abstraction
├── data/
│   ├── exports/                    # Precomputed analytics JSON artifacts
│   ├── models/                     # Saved K-Means, Scaler, and PCA joblib models
│   ├── processed/                  # Quality reports and data validation summaries
│   ├── raw/                        # Raw source files (gitignored)
│   └── reference/                  # Airport & airline reference dictionaries
├── docs/                           # Phase reports, audits, and architectural notes
│   ├── baseline_verification_report.md
│   ├── final_acceptance_audit.md
│   ├── phase1_dataset_validation_report.md
│   ├── phase4_analytics_report.md
│   ├── phase5_dashboard_integration.md
│   └── phase6_live_tracker_report.md
├── models/                         # ML clustering algorithms & training pipelines
│   ├── airport_clustering.py       # K-Means clustering & PCA engine
│   ├── feature_pipeline.py         # Feature matrix construction & scaling
│   └── model_evaluation.py         # Silhouette scores & cluster profiling
├── mongodb/                        # Database scripts & MapReduce definitions
│   ├── mapreduce/                  # Server-side JavaScript MapReduce jobs (A-E)
│   ├── setup_indexes.js            # Compound index definitions
│   └── verification_queries.js     # QA verification MongoDB shell queries
├── presentation/                   # Project presentations and demonstration scripts
│   ├── AeroRoute_Presentation.md
│   └── demo_script.md
├── reports/                        # Project documentation and viva preparation
│   ├── AeroRoute_Project_Report.md
│   └── viva_preparation.md
├── scripts/                        # Automation & pipeline orchestration CLI
│   ├── inspect_dataset.py          # Preliminary raw CSV validator
│   ├── load_indian_data.py         # Indian aviation data loader
│   ├── run_indian_mapreduce.py     # Indian MapReduce executor
│   └── run_pipeline.py             # Unified end-to-end pipeline orchestrator
├── src/                            # Core ETL & database utility modules
│   ├── ingestion/                  # Chunked CSV batch ingestion
│   ├── preprocessing/              # Cleaning, coordinate validation, & typing
│   └── utils/                      # MongoDB connectors & logging
├── tests/                          # Automated test suite (129 unit/integration tests)
│   ├── conftest.py                 # Pytest fixtures and mock database setup
│   ├── test_analytics.py
│   ├── test_clustering.py
│   ├── test_dashboard.py
│   ├── test_indian_mapreduce.py
│   └── test_regional_isolation.py
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore patterns (excluding secrets & large data)
├── pytest.ini                      # Pytest runner configuration
├── requirements.txt                # Production dependencies
└── verify_setup.py                 # Environment health diagnostic script
```

---

## Getting Started

### Prerequisites
- **Python**: 3.10, 3.11, or 3.12
- **MongoDB**: 4.4+ Community or Enterprise Server (with WiredTiger engine)

### 1. Clone the Repository
```bash
git clone https://github.com/Nithish5252/AEROROUTE.git
cd AEROROUTE
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and configure your local MongoDB connection:
```bash
cp .env.example .env
```
*(Default settings connect to `mongodb://localhost:27017/aeroroutedb`)*

### 5. Verify Setup
Run the diagnostic script to confirm installed libraries and database connectivity:
```bash
python verify_setup.py
```

---

## Running the Application

### Launch Streamlit Dashboard
```bash
streamlit run dashboard/app.py
```
Open your browser at `http://localhost:8501`. Use the sidebar **Regional Switcher** to toggle between **India Airspace** and **US Domestic Network**.

### Orchestrate the End-to-End Pipeline
Use the unified CLI orchestrator:
```bash
# Full automated run (Validation -> Ingestion -> MapReduce -> Analytics)
python scripts/run_pipeline.py --region INDIA --mode all

# Run specific stages
python scripts/run_pipeline.py --region INDIA --mode validate
python scripts/run_pipeline.py --region INDIA --mode ingest
python scripts/run_pipeline.py --region INDIA --mode mapreduce
python scripts/run_pipeline.py --region INDIA --mode analytics
```

### Run Automated Tests
```bash
pytest
```

---

## Technical Specifications

| Component | Technology | Version / Spec |
| :--- | :--- | :--- |
| **Language** | Python | 3.12.x |
| **Database** | MongoDB | 4.4+ (WiredTiger Engine) |
| **MapReduce** | SpiderMonkey V8 JS Engine | Server-side execution |
| **Graph Analytics** | NetworkX | 3.3 |
| **Machine Learning**| Scikit-Learn | 1.5.2 (K-Means, PCA, StandardScaler) |
| **Web Dashboard** | Streamlit | 1.39.0 |
| **Visualizations** | Plotly & Folium | Plotly 5.24, Folium 0.17 |
| **Live Telemetry** | OpenSky Network REST API | ADS-B State Vectors (20s TTL) |
| **Test Runner** | Pytest | 8.x (129 automated tests) |

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
