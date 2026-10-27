// ==============================================================================
// AeroRoute -- Phase 5: Server-Side JavaScript MapReduce Definitions
// File   : mongodb/mapreduce/jobs.js
// Target : MongoDB 4.4+ Community Server (mongosh / mongo.exe)
// Usage  : mongo aeroroutedb mongodb/mapreduce/jobs.js
// ==============================================================================

var targetDb = db.getSiblingDB("aeroroutedb");

print("\n=======================================================");
print("  AeroRoute -- Executing Server-Side MapReduce Jobs");
print("=======================================================\n");

var queryFilter = { "is_route_eligible": true };

// ------------------------------------------------------------------------------
// JOB A: Directed Route Activity
// ------------------------------------------------------------------------------
print("[1/5] Running Job A: Directed Route Activity (ATL->ORD vs ORD->ATL)...");
var jobAMapper = function() {
    var key = this.route_key || (this.origin.iata + "->" + this.destination.iata);
    emit(key, 1);
};
var jobAReducer = function(key, values) {
    return Array.sum(values);
};
targetDb.flights.mapReduce(jobAMapper, jobAReducer, {
    out: { replace: "mr_route_activity" },
    query: queryFilter
});
print("  --> mr_route_activity populated with " + targetDb.mr_route_activity.countDocuments({}) + " routes.");

// ------------------------------------------------------------------------------
// JOB B: Airport Outgoing Activity
// ------------------------------------------------------------------------------
print("[2/5] Running Job B: Airport Outgoing Activity...");
var jobBMapper = function() {
    if (this.origin && this.origin.iata) {
        emit(this.origin.iata, 1);
    }
};
var jobBReducer = function(key, values) {
    return Array.sum(values);
};
targetDb.flights.mapReduce(jobBMapper, jobBReducer, {
    out: { replace: "mr_airport_outgoing" },
    query: queryFilter
});
print("  --> mr_airport_outgoing populated with " + targetDb.mr_airport_outgoing.countDocuments({}) + " airports.");

// ------------------------------------------------------------------------------
// JOB C: Airport Incoming Activity
// ------------------------------------------------------------------------------
print("[3/5] Running Job C: Airport Incoming Activity...");
var jobCMapper = function() {
    if (this.destination && this.destination.iata) {
        emit(this.destination.iata, 1);
    }
};
var jobCReducer = function(key, values) {
    return Array.sum(values);
};
targetDb.flights.mapReduce(jobCMapper, jobCReducer, {
    out: { replace: "mr_airport_incoming" },
    query: queryFilter
});
print("  --> mr_airport_incoming populated with " + targetDb.mr_airport_incoming.countDocuments({}) + " airports.");

// ------------------------------------------------------------------------------
// JOB D: Monthly Route Activity
// ------------------------------------------------------------------------------
print("[4/5] Running Job D: Monthly Route Activity...");
var jobDMapper = function() {
    var ym = (this.year || 2015) + "-" + (this.month < 10 ? "0" + this.month : this.month);
    var key = {
        year_month: ym,
        origin: this.origin.iata,
        destination: this.destination.iata,
        route_key: this.route_key || (this.origin.iata + "->" + this.destination.iata)
    };
    emit(key, 1);
};
var jobDReducer = function(key, values) {
    return Array.sum(values);
};
targetDb.flights.mapReduce(jobDMapper, jobDReducer, {
    out: { replace: "mr_monthly_route" },
    query: queryFilter
});
print("  --> mr_monthly_route populated with " + targetDb.mr_monthly_route.countDocuments({}) + " monthly route entries.");

// ------------------------------------------------------------------------------
// JOB E: Airport Connectivity Summary
// ------------------------------------------------------------------------------
print("[5/5] Running Job E: Airport Connectivity Summary (Distinct Connections)...");
var jobEMapper = function() {
    if (this.origin && this.origin.iata && this.destination && this.destination.iata) {
        emit(this.origin.iata, {
            outgoing_flights: 1,
            incoming_flights: 0,
            outgoing_destinations: [this.destination.iata],
            incoming_origins: []
        });
        emit(this.destination.iata, {
            outgoing_flights: 0,
            incoming_flights: 1,
            outgoing_destinations: [],
            incoming_origins: [this.origin.iata]
        });
    }
};

var jobEReducer = function(key, values) {
    var outF = 0;
    var inF = 0;
    var outMap = {};
    var inMap = {};

    values.forEach(function(v) {
        outF += (v.outgoing_flights || 0);
        inF += (v.incoming_flights || 0);

        if (v.outgoing_destinations) {
            for (var i = 0; i < v.outgoing_destinations.length; i++) {
                outMap[v.outgoing_destinations[i]] = true;
            }
        }
        if (v.incoming_origins) {
            for (var j = 0; j < v.incoming_origins.length; j++) {
                inMap[v.incoming_origins[j]] = true;
            }
        }
    });

    return {
        outgoing_flights: outF,
        incoming_flights: inF,
        outgoing_destinations: Object.keys(outMap),
        incoming_origins: Object.keys(inMap)
    };
};

var jobEFinalize = function(key, val) {
    var neighborsMap = {};
    var outList = val.outgoing_destinations || [];
    var inList = val.incoming_origins || [];

    for (var i = 0; i < outList.length; i++) {
        neighborsMap[outList[i]] = true;
    }
    for (var j = 0; j < inList.length; j++) {
        neighborsMap[inList[j]] = true;
    }

    var distinctNeighborList = Object.keys(neighborsMap);

    return {
        outgoing_flights: val.outgoing_flights,
        incoming_flights: val.incoming_flights,
        total_flights: val.outgoing_flights + val.incoming_flights,
        out_degree: outList.length,
        in_degree: inList.length,
        distinct_connections: distinctNeighborList.length,
        neighbor_airports: distinctNeighborList
    };
};

targetDb.flights.mapReduce(jobEMapper, jobEReducer, {
    out: { replace: "mr_airport_connectivity" },
    finalize: jobEFinalize,
    query: queryFilter
});
print("  --> mr_airport_connectivity populated with " + targetDb.mr_airport_connectivity.countDocuments({}) + " airports.");

print("\nAll 5 MapReduce jobs executed successfully.\n");
