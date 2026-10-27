# ============================================================
# AeroRoute -- Flight Operations Console: Live Airspace Tracker
# File : dashboard/pages/8_->️_Live_Tracker.py
# ============================================================

import sys
from pathlib import Path

# Ensure project root directory is in sys.path
_current = Path(__file__).resolve()
for _parent in [_current] + list(_current.parents):
    if (_parent / "dashboard").is_dir() and (_parent / "config").is_dir():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

import time
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, List
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from dashboard.components.styles import apply_custom_css
from dashboard.components.kpi_cards import render_kpi_strip
from dashboard.services.database import check_connection
from dashboard.services.realtime_service import (
    INDIAN_AIRPORTS,
    INTL_AIRPORTS,
    US_AIRPORTS,
    AIRLINES_DIRECTORY,
    AIRCRAFT_FLEET_SPECS,
    get_live_flights,
    get_delay_summary,
    get_delay_trend,
    get_airport_telemetry,
    simulate_network_disruption,
    get_diurnal_traffic_profile,
    get_opensky_telemetry_meta,
)

# ── Color Palette (Finest AI SaaS Design System) ───────────────────────────
CLR_BG        = "#0C0D12"
CLR_PANEL     = "#171821"
CLR_BORDER    = "#232532"
CLR_ACCENT    = "#FF385C"  # Vibrant Coral brand
CLR_BLUE      = "#FFD5C8"  # Soft Warm Peach
CLR_TEXT      = "#F8FAFC"
CLR_MUTED     = "#94A3B8"
CLR_OK        = "#22C55E"
CLR_WARN      = "#F59E0B"
CLR_DANGER    = "#EF4444"
CLR_PURPLE    = "#A855F7"
CLR_ORANGE    = "#FF5A6E"

# ── FlightRadar24 Situation Indication Color Palette ────────────────────────
FR24_CRUISE    = "#FACC15"  # FlightRadar24 Iconic Yellow (Airborne Cruising)
FR24_CLIMB     = "#10B981"  # Emerald Green (Climbing > 600 fpm)
FR24_DESCEND   = "#EAB308"  # Warm Amber Gold (Descending < -600 fpm)
FR24_DELAYED   = "#F97316"  # Bright Orange (Delayed 15-60 min)
FR24_CRITICAL  = "#EF4444"  # Alert Red (Severe Delay > 60 min)
FR24_EMERGENCY = "#DC2626"  # Crimson Red (Diverted / Squawk 7700)
FR24_GROUND    = "#38BDF8"  # Sky Blue (Taxiing / Boarding / Gate)
FR24_LANDED    = "#A855F7"  # Royal Purple (Touchdown / Landed)

def get_fr24_situation(row: pd.Series) -> Tuple[str, str]:
    """
    Returns (situation_label, hex_color) mimicking FlightRadar24 live tracking rules.
    """
    status = str(row.get("status", "")).upper()
    delay = int(row.get("delay_minutes", 0))
    vert = int(row.get("vertical_speed_fpm", 0))
    sqk = str(row.get("squawk", ""))

    if status == "DIVERTED" or sqk == "7700":
        return "DIVERTED / SQUAWK 7700", FR24_EMERGENCY
    if status == "LANDED":
        return "LANDED", FR24_LANDED
    if status in ["BOARDING", "DEPARTED"]:
        return "GROUND / TAXI", FR24_GROUND
    if delay >= 60:
        return f"CRITICAL DELAY (+{delay}m)", FR24_CRITICAL
    if delay > 0:
        return f"DELAYED (+{delay}m)", FR24_DELAYED
    if vert > 600:
        return "CLIMBING", FR24_CLIMB
    if vert < -600:
        return "DESCENDING", FR24_DESCEND
    return "AIRBORNE / CRUISE", FR24_CRUISE


def _heading_to_cardinal(deg: int) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]

# Severity color map
_SEV_COLOR = {
    "none":     CLR_OK,
    "minor":    CLR_WARN,
    "moderate": CLR_ORANGE,
    "severe":   CLR_DANGER,
}

# Status color map
_STATUS_COLOR = {
    "ON TIME":  FR24_CRUISE,
    "AIRBORNE": FR24_CRUISE,
    "BOARDING": FR24_GROUND,
    "DEPARTED": FR24_GROUND,
    "DELAYED":  FR24_DELAYED,
    "DIVERTED": FR24_EMERGENCY,
    "LANDED":   FR24_LANDED,
}

_RISK_COLOR = {
    "LOW":      CLR_OK,
    "MODERATE": CLR_WARN,
    "HIGH":     CLR_ORANGE,
    "CRITICAL": CLR_DANGER,
}


# ─────────────────────────────────────────────────────────────────────────────
# Chart Builders
# ─────────────────────────────────────────────────────────────────────────────

def _dark_layout(fig: go.Figure, height: int = 340, margin=None) -> go.Figure:
    m = margin or dict(l=16, r=16, t=28, b=16)
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CLR_TEXT, family="Inter, sans-serif", size=11),
        margin=m,
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=CLR_BORDER),
    )
    fig.update_xaxes(gridcolor=CLR_BORDER, showgrid=True, zeroline=False)
    fig.update_yaxes(gridcolor=CLR_BORDER, showgrid=True, zeroline=False)
    return fig


def build_flight_map(
    df: pd.DataFrame,
    airspace: str = "india",
    show_callouts: bool = True,
    show_airports: bool = True,
) -> go.Figure:
    """Builds interactive FlightRadar24-style radar map with directional aircraft chevrons."""
    if df.empty:
        return go.Figure()

    df = df.copy()

    # Compute FlightRadar24 situational tags and colors
    situations = [get_fr24_situation(r) for _, r in df.iterrows()]
    df["situation_label"] = [s[0] for s in situations]
    df["situation_color"] = [s[1] for s in situations]

    # Marker sizing scaled by aircraft capacity category (Superjumbo vs Widebody vs Narrowbody)
    df["marker_size"] = df["capacity"].apply(lambda c: 11 if c < 100 else (14 if c < 260 else 18))

    df["hover"] = df.apply(
        lambda r: (
            f"<b>{r['flight_id']}</b> ({r['callsign']}) · {r['airline']}<br>"
            f"Aircraft: <b>{r['aircraft_model']}</b> · Tail: {r['tail_number']} · Hex: <code>{r['mode_s_hex']}</code><br>"
            f"Corridor: <b>{r['origin_city']} ({r['origin']})</b> to <b>{r['dest_city']} ({r['destination']})</b><br>"
            f"Alt: <b>{r['flight_level']}</b> ({r['vertical_speed_label']}) · Speed: <b>{r['speed_kts']} kts</b> · Track: <b>{r['heading']} deg</b><br>"
            f"Squawk: <b>{r['squawk']}</b> · Sector: <b>{r['atc_sector']}</b><br>"
            f"Situation: <b style='color:{r['situation_color']};'>{r['situation_label']}</b><br>"
            f"Progress: {r['progress_pct']}% · ETA: {r['eta']}<br>"
            + (f"Delay: <b>{r['delay_minutes']} min</b> ({r['delay_cause']})<br>" if r['delay_minutes'] > 0 else "Schedule: <b>On Time</b><br>")
            + f"ML Delay Risk: <b>{r['ml_risk_pct']}%</b> [{r['ml_risk_category']}] · {r['gps_integrity']}"
        ),
        axis=1,
    )

    fig = go.Figure()

    # Airport Hub Radar Beacons (FlightRadar24 ground reference)
    if show_airports:
        if airspace == "india":
            airports_dict = INDIAN_AIRPORTS
        elif airspace == "global":
            airports_dict = INTL_AIRPORTS
        else:
            airports_dict = US_AIRPORTS

        apt_lats = [v["lat"] for v in airports_dict.values()]
        apt_lons = [v["lon"] for v in airports_dict.values()]
        apt_names = [f"<b>{k}</b> · {v['name']}<br>{v['city']}" for k, v in airports_dict.items()]
        apt_codes = list(airports_dict.keys())

        fig.add_trace(go.Scattergeo(
            lat=apt_lats,
            lon=apt_lons,
            mode="markers+text",
            text=apt_codes,
            textposition="top center",
            textfont=dict(size=8, color="#64748B", family="JetBrains Mono, monospace"),
            marker=dict(
                symbol="circle",
                size=5,
                color="#1E3A8A",
                opacity=0.75,
                line=dict(width=1, color="#38BDF8"),
            ),
            hoverinfo="text",
            hovertext=apt_names,
            name="Airports & Hubs",
        ))

    # Directional Aircraft Chevrons with Heading Orientation (FlightRadar24 UI)
    mode_str = "markers+text" if show_callouts else "markers"

    fig.add_trace(go.Scattergeo(
        lat=df["lat"],
        lon=df["lon"],
        ids=df["flight_id"],
        mode=mode_str,
        text=df["flight_id"],
        textposition="bottom right",
        textfont=dict(
            size=9,
            color=df["situation_color"],
            family="JetBrains Mono, monospace",
        ),
        marker=dict(
            symbol="triangle-up",
            angle=df["heading"],
            size=df["marker_size"],
            color=df["situation_color"],
            opacity=0.95,
            line=dict(width=1.2, color="#070E18"),
        ),
        texttemplate="%{text}" if show_callouts else None,
        customdata=df["flight_id"],
        hovertext=df["hover"],
        hovertemplate="%{hovertext}<extra></extra>",
        name="En-Route Aircraft",
    ))


    # Configure map projection based on selected airspace
    if airspace == "india":
        fig.update_geos(
            center=dict(lat=21.5, lon=79.0),
            projection_scale=3.4,
            projection_type="natural earth",
            bgcolor="rgba(0,0,0,0)",
            showland=True, landcolor="#0D1B2A",
            showocean=True, oceancolor="#070E18",
            showcoastlines=True, coastlinecolor="#1E3A5F",
            showlakes=True, lakecolor="#070E18",
            showcountries=True, countrycolor="#25466F",
            showframe=False,
            resolution=50,
        )
    elif airspace == "global":
        fig.update_geos(
            projection_type="natural earth",
            bgcolor="rgba(0,0,0,0)",
            showland=True, landcolor="#0D1B2A",
            showocean=True, oceancolor="#070E18",
            showcoastlines=True, coastlinecolor="#1E3A5F",
            showlakes=True, lakecolor="#070E18",
            showcountries=True, countrycolor="#25466F",
            showframe=False,
            resolution=110,
        )
    else:
        # USA Domestic
        fig.update_geos(
            scope="usa",
            projection_type="albers usa",
            bgcolor="rgba(0,0,0,0)",
            showland=True, landcolor="#0D1B2A",
            showcoastlines=True, coastlinecolor="#1E3A5F",
            showlakes=True, lakecolor="#070E18",
            showcountries=True, countrycolor="#1E3A5F",
            showframe=False,
            resolution=110,
        )

    fig.update_layout(
        height=490,
        paper_bgcolor="rgba(0,0,0,0)",
        geo_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=4, b=0),
        showlegend=False,
    )
    return fig


