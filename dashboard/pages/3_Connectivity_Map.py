# ============================================================
# AeroRoute -- Flight Operations Console: Connectivity Map
# File : dashboard/pages/3_Connectivity_Map.py
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

import streamlit as st
import pandas as pd

from config.settings import settings
from dashboard.components.styles import apply_custom_css
from dashboard.components.tables import safe_dataframe
from dashboard.components.kpi_cards import render_kpi_strip, format_kpi_value
from dashboard.components.status_pills import render_status_pill, get_status_pill_html
from dashboard.components.route_cards import render_airport_profile_card
from dashboard.components.charts import (
    create_horizontal_bar_chart,
    create_network_graph_figure,
    create_geographic_map_figure,
    create_empty_chart,
)
from dashboard.services.database import check_connection, get_db
from dashboard.services.analytics_service import (
    get_top_airports,
    get_airport_profile,
    get_airport_network_graph,
    get_airport_centrality_metrics,
)


def main():
    st.set_page_config(
        page_title="Connectivity Map | AeroRoute",
        layout="wide",
    )
    apply_custom_css()

    with st.sidebar:
        st.markdown(
            '<div style="color: #22D3EE; font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">'
            'Airspace Jurisdiction</div>',
            unsafe_allow_html=True,
        )
        cur_stored = st.session_state.get("global_airspace", "india").lower()
        default_idx = 0 if cur_stored in ["india", "in"] else 1

        airspace_selection = st.selectbox(
            "Airspace Jurisdiction",
            options=["india", "usa"],
            format_func=lambda x: {
                "india": "Indian Airspace (DGCA)",
                "usa": "US Domestic (BTS 2015)",
            }[x],
            index=default_idx,
            key="conn_airspace_selector",
            label_visibility="collapsed",
        )
        st.session_state["global_airspace"] = airspace_selection
        st.session_state["dataset_region"] = "INDIA" if airspace_selection == "india" else "US"
        st.markdown("---")

    reg_code = st.session_state.get("dataset_region", "INDIA")
    is_conn, conn_msg = check_connection()

    # Airport selection options based on active region
    airport_options = []
    if is_conn:
        try:
            top_apt_df = get_top_airports(by="total", limit=60, region=reg_code)
            if not top_apt_df.empty:
                airport_options = top_apt_df["airport"].tolist()
        except Exception:
            pass

    if not airport_options:
        airport_options = ["DEL", "BOM", "BLR", "HYD", "CCU", "MAA", "AMD", "GOI"] if reg_code == "INDIA" else ["ATL", "ORD", "DFW", "DEN", "LAX", "SFO", "JFK", "CLT", "LAS", "PHX"]

    # Header (no emojis)
    st.markdown(
        """
        <div style="margin-top: 10px; margin-bottom: 14px;">
            <div class="page-title">
                <span>3. Connectivity Map</span>
                <span class="status-pill status-healthy">Network Graph Topology</span>
            </div>
            <div class="page-subtitle">
                Explore airport hub-and-spoke structures, directed connectivity degrees, NetworkX centralities, and topological graphs.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Search & Airport Selector
    s_col, info_col = st.columns([2, 1])
    with s_col:
        sb_filter = st.session_state.get("filter_origin")
        default_idx = airport_options.index(sb_filter) if sb_filter in airport_options else 0
        selected_airport = st.selectbox(
            "Select Civil Commercial Airport",
            options=airport_options,
            index=default_idx,
            help="Select an airport to inspect its topological degrees, operational volume, and centrality metrics.",
        )

    with info_col:
        st.markdown(
            """
            <div style="background: #111A2B; border: 1px solid #1E293B; border-radius: 6px; padding: 10px 14px; font-size: 0.78rem; color: #94A3B8; margin-top: 24px;">
                <span style="color: #22D3EE; font-weight: 600;">Activity vs. Connectivity:</span>
                <b>Flight Activity</b> is the physical operation volume. <b>Connectivity</b> is the count of distinct reachable airport nodes (degree).
            </div>
            """,
            unsafe_allow_html=True,
        )

    airport_profile = get_airport_profile(selected_airport, region=reg_code) if is_conn else None

    # Top KPI Strip (no emojis)
    kpi_cards = [
        {
            "title": f"Total Operations ({selected_airport})",
            "value": airport_profile.get("total_flights") if airport_profile else None,
            "subtitle": "Inbound + Outbound volume",
            "badge": "Active",
            "badge_color": "healthy" if airport_profile else "warning",
        },
        {
            "title": "Out-Degree (Destinations)",
            "value": airport_profile.get("out_degree") if airport_profile else None,
            "subtitle": "Distinct direct destinations",
            "badge": "Degree",
            "badge_color": "cyan",
        },
        {
            "title": "In-Degree (Origins)",
            "value": airport_profile.get("in_degree") if airport_profile else None,
            "subtitle": "Distinct feeder origins",
            "badge": "Degree",
            "badge_color": "cyan",
        },
        {
            "title": "Degree Balance",
            "value": (
                "Balanced"
                if airport_profile and abs(airport_profile.get("out_degree", 0) - airport_profile.get("in_degree", 0)) <= 2
                else "Asymmetric"
            ) if airport_profile else None,
            "subtitle": "In-degree vs Out-degree",
            "badge": "Topology",
            "badge_color": "healthy" if airport_profile and abs(airport_profile.get("out_degree", 0) - airport_profile.get("in_degree", 0)) <= 2 else "warning",
        },
        {
            "title": "Structural Role",
            "value": (
                "National Super-Hub"
                if airport_profile and airport_profile.get("total_flights", 0) > (10000 if reg_code == "INDIA" else 7000)
                else ("Regional Hub" if airport_profile and airport_profile.get("total_flights", 0) > 2500 else "Feeder Node")
            ) if airport_profile else None,
            "subtitle": "Network classification",
            "badge": "Tier",
            "badge_color": "healthy" if airport_profile else "warning",
        },
    ]
    render_kpi_strip(kpi_cards)

    # Detailed Airport Profile Card
    render_airport_profile_card(airport_profile)

    # Centrality & Inbound vs Outbound Rankings
    st.markdown('<div class="section-header">Topological Rankings & Centrality Metrics</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])

    mr_out_name = "mr_airport_outgoing_in" if reg_code == "INDIA" else "mr_airport_outgoing"
    mr_in_name = "mr_airport_incoming_in" if reg_code == "INDIA" else "mr_airport_incoming"

    with c1:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="color: #E6EDF7; font-weight: 600; font-size: 0.95rem;">Top 10 Airports by Outgoing Flights</span>
                <span style="color: #94A3B8; font-size: 0.76rem;">MapReduce: {mr_out_name}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        outgoing_df = get_top_airports(by="outgoing", limit=10, region=reg_code) if is_conn else pd.DataFrame()
        if not outgoing_df.empty:
            fig_out = create_horizontal_bar_chart(
                outgoing_df,
                x_col="flights",
                y_col="airport",
                title="",
                color_bar="#38BDF8",
                height=320,
            )
            st.plotly_chart(fig_out, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart("No outgoing telemetry found."), use_container_width=True)

    with c2:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="color: #E6EDF7; font-weight: 600; font-size: 0.95rem;">Top 10 Airports by Incoming Flights</span>
                <span style="color: #94A3B8; font-size: 0.76rem;">MapReduce: {mr_in_name}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        incoming_df = get_top_airports(by="incoming", limit=10, region=reg_code) if is_conn else pd.DataFrame()
        if not incoming_df.empty:
            fig_in = create_horizontal_bar_chart(
                incoming_df,
                x_col="flights",
                y_col="airport",
                title="",
                color_bar="#22D3EE",
                height=320,
            )
            st.plotly_chart(fig_in, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart("No incoming telemetry found."), use_container_width=True)

    # Network Centrality Table
    st.markdown('<div class="section-header">NetworkX Graph Centrality Rankings</div>', unsafe_allow_html=True)
    centrality_df = get_airport_centrality_metrics(region=reg_code) if is_conn else pd.DataFrame()
    if not centrality_df.empty:
        safe_dataframe(centrality_df.head(15))
    else:
        st.info("Centrality metrics unavailable. Ensure MapReduce collections are populated.")

    # Visual Graph and Geo Map
    st.markdown('<div class="section-header">Interactive Network Graph & Geographic Distribution</div>', unsafe_allow_html=True)

    g_col, map_col = st.columns([1, 1])

    with g_col:
        nodes_df, edges_df = get_airport_network_graph(top_n=25, region=reg_code) if is_conn else (pd.DataFrame(), pd.DataFrame())
        if not nodes_df.empty and not edges_df.empty:
            fig_graph = create_network_graph_figure(nodes_df, edges_df, title="Top Hubs Directed Topology Graph", height=400)
            st.plotly_chart(fig_graph, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart("Network graph requires airport telemetry."), use_container_width=True)

    with map_col:
        if is_conn:
            try:
                db = get_db()
                if reg_code == "INDIA":
                    geo_docs = list(db.airports_in.find(
                        {"lat": {"$ne": None}, "lon": {"$ne": None}},
                        {"iata": 1, "name": 1, "lat": 1, "lon": 1}
                    ).limit(200))
                    geo_df = pd.DataFrame(geo_docs)
                    if not geo_df.empty:
                        geo_df["airport"] = geo_df["iata"]
                        geo_df["latitude"] = geo_df["lat"]
                        geo_df["longitude"] = geo_df["lon"]
                        fig_map = create_geographic_map_figure(geo_df, title="Geographic Airfield Locations (India)", height=400, region="INDIA")
                        st.plotly_chart(fig_map, use_container_width=True)
                    else:
                        st.plotly_chart(create_empty_chart("Indian airport geographic coordinates not found."), use_container_width=True)
                else:
                    geo_docs = list(db.airports.find(
                        {"latitude": {"$ne": None}, "longitude": {"$ne": None}},
                        {"iata_code": 1, "latitude": 1, "longitude": 1}
                    ).limit(200))
                    geo_df = pd.DataFrame(geo_docs)
                    if not geo_df.empty:
                        geo_df["airport"] = geo_df["iata_code"]
                        fig_map = create_geographic_map_figure(geo_df, title="Geographic Airfield Locations (US)", height=400, region="US")
                        st.plotly_chart(fig_map, use_container_width=True)
                    else:
                        st.plotly_chart(create_empty_chart("Airport geographic coordinates not found in collection."), use_container_width=True)
            except Exception:
                st.plotly_chart(create_empty_chart("Could not render geographic map."), use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart("Database offline."), use_container_width=True)


if __name__ == "__main__":
    main()
