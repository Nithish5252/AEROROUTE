# ============================================================
# AeroRoute -- Flight Operations Console: Route Explorer
# File : dashboard/pages/2_Route_Explorer.py
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

from dashboard.components.styles import apply_custom_css
from dashboard.components.tables import safe_dataframe
from dashboard.components.kpi_cards import render_kpi_strip, format_kpi_value
from dashboard.components.status_pills import render_status_pill, get_status_pill_html
from dashboard.components.route_cards import render_route_summary_card
from dashboard.components.charts import (
    create_time_series_chart,
    create_weekday_bar_chart,
    create_empty_chart,
)
from dashboard.services.database import check_connection, get_db
from dashboard.services.analytics_service import (
    get_top_directed_routes,
    get_route_detail,
    get_monthly_route_activity,
    get_weekday_route_activity,
)


def main():
    st.set_page_config(
        page_title="Route Explorer | AeroRoute",
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
            key="route_airspace_selector",
            label_visibility="collapsed",
        )
        st.session_state["global_airspace"] = airspace_selection
        st.session_state["dataset_region"] = "INDIA" if airspace_selection == "india" else "US"
        st.markdown("---")

    reg_code = st.session_state.get("dataset_region", "INDIA")
    is_conn, conn_msg = check_connection()

    # Corridor options based on active region
    corridor_options = []
    if is_conn:
        try:
            top_routes_df = get_top_directed_routes(limit=100, region=reg_code)
            if not top_routes_df.empty:
                corridor_options = top_routes_df["route_key"].tolist()
        except Exception:
            pass

    if not corridor_options:
        corridor_options = ["DEL->BOM", "BOM->DEL", "SXR->DEL", "DEL->SXR", "BLR->DEL", "DEL->BLR"] if reg_code == "INDIA" else ["JFK->LAX", "LAX->JFK", "SFO->LAX", "LAX->SFO", "ORD->LGA", "ATL->MCO"]

    # Header & Searchable Route Selector (no emojis)
    st.markdown(
        """
        <div style="margin-top: 10px; margin-bottom: 14px;">
            <div class="page-title">
                <span>2. Route Explorer</span>
                <span class="status-pill status-healthy">Directed Corridor Analytics</span>
            </div>
            <div class="page-subtitle">
                Inspect operational volume, directional asymmetry (u -> v vs v -> u), operating carriers, and temporal cycles.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Searchable Route Selection
    search_col, info_col = st.columns([2, 1])
    with search_col:
        # Check if pre-filtered in sidebar
        sb_origin = st.session_state.get("filter_origin")
        sb_dest = st.session_state.get("filter_dest")
        default_index = 0
        if sb_origin and sb_dest:
            candidate = f"{sb_origin}->{sb_dest}"
            if candidate in corridor_options:
                default_index = corridor_options.index(candidate)

        selected_corridor = st.selectbox(
            "Search Directed Air Corridor (Origin -> Destination)",
            options=corridor_options,
            index=default_index,
            help="Select any directed corridor. AeroRoute treats u -> v as operationally distinct from v -> u.",
        )

    with info_col:
        st.markdown(
            """
            <div style="background: #111A2B; border: 1px solid #1E293B; border-radius: 6px; padding: 10px 14px; font-size: 0.78rem; color: #94A3B8; margin-top: 24px;">
                <span style="color: #22D3EE; font-weight: 600;">Directed Graph Semantics:</span>
                Corridors are strictly directional. Inbound and outbound aircraft rotations differ due to wind, scheduling, and turnarounds.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Parse selected route
    if "->" in selected_corridor:
        origin_code, dest_code = selected_corridor.split("->", 1)
    else:
        origin_code, dest_code = selected_corridor, "UNKNOWN"

    route_detail = get_route_detail(origin_code, dest_code, region=reg_code) if is_conn else None

    scope_unit = "weekly departures" if reg_code == "INDIA" else "operated flights"

    # Top KPI Strip for Selected Route
    kpi_cards = [
        {
            "title": f"Forward Flights ({origin_code} -> {dest_code})",
            "value": route_detail.get("volume") if route_detail else None,
            "subtitle": f"{scope_unit.capitalize()} on forward leg",
            "badge": "Active",
            "badge_color": "healthy" if route_detail else "warning",
        },
        {
            "title": f"Return Flights ({dest_code} -> {origin_code})",
            "value": route_detail.get("reverse_volume") if route_detail else None,
            "subtitle": f"{scope_unit.capitalize()} on return leg",
            "badge": "Reverse Leg",
            "badge_color": "cyan",
        },
        {
            "title": "Directional Asymmetry",
            "value": route_detail.get("asymmetry_delta") if route_detail else None,
            "subtitle": "Absolute difference in volume",
            "badge": "Delta",
            "badge_color": "warning" if route_detail and route_detail.get("asymmetry_delta", 0) > 0 else "healthy",
        },
        {
            "title": "Operating Carriers",
            "value": len(route_detail.get("carriers", [])) if route_detail else None,
            "subtitle": "Airlines serving corridor",
            "badge": "Carriers",
            "badge_color": "cyan",
        },
        {
            "title": "Corridor Status",
            "value": "Balanced" if route_detail and route_detail.get("asymmetry_delta", 0) < 15 else "Asymmetric",
            "subtitle": "Flow reciprocity balance",
            "badge": "Reciprocity",
            "badge_color": "healthy" if route_detail and route_detail.get("asymmetry_delta", 0) < 15 else "warning",
        },
    ]
    render_kpi_strip(kpi_cards)

    # Route Summary Card
    render_route_summary_card(route_detail)

    # Temporal Dynamics for Selected Route
    st.markdown('<div class="section-header">Temporal Dynamics for Selected Corridor</div>', unsafe_allow_html=True)

    m_col, w_col = st.columns([1, 1])

    with m_col:
        monthly_df = get_monthly_route_activity(origin_code, dest_code, region=reg_code) if is_conn else pd.DataFrame()
        if not monthly_df.empty:
            fig_month = create_time_series_chart(
                monthly_df,
                x_col="month_label",
                y_col="flights",
                title=f"Monthly Operations: {origin_code} -> {dest_code}",
                line_color="#22D3EE",
                height=320,
            )
            st.plotly_chart(fig_month, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart(f"No monthly records for corridor {selected_corridor}."), use_container_width=True)

    with w_col:
        weekday_df = get_weekday_route_activity(origin_code, dest_code, region=reg_code) if is_conn else pd.DataFrame()
        if not weekday_df.empty:
            fig_weekday = create_weekday_bar_chart(
                weekday_df,
                x_col="day_name",
                y_col="flights",
                title=f"Weekday Operations: {origin_code} -> {dest_code}",
                height=320,
            )
            st.plotly_chart(fig_weekday, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart(f"No weekday records for corridor {selected_corridor}."), use_container_width=True)

    # Carrier Breakdown Table
    if route_detail and route_detail.get("carriers"):
        st.markdown('<div class="section-header">Carrier Market Share on Corridor</div>', unsafe_allow_html=True)
        carrier_df = pd.DataFrame(route_detail["carriers"])
        carrier_df.columns = ["Carrier Code", "Operated Flights"]
        total_cf = carrier_df["Operated Flights"].sum()
        carrier_df["Market Share %"] = (carrier_df["Operated Flights"] / max(total_cf, 1) * 100).round(2)
        safe_dataframe(carrier_df)


if __name__ == "__main__":
    main()
