# ============================================================
# AeroRoute -- Indian Domestic Aviation MapReduce Job Definitions
# File : src/mapreduce/indian_jobs.py
# Phase: Phase 3 MongoDB MapReduce Pipeline Adaptation
# ============================================================

from bson.code import Code

# ============================================================
# JOB A: Indian Directed Route Activity
# Key   : origin airport -> destination airport (e.g. "DEL->BOM")
# Value : Timetable services, weekly frequency, distance, airlines
# Output: mr_route_activity_in
# ============================================================
INDIAN_JOB_A_MAPPER = Code("""
function() {
    if (!this.is_route_eligible) return;
    var key = this.route_key || (this.origin.iata + "->" + this.destination.iata);
    var weeklyFreq = Number(this.operating_days_count) || 1;
    var dist = Number(this.distance_km) || 0;
    var airline = this.airline_code || "UNKNOWN";

    emit(key, {
        timetable_services: 1,
        weekly_frequency: weeklyFreq,
        distance_km: dist,
        airlines: [airline]
    });
}
""")

INDIAN_JOB_A_REDUCER = Code("""
function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var dist = 0;
    var airlineMap = {};

    values.forEach(function(v) {
        totalServices += (v.timetable_services || 0);
        totalWeeklyFreq += (v.weekly_frequency || 0);
        if (v.distance_km) dist = v.distance_km;
        if (v.airlines) {
            for (var i = 0; i < v.airlines.length; i++) {
                airlineMap[v.airlines[i]] = true;
            }
        }
    });

    return {
        timetable_services: totalServices,
        weekly_frequency: totalWeeklyFreq,
        distance_km: dist,
        airlines: Object.keys(airlineMap)
    };
}
""")

INDIAN_JOB_A_FINALIZE = Code("""
function(key, val) {
    var airlinesList = val.airlines || [];
    var weeklyFreq = val.weekly_frequency || 0;
    return {
        timetable_services: val.timetable_services || 0,
        weekly_frequency: weeklyFreq,
        estimated_monthly_departures: Math.round(weeklyFreq * 4.2857),
        distance_km: val.distance_km || 0,
        airlines: airlinesList,
        carrier_count: airlinesList.length,
        metric_type: "SCHEDULED_ROUTE_CAPACITY",
        data_source: "DGCA_Airline_Timetables_2018_2025"
    };
}
""")


# ============================================================
# JOB B: Indian Airport Outgoing Activity
# Key   : origin airport (e.g. "DEL")
# Value : Outgoing timetable services, weekly departures, destinations
# Output: mr_airport_outgoing_in
# ============================================================
INDIAN_JOB_B_MAPPER = Code("""
function() {
    if (!this.is_route_eligible) return;
    if (this.origin && this.origin.iata) {
        var weeklyFreq = Number(this.operating_days_count) || 1;
        var dest = (this.destination && this.destination.iata) ? this.destination.iata : null;
        emit(this.origin.iata, {
            outgoing_timetable_services: 1,
            outgoing_weekly_frequency: weeklyFreq,
            destinations: dest ? [dest] : []
        });
    }
}
""")

INDIAN_JOB_B_REDUCER = Code("""
function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var destMap = {};

    values.forEach(function(v) {
        totalServices += (v.outgoing_timetable_services || 0);
        totalWeeklyFreq += (v.outgoing_weekly_frequency || 0);
        if (v.destinations) {
            for (var i = 0; i < v.destinations.length; i++) {
                destMap[v.destinations[i]] = true;
            }
        }
    });

    return {
        outgoing_timetable_services: totalServices,
        outgoing_weekly_frequency: totalWeeklyFreq,
        destinations: Object.keys(destMap)
    };
}
""")

INDIAN_JOB_B_FINALIZE = Code("""
function(key, val) {
    var destList = val.destinations || [];
    var weeklyFreq = val.outgoing_weekly_frequency || 0;
    return {
        outgoing_timetable_services: val.outgoing_timetable_services || 0,
        outgoing_weekly_frequency: weeklyFreq,
        estimated_monthly_departures: Math.round(weeklyFreq * 4.2857),
        out_degree_destinations: destList.length,
        destinations: destList,
        metric_type: "SCHEDULED_OUTGOING_CAPACITY",
        data_source: "DGCA_Airline_Timetables_2018_2025"
    };
}
""")


