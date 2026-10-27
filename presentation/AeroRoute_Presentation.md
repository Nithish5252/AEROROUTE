# AeroRoute: Flight Route Network Intelligence Platform
## Final Project Presentation Deck (10 Slides)

---

### Slide 1: Title & Project Overview

#### Slide Content:
- **Title**: AeroRoute: Flight Route Network Intelligence Platform
- **Subtitle**: Big Data Architecture, Server-Side MapReduce, Graph Topology & Unsupervised Machine Learning
- **Presented by**: AeroRoute Engineering Team
- **Environment**: Localhost (Windows 11, MongoDB 4.4, Python 3.12, Streamlit, Plotly)
- **Execution Target**: Validated & Safe on 8 GB RAM Consumer Hardware
- **Core Status**: Complete & Verified (68/68 Automated Tests Passing)

#### Key Highlights:
- **100,000** Commercial Flight Operations Analyzed
- **4,129** Directed Air Corridors Mapped
- **322** Civil Airports Evaluated Across **14** Carriers
- **5** Native MongoDB JavaScript MapReduce Jobs Executed
- **4** Empirically Discovered Airport Operational Tiers

#### Speaker Notes:
> "Good morning, respected professors and evaluation committee members. Today, we present AeroRoute, an end-to-end Big Data analytical platform engineered to extract operational intelligence, network topology, and structural airport clusters from United States civil aviation flight records. Our project implements genuine server-side MongoDB MapReduce batch processing, complex network centrality algorithms, and unsupervised machine learning—all rigorously validated to operate under strict 8 GB RAM hardware limits without paid cloud services."

---

### Slide 2: Problem Statement & Objectives

#### Slide Content:
- **Industry Context**: The US air transportation network is a scale-free socio-technical system where delay propagation and traffic volume are heavily concentrated.
- **The Core Problem**:
  - Raw flight logs are massive, dirty, and computationally heavy.
  - Naive in-memory analytics exhaust laptop RAM.
  - Power-law traffic distributions distort classical machine learning models.
- **Primary Objectives**:
  1. Ingest, cleanse, and stage commercial flight records with zero data loss of operated flights.
  2. Implement genuine server-side JavaScript MapReduce jobs on MongoDB 4.4.
  3. Model a directed network graph to compute route concentration (HHI) and node centralities.
  4. Build a reproducible K-Means clustering model mitigating power-law skewness via $\log(1+x)$ transformations.
  5. Deliver a responsive 7-page Streamlit dashboard backed by precomputed analytical caches.
  6. Enforce strict 8 GB RAM compliance and 100% automated test coverage.

#### Speaker Notes:
> "Our motivation stems from addressing genuine Big Data challenges on standard developer hardware. Rather than running simple Pandas aggregations or relying on cloud credits, we designed an architecture that separates high-throughput database storage, server-side distributed MapReduce batch computing, network graph analytics, and machine learning segmentation into distinct, decoupled tiers."

---

### Slide 3: Dataset & System Architecture

#### Slide Content:
- **Data Source**: US Department of Transportation (US DOT) Bureau of Transportation Statistics (BTS).
- **Files**:
  - `flights.csv` (592 MB raw, 100,000 staged commercial flights)
  - `airports.csv` (322 airports with verified IATA codes & coordinates)
  - `airlines.csv` (14 operating carriers)
- **Decoupled Architecture**:
  ```
  [Raw DOT CSVs] 
         │ (Chunked Ingestion: 50k rows, 9.28 MB RAM)
         ▼
  [MongoDB 4.4 'flights'] 
         │ (Server-Side V8 JavaScript MapReduce)
         ▼
  [Precomputed MapReduce Collections] (mr_route_activity, mr_airport_connectivity)
         │ 
         ▼
  [NetworkX Graph & Scikit-Learn ML] (log1p transform, K-Means k=4, 2D PCA)
         │ 
         ▼
  [Streamlit 7-Page Dashboard] (@st.cache_data, Plotly Dark Aviation Theme)
  ```

