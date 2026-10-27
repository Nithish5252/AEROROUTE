# ============================================================
# AeroRoute -- MongoDB MapReduce Job Definitions
# File : src/mapreduce/jobs.py
# ============================================================

from bson.code import Code

# ============================================================
# JOB A: Directed Route Activity
# Key   : origin airport -> destination airport (e.g. "ATL->ORD")
# Value : 1
# Output: count of eligible flights per directed route
# ============================================================
JOB_A_MAPPER = Code("""
function() {
    var key = this.route_key || (this.origin.iata + "->" + this.destination.iata);
    emit(key, 1);
}
""")

JOB_A_REDUCER = Code("""
function(key, values) {
    return Array.sum(values);
}
""")

# ============================================================
# JOB B: Airport Outgoing Activity
# Key   : origin airport (e.g. "ATL")
# Value : 1
# Output: outgoing eligible flight count per airport
# ============================================================
JOB_B_MAPPER = Code("""
function() {
    if (this.origin && this.origin.iata) {
        emit(this.origin.iata, 1);
    }
}
""")

JOB_B_REDUCER = Code("""
function(key, values) {
    return Array.sum(values);
}
""")

# ============================================================
# JOB C: Airport Incoming Activity
# Key   : destination airport (e.g. "ORD")
# Value : 1
# Output: incoming eligible flight count per airport
# ============================================================
JOB_C_MAPPER = Code("""
function() {
    if (this.destination && this.destination.iata) {
        emit(this.destination.iata, 1);
    }
}
""")

JOB_C_REDUCER = Code("""
function(key, values) {
    return Array.sum(values);
}
""")

# ============================================================
# JOB D: Monthly Route Activity
# Key   : year-month, origin airport, destination airport
# Value : 1
# Output: monthly eligible flight count per directed route
# ============================================================
JOB_D_MAPPER = Code("""
function() {
    var ym = (this.year || 2015) + "-" + (this.month < 10 ? "0" + this.month : this.month);
    var key = {
        year_month: ym,
        origin: this.origin.iata,
        destination: this.destination.iata,
        route_key: this.route_key || (this.origin.iata + "->" + this.destination.iata)
    };
    emit(key, 1);
}
""")

JOB_D_REDUCER = Code("""
function(key, values) {
    return Array.sum(values);
}
""")

# ============================================================
# JOB E: Airport Connectivity Summary
# Key   : airport code
# Value : { outgoing_flights, incoming_flights, outgoing_destinations, incoming_origins }
# Finalize: distinct_connections (unique neighboring airports),
#           out_degree, in_degree, total_flights
# ============================================================
JOB_E_MAPPER = Code("""
function() {
    if (this.origin && this.origin.iata && this.destination && this.destination.iata) {
        // Emit for origin (outgoing flight)
        emit(this.origin.iata, {
            outgoing_flights: 1,
            incoming_flights: 0,
            outgoing_destinations: [this.destination.iata],
            incoming_origins: []
        });
        // Emit for destination (incoming flight)
        emit(this.destination.iata, {
            outgoing_flights: 0,
            incoming_flights: 1,
            outgoing_destinations: [],
            incoming_origins: [this.origin.iata]
        });
    }
}
""")

JOB_E_REDUCER = Code("""
function(key, values) {
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
}
""")

JOB_E_FINALIZE = Code("""
function(key, val) {
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
}
""")

# Standard query filter ensuring only valid, non-cancelled, geographically resolved flights are analyzed
MAPREDUCE_QUERY_FILTER = {
    "is_route_eligible": True
}