# ============================================================
# JOB C: Indian Airport Incoming Activity
# Key   : destination airport (e.g. "BOM")
# Value : Incoming timetable services, weekly arrivals, origins
# Output: mr_airport_incoming_in
# ============================================================
INDIAN_JOB_C_MAPPER = Code("""
function() {
    if (!this.is_route_eligible) return;
    if (this.destination && this.destination.iata) {
        var weeklyFreq = Number(this.operating_days_count) || 1;
        var orig = (this.origin && this.origin.iata) ? this.origin.iata : null;
        emit(this.destination.iata, {
            incoming_timetable_services: 1,
            incoming_weekly_frequency: weeklyFreq,
            origins: orig ? [orig] : []
        });
    }
}
""")

INDIAN_JOB_C_REDUCER = Code("""
function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var origMap = {};

    values.forEach(function(v) {
        totalServices += (v.incoming_timetable_services || 0);
        totalWeeklyFreq += (v.incoming_weekly_frequency || 0);
        if (v.origins) {
            for (var i = 0; i < v.origins.length; i++) {
                origMap[v.origins[i]] = true;
            }
        }
    });

    return {
        incoming_timetable_services: totalServices,
        incoming_weekly_frequency: totalWeeklyFreq,
        origins: Object.keys(origMap)
    };
}
""")

INDIAN_JOB_C_FINALIZE = Code("""
function(key, val) {
    var origList = val.origins || [];
    var weeklyFreq = val.incoming_weekly_frequency || 0;
    return {
        incoming_timetable_services: val.incoming_timetable_services || 0,
        incoming_weekly_frequency: weeklyFreq,
        estimated_monthly_arrivals: Math.round(weeklyFreq * 4.2857),
        in_degree_origins: origList.length,
        origins: origList,
        metric_type: "SCHEDULED_INCOMING_CAPACITY",
        data_source: "DGCA_Airline_Timetables_2018_2025"
    };
}
""")


# ============================================================
# JOB D: Indian Monthly Route Activity
# Key   : { year_month, origin, destination, route_key }
# Value : Active timetable services, weekly frequency, airlines
# Output: mr_monthly_route_in
# ============================================================
INDIAN_JOB_D_MAPPER = Code("""
function() {
    if (!this.is_route_eligible) return;
    if (!this.valid_from || !this.valid_to) return;

    var startParts = this.valid_from.split("-");
    var endParts = this.valid_to.split("-");
    var sY = parseInt(startParts[0], 10);
    var sM = parseInt(startParts[1], 10);
    var eY = parseInt(endParts[0], 10);
    var eM = parseInt(endParts[1], 10);

    if (isNaN(sY) || isNaN(sM) || isNaN(eY) || isNaN(eM)) {
        sY = this.year || 2022;
        sM = this.month || 10;
        eY = sY;
        eM = sM;
    }

    var weeklyFreq = Number(this.operating_days_count) || 1;
    var dist = Number(this.distance_km) || 0;
    var airline = this.airline_code || "UNKNOWN";
    var orig = this.origin.iata;
    var dest = this.destination.iata;
    var rKey = this.route_key || (orig + "->" + dest);

    var curY = sY;
    var curM = sM;
    var maxIter = 24; // safety cap to prevent infinite loops
    var iter = 0;

    while ((curY < eY || (curY === eY && curM <= eM)) && iter < maxIter) {
        var ym = curY + "-" + (curM < 10 ? "0" + curM : curM);
        var key = {
            year_month: ym,
            origin: orig,
            destination: dest,
            route_key: rKey
        };
        emit(key, {
            active_timetable_services: 1,
            weekly_frequency: weeklyFreq,
            distance_km: dist,
            airlines: [airline]
        });
        curM++;
        if (curM > 12) {
            curM = 1;
            curY++;
        }
        iter++;
    }
}
""")

INDIAN_JOB_D_REDUCER = Code("""
function(key, values) {
    var totalServices = 0;
    var totalWeeklyFreq = 0;
    var dist = 0;
    var airlineMap = {};

    values.forEach(function(v) {
        totalServices += (v.active_timetable_services || 0);
        totalWeeklyFreq += (v.weekly_frequency || 0);
        if (v.distance_km) dist = v.distance_km;
        if (v.airlines) {
            for (var i = 0; i < v.airlines.length; i++) {
                airlineMap[v.airlines[i]] = true;
            }
        }
    });

    return {
        active_timetable_services: totalServices,
        weekly_frequency: totalWeeklyFreq,
        distance_km: dist,
        airlines: Object.keys(airlineMap)
    };
}
""")