#### Speaker Notes:
> "Here we see our decoupled system architecture. The pipeline begins with chunked ingestion reading 50,000 rows at a time, consuming less than 10 MB of RAM. The cleansed records are staged into MongoDB 4.4, where server-side MapReduce jobs transform 100,000 raw documents into indexed precomputed summary collections. Downstream analytics, NetworkX graph modeling, and machine learning models query only these precomputed collections, protecting the operational database and delivering sub-second response times in our Streamlit UI."

---

### Slide 4: Data Preprocessing & MongoDB Design

#### Slide Content:
- **Data Cleansing & QA Rules**:
  - Validated dates into ISO-8601 (`YYYY-MM-DD`).
  - Integer timestamps parsed into standard 24-hr `HH:MM` (midnight normalized to `00:00`).
  - Strict validation of 3-letter IATA codes against `airports.csv`.
  - Filtered circular hops ($A \to A$) and corrupt missing values.
  - Cohort separation: Preserved 2,389 cancelled flights for temporal audits while isolating 97,611 operated flights for route analysis.
  - **QA Result**: 20/20 data quality checks passed with 100% data integrity.
- **MongoDB Schema & B-Tree Indexing**:
  - Document modeling: Embedded origin/destination airport metadata inside flight documents.
  - Compound Indexes: `{route_key: 1, is_route_eligible: 1}` eliminating table scans.
  - Geospatial Index: `2dsphere` on `location` field for map coordinate queries.

#### Speaker Notes:
> "Data hygiene is the prerequisite for reliable analytics. Our preprocessor enforces explicit, documented rules. We separate flights into distinct cohorts: preserving cancelled flights for disruption auditing while ensuring only operated, fully resolved flights enter route analytics. In MongoDB, we implemented compound B-tree indexes and a 2dsphere geospatial index, ensuring all queries execute via index seeks without in-memory sorting."

---

### Slide 5: Genuine Server-Side MapReduce Implementation

#### Slide Content:
- **Mandatory Academic Requirement**: Real server-side JavaScript MapReduce executed inside MongoDB 4.4's V8 engine.
- **The 5 Production MapReduce Jobs**:
  1. **Job A (Directed Route Activity)**: Emits `this.route_key` $\to$ output `mr_route_activity` (4,129 docs).
  2. **Job B (Airport Outgoing Activity)**: Emits `this.origin.iata` $\to$ output `mr_airport_outgoing` (312 docs).
  3. **Job C (Airport Incoming Activity)**: Emits `this.destination.iata` $\to$ output `mr_airport_incoming` (312 docs).
  4. **Job D (Monthly Route Activity)**: Emits `YYYY-MM_RouteKey` $\to$ output `mr_monthly_route` (4,129 docs).
  5. **Job E (Airport Connectivity)**: Emits origin and destination arrays $\to$ output `mr_airport_connectivity` (312 docs).
- **Live JavaScript Code Snippet (Job A)**:
  ```javascript
  // Mapper
  function() { emit(this.route_key, 1); }
  // Reducer
  function(key, values) { return Array.sum(values); }
  ```
- **Architectural Critique**: In MongoDB 5.0+, MapReduce is deprecated due to JavaScript engine write locking; AeroRoute utilizes MongoDB 4.4 to satisfy academic criteria while architecting precomputed caches for modern performance.

#### Speaker Notes:
> "Slide 5 highlights a cornerstone of our technical implementation: genuine server-side MongoDB MapReduce. Rather than simulating MapReduce in Python or substituting it with aggregation pipelines, we wrote and executed native JavaScript mappers and reducers directly on the database engine. We implemented five dedicated jobs. For example, Job A aggregates all operated flights across 4,129 directed corridors. We also provide a candid architectural critique explaining why modern production systems migrate from V8 MapReduce to the native C++ aggregation pipeline."

---

### Slide 6: Network Topology & Centrality Analytics

