// ==============================================================================
// AeroRoute -- Phase 4: Production MongoDB Index Configuration
// File   : mongodb/setup_indexes.js
// Target : MongoDB 4.4+ Community Server (mongosh / mongo.exe)
// Usage  : mongo aeroroutedb mongodb/setup_indexes.js
//          OR in mongosh: mongosh aeroroutedb mongodb/setup_indexes.js
// ==============================================================================

print("\n=======================================================");
print("  AeroRoute -- Initializing Production Indexes");
print("=======================================================\n");

var targetDb = db.getSiblingDB("aeroroutedb");

// ------------------------------------------------------------------------------
// 1. COLLECTION: flights (~5.82 Million Documents)
// ------------------------------------------------------------------------------
print("[1/4] Configuring indexes for collection: 'flights'...");

// (1) Natural Key Uniqueness & Rerun Idempotence
// WHY NEEDED: Enforces deterministic deduplication. Prevents re-running ingestion
//             from inserting duplicate flight documents.
targetDb.flights.createIndex(
    { "flight_id": 1 },
    { unique: true, name: "uniq_flight_id", background: true }
);

// (2) Route Key Index
// WHY NEEDED: Essential for Phase 5 MapReduce Job 1 (Route Activity Aggregation).
//             Grouping by 'route_key' ("LAX->JFK") avoids full collection table scans.
targetDb.flights.createIndex(
    { "route_key": 1 },
    { name: "idx_route_key", background: true }
);

// (3) Origin Airport Index
// WHY NEEDED: Essential for MapReduce Job 2 (Airport Outgoing Connectivity) and
//             dashboard origin airport dropdown filtering.
targetDb.flights.createIndex(
    { "origin.iata": 1 },
    { name: "idx_origin_iata", background: true }
);

// (4) Destination Airport Index
// WHY NEEDED: Essential for MapReduce Job 3 (Airport Incoming Connectivity) and
//             dashboard destination airport dropdown filtering.
targetDb.flights.createIndex(
    { "destination.iata": 1 },
    { name: "idx_dest_iata", background: true }
);

// (5) Carrier Code Index
// WHY NEEDED: Fast lookups and filtering for airline punctuality and market share queries.
targetDb.flights.createIndex(
    { "airline_code": 1 },
    { name: "idx_airline_code", background: true }
);

// (6) Month Index
// WHY NEEDED: Used by MapReduce Job 4 (Monthly Route Trends) and seasonal filtering.
targetDb.flights.createIndex(
    { "month": 1 },
    { name: "idx_month", background: true }
);

// (7) Route Eligibility Filtering Index
// WHY NEEDED: High-selectivity filter index. Every MapReduce job and route graph query
//             filters on `{ "is_route_eligible": true }` to bypass ~576,000 cancelled
//             or unresolved records without reading them into RAM.
targetDb.flights.createIndex(
    { "is_route_eligible": 1 },
    { name: "idx_is_route_eligible", background: true }
);

// (8) Cancellation Status Index
// WHY NEEDED: Allows quick aggregation of cancellation rates across dates and airlines.
targetDb.flights.createIndex(
    { "is_cancelled": 1 },
    { name: "idx_is_cancelled", background: true }
);

// (9) Compound Route + Temporal Corridor Index
// WHY NEEDED: Fully covers queries filtering by origin, destination, and month simultaneously,
//             satisfying queries entirely from the B-tree index without fetching documents.
targetDb.flights.createIndex(
    { "origin.iata": 1, "destination.iata": 1, "month": 1 },
    { name: "idx_origin_dest_month", background: true }
);

// (10) Compound Geographic Origin Coordinates Index
// WHY NEEDED: Enables rapid spatial range queries and airport coordinate lookups for
//             clustering algorithms without joining airports collection.
targetDb.flights.createIndex(
    { "origin.lat": 1, "origin.lon": 1 },
    { name: "idx_origin_coords", background: true }
);

// OMITTED INDEXES RATIONALE:
// - No index on 'departure_delay' alone: low selectivity; sorting is done after filtering.
// - No index on 'tail_number': rarely queried alone; saves ~120 MB RAM.
// - No index on individual delay breakdown fields: aggregated only in bulk MapReduce.

// ------------------------------------------------------------------------------
// 2. COLLECTION: airports (322 Documents)
// ------------------------------------------------------------------------------
print("[2/4] Configuring indexes for collection: 'airports'...");

// (1) Natural Primary Code
targetDb.airports.createIndex(
    { "iata": 1 },
    { unique: true, name: "uniq_airport_iata" }
);

// (2) 2dsphere Geospatial Index
// WHY NEEDED: Enables geospatial spherical queries ($near, $geoWithin, $centerSphere)
//             for interactive map bounding-box lookups in the dashboard.
targetDb.airports.createIndex(
    { "location": "2dsphere" },
    { name: "geo_airport_location" }
);

// ------------------------------------------------------------------------------
// 3. COLLECTION: airlines (14 Documents)
// ------------------------------------------------------------------------------
print("[3/4] Configuring indexes for collection: 'airlines'...");

// (1) Natural Primary Code
targetDb.airlines.createIndex(
    { "airline_code": 1 },
    { unique: true, name: "uniq_airline_code" }
);

// ------------------------------------------------------------------------------
// 4. COLLECTION: pipeline_runs (Operational Metadata)
// ------------------------------------------------------------------------------
print("[4/4] Configuring indexes for collection: 'pipeline_runs'...");

// (1) Unique Run Identifier
targetDb.pipeline_runs.createIndex(
    { "run_id": 1 },
    { unique: true, name: "uniq_run_id" }
);

// (2) Chronological Sorting Index
targetDb.pipeline_runs.createIndex(
    { "started_at": -1 },
    { name: "idx_started_at_desc" }
);

// ------------------------------------------------------------------------------
// Index Verification & Summary
// ------------------------------------------------------------------------------
print("\n=======================================================");
print("  Index Configuration Summary");
print("=======================================================");

var collections = ["flights", "airports", "airlines", "pipeline_runs"];
collections.forEach(function(col) {
    var idxList = targetDb[col].getIndexes();
    print("Collection [" + col + "] has " + idxList.length + " index(es):");
    idxList.forEach(function(idx) {
        var keyStr = JSON.stringify(idx.key);
        var uniqStr = idx.unique ? " [UNIQUE]" : "";
        print("  - " + idx.name + " on " + keyStr + uniqStr);
    });
});

print("\nAll production indexes successfully created and verified.\n");