def build_flight_profile_chart(flight: pd.Series) -> go.Figure:
    """Builds an interactive Plotly Vertical Altitude & Corridor Profile HUD for an aircraft."""
    total_dist = max(float(flight.get("distance_km", 500)), 50.0)
    pct = max(min(float(flight.get("progress_pct", 0.0)), 100.0), 0.0)
    curr_dist = round(total_dist * (pct / 100.0), 1)
    curr_alt = float(flight.get("altitude_ft", 0))
    cruise_alt = max(curr_alt, 12000.0)
    sit_color = flight.get("situation_color", "#38BDF8")

    toc_x = round(total_dist * 0.12, 1)
    tod_x = round(total_dist * 0.85, 1)

    # Waypoints for planned envelope
    planned_x = [0, toc_x, tod_x, total_dist]
    planned_y = [0, cruise_alt, cruise_alt, 0]

    fig = go.Figure()

    # 1. Planned Corridor Envelope
    fig.add_trace(go.Scatter(
        x=planned_x,
        y=planned_y,
        mode="lines",
        line=dict(color="#334155", width=2, dash="dash"),
        fill="tozeroy",
        fillcolor="rgba(15, 23, 42, 0.45)",
        name="Planned Corridor",
        hoverinfo="skip",
    ))

    # 2. Flown Profile segment
    if curr_dist <= toc_x:
        flown_x = [0, curr_dist]
        flown_y = [0, curr_alt]
    elif curr_dist <= tod_x:
        flown_x = [0, toc_x, curr_dist]
        flown_y = [0, cruise_alt, curr_alt]
    else:
        flown_x = [0, toc_x, tod_x, curr_dist]
        flown_y = [0, cruise_alt, cruise_alt, curr_alt]

    fig.add_trace(go.Scatter(
        x=flown_x,
        y=flown_y,
        mode="lines",
        line=dict(color=sit_color, width=3),
        name="Flown Trajectory",
        hoverinfo="skip",
    ))

    # 3. Origin & Destination Waypoints
    fig.add_trace(go.Scatter(
        x=[0, total_dist],
        y=[0, 0],
        mode="markers+text",
        text=[flight.get("origin", "DEP"), flight.get("destination", "ARR")],
        textposition=["top right", "top left"],
        textfont=dict(size=11, color="#94A3B8", family="JetBrains Mono, monospace"),
        marker=dict(size=8, color=["#22D3EE", "#38BDF8"], symbol="diamond"),
        name="Airports",
        hoverinfo="text",
        hovertext=[
            f"<b>{flight.get('origin', 'DEP')}</b><br>{flight.get('origin_city', '')}<br>Departure Waypoint",
            f"<b>{flight.get('destination', 'ARR')}</b><br>{flight.get('dest_city', '')}<br>Arrival Waypoint",
        ],
    ))

    # 4. Current Aircraft Radar Contact Marker
    fig.add_trace(go.Scatter(
        x=[curr_dist],
        y=[curr_alt],
        mode="markers+text",
        text=[f"{flight.get('flight_id', '')}"],
        textposition="top center",
        textfont=dict(size=11, color=sit_color, family="JetBrains Mono, monospace"),
        marker=dict(
            size=14,
            color=sit_color,
            symbol="circle",
            line=dict(width=2.5, color="#FFFFFF"),
        ),
        name="Live Contact",
        hovertemplate=(
            f"<b>{flight.get('flight_id', '')} Live Telemetry</b><br>"
            f"Corridor Position: %{{x:.0f}} km ({pct:.1f}%)<br>"
            f"Altitude: %{{y:,.0f}} ft ({flight.get('flight_level', '')})<br>"
            f"Ground Speed: {flight.get('speed_kts', '')} kts<br>"
            f"Vertical Rate: {flight.get('vertical_speed_label', 'Level')}<extra></extra>"
        ),
    ))

    # Dynamic ceiling
    y_max = max(cruise_alt * 1.25, 42000.0)

    fig.update_layout(
        height=210,
        margin=dict(l=45, r=25, t=28, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11, 17, 32, 0.7)",
        showlegend=False,
        xaxis=dict(
            title=dict(text="Corridor Distance (km)", font=dict(size=10, color="#64748B")),
            range=[-20, total_dist + 20],
            showgrid=True,
            gridcolor="#1E293B",
            zeroline=False,
            tickfont=dict(size=9, color="#64748B"),
        ),
        yaxis=dict(
            title=dict(text="Altitude (ft)", font=dict(size=10, color="#64748B")),
            range=[-1000, y_max],
            showgrid=True,
            gridcolor="#1E293B",
            zeroline=True,
            zerolinecolor="#334155",
            tickvals=[0, 10000, 20000, 30000, 40000],
            ticktext=["GND", "FL100", "FL200", "FL300", "FL400"],
            tickfont=dict(size=9, color="#64748B"),
        ),
    )
    return fig


def build_delay_cause_bar(by_cause_df: pd.DataFrame) -> go.Figure:
    if by_cause_df is None or by_cause_df.empty:
        return go.Figure()

    colors = [CLR_DANGER, CLR_ORANGE, CLR_WARN, CLR_ACCENT, CLR_PURPLE]
    fig = go.Figure(go.Bar(
        x=by_cause_df["flights"],
        y=by_cause_df["delay_cause"],
        orientation="h",
        marker=dict(color=colors[:len(by_cause_df)], line=dict(width=0)),
        text=by_cause_df["flights"].astype(str) + " flt",
        textposition="auto",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Delayed Flights: %{x}<br>"
            "Avg Delay: %{customdata:.0f} min<extra></extra>"
        ),
        customdata=by_cause_df["avg_delay"],
    ))
    fig.update_layout(
        title=dict(text="Active Delays by Primary Root Cause", font=dict(size=12, color=CLR_MUTED), x=0),
        yaxis=dict(autorange="reversed"),
    )
    return _dark_layout(fig, height=270)


