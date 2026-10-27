# AeroRoute — Phase 1: Dataset Validation & Project Design
### Big Data Analytics & Machine Learning — College IA-3 Project

---

> [!IMPORTANT]
> **Scope Boundary**: This document covers Phase 1 only. Phase 2 (ingestion, ETL, ML modelling) begins only after you confirm the dataset validation results using the inspection script at the bottom of this document.

---

## Table of Contents
1. [Dataset Inventory — Verified Facts](#1-dataset-inventory--verified-facts)
2. [Column Catalogue & Data Types](#2-column-catalogue--data-types)
3. [Facts That Must Be Confirmed After Download](#3-facts-that-must-be-confirmed-after-download)
4. [Assumptions & Proposed Design Decisions](#4-assumptions--proposed-design-decisions)
5. [Dataset Suitability Assessment](#5-dataset-suitability-assessment)
6. [Proposed MongoDB Data Schema](#6-proposed-mongodb-data-schema)
7. [Route-Network Analysis Plan](#7-route-network-analysis-plan)
8. [MongoDB MapReduce Designs](#8-mongodb-mapreduce-designs)
9. [Airport Clustering Approach](#9-airport-clustering-approach)
10. [Dashboard Specification](#10-dashboard-specification)
11. [Storage & RAM Resource Assessment](#11-storage--ram-resource-assessment)
12. [Next Steps for Validating Downloaded Files](#12-next-steps-for-validating-downloaded-files)
13. [Chunk-Based Python Dataset Inspection Script](#13-chunk-based-python-dataset-inspection-script)

---

## 1. Dataset Inventory — Verified Facts

> **Source:** Kaggle Dataset Page — `https://www.kaggle.com/datasets/usdot/flight-delays`
> **Publisher:** U.S. Department of Transportation (DOT) — Bureau of Transportation Statistics (BTS)
> **License:** CC0: Public Domain (free to use, no attribution required)
> **Version:** 1 (published 2017-02-09, covers calendar year 2015)

### 1.1 Files in the Dataset

| File | Description | Rows (Verified) | Columns (Verified) | Approx. Uncompressed Size |
|---|---|---|---|---|
| `flights.csv` | One row = one domestic commercial flight in 2015 | **5,819,079** | **31** | ~600–700 MB |
| `airports.csv` | US airport metadata with coordinates | **322–323** | **7** | ~25 KB |
| `airlines.csv` | Airline carrier lookup table | **14** | **2** | ~350 bytes |
| *(zip archive)* | Compressed download from Kaggle | — | — | **~200 MB** |

### 1.2 Date Coverage
- **Verified:** Calendar year **2015 only** (Jan 1 – Dec 31, 2015).
- The `YEAR` column always equals `2015`. `MONTH` covers 1–12; `DAY` covers 1–31.
- **12 months** of full national domestic air-traffic data.

### 1.3 Airline Identifiers — Verified ✅
- `flights.csv` → column **`AIRLINE`** (2-letter IATA carrier code, e.g., `UA`, `AA`, `DL`)
- `airlines.csv` → columns **`IATA_CODE`** and **`AIRLINE`** (full name lookup)
- **14 major US carriers** are represented.

### 1.4 Airport Codes — Verified ✅
- `flights.csv` → columns **`ORIGIN_AIRPORT`** and **`DESTINATION_AIRPORT`** (3-letter IATA codes)
- `airports.csv` → **`IATA_CODE`** for joining

### 1.5 Airport Latitude & Longitude — Verified ✅
- `airports.csv` → columns **`LATITUDE`** and **`LONGITUDE`**
- Enables geospatial analysis and map-based route visualisation.

### 1.6 Missing-Value Risks — Known from Community Analysis

| Column(s) | Missing % | Root Cause | Risk Level |
|---|---|---|---|
| `YEAR`, `MONTH`, `DAY`, `AIRLINE`, `ORIGIN_AIRPORT`, `DESTINATION_AIRPORT`, `DISTANCE`, `CANCELLED`, `DIVERTED` | **0%** | Core mandatory BTS fields | ✅ None |
| `DEPARTURE_TIME`, `DEPARTURE_DELAY` | ~**1.48%** | Unrecorded departures (rare tracking gaps) | 🟡 Low |
| `TAXI_OUT`, `WHEELS_OFF` | ~**1.53%** | Same as above | 🟡 Low |
| `WHEELS_ON`, `TAXI_IN` | ~**1.59%** | Flight did not land at scheduled destination | 🟡 Low |
| `ARRIVAL_TIME`, `ARRIVAL_DELAY`, `AIR_TIME`, `ELAPSED_TIME` | ~**1.81%** | Cancelled or diverted flights | 🟡 Low |
| `TAIL_NUMBER` | ~**0.25%** | Missing aircraft registration | 🟢 Very Low |
| `CANCELLATION_REASON` | ~**98.45%** | **Structurally correct** — only populated if `CANCELLED=1` (~1.55% of flights) | ✅ Expected |
| `AIR_SYSTEM_DELAY`, `SECURITY_DELAY`, `AIRLINE_DELAY`, `LATE_AIRCRAFT_DELAY`, `WEATHER_DELAY` | ~**81.7%** | **Structurally correct** — only populated if arrival delay ≥ 15 min | ✅ Expected |

### 1.7 Duplicate-Record Risks
- BTS source data is generally free of redundant rows.
- Minor pipeline/extraction overlaps in Kaggle mirror versions **may** introduce duplicates.
- **Risk level: Low but must be confirmed.** A full duplicate check is included in the inspection script below.

---

## 2. Column Catalogue & Data Types

### 2.1 `flights.csv` — 31 Columns

| # | Column | Expected Python/Pandas dtype | MongoDB BSON Type | Notes |
|---|---|---|---|---|
| 1 | `YEAR` | `int16` | Int32 | Always 2015 |
| 2 | `MONTH` | `int8` | Int32 | 1–12 |
| 3 | `DAY` | `int8` | Int32 | 1–31 |
| 4 | `DAY_OF_WEEK` | `int8` | Int32 | 1=Mon … 7=Sun |
| 5 | `AIRLINE` | `object` (str) | String | 2-char IATA code |
| 6 | `FLIGHT_NUMBER` | `int16` | Int32 | — |
| 7 | `TAIL_NUMBER` | `object` (str) | String | ~0.25% null |
| 8 | `ORIGIN_AIRPORT` | `object` (str) | String | 3-char IATA |
| 9 | `DESTINATION_AIRPORT` | `object` (str) | String | 3-char IATA |
| 10 | `SCHEDULED_DEPARTURE` | `int16` | Int32 | HHMM integer (e.g. 1330) |
| 11 | `DEPARTURE_TIME` | `float32` | Double | Nullable; HHMM |
| 12 | `DEPARTURE_DELAY` | `float32` | Double | Minutes; negative=early |
| 13 | `TAXI_OUT` | `float32` | Double | Minutes |
| 14 | `WHEELS_OFF` | `float32` | Double | HHMM |
| 15 | `SCHEDULED_TIME` | `float32` | Double | Planned duration (min) |
| 16 | `ELAPSED_TIME` | `float32` | Double | Actual duration (min) |
| 17 | `AIR_TIME` | `float32` | Double | Airborne minutes |
| 18 | `DISTANCE` | `int16` | Int32 | Miles |
| 19 | `WHEELS_ON` | `float32` | Double | HHMM |
| 20 | `TAXI_IN` | `float32` | Double | Minutes |
| 21 | `SCHEDULED_ARRIVAL` | `int16` | Int32 | HHMM |
| 22 | `ARRIVAL_TIME` | `float32` | Double | HHMM; nullable |
| 23 | `ARRIVAL_DELAY` | `float32` | Double | Minutes; negative=early |
| 24 | `DIVERTED` | `int8` | Int32 | 0/1 flag |
| 25 | `CANCELLED` | `int8` | Int32 | 0/1 flag |
| 26 | `CANCELLATION_REASON` | `object` (str) | String | A/B/C/D or null |
| 27 | `AIR_SYSTEM_DELAY` | `float32` | Double | Minutes or null |
| 28 | `SECURITY_DELAY` | `float32` | Double | Minutes or null |
| 29 | `AIRLINE_DELAY` | `float32` | Double | Minutes or null |
| 30 | `LATE_AIRCRAFT_DELAY` | `float32` | Double | Minutes or null |
| 31 | `WEATHER_DELAY` | `float32` | Double | Minutes or null |

### 2.2 `airports.csv` — 7 Columns

| # | Column | dtype | Notes |
|---|---|---|---|
| 1 | `IATA_CODE` | str | 3-char; join key to flights |
| 2 | `AIRPORT` | str | Full name |
| 3 | `CITY` | str | |
| 4 | `STATE` | str | 2-char US state code |
| 5 | `COUNTRY` | str | Always "USA" |
| 6 | `LATITUDE` | float64 | Decimal degrees |
| 7 | `LONGITUDE` | float64 | Decimal degrees |

### 2.3 `airlines.csv` — 2 Columns

| # | Column | dtype | Notes |
|---|---|---|---|
| 1 | `IATA_CODE` | str | 2-char; join key to flights |
| 2 | `AIRLINE` | str | Full carrier name |

---

## 3. Facts That Must Be Confirmed After Download

> [!WARNING]
> The following items are **not verifiable** from the Kaggle public page alone. Run the inspection script in Section 13 before proceeding.

| # | Item to Confirm | How to Confirm |
|---|---|---|
| 3.1 | Exact row count of `flights.csv` (expected: 5,819,079) | `wc -l flights.csv` or script |
| 3.2 | Exact column count = 31 | `head -1 flights.csv` |
| 3.3 | Any fully-duplicate rows exist | `df.duplicated().sum()` via chunk script |
| 3.4 | `ORIGIN_AIRPORT` / `DESTINATION_AIRPORT` have any non-IATA numeric airport codes (BTS sometimes uses FAA codes for small airports) | `df['ORIGIN_AIRPORT'].str.isnumeric().sum()` |
| 3.5 | `airports.csv` covers all IATA codes appearing in flights (left-join orphans) | Script section: orphan codes |
| 3.6 | `airlines.csv` covers all AIRLINE codes in flights | Similar join check |
| 3.7 | Actual null counts match published community figures | Null report in script |
| 3.8 | `LATITUDE` / `LONGITUDE` in airports.csv have no nulls | `airports_df.isnull().sum()` |
| 3.9 | Date range truly spans Jan 1 – Dec 31, 2015 | `MONTH` min/max, row count per month |
| 3.10 | `DISTANCE` field unit is miles (not km) | Cross-check LAX→JFK: expected ~2,475 miles |

---

## 4. Assumptions & Proposed Design Decisions

> [!NOTE]
> These are **design decisions**, not facts. They will be revisited after dataset validation.

| # | Assumption / Decision | Rationale |
|---|---|---|
| 4.1 | Use **directed graph** model for routes (ORD→LAX ≠ LAX→ORD) | BTS data has explicit origin/destination directionality |
| 4.2 | Filter out `CANCELLED=1` flights from route analysis | Cancelled flights never operated; distorts frequency counts |
| 4.3 | Filter out `DIVERTED=1` flights from arrival-delay analysis | Arrived at a different airport; arrival metrics are meaningless |
| 4.4 | `CANCELLATION_REASON` null → treat as "N/A" (not missing) | Structurally expected; imputation would be wrong |
| 4.5 | Delay-breakdown nulls → treat as 0 for aggregation | Null means no delay ≥ 15 min; substituting 0 is semantically correct |
| 4.6 | MongoDB collection `flights` will hold denormalised documents (airline name and airport lat/lon embedded) | Avoids repeated $lookup at query time; acceptable write-once pattern |
| 4.7 | Chunk size for Python ingestion = **50,000 rows** | Keeps peak RAM under 300 MB during ETL |
| 4.8 | MapReduce results will be stored in separate **output collections** | Allows incremental re-computation without touching raw data |
| 4.9 | K-Means clustering with **k=5** as a starting estimate | Rule-of-thumb for ~322 airports; to be tuned with elbow method |
| 4.10 | No latitude/longitude for airports with numeric IATA codes | Fallback: drop or use state centroid |

---

## 5. Dataset Suitability Assessment

### ✅ Supported Analyses

| Analysis Type | Available Fields | Verdict |
|---|---|---|
| **Route Analysis** | `ORIGIN_AIRPORT`, `DESTINATION_AIRPORT`, `DISTANCE`, `FLIGHT_NUMBER`, `AIRLINE` | ✅ Fully Supported |
| **Airport Connectivity** | All route fields + `airports.csv` with lat/lon | ✅ Fully Supported |
| **Temporal Analysis** | `YEAR`, `MONTH`, `DAY`, `DAY_OF_WEEK`, `SCHEDULED_DEPARTURE` | ✅ Fully Supported |
| **Network Analysis** | Route pairs allow in-degree / out-degree / betweenness via graph construction | ✅ Fully Supported |
| **Airport Clustering** | Lat/lon + derived metrics (traffic volume, avg delay, connectivity) | ✅ Fully Supported |
| **Delay Classification** | `DEPARTURE_DELAY`, `ARRIVAL_DELAY`, 5 delay breakdown columns | ✅ Fully Supported |
| **Airline Performance** | `AIRLINE` linked to delay and cancellation data | ✅ Fully Supported |

### ⚠️ Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| **Single year (2015)** | Cannot analyse YoY trends | Focus on monthly/seasonal patterns within 2015 |
| **Domestic US only** | No international routes | Scope project accordingly; state so in report |
| **No passenger volume** | Route traffic = flight count only, not seats/load factor | Use flight count as proxy; note caveat |
| **HHMM integer time format** | Requires custom parsing | Handled in ETL transform |
| **~322 airports max** | Not every small regional airport present | Sufficient for hub/spoke network analysis |

### Overall Verdict: 🟢 EXCELLENT

> The dataset is **highly suitable** for all five proposed analytical pillars. At 5.8 M rows spanning a full calendar year with lat/lon, delay breakdowns, and complete origin-destination pairs, it is one of the best open aviation datasets available for a college Big Data project.

---

## 6. Proposed MongoDB Data Schema

### 6.1 Database: `aeroroutedb`

#### Collection 1: `flights` (raw + enriched, ~5.82 M documents)

```javascript
// Sample document after ETL enrichment
{
  "_id": ObjectId("..."),
  "flight_date": ISODate("2015-01-15T00:00:00Z"),  // constructed from YEAR+MONTH+DAY
  "year": 2015,
  "month": 1,
  "day": 15,
  "day_of_week": 4,
  "airline_code": "AA",
  "airline_name": "American Airlines Inc.",        // denormalised from airlines.csv
  "flight_number": 1,
  "tail_number": "N787AA",
  "origin": {
    "iata": "LAX",
    "name": "Los Angeles International Airport",   // denormalised from airports.csv
    "city": "Los Angeles",
    "state": "CA",
    "lat": 33.9425,
    "lon": -118.4081
  },
  "destination": {
    "iata": "JFK",
    "name": "John F Kennedy International Airport",
    "city": "New York",
    "state": "NY",
    "lat": 40.6398,
    "lon": -73.7789
  },
  "route_key": "LAX->JFK",                         // computed field for grouping
  "scheduled_departure": 800,                       // HHMM integer kept as-is
  "departure_time": 810.0,
  "departure_delay": 10.0,
  "taxi_out": 14.0,
  "wheels_off": 824.0,
  "scheduled_time": 319.0,
  "elapsed_time": 320.0,
  "air_time": 298.0,
  "distance": 2475,
  "wheels_on": 1342.0,
  "taxi_in": 8.0,
  "scheduled_arrival": 1339,
  "arrival_time": 1350.0,
  "arrival_delay": 11.0,
  "diverted": 0,
  "cancelled": 0,
  "cancellation_reason": null,
  "delay_breakdown": {
    "air_system": 0.0,
    "security": 0.0,
    "airline": 11.0,
    "late_aircraft": 0.0,
    "weather": 0.0
  }
}
```

**Indexes on `flights`:**
```javascript
db.flights.createIndex({ "route_key": 1 })
db.flights.createIndex({ "origin.iata": 1 })
db.flights.createIndex({ "destination.iata": 1 })
db.flights.createIndex({ "airline_code": 1 })
db.flights.createIndex({ "month": 1 })
db.flights.createIndex({ "cancelled": 1 })
db.flights.createIndex({ "origin.iata": 1, "destination.iata": 1, "month": 1 })
db.flights.createIndex({ "origin.lat": 1, "origin.lon": 1 })  // for geospatial
```

---

#### Collection 2: `airports` (~322 documents)

```javascript
{
  "_id": "LAX",                          // IATA_CODE as natural _id
  "name": "Los Angeles International Airport",
  "city": "Los Angeles",
  "state": "CA",
  "country": "USA",
  "location": {
    "type": "Point",
    "coordinates": [-118.4081, 33.9425] // GeoJSON [lon, lat]
  },
  // Derived fields populated after MapReduce (Phase 2)
  "metrics": {
    "total_departures": null,
    "total_arrivals": null,
    "out_degree": null,
    "in_degree": null,
    "avg_departure_delay": null,
    "avg_arrival_delay": null,
    "cluster_id": null
  }
}
```

---

#### Collection 3: `airlines` (14 documents)

```javascript
{
  "_id": "AA",
  "name": "American Airlines Inc.",
  // Derived after Phase 2
  "metrics": {
    "total_flights": null,
    "cancellation_rate": null,
    "avg_departure_delay": null,
    "avg_arrival_delay": null,
    "on_time_rate": null
  }
}
```

---

#### Output Collections (populated by MapReduce — Section 8)

| Collection | Purpose |
|---|---|
| `mr_route_activity` | Directed route frequency, avg delay, avg distance |
| `mr_airport_outgoing` | Per-airport departure aggregates |
| `mr_airport_incoming` | Per-airport arrival aggregates |
| `mr_monthly_route` | Route activity broken down by month |
| `mr_airport_connectivity` | In-degree, out-degree, connectivity summary |
| `ml_cluster_results` | K-Means cluster labels per airport |

---

## 7. Route-Network Analysis Plan

### Analytical Pillars

```
flights.csv  ──►  MongoDB `flights` collection
                        │
           ┌────────────┼────────────┬──────────────────┐
           ▼            ▼            ▼                  ▼
    Route Analysis  Airport     Temporal           Network
    (MapReduce)    Connectivity  Analysis           Graph
    ─────────────  ──────────  ──────────         ─────────
    Busiest routes  Hub airports Monthly trends   In/Out degree
    Avg delay/route In/Out degree Seasonal patterns Betweenness
    Route distance  Cluster by   Day-of-week      Hub detection
    Cancellations   traffic+geo  patterns
```

### Analysis Steps

| Step | Operation | Output |
|---|---|---|
| **A** | Group by `route_key` → count flights, avg delays, avg distance | `mr_route_activity` |
| **B** | Group by `origin.iata` → count departures, distinct destinations | `mr_airport_outgoing` |
| **C** | Group by `destination.iata` → count arrivals, distinct origins | `mr_airport_incoming` |
| **D** | Group by `route_key` + `month` → monthly frequency | `mr_monthly_route` |
| **E** | Join A+B+C → compute in-degree, out-degree, total connectivity | `mr_airport_connectivity` |
| **F** | Join E with `airports.lat/lon` → feature matrix for K-Means | Input to clustering |
| **G** | K-Means on feature matrix → cluster labels | `ml_cluster_results` |
| **H** | Merge cluster labels back to `airports.metrics.cluster_id` | Dashboard display |

---

## 8. MongoDB MapReduce Designs

> [!NOTE]
> MongoDB's built-in `mapReduce()` command is used here as required by the project. In production, MongoDB Aggregation Pipeline is preferred for performance on modern versions (≥ 4.2).

### 8.1 Directed Route Activity

**Goal:** For each directed route (origin → destination), compute: total flight count, average departure delay, average arrival delay, average distance, cancellation count.

```javascript
// MapReduce 1: Directed Route Activity
// Output collection: mr_route_activity

var mapRouteActivity = function() {
    var routeKey = this.origin.iata + "->" + this.destination.iata;
    emit(routeKey, {
        flight_count: 1,
        dep_delay_sum: (this.departure_delay && this.cancelled === 0) ? this.departure_delay : 0,
        arr_delay_sum: (this.arrival_delay && this.cancelled === 0)   ? this.arrival_delay  : 0,
        distance: this.distance,
        cancelled_count: this.cancelled,
        valid_dep: (this.cancelled === 0 && this.departure_delay != null) ? 1 : 0,
        valid_arr: (this.cancelled === 0 && this.arrival_delay  != null) ? 1 : 0
    });
};

var reduceRouteActivity = function(key, values) {
    var result = {
        flight_count: 0,
        dep_delay_sum: 0,
        arr_delay_sum: 0,
        distance: 0,
        cancelled_count: 0,
        valid_dep: 0,
        valid_arr: 0
    };
    values.forEach(function(v) {
        result.flight_count    += v.flight_count;
        result.dep_delay_sum   += v.dep_delay_sum;
        result.arr_delay_sum   += v.arr_delay_sum;
        result.distance         = v.distance;        // same for a route
        result.cancelled_count += v.cancelled_count;
        result.valid_dep       += v.valid_dep;
        result.valid_arr       += v.valid_arr;
    });
    return result;
};

var finalizeRouteActivity = function(key, reducedVal) {
    reducedVal.avg_dep_delay = reducedVal.valid_dep > 0
        ? reducedVal.dep_delay_sum / reducedVal.valid_dep : null;
    reducedVal.avg_arr_delay = reducedVal.valid_arr > 0
        ? reducedVal.arr_delay_sum / reducedVal.valid_arr : null;
    reducedVal.cancellation_rate = reducedVal.flight_count > 0
        ? reducedVal.cancelled_count / reducedVal.flight_count : 0;
    var parts = key.split("->");
    reducedVal.origin      = parts[0];
    reducedVal.destination = parts[1];
    return reducedVal;
};

db.flights.mapReduce(
    mapRouteActivity,
    reduceRouteActivity,
    {
        out:      { replace: "mr_route_activity" },
        finalize: finalizeRouteActivity,
        query:    {}          // all documents
    }
);

// Index the output
db.mr_route_activity.createIndex({ "value.origin": 1 });
db.mr_route_activity.createIndex({ "value.flight_count": -1 });
```

---

### 8.2 Airport Outgoing Activity

**Goal:** Per airport, count all departures, compute average departure delay, list distinct destination airports (out-degree), track cancellations per airline.

```javascript
// MapReduce 2: Airport Outgoing Activity
// Output collection: mr_airport_outgoing

var mapOutgoing = function() {
    emit(this.origin.iata, {
        departures: 1,
        dep_delay_sum: (this.departure_delay != null && this.cancelled === 0)
                       ? this.departure_delay : 0,
        valid_dep: (this.departure_delay != null && this.cancelled === 0) ? 1 : 0,
        cancelled: this.cancelled,
        destinations: [this.destination.iata]
    });
};

var reduceOutgoing = function(key, values) {
    var result = {
        departures: 0,
        dep_delay_sum: 0,
        valid_dep: 0,
        cancelled: 0,
        destinations: []
    };
    values.forEach(function(v) {
        result.departures    += v.departures;
        result.dep_delay_sum += v.dep_delay_sum;
        result.valid_dep     += v.valid_dep;
        result.cancelled     += v.cancelled;
        // Collect destinations (will deduplicate in finalize)
        v.destinations.forEach(function(d) {
            if (result.destinations.indexOf(d) === -1) {
                result.destinations.push(d);
            }
        });
    });
    return result;
};

var finalizeOutgoing = function(key, reducedVal) {
    reducedVal.avg_dep_delay = reducedVal.valid_dep > 0
        ? reducedVal.dep_delay_sum / reducedVal.valid_dep : null;
    reducedVal.out_degree    = reducedVal.destinations.length;
    reducedVal.cancel_rate   = reducedVal.departures > 0
        ? reducedVal.cancelled / reducedVal.departures : 0;
    return reducedVal;
};

db.flights.mapReduce(
    mapOutgoing,
    reduceOutgoing,
    {
        out:      { replace: "mr_airport_outgoing" },
        finalize: finalizeOutgoing
    }
);
```

---

### 8.3 Airport Incoming Activity

**Goal:** Per airport, count all arrivals, compute average arrival delay, list distinct origin airports (in-degree).

```javascript
// MapReduce 3: Airport Incoming Activity
// Output collection: mr_airport_incoming

var mapIncoming = function() {
    if (this.cancelled === 0) {                       // only count actually-operated arrivals
        emit(this.destination.iata, {
            arrivals: 1,
            arr_delay_sum: this.arrival_delay != null ? this.arrival_delay : 0,
            valid_arr: this.arrival_delay != null ? 1 : 0,
            origins: [this.origin.iata]
        });
    }
};

var reduceIncoming = function(key, values) {
    var result = {
        arrivals: 0,
        arr_delay_sum: 0,
        valid_arr: 0,
        origins: []
    };
    values.forEach(function(v) {
        result.arrivals     += v.arrivals;
        result.arr_delay_sum += v.arr_delay_sum;
        result.valid_arr    += v.valid_arr;
        v.origins.forEach(function(o) {
            if (result.origins.indexOf(o) === -1) {
                result.origins.push(o);
            }
        });
    });
    return result;
};

var finalizeIncoming = function(key, reducedVal) {
    reducedVal.avg_arr_delay = reducedVal.valid_arr > 0
        ? reducedVal.arr_delay_sum / reducedVal.valid_arr : null;
    reducedVal.in_degree = reducedVal.origins.length;
    return reducedVal;
};

db.flights.mapReduce(
    mapIncoming,
    reduceIncoming,
    {
        out:      { replace: "mr_airport_incoming" },
        finalize: finalizeIncoming
    }
);
```

---

### 8.4 Monthly Route Activity

**Goal:** For each (route, month) pair, count flights and compute average delays — enables seasonal trend analysis.

```javascript
// MapReduce 4: Monthly Route Activity
// Output collection: mr_monthly_route
// Composite key: "ORIGIN->DEST::MONTH"

var mapMonthlyRoute = function() {
    if (this.cancelled === 0) {
        var compositeKey = this.origin.iata + "->" + this.destination.iata
                           + "::" + this.month;
        emit(compositeKey, {
            flight_count: 1,
            dep_delay_sum: this.departure_delay != null ? this.departure_delay : 0,
            arr_delay_sum: this.arrival_delay   != null ? this.arrival_delay   : 0,
            valid_dep: this.departure_delay != null ? 1 : 0,
            valid_arr: this.arrival_delay   != null ? 1 : 0,
            origin:      this.origin.iata,
            destination: this.destination.iata,
            month:       this.month
        });
    }
};

var reduceMonthlyRoute = function(key, values) {
    var result = {
        flight_count: 0,
        dep_delay_sum: 0,
        arr_delay_sum: 0,
        valid_dep: 0,
        valid_arr: 0,
        origin: values[0].origin,
        destination: values[0].destination,
        month: values[0].month
    };
    values.forEach(function(v) {
        result.flight_count  += v.flight_count;
        result.dep_delay_sum += v.dep_delay_sum;
        result.arr_delay_sum += v.arr_delay_sum;
        result.valid_dep     += v.valid_dep;
        result.valid_arr     += v.valid_arr;
    });
    return result;
};

var finalizeMonthlyRoute = function(key, reducedVal) {
    reducedVal.avg_dep_delay = reducedVal.valid_dep > 0
        ? reducedVal.dep_delay_sum / reducedVal.valid_dep : null;
    reducedVal.avg_arr_delay = reducedVal.valid_arr > 0
        ? reducedVal.arr_delay_sum / reducedVal.valid_arr : null;
    return reducedVal;
};

db.flights.mapReduce(
    mapMonthlyRoute,
    reduceMonthlyRoute,
    {
        out:      { replace: "mr_monthly_route" },
        finalize: finalizeMonthlyRoute
    }
);
```

---

### 8.5 Airport Connectivity Summary

**Goal:** Combine outgoing + incoming results per airport into a single connectivity document showing total traffic, in-degree, out-degree, and a connectivity score.

```javascript
// MapReduce 5: Airport Connectivity Summary
// This runs AFTER MR2 and MR3 have populated their output collections.
// Source: mr_airport_outgoing  (using out + in counts merged via finalize pass)
// Output collection: mr_airport_connectivity

// Step A — emit from outgoing results
var mapConnectivityOut = function() {
    emit(this._id, {
        type: "out",
        departures: this.value.departures,
        out_degree: this.value.out_degree,
        avg_dep_delay: this.value.avg_dep_delay,
        cancel_rate: this.value.cancel_rate,
        arrivals: 0,
        in_degree: 0,
        avg_arr_delay: null
    });
};

// Step B — separately emit from incoming results
var mapConnectivityIn = function() {
    emit(this._id, {
        type: "in",
        arrivals: this.value.arrivals,
        in_degree: this.value.in_degree,
        avg_arr_delay: this.value.avg_arr_delay,
        departures: 0,
        out_degree: 0,
        avg_dep_delay: null,
        cancel_rate: 0
    });
};

var reduceConnectivity = function(key, values) {
    var result = {
        departures: 0, out_degree: 0, avg_dep_delay: null, cancel_rate: 0,
        arrivals: 0,   in_degree: 0,  avg_arr_delay: null
    };
    values.forEach(function(v) {
        result.departures   += v.departures;
        result.out_degree   += v.out_degree;
        result.arrivals     += v.arrivals;
        result.in_degree    += v.in_degree;
        if (v.avg_dep_delay != null) result.avg_dep_delay = v.avg_dep_delay;
        if (v.avg_arr_delay != null) result.avg_arr_delay = v.avg_arr_delay;
        result.cancel_rate  += v.cancel_rate;
    });
    return result;
};

var finalizeConnectivity = function(key, reducedVal) {
    reducedVal.total_flights = reducedVal.departures + reducedVal.arrivals;
    // Simple connectivity score: total traffic normalised by degree
    var degree = reducedVal.in_degree + reducedVal.out_degree;
    reducedVal.connectivity_score = degree > 0
        ? reducedVal.total_flights / degree : 0;
    return reducedVal;
};

// Run MR on outgoing collection
db.mr_airport_outgoing.mapReduce(
    mapConnectivityOut,
    reduceConnectivity,
    { out: { replace: "mr_airport_connectivity" }, finalize: finalizeConnectivity }
);

// Run MR on incoming collection — MERGE into same output
db.mr_airport_incoming.mapReduce(
    mapConnectivityIn,
    reduceConnectivity,
    { out: { merge: "mr_airport_connectivity" }, finalize: finalizeConnectivity }
);

// Index for dashboard queries
db.mr_airport_connectivity.createIndex({ "value.total_flights": -1 });
db.mr_airport_connectivity.createIndex({ "value.out_degree": -1 });
```

---

## 9. Airport Clustering Approach

### Goal
Group the ~322 US airports into **meaningful clusters** based on traffic volume, connectivity, delay profile, and geographic location — revealing hub, mid-tier, regional, and spoke categories.

### Feature Matrix (per airport, post-MapReduce)

| Feature | Source | Reason |
|---|---|---|
| `total_departures` | `mr_airport_outgoing` | Traffic volume |
| `total_arrivals` | `mr_airport_incoming` | Traffic volume |
| `out_degree` | `mr_airport_outgoing` | Route diversity (hub indicator) |
| `in_degree` | `mr_airport_incoming` | Route diversity |
| `avg_departure_delay` | `mr_airport_outgoing` | Operational efficiency |
| `avg_arrival_delay` | `mr_airport_incoming` | Operational efficiency |
| `cancellation_rate` | `mr_airport_outgoing` | Reliability |
| `latitude` | `airports.csv` | Geographic positioning |
| `longitude` | `airports.csv` | Geographic positioning |

### Algorithm: K-Means (scikit-learn)

```
Step 1  →  Extract feature matrix from MongoDB  (pymongo query → DataFrame)
Step 2  →  StandardScaler normalisation          (removes scale dominance of traffic volume)
Step 3  →  Elbow Method (k = 2 to 12)           (plot inertia to select optimal k)
Step 4  →  K-Means fit with k=5 (initial)        (adjust after elbow plot)
Step 5  →  Assign cluster labels to airports     (write back to MongoDB airports.metrics.cluster_id)
Step 6  →  Profile each cluster                  (mean features per cluster)
Step 7  →  Visualise on US map                   (matplotlib + Folium/Plotly)
```

### Expected Cluster Profiles

| Cluster ID | Expected Profile | Example Airports |
|---|---|---|
| 0 | **Mega Hubs** — extreme volume + high degree | ATL, ORD, LAX, DFW, DEN |
| 1 | **Major Hubs** — high volume, moderate delay | JFK, SFO, SEA, MIA, BOS |
| 2 | **Mid-Tier Regional** — moderate traffic | MSP, PDX, RDU, STL |
| 3 | **Small Spoke** — low volume, few routes | most regional airports |
| 4 | **Delay-Prone Outliers** — moderate traffic but high delay | airports in weather-prone areas |

### Validation Metrics
- **Silhouette Score** — should be > 0.35 for good separation
- **Davies-Bouldin Index** — lower is better
- **Visual inspection** on US map

---

## 10. Dashboard Specification

### 10.1 Dashboard Modules

| Module | Charts | Data Source |
|---|---|---|
| **Overview KPIs** | Total flights, cancellation rate, avg delay, top airline | `flights` collection count queries |
| **Route Heat Map** | Top 50 routes overlaid on US map, line width = frequency | `mr_route_activity` + `airports` lat/lon |
| **Busiest Routes** | Horizontal bar chart: Top 20 routes by flight count | `mr_route_activity` sorted by flight_count |
| **Delay Analysis** | Stacked bar: delay types per airline | `flights` delay_breakdown aggregation |
| **Monthly Trends** | Line chart: flights + avg delay per month | `mr_monthly_route` grouped by month |
| **Day-of-Week Patterns** | Radar/polar chart: avg delay by day_of_week | Aggregation on `flights` |
| **Airport Connectivity** | Network graph (D3.js / NetworkX): nodes = airports, edges = routes | `mr_airport_connectivity` + `mr_route_activity` |
| **Airport Clusters** | US map with colour-coded cluster membership | `airports` + `ml_cluster_results` |
| **Airline Scorecard** | Table: on-time rate, cancel rate, avg delay per carrier | `mr_airport_outgoing` + `airlines` |
| **Hub Ranking** | Bar chart: Top 20 airports by in+out degree | `mr_airport_connectivity` sorted by out_degree |

### 10.2 Recommended Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Backend API | Python + Flask | Lightweight; familiar |
| MongoDB Driver | PyMongo | Native Python driver |
| Data Wrangling | Pandas | Post-MapReduce post-processing |
| ML | scikit-learn | K-Means, scaling, metrics |
| Charts | Plotly / Chart.js | Interactive, no server render |
| Map | Folium or Plotly Geo | Free, works offline |
| Frontend | HTML + Vanilla JS or Streamlit | Keep it simple for IA-3 |

---

## 11. Storage & RAM Resource Assessment

### 11.1 Raw File Sizes

| Item | Size |
|---|---|
| Compressed Kaggle ZIP | ~200 MB |
| `flights.csv` (uncompressed) | ~600–700 MB |
| `airports.csv` | ~25 KB |
| `airlines.csv` | ~350 bytes |
| **Total disk for raw files** | **~700 MB** |

### 11.2 MongoDB Storage Estimate

| Collection | Documents | Avg Doc Size | Estimated Storage |
|---|---|---|---|
| `flights` (denormalised) | 5,819,079 | ~900 bytes | **~5.2 GB** |
| `airports` | 322 | ~400 bytes | < 1 MB |
| `airlines` | 14 | ~200 bytes | < 1 MB |
| `mr_route_activity` | ~5,000–7,000 | ~300 bytes | ~2 MB |
| `mr_airport_outgoing` | ~322 | ~500 bytes | < 1 MB |
| `mr_airport_incoming` | ~322 | ~500 bytes | < 1 MB |
| `mr_monthly_route` | ~50,000 | ~300 bytes | ~15 MB |
| `mr_airport_connectivity` | ~322 | ~600 bytes | < 1 MB |
| **MongoDB WiredTiger (with indexes)** | — | — | **~6–7 GB total** |

### 11.3 RAM Usage Assessment (8 GB System)

| Process | Peak RAM |
|---|---|
| OS + background | ~1.5 GB |
| MongoDB (WiredTiger cache default = 50% of RAM) | ~4 GB (adjustable) |
| Python ETL script (chunk=50,000 rows) | ~250–300 MB |
| Python ML/analysis script | ~500 MB – 1 GB |
| Dashboard/Flask | ~100–200 MB |
| **Total Peak** | **~6.5–7.0 GB** |

> [!WARNING]
> **8 GB RAM is tight but workable.** Key mitigations:
> - Set `wiredTigerCacheSizeGB: 2.5` in `mongod.conf` to leave more RAM for Python.
> - Always use chunk-based CSV reading (never `pd.read_csv()` without `chunksize`).
> - Use `projection` in PyMongo queries to return only needed fields.
> - Close Pandas DataFrames with `del df; gc.collect()` after use.
> - Do not run ETL and MapReduce simultaneously.

---

## 12. Next Steps for Validating Downloaded Files

> [!IMPORTANT]
> Do these steps **in order** before starting Phase 2.

| Step | Action | Command / Tool |
|---|---|---|
| **12.1** | Download the Kaggle ZIP (requires Kaggle login or `kaggle datasets download -d usdot/flight-delays`) | Kaggle CLI or browser |
| **12.2** | Unzip to your project folder | `unzip flight-delays.zip` |
| **12.3** | Confirm 3 files exist: `flights.csv`, `airports.csv`, `airlines.csv` | `dir` / `ls` |
| **12.4** | Count lines in `flights.csv` (expect ~5,819,080 including header) | `(Get-Content flights.csv).Count` (PowerShell) |
| **12.5** | Print header of `flights.csv` — confirm 31 column names | `head -1 flights.csv` or PowerShell |
| **12.6** | Run the Python inspection script (Section 13) | `python inspect_dataset.py` |
| **12.7** | Review script output — flag any anomalies vs. expected values in this document | Manual review |
| **12.8** | Check for numeric airport codes in ORIGIN_AIRPORT (non-IATA) | Script output section |
| **12.9** | Confirm airports.csv covers all IATA codes in flights | Script orphan check section |
| **12.10** | Report findings back — then Phase 2 begins | Team review |

---

## 13. Chunk-Based Python Dataset Inspection Script

> **Purpose:** Safely inspect all three CSV files without loading any full file into memory. Works on any machine with 2 GB+ RAM.

```python
# ============================================================
# AeroRoute Phase 1 — Dataset Inspection Script
# File: inspect_dataset.py
# Usage: python inspect_dataset.py
# Requirements: pandas >= 1.3, tqdm (optional)
# ============================================================

import os
import csv
import sys
import gc
import hashlib
from collections import Counter, defaultdict

import pandas as pd

# ── Configuration ────────────────────────────────────────────
FLIGHTS_CSV  = "flights.csv"
AIRPORTS_CSV = "airports.csv"
AIRLINES_CSV = "airlines.csv"
CHUNK_SIZE   = 50_000          # rows per chunk — safe for 8 GB RAM

# ── Utility ──────────────────────────────────────────────────
def separator(title):
    width = 65
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)

def check_file_exists(path):
    if not os.path.exists(path):
        print(f"  [ERROR] File not found: {path}")
        return False
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  [OK] {path}  |  {size_mb:.1f} MB")
    return True

# ════════════════════════════════════════════════════════════
# SECTION 0 — File Presence and Sizes
# ════════════════════════════════════════════════════════════
separator("SECTION 0 — File Presence & Sizes")
all_present = all([
    check_file_exists(FLIGHTS_CSV),
    check_file_exists(AIRPORTS_CSV),
    check_file_exists(AIRLINES_CSV),
])
if not all_present:
    print("\n[FATAL] One or more required files are missing. Exiting.")
    sys.exit(1)

# ════════════════════════════════════════════════════════════
# SECTION 1 — airports.csv  (small file — full load is safe)
# ════════════════════════════════════════════════════════════
separator("SECTION 1 — airports.csv Analysis")
airports_df = pd.read_csv(AIRPORTS_CSV, dtype=str)
print(f"  Row count       : {len(airports_df)}")
print(f"  Column count    : {len(airports_df.columns)}")
print(f"  Columns         : {list(airports_df.columns)}")
print(f"\n  Null counts:")
print(airports_df.isnull().sum().to_string(header=False))
print(f"\n  Sample rows:")
print(airports_df.head(3).to_string(index=False))

# Collect known airport IATA codes
known_airport_codes = set(airports_df["IATA_CODE"].dropna().str.strip())
print(f"\n  Distinct IATA codes in airports.csv: {len(known_airport_codes)}")

# Check lat/lon are numeric
airports_df["LATITUDE"]  = pd.to_numeric(airports_df["LATITUDE"],  errors="coerce")
airports_df["LONGITUDE"] = pd.to_numeric(airports_df["LONGITUDE"], errors="coerce")
print(f"\n  LATITUDE  nulls after coerce : {airports_df['LATITUDE'].isnull().sum()}")
print(f"  LONGITUDE nulls after coerce : {airports_df['LONGITUDE'].isnull().sum()}")
print(f"  LATITUDE  range              : {airports_df['LATITUDE'].min():.4f} to {airports_df['LATITUDE'].max():.4f}")
print(f"  LONGITUDE range              : {airports_df['LONGITUDE'].min():.4f} to {airports_df['LONGITUDE'].max():.4f}")

del airports_df
gc.collect()

# ════════════════════════════════════════════════════════════
# SECTION 2 — airlines.csv  (tiny file)
# ════════════════════════════════════════════════════════════
separator("SECTION 2 — airlines.csv Analysis")
airlines_df = pd.read_csv(AIRLINES_CSV, dtype=str)
print(f"  Row count       : {len(airlines_df)}")
print(f"  Columns         : {list(airlines_df.columns)}")
print(f"\n  Full content:")
print(airlines_df.to_string(index=False))
known_airline_codes = set(airlines_df["IATA_CODE"].dropna().str.strip())

del airlines_df
gc.collect()

# ════════════════════════════════════════════════════════════
# SECTION 3 — flights.csv  (chunked — never fully loaded)
# ════════════════════════════════════════════════════════════
separator("SECTION 3 — flights.csv Chunked Analysis")

# Accumulators
total_rows          = 0
total_duplicates    = 0
null_counts         = Counter()
col_names           = None
month_counter       = Counter()
airline_counter     = Counter()
origin_codes        = set()
dest_codes          = set()
numeric_origin      = 0      # non-IATA (numeric) origin codes
numeric_dest        = 0
distance_min        = float("inf")
distance_max        = float("-inf")
seen_hashes         = set()  # lightweight duplicate detection via row hash
dep_delay_nulls     = 0
arr_delay_nulls     = 0
cancel_count        = 0
divert_count        = 0
cancel_reason_vals  = Counter()
year_set            = set()

# dtypes to use when reading (reduces RAM by ~30%)
DTYPE_MAP = {
    "YEAR": "Int16", "MONTH": "Int8", "DAY": "Int8", "DAY_OF_WEEK": "Int8",
    "FLIGHT_NUMBER": "Int32", "SCHEDULED_DEPARTURE": "Int32",
    "DISTANCE": "Int32", "DIVERTED": "Int8", "CANCELLED": "Int8",
    "DEPARTURE_DELAY": "float32", "ARRIVAL_DELAY": "float32",
    "AIR_TIME": "float32", "ELAPSED_TIME": "float32",
}

print(f"  Reading in chunks of {CHUNK_SIZE:,} rows …")
chunk_reader = pd.read_csv(
    FLIGHTS_CSV,
    chunksize=CHUNK_SIZE,
    dtype=DTYPE_MAP,
    low_memory=False,
    na_values=["", "NA", "N/A"],
    keep_default_na=True,
)

chunk_num = 0
for chunk in chunk_reader:
    chunk_num += 1
    row_count   = len(chunk)
    total_rows += row_count

    # Capture column names once
    if col_names is None:
        col_names = list(chunk.columns)

    # Null accumulation
    for col in chunk.columns:
        null_counts[col] += chunk[col].isnull().sum()

    # Month distribution
    if "MONTH" in chunk.columns:
        month_counter.update(chunk["MONTH"].dropna().astype(int).tolist())

    # Year check
    if "YEAR" in chunk.columns:
        year_set.update(chunk["YEAR"].dropna().astype(int).tolist())

    # Airline codes
    if "AIRLINE" in chunk.columns:
        airline_counter.update(chunk["AIRLINE"].dropna().tolist())

    # Airport code collection + numeric check
    if "ORIGIN_AIRPORT" in chunk.columns:
        origin_series = chunk["ORIGIN_AIRPORT"].dropna().str.strip()
        origin_codes.update(origin_series.tolist())
        numeric_origin += origin_series.str.isnumeric().sum()

    if "DESTINATION_AIRPORT" in chunk.columns:
        dest_series = chunk["DESTINATION_AIRPORT"].dropna().str.strip()
        dest_codes.update(dest_series.tolist())
        numeric_dest += dest_series.str.isnumeric().sum()

    # Distance range
    if "DISTANCE" in chunk.columns:
        d_min = chunk["DISTANCE"].min()
        d_max = chunk["DISTANCE"].max()
        if pd.notna(d_min) and d_min < distance_min:
            distance_min = d_min
        if pd.notna(d_max) and d_max > distance_max:
            distance_max = d_max

    # Delay nulls
    if "DEPARTURE_DELAY" in chunk.columns:
        dep_delay_nulls += chunk["DEPARTURE_DELAY"].isnull().sum()
    if "ARRIVAL_DELAY" in chunk.columns:
        arr_delay_nulls += chunk["ARRIVAL_DELAY"].isnull().sum()

    # Cancellation stats
    if "CANCELLED" in chunk.columns:
        cancel_count += (chunk["CANCELLED"] == 1).sum()
    if "DIVERTED" in chunk.columns:
        divert_count += (chunk["DIVERTED"] == 1).sum()
    if "CANCELLATION_REASON" in chunk.columns:
        cancel_reason_vals.update(
            chunk["CANCELLATION_REASON"].dropna().tolist()
        )

    # Lightweight duplicate detection (hash first 6 key fields)
    key_cols = ["YEAR", "MONTH", "DAY", "AIRLINE",
                "FLIGHT_NUMBER", "ORIGIN_AIRPORT", "DESTINATION_AIRPORT",
                "SCHEDULED_DEPARTURE"]
    available_key_cols = [c for c in key_cols if c in chunk.columns]
    chunk_keys = chunk[available_key_cols].astype(str).agg("|".join, axis=1)
    for key in chunk_keys:
        h = hashlib.md5(key.encode()).hexdigest()
        if h in seen_hashes:
            total_duplicates += 1
        else:
            seen_hashes.add(h)

    if chunk_num % 10 == 0:
        print(f"    … processed {total_rows:,} rows so far (chunk {chunk_num})")

    del chunk
    gc.collect()

# ════════════════════════════════════════════════════════════
# SECTION 4 — Summary Report
# ════════════════════════════════════════════════════════════
separator("SECTION 4 — flights.csv Summary Report")

print(f"\n  Total rows (excl. header)   : {total_rows:,}")
print(f"  Total columns               : {len(col_names)}")
print(f"  Column names                : {col_names}")
print(f"\n  Year values found           : {sorted(year_set)}")
print(f"  Months present              : {sorted(month_counter.keys())}")
print(f"\n  Month distribution:")
for m in sorted(month_counter.keys()):
    print(f"    Month {m:2d} : {month_counter[m]:>8,} flights")

print(f"\n  Distinct ORIGIN codes       : {len(origin_codes)}")
print(f"  Distinct DEST codes         : {len(dest_codes)}")
print(f"  Numeric (non-IATA) ORIGIN   : {numeric_origin:,}  [non-zero = REVIEW NEEDED]")
print(f"  Numeric (non-IATA) DEST     : {numeric_dest:,}  [non-zero = REVIEW NEEDED]")

print(f"\n  Airlines in flights.csv     : {len(airline_counter)}")
print(f"  Airline codes found         : {sorted(airline_counter.keys())}")
unknown_airlines = set(airline_counter.keys()) - known_airline_codes
print(f"  Airlines NOT in airlines.csv: {unknown_airlines}  [empty = OK]")

orphan_airports = (origin_codes | dest_codes) - known_airport_codes
print(f"\n  Airport codes in flights but NOT in airports.csv: {len(orphan_airports)}")
if orphan_airports:
    print(f"    {sorted(orphan_airports)[:30]}  (showing first 30)")

print(f"\n  Distance range (miles)      : {distance_min} – {distance_max}")
print(f"\n  Cancelled flights           : {cancel_count:,}  ({cancel_count/total_rows*100:.2f}%)")
print(f"  Diverted flights            : {divert_count:,}  ({divert_count/total_rows*100:.2f}%)")
print(f"  Cancellation reasons found  : {dict(cancel_reason_vals)}")
print(f"\n  DEPARTURE_DELAY nulls       : {dep_delay_nulls:,}  ({dep_delay_nulls/total_rows*100:.2f}%)")
print(f"  ARRIVAL_DELAY nulls         : {arr_delay_nulls:,}  ({arr_delay_nulls/total_rows*100:.2f}%)")

separator("SECTION 5 — Null Counts Per Column (sorted by severity)")
null_pct = {col: (cnt, cnt/total_rows*100) for col, cnt in null_counts.items()}
for col, (cnt, pct) in sorted(null_pct.items(), key=lambda x: -x[1][0]):
    flag = "  ← EXPECTED" if col in [
        "CANCELLATION_REASON","AIR_SYSTEM_DELAY","SECURITY_DELAY",
        "AIRLINE_DELAY","LATE_AIRCRAFT_DELAY","WEATHER_DELAY"
    ] else ""
    print(f"  {col:<30} {cnt:>8,}  ({pct:5.2f}%){flag}")

separator("SECTION 6 — Duplicate Record Check")
print(f"  Approximate duplicate key groups detected: {total_duplicates:,}")
if total_duplicates == 0:
    print("  [OK] No duplicate records detected.")
else:
    print(f"  [WARNING] {total_duplicates:,} potential duplicate rows found — review before ingestion.")

separator("SECTION 7 — Dataset Validation Verdict")
issues = []
if total_rows < 5_800_000:
    issues.append(f"Row count {total_rows:,} is below expected 5,819,079")
if len(col_names) != 31:
    issues.append(f"Column count {len(col_names)} ≠ expected 31")
if numeric_origin > 0:
    issues.append(f"{numeric_origin:,} numeric origin codes (non-IATA) found")
if len(orphan_airports) > 0:
    issues.append(f"{len(orphan_airports)} airport codes not in airports.csv")
if unknown_airlines:
    issues.append(f"Unknown airline codes: {unknown_airlines}")
if total_duplicates > 0:
    issues.append(f"{total_duplicates:,} duplicate records detected")

if not issues:
    print("\n  ✅ DATASET VALIDATED — No critical issues found.")
    print("  Report these results and proceed to Phase 2.")
else:
    print(f"\n  ⚠️  {len(issues)} issue(s) require attention before Phase 2:")
    for i, issue in enumerate(issues, 1):
        print(f"    {i}. {issue}")

print("\n" + "=" * 65)
print("  Inspection complete. Share the full output with your mentor.")
print("=" * 65 + "\n")
```

### How to Run

```powershell
# 1. Navigate to your data folder
cd "C:\Users\nithi\Downloads\BIG DATA PROJECT"

# 2. Install dependencies (one-time)
pip install pandas

# 3. Run the script
python inspect_dataset.py

# 4. Save output to a file for sharing
python inspect_dataset.py > validation_report.txt 2>&1
```

### What to Report Back After Running

When you run the script, share the output for these key lines:

- `Total rows` → confirm ~5,819,079
- `Total columns` → confirm 31
- `Months present` → confirm `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]`
- `Numeric (non-IATA) ORIGIN/DEST` → should be 0
- `Airport codes NOT in airports.csv` → review if non-empty
- `Duplicate key groups detected` → should be 0
- **Final verdict line** → `✅ DATASET VALIDATED` or list of issues

---

*Document version 1.0 — Phase 1 only. Phase 2 commences upon validation confirmation.*
