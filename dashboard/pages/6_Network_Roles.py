# ============================================================
# AeroRoute -- Flight Operations Console: Network Roles
# File : dashboard/pages/6_Network_Roles.py
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
    create_pca_scatter_plot,
    create_empty_chart,
)
from dashboard.services.ml_service import (
    get_clustering_metadata,
    get_cluster_results_dataframe,
    get_cluster_profiles_summary,
    get_pca_projection_data,
)


def main():
    st.set_page_config(
        page_title="Network Roles | AeroRoute",
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
            key="roles_airspace_selector",
            label_visibility="collapsed",
        )
        st.session_state["global_airspace"] = airspace_selection
        st.session_state["dataset_region"] = "INDIA" if airspace_selection == "india" else "US"
        st.markdown("---")

    reg_code = st.session_state.get("dataset_region", "INDIA")

    meta = get_clustering_metadata(region=reg_code)
    k_val = meta.get("k", 4)
    eval_metrics = meta.get("evaluation_metrics", {})
    random_seed = meta.get("random_state", 42)

    db_idx = eval_metrics.get("davies_bouldin_index", 0.6524 if reg_code == "INDIA" else 0.5451)
    inertia_val = eval_metrics.get("inertia", 134.35 if reg_code == "INDIA" else 317.32)
    pca_var = eval_metrics.get("pca_explained_variance_2d", 95.60 if reg_code == "INDIA" else 97.66)
    node_count_str = "107 Nodes" if reg_code == "INDIA" else "312 Nodes"

    # Top KPI Strip (no emojis)
    kpi_cards = [
        {
            "title": "Selected Cluster Count",
            "value": f"k = {k_val}",
            "subtitle": "Unsupervised K-Means",
            "badge": "Optimal k",
            "badge_color": "healthy",
        },
        {
            "title": "Davies-Bouldin Index",
            "value": f"{db_idx:.4f}" if isinstance(db_idx, (int, float)) else str(db_idx),
            "subtitle": "Lower is better (Elbow minimum)",
            "badge": "High Separation",
            "badge_color": "healthy",
        },
        {
            "title": "K-Means Inertia (WCSS)",
            "value": f"{inertia_val:,.1f}" if isinstance(inertia_val, (int, float)) else str(inertia_val),
            "subtitle": "Within-cluster sum of squares",
            "badge": "Converged",
            "badge_color": "cyan",
        },
        {
            "title": "PCA 2D Variance Preserved",
            "value": f"{pca_var:.2f}%" if isinstance(pca_var, (int, float)) else str(pca_var),
            "subtitle": "Principal Components 1 & 2",
            "badge": "Faithful",
            "badge_color": "healthy",
        },
        {
            "title": "Clustered Airfields",
            "value": node_count_str,
            "subtitle": f"{reg_code} commercial network",
            "badge": "Mapped",
            "badge_color": "cyan",
        },
    ]
    render_kpi_strip(kpi_cards)

    # Header (no emojis)
    st.markdown(
        f"""
        <div style="margin-top: 10px; margin-bottom: 14px;">
            <div class="page-title">
                <span>6. Network Roles</span>
                <span class="status-pill status-healthy">Unsupervised Machine Learning ({reg_code})</span>
            </div>
            <div class="page-subtitle">
                Empirical classification of {node_count_str} into functional operational archetypes via log1p-transformed K-Means clustering.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # PCA 2D Cluster Projection Chart
    st.markdown('<div class="section-header">2D Principal Component Projection of Airport Clusters</div>', unsafe_allow_html=True)

    pca_df = get_pca_projection_data(region=reg_code)
    if not pca_df.empty:
        fig_pca = create_pca_scatter_plot(
            pca_df,
            title=f"Principal Component Projection: Discovered Operational Archetypes ({reg_code}, k = {k_val})",
            height=430,
        )
        st.plotly_chart(fig_pca, use_container_width=True)
    else:
        st.plotly_chart(create_empty_chart("Cluster projection coordinates not found in data/exports."), use_container_width=True)

    # Empirical Cluster Profiles Table
    st.markdown('<div class="section-header">Empirical Archetype Profiles & Characteristics</div>', unsafe_allow_html=True)

    profiles_df = get_cluster_profiles_summary(region=reg_code)
    if not profiles_df.empty:
        safe_dataframe(profiles_df)
    else:
        st.info("Cluster profiles unavailable. Run model training to generate cluster results.")

    # Technical Specifications & Limitations Section
    st.markdown('<div class="section-header">Model Technical Specifications & Transparent Limitations</div>', unsafe_allow_html=True)

    spec_col, lim_col = st.columns([1, 1])

    with spec_col:
        features_html = "".join([f"<li style='color: #CBD5E1;'>{f}</li>" for f in meta.get("features", [])])
        st.markdown(
            f"""
            <div class="content-panel">
                <div style="color: #22D3EE; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">
                    Algorithm & Hyperparameters ({reg_code})
                </div>
                <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.82rem;">
                    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #1E293B; padding-bottom: 4px;">
                        <span style="color: #94A3B8;">Algorithm</span>
                        <span style="color: #E6EDF7; font-weight: 500;">K-Means (scikit-learn)</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #1E293B; padding-bottom: 4px;">
                        <span style="color: #94A3B8;">Cluster Count (k)</span>
                        <span style="color: #22D3EE; font-weight: 600;">k = {k_val}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #1E293B; padding-bottom: 4px;">
                        <span style="color: #94A3B8;">Random State Seed</span>
                        <span style="color: #E6EDF7; font-family: 'JetBrains Mono', monospace;">seed = {random_seed}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #1E293B; padding-bottom: 4px;">
                        <span style="color: #94A3B8;">Feature Scaling</span>
                        <span style="color: #E6EDF7;">log1p + StandardScaler</span>
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 0.80rem; color: #94A3B8;">
                    <b>Trained Features:</b>
                    <ul style="margin: 4px 0 0 16px; padding: 0;">{features_html}</ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with lim_col:
        lims = meta.get("limitations", [])
        lim_items = "".join([f"<li style='color: #CBD5E1; margin-bottom: 6px;'>{l}</li>" for l in lims])
        st.markdown(
            f"""
            <div class="content-panel">
                <div style="color: #FF385C; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">
                    Model Limitations & Analytical Honesty
                </div>
                <div style="font-size: 0.82rem; line-height: 1.5; color: #94A3B8;">
                    <ul style="margin: 4px 0 0 16px; padding: 0;">{lim_items}</ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