#### Slide Content:
- **Graph Formulation**: Directed Graph $G = (V, E)$ where $|V| = 322$ airports and $|E| = 4,129$ directed edges.
- **Network Reciprocity**: **$89.1\%$** ($r = 0.891$). Over $89\%$ of all commercial flight routes operate as balanced two-way city pairs.
- **Route Concentration**: Herfindahl-Hirschman Index **$\text{HHI} = 0.00075$** ("Highly Competitive / Open Mesh").
- **Top Directed Corridors**:
  - `JFK->LAX` (238 flights) & `LAX->JFK` (238 flights)
  - `SFO->LAX` (212 flights) & `LAX->SFO` (210 flights)
  - `ORD->LGA` (202 flights) & `LGA->ORD` (202 flights)
- **Top Bridge Hubs (Betweenness Centrality)**:
  1. **ATL**: $C_B = 0.17741$ (Controls $17.7\%$ of all shortest paths)
  2. **DFW**: $C_B = 0.16233$ ($16.2\%$)
  3. **ORD**: $C_B = 0.15744$ ($15.7\%$)
  4. **DEN**: $C_B = 0.12906$ ($12.9\%$)

#### Speaker Notes:
> "Our network analytics reveal the structural topology of American airspace. The route network has an HHI of 0.00075, indicating an extremely competitive, distributed commercial route system rather than a monopoly corridor. Network reciprocity is 89.1%, confirming high scheduling symmetry. When evaluating Betweenness Centrality—which measures which airports act as essential transit bridges across shortest paths—we discover that just four mega-hubs: Atlanta, Dallas, Chicago, and Denver, control over 62% of all national shortest paths combined."

---

### Slide 7: Machine Learning Clustering & Evaluation

#### Slide Content:
- **Clustering Objective**: Unsupervised segmentation of 312 commercial airports using 7 operational and topological features.
- **Power-Law Skewness Mitigation**: Applied natural log transformation $y = \ln(1+x)$ (`log1p`) to flight counts and degrees (skewness reduced from $> 4.5$ to $< 0.8$), followed by `StandardScaler`.
- **Evaluation of Candidate $k$ ($2 \le k \le 8$)**:
  - $k=2$: Inertia = 957.21, Silhouette = 0.6035, DB = 0.6910
  - $k=3$: Inertia = 551.44, Silhouette = 0.5751, DB = 0.6472
  - **$k=4$**: **Inertia = 317.32, Silhouette = 0.5265, DB = 0.5451 (Global Minimum)**
  - $k=5$: Inertia = 216.88, Silhouette = 0.4988, DB = 0.6009
- **2D PCA Projection**:
  - PC1 explains **$82.9\%$** of variance; PC2 explains **$14.8\%$**
  - **Cumulative Explained Variance**: **$97.66\%$**
- **The 4 Discovered Operational Tiers**:
  - **Tier 0 (Regional Feeders)**: 152 airports ($48.7\%$, median flights: 34, dests: 2, betweenness: 0.0)
  - **Tier 1 (Regional Connections)**: 107 airports ($34.3\%$, median flights: 215, dests: 7, betweenness: 0.0)
  - **Tier 2 (Commercial Hubs)**: 49 airports ($15.7\%$, median flights: 1,980, dests: 43, betweenness: 0.0036)
  - **Tier 3 (National Super-Hubs)**: 4 airports ($1.3\%$: ATL, DFW, ORD, DEN; median flights: 9,238, dests: 150, betweenness: 0.1598)

#### Speaker Notes:
> "Slide 7 details our machine learning methodology. Because flight volumes follow power-law distributions, clustering raw numbers causes mega-hubs to act as Euclidean outliers. By applying a log1p transformation, we stabilized variance before standardizing features. We evaluated cluster counts from 2 to 8. While Silhouette score peaked at k=2, it only split the network into a coarse high-versus-low dichotomy. The Davies-Bouldin Index reached its global minimum at k=4 (0.5451), which cleanly isolated four operationally distinct tiers. Our 2D PCA projection captures 97.7% of total variance, mathematically proving the separation of these tiers."

---

### Slide 8: Interactive Dashboard Demonstration

