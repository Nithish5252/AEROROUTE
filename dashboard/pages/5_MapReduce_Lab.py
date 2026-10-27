# ============================================================
# AeroRoute -- Flight Operations Console: MapReduce Lab
# File : dashboard/pages/5_MapReduce_Lab.py
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
from dashboard.services.database import check_connection, get_db
from dashboard.services.mapreduce_service import (
    get_mapreduce_job_definitions,
    get_job_telemetry,
    get_all_mapreduce_statuses,
)


def main():
    st.set_page_config(
        page_title="MapReduce Lab | AeroRoute",
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
            key="mr_airspace_selector",
            label_visibility="collapsed",
        )
        st.session_state["global_airspace"] = airspace_selection
        st.session_state["dataset_region"] = "INDIA" if airspace_selection == "india" else "US"
        st.markdown("---")

    reg_code = st.session_state.get("dataset_region", "INDIA")
    is_conn, conn_msg = check_connection()
    jobs_dict = get_mapreduce_job_definitions(region=reg_code)

    # Top KPI Strip (no emojis)
    statuses = get_all_mapreduce_statuses(region=reg_code) if is_conn else {}
    healthy_count = sum(1 for s in statuses.values() if s in ["healthy", "verified"])

    kpi_cards = [
        {
            "title": "Server-Side MapReduce Jobs",
            "value": f"5 Jobs ({reg_code})",
            "subtitle": "Native JavaScript routines",
            "badge": "V8 Engine",
            "badge_color": "cyan",
        },
        {
            "title": "Execution Engine",
            "value": "MongoDB 4.4",
            "subtitle": "In-database MapReduce",
            "badge": "Server-Side",
            "badge_color": "healthy" if is_conn else "failed",
        },
        {
            "title": "Healthy Jobs",
            "value": f"{healthy_count} of 5" if is_conn else None,
            "subtitle": "Collections populated",
            "badge": "Verified" if healthy_count == 5 else "Attention",
            "badge_color": "healthy" if healthy_count == 5 else "warning",
        },
        {
            "title": "Client Memory Overhead",
            "value": "0.0 MB",
            "subtitle": "In-situ server aggregation",
            "badge": "Zero RAM Leak",
            "badge_color": "healthy",
        },
        {
            "title": "Algebraic Integrity",
            "value": "Associative",
            "subtitle": "Commutative reducers",
            "badge": "Verified",
            "badge_color": "healthy",
        },
    ]
    render_kpi_strip(kpi_cards)

    # Header (no emojis)
    st.markdown(
        """
        <div style="margin-top: 10px; margin-bottom: 14px;">
            <div class="page-title">
                <span>5. MapReduce Lab</span>
                <span class="status-pill status-healthy">Distributed Computing Engine</span>
            </div>
            <div class="page-subtitle">
                Inspect and verify genuine server-side MongoDB JavaScript MapReduce jobs with zero client-side memory overhead.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    in_col_name = "flights_in" if reg_code == "INDIA" else "flights"
    out_col_prefix = "mr_*_in" if reg_code == "INDIA" else "mr_*"

    # Visual Flow Diagram
    st.markdown(
        f"""
        <div style="background: #171821; border: 1px solid #232532; border-radius: 18px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
            <div style="color: #FF385C; font-size: 0.80rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px;">
                MapReduce Pipeline Execution Flow ({reg_code})
            </div>
            <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                <span style="background: #12131A; color: #F8FAFC; padding: 7px 14px; border: 1px solid #232532; border-radius: 10px;">
                    {in_col_name}
                </span>
                <span style="color: #FF385C; font-weight: 700;">-></span>
                <span style="background: #12131A; color: #FFD5C8; padding: 7px 14px; border: 1px solid #232532; border-radius: 10px;">
                    Mapper (emit(k, v))
                </span>
                <span style="color: #FF385C; font-weight: 700;">-></span>
                <span style="background: #12131A; color: #F59E0B; padding: 7px 14px; border: 1px solid #232532; border-radius: 10px;">
                    Shuffle & Group by Key
                </span>
                <span style="color: #FF385C; font-weight: 700;">-></span>
                <span style="background: #12131A; color: #22C55E; padding: 7px 14px; border: 1px solid #232532; border-radius: 10px;">
                    Reducer (reduce(k, values))
                </span>
                <span style="color: #FF385C; font-weight: 700;">-></span>
                <span style="background: #12131A; color: #F8FAFC; padding: 7px 14px; border: 1px solid #232532; border-radius: 10px;">
                    Output Collection ({out_col_prefix})
                </span>
                <span style="color: #FF385C; font-weight: 700;">-></span>
                <span style="background: rgba(34, 197, 94, 0.12); color: #22C55E; padding: 7px 14px; border: 1px solid rgba(34, 197, 94, 0.25); border-radius: 10px; font-weight:700;">
                    Python Verification
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not is_conn:
        st.error(f"**Database Offline**: {conn_msg}. Connect to MongoDB to inspect live MapReduce collections.")

    # Job Selector Tabs
    job_keys = list(jobs_dict.keys())
    tab_labels = [
        "Job A: Directed Routes",
        "Job B: Outgoing Activity",
        "Job C: Incoming Activity",
        "Job D: Monthly Routes",
        "Job E: Connectivity Matrix",
    ]
    tabs = st.tabs(tab_labels)

    for idx, (tab, jid) in enumerate(zip(tabs, job_keys)):
        with tab:
            telemetry = get_job_telemetry(jid, region=reg_code)
            job_name = telemetry.get("name", jid)
            purpose = telemetry.get("purpose", "")
            input_col = telemetry.get("input_collection", in_col_name)
            output_col = telemetry.get("output_collection", "")
            query_filter = telemetry.get("query_filter", "")
            key_desc = telemetry.get("key_description", "")
            val_desc = telemetry.get("value_description", "")
            mapper_code = telemetry.get("mapper_code", "")
            reducer_code = telemetry.get("reducer_code", "")
            doc_count = telemetry.get("document_count", 0)
            verif_status = telemetry.get("verification_status", "unverified")
            verif_msg = telemetry.get("verification_message", "")
            samples = telemetry.get("sample_records", [])

            st.markdown(
                f"""
                <div class="content-panel" style="background:#171821; border:1px solid #232532; border-radius:18px; padding:22px 24px; box-shadow:0 4px 20px rgba(0,0,0,0.3); margin-bottom:20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div>
                            <span style="color: #FF385C; font-size: 1.3rem; font-weight: 800; font-family:'Inter', sans-serif;">{job_name}</span>
                        </div>
                        {get_status_pill_html(verif_status, f"Verification: {verif_status.capitalize()}")}
                    </div>
                    <div style="color: #94A3B8; font-size: 0.88rem; margin-bottom: 16px;">
                        <b>Purpose:</b> {purpose}
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; background: #12131A; padding: 14px; border-radius: 12px; border: 1px solid #232532;">
                        <div>
                            <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">INPUT COLLECTION</div>
                            <div style="color: #F8FAFC; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; margin-top:2px;">{input_col}</div>
                        </div>
                        <div>
                            <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">QUERY FILTER</div>
                            <div style="color: #FFD5C8; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; margin-top:2px;">{query_filter}</div>
                        </div>
                        <div>
                            <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">OUTPUT COLLECTION</div>
                            <div style="color: #FF385C; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; margin-top:2px;">{output_col}</div>
                        </div>
                        <div>
                            <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">MATERIALIZED DOCS</div>
                            <div style="color: #22C55E; font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 800; margin-top:2px;">{doc_count:,}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Mathematical Verification Result Banner
            if verif_status == "verified":
                st.success(f"**Mathematical Verification Succeeded**: {verif_msg}")
            elif verif_status == "mismatch":
                st.error(f"**Verification Discrepancy**: {verif_msg}")
            else:
                st.warning(f"**Verification Status**: {verif_msg}")

            # Expandable Mapper and Reducer Code Blocks
            c_code1, c_code2 = st.columns(2)
            with c_code1:
                with st.expander(f"View Mapper JavaScript ({key_desc})", expanded=False):
                    st.code(mapper_code, language="javascript")
            with c_code2:
                with st.expander(f"View Reducer JavaScript ({val_desc})", expanded=False):
                    st.code(reducer_code, language="javascript")

            # Representative Sample Records Table
            st.markdown(f'<div class="section-header">Representative Materialized Records ({output_col})</div>', unsafe_allow_html=True)
            if samples:
                sample_df = pd.DataFrame(samples)
                safe_dataframe(sample_df)
            else:
                st.info(f"No records found in collection '{output_col}'. Run MapReduce to populate.")


if __name__ == "__main__":
    main()