INDIAN_JOB_D_FINALIZE = Code("""
function(key, val) {
    var airlineList = val.airlines || [];
    var weeklyFreq = val.weekly_frequency || 0;
    return {
        active_timetable_services: val.active_timetable_services || 0,
        weekly_frequency: weeklyFreq,
        estimated_monthly_departures: Math.round(weeklyFreq * 4.2857),
        distance_km: val.distance_km || 0,
        airlines: airlineList,
        carrier_count: airlineList.length,
        metric_description: "Published schedule services whose approved validity period covers this calendar month. Does not represent operated flight events.",
        data_source: "DGCA_Airline_Timetables_2018_2025"
    };
}
""")


# ============================================================
# JOB E: Indian Airport Connectivity Summary
# Key   : airport code (e.g. "DEL")
# Value : Outgoing/incoming schedules, frequencies, neighbors
# Finalize: out_degree, in_degree, distinct_connections, neighbor_airports
# Output: mr_airport_connectivity_in
# ============================================================
INDIAN_JOB_E_MAPPER = Code("""
function() {
    if (!this.is_route_eligible) return;
    if (this.origin && this.origin.iata && this.destination && this.destination.iata) {
        var weeklyFreq = Number(this.operating_days_count) || 1;
        var orig = this.origin.iata;
        var dest = this.destination.iata;

        // Emit for origin (outgoing schedule service)
        emit(orig, {
            outgoing_schedules: 1,
            incoming_schedules: 0,
            outgoing_weekly_frequency: weeklyFreq,
            incoming_weekly_frequency: 0,
            outgoing_destinations: [dest],
            incoming_origins: []
        });

        // Emit for destination (incoming schedule service)
        emit(dest, {
            outgoing_schedules: 0,
            incoming_schedules: 1,
            outgoing_weekly_frequency: 0,
            incoming_weekly_frequency: weeklyFreq,
            outgoing_destinations: [],
            incoming_origins: [orig]
        });
    }
}
""")

INDIAN_JOB_E_REDUCER = Code("""
function(key, values) {
    var outS = 0;
    var inS = 0;
    var outF = 0;
    var inF = 0;
    var outMap = {};
    var inMap = {};

    values.forEach(function(v) {
        outS += (v.outgoing_schedules || 0);
        inS += (v.incoming_schedules || 0);
        outF += (v.outgoing_weekly_frequency || 0);
        inF += (v.incoming_weekly_frequency || 0);

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
        outgoing_schedules: outS,
        incoming_schedules: inS,
        outgoing_weekly_frequency: outF,
        incoming_weekly_frequency: inF,
        outgoing_destinations: Object.keys(outMap),
        incoming_origins: Object.keys(inMap)
    };
}
""")

INDIAN_JOB_E_FINALIZE = Code("""
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
    var totalSched = (val.outgoing_schedules || 0) + (val.incoming_schedules || 0);
    var totalWeeklyFreq = (val.outgoing_weekly_frequency || 0) + (val.incoming_weekly_frequency || 0);

    return {
        outgoing_schedules: val.outgoing_schedules || 0,
        incoming_schedules: val.incoming_schedules || 0,
        total_schedules: totalSched,
        outgoing_weekly_frequency: val.outgoing_weekly_frequency || 0,
        incoming_weekly_frequency: val.incoming_weekly_frequency || 0,
        total_weekly_frequency: totalWeeklyFreq,
        estimated_monthly_movements: Math.round(totalWeeklyFreq * 4.2857),
        out_degree: outList.length,
        in_degree: inList.length,
        distinct_connections: distinctNeighborList.length,
        neighbor_airports: distinctNeighborList,
        metric_description: "Topological node degree and scheduled service connectivity for Indian domestic airports.",
        data_source: "DGCA_Airline_Timetables_2018_2025"
    };
}
""")

# Standard query filter ensuring only valid scheduled flights are processed
INDIAN_MAPREDUCE_QUERY_FILTER = {
    "is_route_eligible": True
}