#### Slide Content:
- **Technology**: Streamlit 1.39, Plotly 5.24, Custom Aviation CSS Theme (`#0B132B`, `#1C2541`, `#00B4D8`).
- **The 7 Live Interactive Pages**:
  1. **Executive Overview**: Real-time KPI cards, US Geo Airport Hub Map, Top 10 Corridors, Tier Share Donut.
  2. **Route Intelligence**: Case-insensitive corridor search, flight threshold slider, frequency histogram, bi-directional symmetry, CSV export.
  3. **Airport Network**: Centrality matrix (Betweenness vs. PageRank), in-degree vs out-degree comparison, state filters.
  4. **Temporal Patterns**: Friday/Monday peak departure volume, operated vs. cancelled breakdown.
  5. **MapReduce Laboratory**: Interactive selector for Jobs A–E, live JavaScript code inspection, raw BSON browser.
  6. **Airport Clustering**: 2D PCA projection plot, Elbow/Metrics curves, tier profile tabs, individual airport inspector.
  7. **Data Quality & System**: WiredTiger collection storage audit, 20/20 QA matrix, pipeline audit logs.

#### Speaker Notes:
> "Our presentation layer is an interactive 7-page Streamlit dashboard styled with a custom dark aviation theme. It avoids simulated data entirely. Users can search corridors with case-insensitive filters, inspect the US geographic scatter map, observe airport centrality quadrants, view the genuine JavaScript MapReduce code, explore the 2D PCA cluster space, and verify MongoDB storage metrics."

---

### Slide 9: Performance Profiling & Limitations

#### Slide Content:
- **8 GB RAM Benchmark Verification (`benchmark_performance.py`)**:
  - Chunked CSV Read (50,000 rows): **0.044s** | Peak RAM: **9.28 MB**
  - MongoDB Indexed Lookups (3 queries): **0.017s** | Peak RAM: **0.38 MB**
  - Feature Pipeline & K-Means: **0.944s** | Peak RAM: **2.79 MB**
  - Dashboard Cached Access: **0.415s** | Peak RAM: **10.22 MB**
  - **Maximum Peak RAM Observed**: **$10.22\text{ MB}$** (Budget: 2,048 MB $\implies > 6\text{ GB}$ headroom maintained).
- **Automated Testing Suite**: **68 / 68 automated Pytest unit and integration tests passing (100%)**.
- **Transparent Limitations**:
  - **No Passenger Demand Forecasting**: Tracks aircraft flight operations, not passenger manifests, ticket pricing, or airline revenue.
  - **Fixed Temporal Sample**: Historical 2015 operational baseline.
  - **Commercial Only**: Excludes general aviation, military, and unserved grass airfields.

#### Speaker Notes:
> "Performance profiling was conducted using Python's tracemalloc. On our 8 GB development machine, the peak memory footprint never exceeded 10.22 MB—well beneath our 2 GB software budget. We maintain 100% test passing rates across 68 automated Pytest tests. Furthermore, we maintain scientific honesty: AeroRoute analyzes aircraft movements and topology; it does not claim to predict passenger demand, seat load factors, or airline revenues."

---

### Slide 10: Conclusion & Future Roadmap

#### Slide Content:
- **Project Achievements**:
  - Engineered an end-to-end Big Data analytics and machine learning system.
  - Validated 100,000 flight records, 4,129 directed corridors, and 322 civil airports.
  - Successfully executed 5 native server-side JavaScript MapReduce jobs on MongoDB 4.4.
  - Identified the US civil aviation hierarchy via mathematically grounded K-Means clustering ($k=4$).
  - Delivered a sub-second, multi-page Streamlit visualization platform safe for 8 GB RAM.
- **Future Roadmap**:
  - **Real-Time Streaming**: Ingest live ADS-B flight transponder telemetry via Apache Kafka and MongoDB Change Streams.
  - **Aggregation Migration**: Upgrade legacy MapReduce jobs to MongoDB `$facet` aggregation pipelines.
  - **Graph Neural Networks (GNNs)**: Train Graph Convolutional Networks to predict delay propagation cascades across interconnected hubs.

#### Speaker Notes:
> "In conclusion, AeroRoute successfully bridges distributed database batch computing, network graph theory, and unsupervised machine learning in a production-ready application. We have satisfied all academic and engineering criteria with full test automation and verifiable reproducibility. Thank you for your time, and we look forward to your questions."
