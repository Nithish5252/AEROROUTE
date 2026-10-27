# Phase 6 Live Flight Tracker & ADS-B Integration Report

**Project**: AeroRoute Flight Route Network Intelligence Platform  
**Phase**: Phase 6 -- Live OpenSky Network ADS-B Integration  
**Timestamp**: 2026-10-27  
**Data Provider**: OpenSky Network REST API v2  
**Status**: Completed and Live Verified

---

## 1. Overview & Architecture

Phase 6 integrated live ADS-B flight telemetry into the AeroRoute platform. The tracker connects to the public OpenSky Network API to retrieve aircraft state vectors in real time, filtered by geographical bounding boxes.

### Airspace Bounds:
- **Indian Airspace Scope**:
  - Latitude: `6.0° N` to `37.0° N`
  - Longitude: `68.0° E` to `98.0° E`
  - Covers all Indian FIRs (Delhi, Mumbai, Kolkata, Chennai, and Guwahati).
- **US Airspace Scope**:
  - Latitude: `24.0° N` to `50.0° N`
  - Longitude: `-125.0° W` to `-66.0° W`

---

## 2. API Caching, Rate-Limit Protection & Fallback Resilience

The OpenSky Network enforces anonymous access limits (maximum ~1 request per 10–15 seconds). To ensure responsiveness without rate-limit blocking:
1. **TTL Caching**: Implemented a thread-safe 20-second cache in `src/services/opensky_service.py`. If a new request arrives within the TTL window, cached vectors are returned immediately.
2. **Transparent Status Labeling**:
   - `LIVE ADS-B`: Displayed when live aircraft telemetry is successfully fetched from OpenSky within the active TTL.
   - `SIMULATED / FALLBACK`: Displayed when OpenSky is unreachable, throttled, or returns an empty state vector. Aircraft coordinates and altitudes are then synthesized along known scheduled corridors for visual testing, with explicit badge notification.
3. **FlightRadar24 Situation Badges**:
   - Computes operational status metrics (airspace density, average ground speed, average cruise altitude, airborne vs ground breakdown).

---

## 3. UI Features on Page 8 (`8_Live_Tracker.py`)

- **Live Flight Map**: Plotly Scattergeo plot with directional aircraft chevrons oriented according to true heading (`true_track`), color-coded by altitude bands (FL000 to FL450+).
- **Vertical Altitude HUD Profile**: Displays distribution of aircraft across flight levels.
- **Flight Data Table**: Sortable table of active aircraft with Callsign, ICAO24 transponder code, origin country, true airspeed, barometric altitude, and vertical climb/descent rate.
- **HUD Telemetry Strip**: Displays total airborne aircraft, tracked corridors, and data freshness timestamp in UTC and IST.
