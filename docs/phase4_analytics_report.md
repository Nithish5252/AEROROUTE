# Phase 4 Analytics Adaptation Report: Indian Civil Aviation Intelligence

**Project**: AeroRoute Flight Route Network Intelligence Platform  
**Phase**: Phase 4 -- Analytics & Machine Learning Regional Adaptation  
**Timestamp**: 2026-10-27  
**Engine**: Python 3.12, scikit-learn 1.6, NetworkX 3.4, MongoDB 4.4 Community  
**Status**: Completed and Mathematically Verified (100% Pass)

---

## 1. Executive Summary

Phase 4 adapted all core statistical, topological, and machine learning analytical engines within AeroRoute to support dual-region processing (`INDIA` and `US`). The Indian analytics pipeline processes approved Directorate General of Civil Aviation (DGCA) and Airports Authority of India (AAI) domestic airline schedules (spanning 2018–2025).

All analytics modules distinguish between published timetable schedule entries, operational days per week, and weekly scheduled frequencies. Operational delays, cancellations, and passenger load factors are never fabricated.

---

## 2. Mathematical Integrity & Corpus Verification

| Metric / Collection | Indian Dataset (`*_in`) | US Dataset (Baseline) | Verification Result |
| :--- | :--- | :--- | :--- |
| **Active Flights / Schedules** | 33,023 eligible services | 97,611 eligible flights | Exact document match |
| **Commercial Airports** | 107 active airports | 322 active airports | Complete coordinate mapping |
| **Operating Airlines** | 14 scheduled carriers | 14 scheduled carriers | Complete ICAO/IATA resolution |
| **Directed Corridors** | 1,381 unique directed routes | 4,129 unique directed routes | Bidirectional reciprocity verified |
| **Total Weekly Departures** | 183,324 movements/week | N/A (single-snapshot operated flights) | MapReduce Job A sum = 183,324 |
| **Route Activity HHI** | 0.00341 (Normalized: 0.00268) | 0.00192 (Normalized: 0.00168) | Highly competitive / unconcentrated |
| **Network Reciprocity** | 0.9413 (94.1% symmetric) | 0.9632 (96.3% symmetric) | Strong bilateral air service agreements |

---

## 3. Top Indian Aviation Corridors (Job A & Route Intelligence)

| Rank | Route Key | Origin Hub | Destination Hub | Weekly Frequency | Timetable Services | Est. Monthly Departures |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **BOM -> DEL** | Mumbai (BOM) | Delhi (DEL) | 2,314 | 337 | 9,950 |
| 2 | **DEL -> BOM** | Delhi (DEL) | Mumbai (BOM) | 1,855 | 272 | 7,976 |
| 3 | **BLR -> DEL** | Bengaluru (BLR) | Delhi (DEL) | 1,603 | 231 | 6,892 |
| 4 | **DEL -> BLR** | Delhi (DEL) | Bengaluru (BLR) | 1,484 | 215 | 6,381 |
| 5 | **HYD -> DEL** | Hyderabad (HYD) | Delhi (DEL) | 1,218 | 176 | 5,237 |
| 6 | **DEL -> HYD** | Delhi (DEL) | Hyderabad (HYD) | 1,176 | 170 | 5,056 |
| 7 | **DEL -> CCU** | Delhi (DEL) | Kolkata (CCU) | 1,064 | 154 | 4,575 |
| 8 | **CCU -> DEL** | Kolkata (CCU) | Delhi (DEL) | 1,029 | 149 | 4,424 |
| 9 | **BLR -> BOM** | Bengaluru (BLR) | Mumbai (BOM) | 994 | 144 | 4,274 |
| 10 | **BOM -> BLR** | Mumbai (BOM) | Bengaluru (BLR) | 980 | 142 | 4,214 |

---

## 4. Top Indian Airport Hubs & Centrality Analysis

Network analysis via NetworkX 3.4 produced the following hub topological hierarchy across Indian domestic airspace:

| IATA | Airport Name | City | Total Weekly Volume | Outbound Dests | Betweenness Centrality | PageRank |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **DEL** | Indira Gandhi International | Delhi | 38,416 | 72 | 0.2418 | 0.0712 |
| **BOM** | Chhatrapati Shivaji Maharaj | Mumbai | 31,892 | 64 | 0.1895 | 0.0594 |
| **BLR** | Kempegowda International | Bengaluru | 24,108 | 58 | 0.1241 | 0.0468 |
| **HYD** | Rajiv Gandhi International | Hyderabad | 19,453 | 54 | 0.0982 | 0.0389 |
| **CCU** | Netaji Subhash Chandra Bose | Kolkata | 14,882 | 46 | 0.0815 | 0.0321 |
| **MAA** | Chennai International | Chennai | 14,210 | 44 | 0.0764 | 0.0305 |
| **AMD** | Sardar Vallabhbhai Patel | Ahmedabad | 8,918 | 36 | 0.0352 | 0.0211 |
| **GOI** | Dabolim / Manohar International | Goa | 7,644 | 28 | 0.0219 | 0.0182 |

---

## 5. Machine Learning Clustering (K-Means, k = 4)

- **Input Features (7 total)**: `total_flights`, `outgoing_flights`, `incoming_flights`, `distinct_destinations`, `distinct_origins`, `betweenness_centrality`, `pagerank`.
- **Transformation Pipeline**: Skewed count log1p transformation (`np.log1p`) followed by `StandardScaler` to normalize distributions before distance computation.
- **Dimensionality Reduction**: 2D Principal Component Analysis (PCA) capturing **95.60% cumulative explained variance** (PC1: 80.22%, PC2: 15.38%).
- **Evaluation Scores**:
  - Inertia: 134.35
  - Silhouette Score: 0.4407
  - Calinski-Harabasz Index: 157.08
  - Davies-Bouldin Score: 0.6524

### Discovered Archetypes:
1. **Tier 3: Core National Super-Hubs (5 airports: DEL, BOM, BLR, HYD, CCU)**
   - Massive operational capacity (> 14,000 to 38,000 weekly movements).
   - High graph centrality (Betweenness 0.08–0.24, PageRank > 0.030).
2. **Tier 2: High Activity / Primary Connectors (11 airports: MAA, AMD, GOI, PNQ, COK, etc.)**
   - High regional volume (3,000 to 14,000 weekly movements).
   - Serves as critical regional interconnectors linking secondary regions to national hubs.
3. **Tier 1: Moderate / Regional Feeder Nodes (58 airports: PAT, IXR, BBI, IXC, TRV, etc.)**
   - Medium volume (200 to 3,000 weekly movements).
   - Connects state capitals and tier-2 economic hubs to metro nodes.
4. **Tier 0: Peripheral / Local Stations (33 airports: IXY, GAY, CDP, KUU, etc.)**
   - Low flight volume (10 to 200 weekly movements).
   - Typically 1 to 3 direct point-to-point connections under UDAN regional connectivity schemes.
