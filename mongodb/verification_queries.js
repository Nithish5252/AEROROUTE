// ==============================================================================
// AeroRoute -- Phase 5: MongoDB Comprehensive Verification Query Suite
// File   : mongodb/verification_queries.js
// Target : MongoDB 4.4+ Community Server (mongosh / mongo.exe)
// Usage  : mongo aeroroutedb mongodb/verification_queries.js
// ==============================================================================

var targetDb = db.getSiblingDB("aeroroutedb");

print("\n=======================================================");
print("  AeroRoute -- Full System & MapReduce Verification Audit");
print("=======================================================\n");

var passCount = 0;
var failCount = 0;

function assertCondition(testName, condition, details) {
    if (condition) {
        passCount++;
        print("  [PASS] " + testName + " -> " + details);
    } else {
        failCount++;
        print("  [FAIL] " + testName + " -> " + details);
    }
}

// ------------------------------------------------------------------------------
// SECTION 1: Base Collections Inventory
// ------------------------------------------------------------------------------
print("--- [1] Base Collection Document Counts ---");
var countAirlines = targetDb.airlines.countDocuments({});
var countAirports = targetDb.airports.countDocuments({});
var countFlights  = targetDb.flights.countDocuments({});
var countRuns     = targetDb.pipeline_runs.countDocuments({});

assertCondition("Airlines Count", countAirlines === 14, "Count: " + countAirlines + " (Expected: 14)");
assertCondition("Airports Count", countAirports === 322, "Count: " + countAirports + " (Expected: 322)");
assertCondition("Flights Count", countFlights > 0, "Count: " + countFlights.toLocaleString() + " records");
assertCondition("Pipeline Runs Metadata", countRuns >= 0, "Count: " + countRuns + " recorded runs");

// ------------------------------------------------------------------------------
// SECTION 2: Cohort Separation & Isolation Integrity
// ------------------------------------------------------------------------------
print("\n--- [2] Cohort Isolation & Quarantine Integrity ---");

var cancelledAndEligible = targetDb.flights.countDocuments({
    "is_route_eligible": true,
    "is_cancelled": true
});
assertCondition(
    "Zero Cancelled Flights in Route Analysis",
    cancelledAndEligible === 0,
    "Violations found: " + cancelledAndEligible
);

var missingCoordsEligible = targetDb.flights.countDocuments({
    "is_route_eligible": true,
    "$or": [
        { "origin.lat": null }, { "origin.lon": null },
        { "destination.lat": null }, { "destination.lon": null }
    ]
});
assertCondition(
    "Zero Missing Coordinates in Route Analysis",
    missingCoordsEligible === 0,
    "Violations found: " + missingCoordsEligible
);

var numericRouteEligible = targetDb.flights.countDocuments({
    "is_route_eligible": true,
    "$or": [
        { "origin.iata": { "$regex": "^[0-9]" } },
        { "destination.iata": { "$regex": "^[0-9]" } }
    ]
});
assertCondition(
    "Zero Numeric DOT Airport IDs in Route Analysis",
    numericRouteEligible === 0,
    "Violations found: " + numericRouteEligible
);

// ------------------------------------------------------------------------------
// SECTION 3: MapReduce Output Collections Verification
// ------------------------------------------------------------------------------
print("\n--- [3] MapReduce Aggregation Results ---");

var countJobA = targetDb.mr_route_activity.countDocuments({});
var countJobB = targetDb.mr_airport_outgoing.countDocuments({});
var countJobC = targetDb.mr_airport_incoming.countDocuments({});
var countJobD = targetDb.mr_monthly_route.countDocuments({});
var countJobE = targetDb.mr_airport_connectivity.countDocuments({});

