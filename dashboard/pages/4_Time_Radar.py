# ============================================================
# AeroRoute -- Flight Operations Console: Time Radar
# File : dashboard/pages/4_Time_Radar.py
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
from dashboard.components.charts import (
    create_time_series_chart,
    create_weekday_bar_chart,
    create_month_weekday_heatmap,
    create_empty_chart,
)
from dashboard.services.database import check_connection, get_db
from dashboard.services.analytics_service import (
    get_monthly_flight_distribution,
    get_weekday_flight_distribution,
    get_month_weekday_matrix,
    get_monthly_route_activity,
    get_top_directed_routes,
)


def main():
    st.set_page_config(
        page_title="Time Radar | AeroRoute",
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
            key="time_airspace_selector",
            label_visibility="collapsed",
        )
        st.session_state["global_airspace"] = airspace_selection
        st.session_state["dataset_region"] = "INDIA" if airspace_selection == "india" else "US"
        st.markdown("---")

    reg_code = st.session_state.get("dataset_region", "INDIA")
    is_conn, conn_msg = check_connection()

    # Header (no emojis)
    st.markdown(
        """
        <div style="margin-top: 10px; margin-bottom: 14px;">
            <div class="page-title">
                <span>4. Time Radar</span>
                <span class="status-pill status-healthy">Temporal Network Cycles</span>
            </div>
            <div class="page-subtitle">
                Operational tempo across months, day-of-week demand patterns, cross-tabulated heatmaps, and multi-corridor comparisons.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Observation Window Notice based on region
    if reg_code == "INDIA":
        obs_html = """
        <div style="background: rgba(34, 211, 238, 0.08); border-left: 3px solid #22D3EE; border-radius: 4px; padding: 10px 14px; margin-bottom: 16px; font-size: 0.82rem; color: #E6EDF7;">
            <b>Operational Observation Note:</b> All temporal trends apply to the validated 
            <b>2018–2025 DGCA Civil Aviation Timetable</b> filings across 12 calendar months. Peaks in March and October reflect DGCA Summer and Winter schedule transition filings.
        </div>
        """
    else:
        obs_html = """
        <div style="background: rgba(34, 211, 238, 0.08); border-left: 3px solid #22D3EE; border-radius: 4px; padding: 10px 14px; margin-bottom: 16px; font-size: 0.82rem; color: #E6EDF7;">
            <b>Operational Observation Note:</b> All temporal trends and conclusions apply strictly to the validated 
            <b>January – June 2015</b> BTS observation window. They reflect empirical airframe movements, not year-round seasonal demand.
        </div>
        """
    st.markdown(obs_html, unsafe_allow_html=True)

    monthly_df = get_monthly_flight_distribution(region=reg_code) if is_conn else pd.DataFrame()
    weekday_df = get_weekday_flight_distribution(region=reg_code) if is_conn else pd.DataFrame()

    total_ops = monthly_df["flights"].sum() if not monthly_df.empty and "flights" in monthly_df.columns else None
    peak_month = monthly_df.loc[monthly_df["flights"].idxmax()]["month_name"] if not monthly_df.empty and "flights" in monthly_df.columns else None
    peak_weekday = weekday_df.loc[weekday_df["flights"].idxmax()]["day_name"] if not weekday_df.empty and "flights" in weekday_df.columns else None
    trough_weekday = weekday_df.loc[weekday_df["flights"].idxmin()]["day_name"] if not weekday_df.empty and "flights" in weekday_df.columns else None

    # Top KPI Strip (no emojis)
    kpi_cards = [
        {
            "title": "Total Operations Sampled",
            "value": total_ops,
            "subtitle": "Operated flights observed" if reg_code == "US" else "Timetable monthly volume",
            "badge": "Active",
            "badge_color": "healthy" if total_ops else "warning",
        },
        {
            "title": "Peak Operational Month",
            "value": peak_month,
            "subtitle": "Highest flight volume",
            "badge": "Peak",
            "badge_color": "cyan",
        },
        {
            "title": "Peak Operational Weekday",
            "value": peak_weekday,
            "subtitle": "Highest daily volume",
            "badge": "Mid-Week",
            "badge_color": "cyan",
        },
        {
            "title": "Lowest Operational Weekday",
            "value": trough_weekday,
            "subtitle": "Lowest daily volume",
            "badge": "Trough",
            "badge_color": "warning",
        },
        {
            "title": "Temporal Stability",
            "value": "High (CV < 0.12)" if not monthly_df.empty else None,
            "subtitle": "Monthly variance coefficient",
            "badge": "Stable",
            "badge_color": "healthy" if not monthly_df.empty else "warning",
        },
    ]
    render_kpi_strip(kpi_cards)

    # Monthly & Weekday Charts
    st.markdown('<div class="section-header">Macro Temporal Operations</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])

    with c1:
        if not monthly_df.empty:
            fig_m = create_time_series_chart(
                monthly_df,
                x_col="month_name",
                y_col="flights",
                title=f"Monthly Flight Volume Trajectory ({'DGCA Timetable' if reg_code == 'INDIA' else '2015 BTS'})",
                line_color="#22D3EE",
                height=340,
            )
            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart("No monthly records found."), use_container_width=True)

    with c2:
        if not weekday_df.empty:
            fig_w = create_weekday_bar_chart(
                weekday_df,
                x_col="day_name",
                y_col="flights",
                title="Weekly Operational Rhythm (Monday - Sunday)",
                height=340,
            )
            st.plotly_chart(fig_w, use_container_width=True)
        else:
            st.plotly_chart(create_empty_chart("No weekday records found."), use_container_width=True)

    # Cross-tabulated Heatmap
    st.markdown('<div class="section-header">Operational Density Matrix (Month vs. Weekday)</div>', unsafe_allow_html=True)

    matrix_df = get_month_weekday_matrix(region=reg_code) if is_conn else pd.DataFrame()
    if not matrix_df.empty:
        fig_heat = create_month_weekday_heatmap(
            matrix_df,
            title="Flight Density Heatmap: Cross-Tabulation of Month and Day-of-Week",
            height=360,
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.plotly_chart(create_empty_chart("No cross-tabulated heatmap records available."), use_container_width=True)

    # Route Comparison Selector
    st.markdown('<div class="section-header">Dual-Corridor Temporal Comparison</div>', unsafe_allow_html=True)

    default_routes = ["DEL->BOM", "BOM->DEL", "SXR->DEL", "DEL->SXR", "BLR->DEL", "DEL->BLR"] if reg_code == "INDIA" else ["JFK->LAX", "LAX->JFK", "SFO->LAX", "LAX->SFO", "ORD->LGA", "ATL->MCO"]
    routes_options = default_routes
    if is_conn:
        try:
            top_r_df = get_top_directed_routes(limit=30, region=reg_code)
            if not top_r_df.empty:
                routes_options = top_r_df["route_key"].tolist()
        except Exception:
            pass

    rc1, rc2 = st.columns(2)
    with rc1:
        route_a = st.selectbox("Select Benchmark Corridor A", options=routes_options, index=0)
    with rc2:
        route_b = st.selectbox("Select Comparison Corridor B", options=routes_options, index=min(1, len(routes_options) - 1))

    if is_conn and route_a and route_b:
        orig_a, dest_a = route_a.split("->", 1) if "->" in route_a else (route_a, "UNK")
        orig_b, dest_b = route_b.split("->", 1) if "->" in route_b else (route_b, "UNK")

        m_a = get_monthly_route_activity(orig_a, dest_a, region=reg_code)
        m_b = get_monthly_route_activity(orig_b, dest_b, region=reg_code)

        if not m_a.empty or not m_b.empty:
            merged_df = pd.merge(m_a, m_b, on="month_label", how="outer", suffixes=(f"_{route_a}", f"_{route_b}")).fillna(0)
            safe_dataframe(merged_df)


if __name__ == "__main__":
    main()