def build_ml_risk_donut(df: pd.DataFrame) -> go.Figure:
    """Donut chart showing Predictive ML Delay Risk distribution across fleet."""
    if df.empty:
        return go.Figure()

    risk_counts = df["ml_risk_category"].value_counts().reset_index()
    risk_counts.columns = ["category", "count"]
    colors = [_RISK_COLOR.get(cat, CLR_MUTED) for cat in risk_counts["category"]]

    fig = go.Figure(go.Pie(
        labels=risk_counts["category"],
        values=risk_counts["count"],
        hole=0.62,
        marker=dict(colors=colors, line=dict(color=CLR_PANEL, width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label} Risk</b>: %{value} flights<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>ML RISK</b><br><span style='font-size:10px'>Scored</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=13, color=CLR_TEXT),
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", font=dict(size=10)),
        title=dict(text="Predictive ML Delay Risk Profile", font=dict(size=12, color=CLR_MUTED), x=0),
        margin=dict(l=0, r=0, t=28, b=0),
    )
    return _dark_layout(fig, height=270)


def build_status_donut(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()

    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    colors = [_STATUS_COLOR.get(s, CLR_MUTED) for s in status_counts["status"]]

    fig = go.Figure(go.Pie(
        labels=status_counts["status"],
        values=status_counts["count"],
        hole=0.60,
        marker=dict(colors=colors, line=dict(color=CLR_PANEL, width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b>: %{value} flights<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{len(df)}</b><br><span style='font-size:10px'>Tracked</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=15, color=CLR_TEXT),
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", font=dict(size=10)),
        title=dict(text="Airborne & Ground Fleet Status", font=dict(size=12, color=CLR_MUTED), x=0),
        margin=dict(l=0, r=0, t=28, b=0),
    )
    return _dark_layout(fig, height=270)


def build_delay_severity_gauge(delay_rate: float) -> go.Figure:
    color = CLR_OK if delay_rate < 15 else (CLR_WARN if delay_rate < 25 else CLR_DANGER)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=delay_rate,
        delta={"reference": 20, "increasing": {"color": CLR_DANGER}, "decreasing": {"color": CLR_OK}},
        number={"suffix": "%", "font": {"size": 30, "color": CLR_TEXT}},
        gauge={
            "axis": {"range": [0, 50], "tickwidth": 1, "tickcolor": CLR_MUTED},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": CLR_PANEL,
            "borderwidth": 0,
            "steps": [
                {"range": [0, 15],  "color": "rgba(34,197,94,0.12)"},
                {"range": [15, 25], "color": "rgba(245,158,11,0.12)"},
                {"range": [25, 50], "color": "rgba(239,68,68,0.12)"},
            ],
            "threshold": {"line": {"color": CLR_DANGER, "width": 2}, "thickness": 0.75, "value": 20},
        },
    ))
    fig.update_layout(
        height=210,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CLR_TEXT, family="Inter, sans-serif"),
        margin=dict(l=20, r=20, t=35, b=0),
    )
    return fig


def build_delay_trend_chart(trend_df: pd.DataFrame) -> go.Figure:
    if trend_df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend_df["timestamp"],
        y=trend_df["delay_rate_pct"],
        mode="lines+markers",
        name="Delay Rate (%)",
        line=dict(color=CLR_WARN, width=2.5),
        marker=dict(size=5, color=CLR_WARN),
        hovertemplate="Time: %{x}<br>Delay Rate: <b>%{y}%</b><extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=trend_df["timestamp"],
        y=trend_df["airborne_count"],
        name="Airborne Flights",
        marker=dict(color="rgba(34,211,238,0.25)", line=dict(color=CLR_ACCENT, width=1)),
        yaxis="y2",
        hovertemplate="Time: %{x}<br>Airborne: <b>%{y}</b><extra></extra>",
    ))
    fig.update_layout(
        yaxis2=dict(
            title=dict(text="Airborne Count", font=dict(color=CLR_ACCENT, size=10)),
            tickfont=dict(color=CLR_ACCENT, size=9),
            overlaying="y",
            side="right",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=dict(text="Rolling Delay & Traffic Trend (Last 60 Min)", font=dict(size=12, color=CLR_MUTED), x=0),
    )
    return _dark_layout(fig, height=270)


# ─────────────────────────────────────────────────────────────────────────────
# UI HTML Component Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pill(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}22; color:{color}; border:1px solid {color}55; '
        f'border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:600;">{text}</span>'
    )


def _flight_row_html(row: pd.Series) -> str:
    sev_col = _SEV_COLOR.get(row["delay_severity"], CLR_MUTED)
    risk_col = _RISK_COLOR.get(row["ml_risk_category"], CLR_MUTED)
    sit_label, sit_col = get_fr24_situation(row)
    heading = int(row.get("heading", 0))

    delay_txt = (
        f"<b style='color:{sev_col}'>{row['delay_minutes']} min</b><br><span style='font-size:0.68rem; color:{CLR_MUTED};'>{row['delay_cause']}</span>"
        if row["delay_minutes"] > 0
        else "<span style='color:#22C55E; font-weight:600;'>On Time</span>"
    )

    prog_bar = (
        f'<div style="background:{CLR_BORDER};border-radius:2px;height:4px;margin-top:3px;">'
        f'<div style="background:{sit_col};width:{row["progress_pct"]}%;height:4px;border-radius:2px;"></div>'
        f'</div>'
    )

    # FlightRadar24 situational aircraft icon rotated to true heading compass track
    plane_icon = (
        f'<div style="width:28px; height:28px; border-radius:50%; background:{sit_col}22; '
        f'border:1.5px solid {sit_col}99; display:flex; align-items:center; justify-content:center; flex-shrink:0;" '
        f'title="{sit_label} · Heading {heading}°">'
        f'<span style="color:{sit_col}; font-size:1.05rem; display:inline-block; '
        f'transform:rotate({heading - 45}deg); line-height:1;">-></span>'
        f'</div>'
    )

    return f"""
    <div style="display:flex; align-items:center; gap:10px; padding:8px 10px;
                border-bottom:1px solid {CLR_BORDER}; font-size:0.79rem;">
        <div style="min-width:145px; display:flex; align-items:center; gap:8px;">
            {plane_icon}
            <div>
                <span style="color:{CLR_TEXT}; font-weight:700; font-family:'JetBrains Mono',monospace;">{row['flight_id']}</span>
                <span style="background:#1E293B; color:#38BDF8; font-size:0.65rem; padding:1px 4px; border-radius:3px; margin-left:3px;">{row['mode_s_hex']}</span><br>
                <span style="color:{CLR_MUTED}; font-size:0.70rem;">{row['airline']}</span>
            </div>
        </div>
        <div style="min-width:130px;">
            <span style="color:#CBD5E1; font-weight:600;">{row['aircraft_model']}</span><br>
            <span style="color:{CLR_MUTED}; font-size:0.69rem;">{row['tail_number']} · {row['capacity']} pax</span>
        </div>
        <div style="min-width:160px;">
            <span style="color:{CLR_ACCENT}; font-weight:700;">{row['origin']}</span>
            <span style="color:{sit_col}; font-weight:700; margin:0 4px;">-></span>
            <span style="color:{CLR_BLUE}; font-weight:700;">{row['destination']}</span><br>
            <span style="color:{CLR_MUTED}; font-size:0.69rem;">{row['origin_city']} → {row['dest_city']}</span>
        </div>
        <div style="min-width:90px;">
            <span style="color:#F1F5F9; font-weight:700; font-family:'JetBrains Mono',monospace;">{row['flight_level']}</span><br>
            <span style="color:{CLR_MUTED}; font-size:0.68rem;">{row['vertical_speed_label']}</span>
        </div>
        <div style="min-width:95px;">
            <span style="color:#38BDF8; font-family:'JetBrains Mono',monospace; font-weight:600;">SQK {row['squawk']}</span><br>
            <span style="color:{CLR_MUTED}; font-size:0.66rem;">{row['speed_kts']} kts · {heading}°</span>
        </div>
        <div style="min-width:120px;">{_pill(sit_label, sit_col)}</div>
        <div style="min-width:105px;">
            {_pill(f"{row['ml_risk_pct']}% {row['ml_risk_category']}", risk_col)}<br>
            <span style="color:{CLR_MUTED}; font-size:0.66rem;">{row['ml_risk_factor']}</span>
        </div>
        <div style="min-width:105px;">{delay_txt}</div>
        <div style="flex:1; min-width:110px;">
            {prog_bar}
            <span style="color:{CLR_MUTED}; font-size:0.68rem;">{row['progress_pct']}% · ETA {row['eta']}</span>
        </div>
    </div>
    """