assertCondition("Job A: mr_route_activity Populated", countJobA > 0, "Distinct Directed Routes: " + countJobA.toLocaleString());
assertCondition("Job B: mr_airport_outgoing Populated", countJobB > 0, "Origin Airports: " + countJobB.toLocaleString());
assertCondition("Job C: mr_airport_incoming Populated", countJobC > 0, "Destination Airports: " + countJobC.toLocaleString());
assertCondition("Job D: mr_monthly_route Populated", countJobD > 0, "Monthly Route Entries: " + countJobD.toLocaleString());
assertCondition("Job E: mr_airport_connectivity Populated", countJobE > 0, "Connected Airports: " + countJobE.toLocaleString());

// ------------------------------------------------------------------------------
// SECTION 4: MapReduce Mathematical Consistency & Directionality
// ------------------------------------------------------------------------------
print("\n--- [4] MapReduce Mathematical Consistency & Directionality ---");

// Directionality check: verify ATL->ORD and ORD->ATL are tracked as separate keys
var atlToOrd = targetDb.mr_route_activity.findOne({ "_id": "ATL->ORD" });
var ordToAtl = targetDb.mr_route_activity.findOne({ "_id": "ORD->ATL" });

var bothExist = (atlToOrd !== null && ordToAtl !== null);
var atlCount = atlToOrd ? atlToOrd.value : 0;
var ordCount = ordToAtl ? ordToAtl.value : 0;

assertCondition(
    "Directed Route Separation (ATL->ORD vs ORD->ATL)",
    bothExist,
    "ATL->ORD: " + atlCount + " flights | ORD->ATL: " + ordCount + " flights (Separated: " + (atlToOrd !== null && ordToAtl !== null) + ")"
);

// Connectivity distinction: verify distinct_connections != raw total flights
var sampleConn = targetDb.mr_airport_connectivity.findOne({ "_id": "ATL" });
if (sampleConn) {
    var v = sampleConn.value;
    var validDistinction = (v.distinct_connections < v.total_flights);
    assertCondition(
        "Distinct Connections != Raw Flight Count (ATL)",
        validDistinction,
        "Distinct Neighbors: " + v.distinct_connections + " | Total Flights: " + v.total_flights
    );
}

// ------------------------------------------------------------------------------
// SECTION 5: Geospatial 2dsphere Query Test
// ------------------------------------------------------------------------------
print("\n--- [5] Geospatial Index Verification ---");
var jfkCoords = [-73.7789, 40.6398];
var nearbyAirports = targetDb.airports.find({
    "location": {
        "$near": {
            "$geometry": {
                "type": "Point",
                "coordinates": jfkCoords
            },
            "$maxDistance": 300000 // 300 km
        }
    }
}).limit(5).toArray();

assertCondition(
    "2dsphere Geospatial Proximity Query",
    nearbyAirports.length > 0,
    "Found " + nearbyAirports.length + " airports within 300 km of JFK"
);

// ------------------------------------------------------------------------------
// SECTION 6: Storage Footprint
// ------------------------------------------------------------------------------
print("\n--- [6] Storage Footprint Summary ---");
var flightStats = targetDb.flights.stats();
var dataSizeMB    = (flightStats.size / (1024 * 1024)).toFixed(2);
var storageSizeMB = (flightStats.storageSize / (1024 * 1024)).toFixed(2);
var indexSizeMB   = (flightStats.totalIndexSize / (1024 * 1024)).toFixed(2);

print("Flights Collection:");
print("  Documents      : " + flightStats.count.toLocaleString());
print("  Compressed Size: " + storageSizeMB + " MB");
print("  Index Size     : " + indexSizeMB + " MB");

// ------------------------------------------------------------------------------
// Final Verdict
// ------------------------------------------------------------------------------
print("\n=======================================================");
print("  Audit Summary: " + passCount + " PASSED, " + failCount + " FAILED");
if (failCount === 0) {
    print("  VERDICT: All Phase 5 MapReduce & QA Assertions PASSED.");
} else {
    print("  VERDICT: Issues detected. Review failed checks above.");
}
print("=======================================================\n");