def render_flight_board(df: pd.DataFrame, max_rows: int = 25):
    """Render a live flight board table."""
    if df.empty:
        st.info("No flight records match the selected filters.")
        return

    header = f"""
    <div style="background:{CLR_PANEL}; border:1px solid {CLR_BORDER}; border-radius:8px; overflow:hidden; margin-top:8px;">
        <div style="display:flex; gap:10px; padding:8px 10px; background:{CLR_BG};
                    border-bottom:1px solid {CLR_BORDER}; font-size:0.71rem;
                    color:{CLR_MUTED}; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;">
            <div style="min-width:145px;">Flight / Mode-S</div>
            <div style="min-width:130px;">Aircraft Equipment</div>
            <div style="min-width:160px;">Corridor</div>
            <div style="min-width:90px;">Flight Level</div>
            <div style="min-width:95px;">Squawk / Speed</div>
            <div style="min-width:120px;">FR24 Situation</div>
            <div style="min-width:105px;">ML Delay Risk</div>
            <div style="min-width:105px;">Delay</div>
            <div style="flex:1">Flight Progress / ETA</div>
        </div>
    """
    rows_html = "".join(_flight_row_html(row) for _, row in df.head(max_rows).iterrows())
    st.markdown(header + rows_html + "</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main Page Application
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Live Airspace Tracker | AeroRoute",
                layout="wide",
    )
    apply_custom_css()

    # ── Sidebar Controls ──────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            f'<div style="color:{CLR_ACCENT}; font-weight:700; font-size:0.92rem; '
            f'text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;">Airspace & Fleet Command</div>',
            unsafe_allow_html=True,
        )

        airspace = st.selectbox(
            "Airspace Jurisdiction",
            options=["india", "global", "usa"],
            format_func=lambda x: {
                "india": "Indian Airspace & Gulf (DGCA / AAI)",
                "global": "Global Intercontinental Hubs",
                "usa": "US Domestic & Transatlantic",
            }[x],
            index=0,
        )

        n_flights = st.slider("Simulated Fleet Size", 20, 100, 60, 5)

        st.markdown("---")
        st.markdown(
            f'<div style="color:{CLR_TEXT}; font-weight:600; font-size:0.8rem; margin-bottom:6px;">'
            f'24-Hour Diurnal Wave Time Scrubber</div>',
            unsafe_allow_html=True,
        )
        sim_hour = st.slider("Operational Time (Hour UTC/IST)", 0, 23, 14, 1, format="%02d:00")
        wave_profile = get_diurnal_traffic_profile(sim_hour)
        st.caption(f"{wave_profile['wave_name']}<br><span style='color:{CLR_MUTED}'>{wave_profile['description']}</span>", unsafe_allow_html=True)

        st.markdown("---")
        auto_refresh = st.toggle("Auto-Refresh Telemetry", value=False)
        refresh_interval = st.selectbox("Refresh Rate", [30, 60, 120], index=1, format_func=lambda x: f"{x}s")

        st.markdown("---")
        st.markdown(
            f'<div style="color:{CLR_TEXT}; font-weight:600; font-size:0.8rem; margin-bottom:6px;">Flight Filters</div>',
            unsafe_allow_html=True,
        )
        filter_status = st.multiselect(
            "Filter by Status",
            ["ON TIME", "DELAYED", "BOARDING", "DEPARTED", "AIRBORNE", "LANDED", "DIVERTED"],
            default=[],
        )
        filter_risk = st.multiselect(
            "Filter by ML Risk",
            ["LOW", "MODERATE", "HIGH", "CRITICAL"],
            default=[],
        )
        min_delay = st.slider("Min Delay Filter (min)", 0, 180, 0, 5)
        sort_by = st.selectbox("Sort Flight Board By", ["delay_minutes", "ml_risk_pct", "flight_id", "progress_pct", "status"])

        st.markdown("---")
        st.markdown(
            f'<div style="color:{CLR_TEXT}; font-weight:600; font-size:0.8rem; margin-bottom:6px;">Radar Display Settings</div>',
            unsafe_allow_html=True,
        )
        show_callouts = st.toggle("Show Aircraft Callsigns on Radar", value=True)
        show_airports = st.toggle("Show Airport Hubs on Radar", value=True)

    # ── Page Header ───────────────────────────────────────────────────────
    airspace_label = {
        "india": "Indian Subcontinent & Gulf Corridors",
        "global": "Global Intercontinental Network",
        "usa": "US Domestic Network",
    }[airspace]

    st.markdown(
        f"""
        <div style="margin-top:6px; margin-bottom:14px;">
            <div class="page-title">
                <span>8. Live Airspace Tracker & Flight Delay Analytics</span>
                <span class="status-pill status-healthy">{airspace_label}</span>
            </div>
            <div class="page-subtitle">
                Real-time aircraft positions, airline fleet equipment, predictive ML delay risk scoring,
                live airport radar telemetry, and hub disruption resilience analysis.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── OpenSky Live Telemetry Status Banner ──────────────────────────────
    try:
        telemetry_meta = get_opensky_telemetry_meta()
        is_live_feed = telemetry_meta.get("is_live", True)
        feed_source = telemetry_meta.get("source", "OpenSky Network Live ADS-B")
        live_aircraft = telemetry_meta.get("live_aircraft_count", 0)
        status_pill_type = "healthy" if is_live_feed else "warning"
        status_label = "Live ADS-B Stream" if is_live_feed else "Cached / Fallback Telemetry"

        st.markdown(
            f"""
            <div style="background:#171821; border:1px solid #232532; border-left:4px solid {'#22C55E' if is_live_feed else '#F59E0B'}; border-radius:14px; padding:12px 18px; margin-bottom:18px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:{'#22C55E' if is_live_feed else '#F59E0B'}; box-shadow:0 0 8px {'#22C55E' if is_live_feed else '#F59E0B'};"></span>
                        <span style="color:#F8FAFC; font-weight:700; font-size:0.85rem;">{feed_source}</span>
                        <span style="background:{'rgba(34,197,94,0.12)' if is_live_feed else 'rgba(245,158,11,0.12)'}; color:{'#22C55E' if is_live_feed else '#F59E0B'}; border:1px solid {'rgba(34,197,94,0.25)' if is_live_feed else 'rgba(245,158,11,0.25)'}; font-size:0.70rem; font-weight:700; padding:2px 8px; border-radius:8px;">{status_label}</span>
                    </div>
                    <div style="color:#94A3B8; font-size:0.75rem;">
                        Radar Envelopes: <b style="color:#F8FAFC;">6.0°N–37.0°N, 68.0°E–98.0°E (India)</b> &nbsp;|&nbsp; Active Aircraft: <b style="color:#F8FAFC;">{live_aircraft}</b>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    # ── Load Snapshot Data ────────────────────────────────────────────────
    with st.spinner("Acquiring real-time airspace telemetry snapshot…"):
        flights_df = get_live_flights(
            airspace=airspace,
            n_flights=n_flights,
            time_hour=sim_hour,
            time_minute=30,
        )

    summary = get_delay_summary(flights_df)
    trend_df = get_delay_trend(n_snapshots=12, airspace=airspace)

    # Apply filters
    view_df = flights_df.copy()
    if filter_status:
        view_df = view_df[view_df["status"].isin(filter_status)]
    if filter_risk:
        view_df = view_df[view_df["ml_risk_category"].isin(filter_risk)]
    if min_delay > 0:
        view_df = view_df[view_df["delay_minutes"] >= min_delay]

    view_df = view_df.sort_values(sort_by, ascending=(sort_by not in ["delay_minutes", "ml_risk_pct"])).reset_index(drop=True)

    # ── Top KPI Strip ─────────────────────────────────────────────────────
    delay_rate = summary.get("delay_rate_pct", 0)
    dr_badge, dr_color = (
        ("Optimal", "healthy") if delay_rate < 15
        else (("Elevated", "warning") if delay_rate < 25 else ("Critical", "failed"))
    )

    high_risk_count = len(flights_df[flights_df["ml_risk_category"].isin(["HIGH", "CRITICAL"])])

    kpi_cards = [
        {
            "title": "Tracked Aircraft",
            "value": summary.get("total_flights", 0),
            "subtitle": f"{wave_profile['wave_name'][:18]}...",
            "badge": "Active Fleet",
            "badge_color": "cyan",
        },
        {
            "title": "Airborne Fleet",
            "value": len(flights_df[flights_df["status"].isin(["AIRBORNE", "DEPARTED", "BOARDING"])]),
            "subtitle": "En-route or in departure queue",
            "badge": "In Flight",
            "badge_color": "healthy",
        },
        {
            "title": "Network Delay Rate",
            "value": f"{delay_rate}%",
            "subtitle": f"{summary.get('delayed_flights', 0)} delayed aircraft",
            "badge": dr_badge,
            "badge_color": dr_color,
        },
        {
            "title": "Avg Delay Incurred",
            "value": f"{summary.get('avg_delay_minutes', 0)} min" if summary.get("avg_delay_minutes", 0) > 0 else "0 min",
            "subtitle": "Among delayed aircraft only",
            "badge": "Network Mean",
            "badge_color": "warning" if summary.get("avg_delay_minutes", 0) > 30 else "cyan",
        },
        {
            "title": "Predictive ML Risk Alert",
            "value": high_risk_count,
            "subtitle": "Flights flagged High/Critical delay risk",
            "badge": "ML Guard",
            "badge_color": "failed" if high_risk_count > 5 else "healthy",
        },
    ]
    render_kpi_strip(kpi_cards)

    # ── Main Tabs for Core Modules ─────────────────────────────────────────
    tab_map, tab_radar, tab_disrupt, tab_analytics = st.tabs([
        "Live Airspace Radar & Map",
        "Airport Terminal Telemetry HUD",
        "Hub Disruption Resilience Simulator",
        "Delay Root Cause & ML Analytics",
    ])

    # ─────────────────────────────────────────────────────────────────────
    # TAB 1: Live Airspace Radar & Map
    # ─────────────────────────────────────────────────────────────────────
    with tab_map:
        # FlightRadar24 Situational Legend
        legend_items = [
            ("CRUISE (ON TIME)", FR24_CRUISE),
            ("CLIMBING (>600 fpm)", FR24_CLIMB),
            ("DESCENDING (<-600 fpm)", FR24_DESCEND),
            ("DELAYED (<60m)", FR24_DELAYED),
            ("CRITICAL DELAY (≥60m)", FR24_CRITICAL),
            ("GROUND / TAXI", FR24_GROUND),
            ("LANDED", FR24_LANDED),
            ("DIVERTED / 7700", FR24_EMERGENCY),
        ]
        legend_html = '<div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:10px; font-size:0.75rem; background:#0F172A; padding:8px 12px; border-radius:6px; border:1px solid #1E293B;">'
        for label, color in legend_items:
            legend_html += (
                f'<div style="display:flex; align-items:center; gap:5px;">'
                f'<span style="color:{color}; font-size:0.80rem; font-weight:700;">●</span>'
                f'<span style="color:#E2E8F0; font-weight:500;">{label}</span></div>'
            )
        legend_html += (
            f'<div style="margin-left:auto; color:#94A3B8; font-size:0.72rem;">'
            f'Aircraft chevrons oriented to True Heading (0°–360°) · Size indicates Widebody vs Narrowbody</div>'
        )
        legend_html += "</div>"
        st.markdown(legend_html, unsafe_allow_html=True)

        map_col, gauge_col = st.columns([3, 1])
        with map_col:
            fig_map = build_flight_map(
                view_df,
                airspace=airspace,
                show_callouts=show_callouts,
                show_airports=show_airports,
            )
            map_event = st.plotly_chart(
                fig_map,
                use_container_width=True,
                on_select="rerun",
                selection_mode="points",
                key="airspace_radar_map",
                config={"displayModeBar": False},
            )

        with gauge_col:
            st.markdown(
                f'<div style="color:{CLR_MUTED}; font-size:0.75rem; font-weight:600; '
                f'text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;">Network Congestion Gauge</div>',
                unsafe_allow_html=True,
            )
            fig_gauge = build_delay_severity_gauge(delay_rate)
            st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})

            fig_donut = build_status_donut(flights_df)
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})

        # ── Reactive Aircraft Telemetry State Management ─────────────────
        if not view_df.empty:
            fl_options = view_df["flight_id"].tolist()

            # Ensure valid session state for selected flight
            if "selected_flight_id" not in st.session_state or st.session_state["selected_flight_id"] not in fl_options:
                st.session_state["selected_flight_id"] = fl_options[0]

            # Method 1: Process Map Point Selection
            if map_event and hasattr(map_event, "selection") and map_event.selection:
                sel_pts = getattr(map_event.selection, "points", None) or map_event.selection.get("points", [])
                if sel_pts:
                    pt_info = sel_pts[0]
                    clicked_id = pt_info.get("id") or pt_info.get("customdata")
                    if isinstance(clicked_id, list):
                        clicked_id = clicked_id[0] if clicked_id else None
                    if clicked_id and str(clicked_id) in fl_options:
                        if st.session_state["selected_flight_id"] != str(clicked_id):
                            st.session_state["selected_flight_id"] = str(clicked_id)
                            st.session_state["flight_selector_dropdown"] = str(clicked_id)
                            st.rerun()

            st.markdown(
                f'<div style="color:{CLR_TEXT}; font-weight:700; font-size:0.9rem; '
                f'text-transform:uppercase; letter-spacing:0.05em; margin-top:14px; margin-bottom:6px;">'
                f'Live Aircraft Telemetry Inspector</div>',
                unsafe_allow_html=True,
            )

            # Method 2: Tactical Quick-Lock Preset Buttons
            st.caption("Quick-Lock Radar Shortcuts: Click any button below to instantly lock the radar feed onto that target:")
            ql_c1, ql_c2, ql_c3, ql_c4, ql_c5 = st.columns(5)
            with ql_c1:
                # Emergency / 7700 / Diverted
                emerg_df = view_df[view_df["status"].isin(["DIVERTED", "EMERGENCY"]) | (view_df["squawk"] == "7700") | (view_df["delay_minutes"] >= 90)]
                emerg_target = emerg_df["flight_id"].iloc[0] if not emerg_df.empty else fl_options[0]
                if st.button("Diverted / 7700", use_container_width=True, key="ql_emerg", help=f"Lock to {emerg_target}"):
                    st.session_state["selected_flight_id"] = emerg_target
                    st.session_state["flight_selector_dropdown"] = emerg_target
                    st.rerun()

            with ql_c2:
                # Highest Delayed Flight
                max_del_df = view_df.sort_values(by="delay_minutes", ascending=False)
                max_del_target = max_del_df["flight_id"].iloc[0] if not max_del_df.empty else fl_options[0]
                if st.button("Highest Delay", use_container_width=True, key="ql_delay", help=f"Lock to {max_del_target}"):
                    st.session_state["selected_flight_id"] = max_del_target
                    st.session_state["flight_selector_dropdown"] = max_del_target
                    st.rerun()

            with ql_c3:
                # Widebody Twin-Aisle Flagship
                wb_df = view_df[view_df["aircraft_category"].str.contains("Widebody", na=False)]
                wb_target = wb_df["flight_id"].iloc[0] if not wb_df.empty else fl_options[0]
                if st.button("Widebody Flagship", use_container_width=True, key="ql_widebody", help=f"Lock to {wb_target}"):
                    st.session_state["selected_flight_id"] = wb_target
                    st.session_state["flight_selector_dropdown"] = wb_target
                    st.rerun()

            with ql_c4:
                # Fastest Ground Speed
                speed_df = view_df.sort_values(by="speed_kts", ascending=False)
                speed_target = speed_df["flight_id"].iloc[0] if not speed_df.empty else fl_options[0]
                if st.button("Top Speed", use_container_width=True, key="ql_speed", help=f"Lock to {speed_target}"):
                    st.session_state["selected_flight_id"] = speed_target
                    st.session_state["flight_selector_dropdown"] = speed_target
                    st.rerun()

            with ql_c5:
                # Highest Cruise FL
                alt_df = view_df.sort_values(by="altitude_ft", ascending=False)
                alt_target = alt_df["flight_id"].iloc[0] if not alt_df.empty else fl_options[0]
                if st.button("Top Cruise FL", use_container_width=True, key="ql_alt", help=f"Lock to {alt_target}"):
                    st.session_state["selected_flight_id"] = alt_target
                    st.session_state["flight_selector_dropdown"] = alt_target
                    st.rerun()

            # Method 3: Synchronized Selectbox Dropdown with State Callback
            def _on_flight_select():
                val = st.session_state.get("flight_selector_dropdown")
                if val and val in fl_options:
                    st.session_state["selected_flight_id"] = val

            curr_sel = st.session_state.get("selected_flight_id", fl_options[0])
            sel_idx = fl_options.index(curr_sel) if curr_sel in fl_options else 0

            st.selectbox(
                "Select Aircraft to Lock On Radar & Telemetry Feed",
                fl_options,
                index=sel_idx,
                key="flight_selector_dropdown",
                on_change=_on_flight_select,
                format_func=lambda x: f"{x} - {view_df.loc[view_df['flight_id']==x, 'airline'].values[0]} ({view_df.loc[view_df['flight_id']==x, 'origin'].values[0]} -> {view_df.loc[view_df['flight_id']==x, 'destination'].values[0]}) [{view_df.loc[view_df['flight_id']==x, 'aircraft_model'].values[0]}]",
                label_visibility="collapsed",
            )

            # Retrieve active locked flight
            active_id = st.session_state.get("selected_flight_id", fl_options[0])
            sel_matches = view_df[view_df["flight_id"] == active_id]
            sel_flight = sel_matches.iloc[0] if not sel_matches.empty else view_df.iloc[0]

            sit_label, sit_col = get_fr24_situation(sel_flight)
            h_deg = int(sel_flight.get("heading", 0))

            dist_total = float(sel_flight["distance_km"])
            pct = float(sel_flight["progress_pct"])
            dist_covered = round(dist_total * (pct / 100.0), 1)
            dist_remaining = max(round(dist_total - dist_covered, 1), 0.0)

            duration_min = float(sel_flight.get("flight_duration_min", max(round((dist_total / 800.0) * 60, 0), 25)))
            elapsed_min = int(duration_min * (pct / 100.0))
            remaining_min = max(int(duration_min - elapsed_min), 0)

            std_val = sel_flight.get("std", sel_flight.get("departed_at", "—"))
            atd_val = sel_flight.get("atd", sel_flight.get("departed_at", "—"))
            sta_val = sel_flight.get("sta", sel_flight.get("eta", "—"))
            eta_val = sel_flight.get("eta", "—")
            delay_m = int(sel_flight.get("delay_minutes", 0))

            cardinal = _heading_to_cardinal(h_deg)
            mach_spd = round(float(sel_flight["speed_kts"]) / 573.8, 2)
            speed_kmh = int(float(sel_flight["speed_kts"]) * 1.852)
            gps_str = str(sel_flight.get("gps_integrity", "NACp: 9 (EPU < 30m)"))

            vert_label = str(sel_flight.get("vertical_speed_label", "Level (Cruise)"))
            vert_arrow = (
                "▲ " if "Climb" in vert_label
                else ("▼ " if "Descend" in vert_label else "━ ")
            )

            # Method 4: Modern Native Streamlit UI + Plotly Altitude Profile HUD
            with st.container(border=True):
                # ── Header Ribbon ──
                head_c1, head_c2 = st.columns([3, 1])
                with head_c1:
                    st.markdown(
                        f"""
                        <div style="display:flex; align-items:center; gap:12px;">
                            <div style="width:46px; height:46px; border-radius:50%; background:{sit_col}22; border:2px solid {sit_col}; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px {sit_col}55;">
                                <span style="color:{sit_col}; font-size:1.7rem; transform:rotate({h_deg - 45}deg); display:inline-block; line-height:1;">-></span>
                            </div>
                            <div>
                                <div style="font-size:1.35rem; font-weight:800; color:{CLR_TEXT}; font-family:'JetBrains Mono',monospace;">
                                    {sel_flight['flight_id']} <span style="font-size:0.92rem; color:{CLR_MUTED}; font-weight:500;">({sel_flight['callsign']})</span>
                                </div>
                                <div style="font-size:0.76rem; color:{CLR_MUTED}; margin-top:2px;">
                                    {sel_flight['airline']} · Tail: <code style="color:#F1F5F9;">{sel_flight['tail_number']}</code> · Mode-S: <code style="color:#38BDF8;">{sel_flight['mode_s_hex']}</code>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with head_c2:
                    st.markdown(
                        f"""
                        <div style="text-align:right;">
                            {_pill(sit_label, sit_col)}
                            <div style="font-size:0.74rem; color:{CLR_MUTED}; margin-top:6px;">
                                Squawk: <b style="color:#38BDF8; font-family:'JetBrains Mono',monospace;">{sel_flight['squawk']}</b> · Sector: {sel_flight['atc_sector']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.divider()

                # ── Corridor Waypoints & Vertical Altitude Profile HUD ──
                r_col1, r_col2, r_col3 = st.columns([1, 2, 1])
                with r_col1:
                    st.markdown(
                        f"""
                        <div style="text-align:left;">
                            <div style="font-size:1.8rem; font-weight:800; color:{CLR_ACCENT}; font-family:'JetBrains Mono',monospace; line-height:1;">{sel_flight['origin']}</div>
                            <div style="font-size:0.82rem; color:#F1F5F9; font-weight:600; margin-top:3px;">{sel_flight['origin_city']}</div>
                            <div style="font-size:0.72rem; color:{CLR_MUTED}; margin-top:6px; line-height:1.5;">
                                STD: <span style="color:#94A3B8;">{std_val}</span><br>
                                ATD: <span style="color:{'#F97316' if delay_m > 0 else '#22C55E'}; font-weight:600;">{atd_val}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with r_col2:
                    st.markdown(
                        f"""
                        <div style="text-align:center;">
                            <span style="color:{sit_col}; font-weight:700; font-size:0.82rem;">-> {sel_flight['aircraft_model']}</span>
                            <span style="color:{CLR_MUTED}; font-size:0.72rem;"> · {sel_flight['aircraft_category']} · {sel_flight['capacity']} seats</span>
                            <div style="font-size:0.72rem; color:{CLR_MUTED}; margin-top:4px;">
                                <b>{dist_covered} km</b> ({pct}%) flown · <span style="color:#CBD5E1; font-weight:600;">{elapsed_min}m elapsed, {remaining_min}m left</span> · <b>{dist_remaining} km</b> remaining
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with r_col3:
                    st.markdown(
                        f"""
                        <div style="text-align:right;">
                            <div style="font-size:1.8rem; font-weight:800; color:{CLR_BLUE}; font-family:'JetBrains Mono',monospace; line-height:1;">{sel_flight['destination']}</div>
                            <div style="font-size:0.82rem; color:#F1F5F9; font-weight:600; margin-top:3px;">{sel_flight['dest_city']}</div>
                            <div style="font-size:0.72rem; color:{CLR_MUTED}; margin-top:6px; line-height:1.5;">
                                STA: <span style="color:#94A3B8; {('text-decoration:line-through;' if delay_m > 0 else '')}">{sta_val}</span><br>
                                ETA: <span style="color:{sit_col}; font-weight:700;">{eta_val}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Embedded Plotly Vertical Profile HUD (Interactive & 100% reactive)
                fig_profile = build_flight_profile_chart(sel_flight)
                st.plotly_chart(fig_profile, use_container_width=True, config={"displayModeBar": False})

                # ── 5 Native Telemetry Instrument Readouts ──
                m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
                with m_c1:
                    st.metric(
                        label="ALTITUDE & V-RATE",
                        value=f"{sel_flight['flight_level']}",
                        delta=f"{vert_arrow}{vert_label}",
                        delta_color="normal" if "Climb" in vert_label else ("inverse" if "Descend" in vert_label else "off"),
                        help="Barometric Flight Level (pressure altitude standard 1013.25 hPa) and vertical speed climb/descent rate.",
                    )
                with m_c2:
                    st.metric(
                        label="GROUND SPEED",
                        value=f"{sel_flight['speed_kts']} kts",
                        delta=f"~{speed_kmh} km/h · M{mach_spd}",
                        delta_color="off",
                        help="Calibrated ADS-B ground speed in knots, km/h equivalent, and estimated Mach number.",
                    )
                with m_c3:
                    st.metric(
                        label="TRUE TRACK",
                        value=f" {h_deg}° {cardinal}",
                        delta="GPS Locked",
                        delta_color="normal",
                        help=f"True magnetic compass ground track and GNSS navigation integrity: {gps_str}.",
                    )
                with m_c4:
                    if delay_m == 0:
                        st.metric(label="SCHEDULE STATUS", value="ON TIME", delta="Operating On Schedule", delta_color="normal")
                    else:
                        st.metric(label="SCHEDULE STATUS", value=f"+{delay_m} MIN DELAY", delta=f"{sel_flight['delay_cause']}", delta_color="inverse")
                with m_c5:
                    st.metric(
                        label="PREDICTIVE ML RISK",
                        value=f"{sel_flight['ml_risk_pct']}% [{sel_flight['ml_risk_category']}]",
                        delta=sel_flight["ml_risk_factor"],
                        delta_color="inverse" if sel_flight["ml_risk_category"] in ["HIGH", "CRITICAL"] else "normal",
                        help="XGBoost & Random Forest multi-factor delay risk inference trained on historical corridor operations.",
                    )

                # ── Real-Time ADS-B Transponder & Avionics Matrix ──
                with st.expander(" Real-Time ADS-B Transponder & Flight Physics Specification", expanded=False):
                    t_c1, t_c2, t_c3, t_c4 = st.columns(4)
                    with t_c1:
                        st.markdown(f"**Transponder Mode-S:** `{sel_flight['mode_s_hex']}`")
                        st.markdown(f"**Squawk Code:** `{sel_flight['squawk']}`")
                        st.markdown(f"**Assigned Sector:** `{sel_flight['atc_sector']}`")
                    with t_c2:
                        st.markdown(f"**GPS Integrity:** `{gps_str}`")
                        st.markdown(f"**Coordinates:** `{sel_flight['lat']:.4f}°N, {sel_flight['lon']:.4f}°E`")
                        st.markdown(f"**Airway Corridor:** `{sel_flight['origin']} -> {sel_flight['destination']}`")
                    with t_c3:
                        st.markdown(f"**Aircraft Model:** `{sel_flight['aircraft_model']}`")
                        st.markdown(f"**Wake Category:** `{sel_flight['aircraft_category']}`")
                        st.markdown(f"**Seating Capacity:** `{sel_flight['capacity']} Pax`")
                    with t_c4:
                        st.markdown(f"**Estimated Fuel Burn:** `{int(sel_flight['distance_km'] * 2.8):,} kg`")
                        st.markdown(f"**Corridor Duration:** `{int(duration_min)} min`")
                        st.markdown(f"**Remaining Distance:** `{dist_remaining} km`")

    # ─────────────────────────────────────────────────────────────────────
    # TAB 2: Airport Radar HUD & Terminal Gate Telemetry
    # ─────────────────────────────────────────────────────────────────────
    with tab_radar:
        st.markdown(
            f'<div class="section-header">Live Terminal Radar HUD & METAR Weather Telemetry</div>',
            unsafe_allow_html=True,
        )

        # Selectable airport list depending on airspace
        if airspace == "india":
            airport_options = list(INDIAN_AIRPORTS.keys()) + ["DXB", "SIN", "DOH", "LHR"]
        elif airspace == "global":
            airport_options = list(INTL_AIRPORTS.keys()) + ["DEL", "BOM", "BLR"]
        else:
            airport_options = list(US_AIRPORTS.keys())

        r_col1, r_col2 = st.columns([1, 2])
        with r_col1:
            selected_airport = st.selectbox(
                "Select Airport Terminal to Inspect",
                airport_options,
                index=0,
                format_func=lambda x: f"{x} - {INDIAN_AIRPORTS.get(x, INTL_AIRPORTS.get(x, US_AIRPORTS.get(x, {}))).get('name', x)}",
            )
            tel = get_airport_telemetry(selected_airport)

            st.markdown(
                f"""
                <div class="content-panel" style="margin-top:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid {CLR_BORDER}; padding-bottom:8px; margin-bottom:10px;">
                        <div>
                            <span style="color:{CLR_ACCENT}; font-size:1.4rem; font-weight:700;">{tel['iata']}</span>
                            <span style="color:{CLR_MUTED}; font-size:0.85rem;"> / {tel['icao']}</span>
                        </div>
                        <span class="status-pill status-healthy">{tel['country']}</span>
                    </div>
                    <div style="color:{CLR_TEXT}; font-weight:600; font-size:0.95rem; margin-bottom:4px;">{tel['name']}</div>
                    <div style="color:{CLR_MUTED}; font-size:0.75rem; margin-bottom:12px;">City: {tel['city']} · Elevation: {tel['elevation_ft']:,} ft</div>
                    
                    <div style="background:{CLR_BG}; padding:8px; border-radius:6px; font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#38BDF8; margin-bottom:12px; border:1px solid {CLR_BORDER};">
                        <b>METAR:</b> {tel['metar_raw']}
                    </div>

                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.78rem;">
                        <div> Temp: <b>{tel['temperature_c']}°C</b> (Dew: {tel['dew_point_c']}°C)</div>
                        <div> Wind: <b>{tel['wind']}</b></div>
                        <div> Visibility: <b>{tel['visibility_km']} km</b></div>
                        <div> QNH Altimeter: <b>{tel['altimeter_qnh']} hPa</b></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with r_col2:
            st.markdown(
                f"""
                <div class="content-panel" style="margin-top:10px;">
                    <div style="color:{CLR_ACCENT}; font-size:0.85rem; font-weight:700; text-transform:uppercase; margin-bottom:12px;">
                        Runway & Terminal Gate Operations Telemetry
                    </div>
                    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; margin-bottom:14px;">
                        <div style="background:{CLR_BG}; padding:10px; border-radius:6px; text-align:center; border:1px solid {CLR_BORDER};">
                            <div style="color:{CLR_MUTED}; font-size:0.70rem;">Active Runway</div>
                            <div style="color:{CLR_TEXT}; font-weight:700; font-size:0.95rem; margin-top:2px;">{tel['active_runway']}</div>
                        </div>
                        <div style="background:{CLR_BG}; padding:10px; border-radius:6px; text-align:center; border:1px solid {CLR_BORDER};">
                            <div style="color:{CLR_MUTED}; font-size:0.70rem;">Inbound Queue</div>
                            <div style="color:{CLR_ACCENT}; font-weight:700; font-size:1.1rem; margin-top:2px;">{tel['inbound_queue']} acft</div>
                        </div>
                        <div style="background:{CLR_BG}; padding:10px; border-radius:6px; text-align:center; border:1px solid {CLR_BORDER};">
                            <div style="color:{CLR_MUTED}; font-size:0.70rem;">Outbound Queue</div>
                            <div style="color:{CLR_WARN}; font-weight:700; font-size:1.1rem; margin-top:2px;">{tel['outbound_queue']} acft</div>
                        </div>
                        <div style="background:{CLR_BG}; padding:10px; border-radius:6px; text-align:center; border:1px solid {CLR_BORDER};">
                            <div style="color:{CLR_MUTED}; font-size:0.70rem;">Gate Occupancy</div>
                            <div style="color:{CLR_OK}; font-weight:700; font-size:1.1rem; margin-top:2px;">{tel['gate_occupancy_pct']}%</div>
                        </div>
                    </div>

                    <div style="color:{CLR_MUTED}; font-size:0.75rem; margin-bottom:6px;">Available Runways:</div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
                        {"".join(f'<span style="background:#1E293B; color:#E2E8F0; padding:3px 8px; border-radius:4px; font-size:0.72rem;">{rwy}</span>' for rwy in tel['runways'])}
                    </div>

                    <div style="color:{CLR_MUTED}; font-size:0.75rem; margin-bottom:6px;">Terminal Facilities:</div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        {"".join(f'<span style="background:#1E293B; color:#38BDF8; padding:3px 8px; border-radius:4px; font-size:0.72rem;">{term}</span>' for term in tel['terminals'])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Filter arrivals and departures for this airport
            apt_flights = flights_df[(flights_df["origin"] == selected_airport) | (flights_df["destination"] == selected_airport)]
            if not apt_flights.empty:
                st.markdown(f'<div style="color:{CLR_TEXT}; font-weight:600; font-size:0.85rem; margin-top:14px; margin-bottom:6px;">Active Inbound & Outbound Flights at {selected_airport}</div>', unsafe_allow_html=True)
                render_flight_board(apt_flights, max_rows=8)
            else:
                st.info(f"No active simulated flights currently en-route directly to/from {selected_airport}. Try increasing fleet size or switching operational hour.")

    # ─────────────────────────────────────────────────────────────────────
    # TAB 3: "What-If" Network Resilience & Hub Disruption Simulator
    # ─────────────────────────────────────────────────────────────────────
    with tab_disrupt:
        st.markdown(
            f'<div class="section-header">"What-If" Hub Disruption & Network Resilience Simulator</div>',
            unsafe_allow_html=True,
        )
        st.caption("Simulate the system-wide cascade effect when an airport hub is incapacitated by severe weather, ATC outages, or ground stops.")

        sim_c1, sim_c2, sim_c3 = st.columns([1, 1, 1])
        with sim_c1:
            disrupt_hub = st.selectbox(
                "Hub to Disrupt",
                options=["DEL", "BOM", "BLR", "DXB", "ATL", "ORD", "JFK"],
                index=0,
                format_func=lambda x: f"{x} - {INDIAN_AIRPORTS.get(x, INTL_AIRPORTS.get(x, US_AIRPORTS.get(x, {}))).get('city', x)}",
            )
        with sim_c2:
            disrupt_scenario = st.selectbox(
                "Disruption Scenario",
                options=[
                    "Severe Winter Fog / CAT IIIb Ground Stop",
                    "Monsoon Cloudburst & Runway Flooding",
                    "ATC Radar Telemetry Power Grid Glitch",
                    "Tropical Cyclone & High Crosswinds",
                    "Emergency Airspace Runway Maintenance",
                ],
                index=0,
            )
        with sim_c3:
            severity_pct = st.slider("Capacity Reduction / Closure Severity", 25, 100, 75, 25, format="%d%%")

        sim_result = simulate_network_disruption(
            disrupted_airport=disrupt_hub,
            scenario_name=disrupt_scenario,
            severity_pct=severity_pct,
            flights_df=flights_df,
        )

        if sim_result:
            st.markdown(
                f"""
                <div style="display:grid; grid-template-columns:repeat(5, 1fr); gap:12px; margin-top:14px; margin-bottom:16px;">
                    <div style="background:{CLR_PANEL}; border:1px solid {CLR_BORDER}; border-radius:8px; padding:12px; text-align:center;">
                        <div style="color:{CLR_MUTED}; font-size:0.72rem; text-transform:uppercase;">Directly Grounded</div>
                        <div style="color:{CLR_DANGER}; font-size:1.6rem; font-weight:700;">{sim_result['grounded_or_diverted']} flights</div>
                        <div style="color:{CLR_MUTED}; font-size:0.70rem;">of {sim_result['direct_flights']} total hub flights</div>
                    </div>
                    <div style="background:{CLR_PANEL}; border:1px solid {CLR_BORDER}; border-radius:8px; padding:12px; text-align:center;">
                        <div style="color:{CLR_MUTED}; font-size:0.72rem; text-transform:uppercase;">Stranded Passengers</div>
                        <div style="color:{CLR_ORANGE}; font-size:1.6rem; font-weight:700;">{sim_result['stranded_passengers']:,}</div>
                        <div style="color:{CLR_MUTED}; font-size:0.70rem;">Estimated terminal load</div>
                    </div>
                    <div style="background:{CLR_PANEL}; border:1px solid {CLR_BORDER}; border-radius:8px; padding:12px; text-align:center;">
                        <div style="color:{CLR_MUTED}; font-size:0.72rem; text-transform:uppercase;">Downstream Spokes</div>
                        <div style="color:{CLR_WARN}; font-size:1.6rem; font-weight:700;">{sim_result['spoke_count']} airports</div>
                        <div style="color:{CLR_MUTED}; font-size:0.70rem;">Ripple delay propagation</div>
                    </div>
                    <div style="background:{CLR_PANEL}; border:1px solid {CLR_BORDER}; border-radius:8px; padding:12px; text-align:center;">
                        <div style="color:{CLR_MUTED}; font-size:0.72rem; text-transform:uppercase;">Network Delay Surge</div>
                        <div style="color:#F43F5E; font-size:1.6rem; font-weight:700;">+{sim_result['cascade_delay_minutes']:,} min</div>
                        <div style="color:{CLR_MUTED}; font-size:0.70rem;">Added system turnaround lag</div>
                    </div>
                    <div style="background:{CLR_PANEL}; border:1px solid {CLR_BORDER}; border-radius:8px; padding:12px; text-align:center;">
                        <div style="color:{CLR_MUTED}; font-size:0.72rem; text-transform:uppercase;">Resilience Score</div>
                        <div style="color:{CLR_OK if sim_result['resilience_health_score'] > 70 else CLR_WARN}; font-size:1.6rem; font-weight:700;">
                            {sim_result['resilience_health_score']}/100
                        </div>
                        <div style="color:{CLR_MUTED}; font-size:0.70rem;">Network fault tolerance</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class="content-panel">
                    <div style="color:{CLR_ACCENT}; font-size:0.80rem; font-weight:700; text-transform:uppercase; margin-bottom:8px;">
                        Ripple Propagation Across Connected Spoke Airports:
                    </div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        {"".join(f'<span style="background:rgba(239,68,68,0.18); color:#FCA5A5; border:1px solid #EF444455; padding:4px 10px; border-radius:4px; font-weight:600; font-size:0.78rem;"> {spk}</span>' for spk in sim_result['affected_spoke_airports'])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 4: Delay Root Cause & ML Analytics
    # ─────────────────────────────────────────────────────────────────────
    with tab_analytics:
        st.markdown('<div class="section-header">Delay Decomposition & Machine Learning Profiling</div>', unsafe_allow_html=True)

        an1, an2 = st.columns(2)
        with an1:
            by_cause = summary.get("by_cause", pd.DataFrame())
            fig_cause = build_delay_cause_bar(by_cause)
            st.plotly_chart(fig_cause, use_container_width=True, config={"displayModeBar": False})

        with an2:
            fig_ml_risk = build_ml_risk_donut(flights_df)
            st.plotly_chart(fig_ml_risk, use_container_width=True, config={"displayModeBar": False})

        an3, an4 = st.columns(2)
        with an3:
            fig_trend = build_delay_trend_chart(trend_df)
            st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

        with an4:
            worst = summary.get("worst_routes", pd.DataFrame())
            if not worst.empty:
                fig_worst = go.Figure(go.Bar(
                    x=worst["avg_delay_min"].round(0),
                    y=worst["route_key"],
                    orientation="h",
                    marker=dict(
                        color=worst["avg_delay_min"],
                        colorscale=[[0, CLR_WARN], [0.5, CLR_ORANGE], [1, CLR_DANGER]],
                        showscale=False,
                        line=dict(width=0),
                    ),
                    text=worst["avg_delay_min"].round(0).astype(int).astype(str) + " min",
                    textposition="auto",
                    hovertemplate="<b>%{y}</b><br>Avg Delay: %{x:.0f} min<br>Delayed Flights: %{customdata}<extra></extra>",
                    customdata=worst["delayed_flights"],
                ))
                fig_worst.update_layout(
                    title=dict(text="Top Delay Hotspot Corridors", font=dict(size=12, color=CLR_MUTED), x=0),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(_dark_layout(fig_worst, height=270), use_container_width=True, config={"displayModeBar": False})

    # ── Live Flight Telemetry Board (Always visible on page) ───────────────
    st.markdown(
        f'<div class="section-header">Live Aircraft Telemetry Board ({len(view_df)} flights matching filters)</div>',
        unsafe_allow_html=True,
    )

    # Search bar
    search_query = st.text_input(
        " Search flight ID, airline, aircraft model, or airport (e.g., 6E, DEL, A350, AI101)",
        placeholder="Type to search e.g. 6E, DEL, BOM, A350, IndiGo, Vistara, Dreamliner",
        label_visibility="collapsed",
    )
    if search_query:
        sq = search_query.upper()
        view_df = view_df[
            view_df["flight_id"].str.contains(sq, na=False) |
            view_df["airline"].str.contains(sq, na=False) |
            view_df["aircraft_model"].str.contains(sq, na=False) |
            view_df["origin"].str.contains(sq, na=False) |
            view_df["destination"].str.contains(sq, na=False) |
            view_df["origin_city"].str.contains(sq, na=False) |
            view_df["dest_city"].str.contains(sq, na=False)
        ]

    render_flight_board(view_df, max_rows=25)

    # Full data table expander & CSV download
    with st.expander(" Export Raw Telemetry & Fleet Specification Dataset"):
        display_cols = [
            "flight_id", "airline", "aircraft_model", "aircraft_category", "capacity",
            "tail_number", "origin", "destination", "status",
            "altitude_ft", "speed_kts", "progress_pct", "delay_minutes",
            "delay_cause", "delay_severity", "ml_risk_pct", "ml_risk_category",
            "ml_risk_factor", "departed_at", "eta", "distance_km",
        ]
        export_df = view_df[display_cols].rename(columns={
            "flight_id": "Flight", "airline": "Airline",
            "aircraft_model": "Aircraft Model", "aircraft_category": "Category",
            "capacity": "Capacity", "tail_number": "Tail Reg",
            "origin": "Origin", "destination": "Dest",
            "status": "Status", "altitude_ft": "Alt (ft)",
            "speed_kts": "Speed (kts)", "progress_pct": "Progress %",
            "delay_minutes": "Delay (min)", "delay_cause": "Cause",
            "delay_severity": "Severity", "ml_risk_pct": "ML Risk %",
            "ml_risk_category": "Risk Grade", "ml_risk_factor": "ML Risk Factor",
            "departed_at": "Departed", "eta": "ETA", "distance_km": "Dist (km)",
        })
        try:
            st.dataframe(export_df, use_container_width=True, height=380)
        except Exception:
            st.markdown(
                f'<div style="max-height:380px; overflow:auto; border:1px solid #1E293B; border-radius:6px; font-size:0.75rem;">'
                + export_df.to_html(classes="dataframe", index=False)
                + '</div>',
                unsafe_allow_html=True,
            )
        csv = view_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Live Telemetry Snapshot CSV",
            data=csv,
            file_name=f"aeroroute_live_{airspace}_snapshot.csv",
            mime="text/csv",
        )

    # ── Auto-Refresh Footer ────────────────────────────────────────────────
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    st.markdown(
        f"""
        <div style="margin-top:28px; border-top:1px solid {CLR_BORDER}; padding-top:10px;
                    display:flex; justify-content:space-between; align-items:center;">
            <div style="color:{CLR_MUTED}; font-size:0.75rem;">
                ->️ <b>AeroRoute Live Airspace Console</b> · Airspace: <b>{airspace.upper()}</b> · Snapshot: <code>{now_str}</code>
            </div>
            <div style="color:{CLR_MUTED}; font-size:0.75rem;">
                DGCA / AAI / IATA / BTS Integrated Pipeline · Predictive ML Scorer Active
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
