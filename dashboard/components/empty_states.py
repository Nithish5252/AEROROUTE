# ============================================================
# AeroRoute -- Empty State & Error Banner Components
# File : dashboard/components/empty_states.py
# ============================================================

from typing import Optional
import streamlit as st


def render_empty_state(
    message: str = "No records matched your query.",
    title: str = "No Data Found",
    icon: str = "",
    action_hint: Optional[str] = "Try loosening your search filters or resetting thresholds.",
):
    """Render an aesthetic empty state message."""
    html = f"""
    <div style="background-color: #131B2E; border: 1px dashed #2A3B5C; border-radius: 8px; padding: 36px 20px; text-align: center; margin: 20px 0;">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">{icon}</div>
        <div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 600; margin-bottom: 6px;">{title}</div>
        <div style="color: #94A3B8; font-size: 0.9rem; margin-bottom: 12px;">{message}</div>
        {f'<div style="color: #38BDF8; font-size: 0.8rem; font-style: italic;">{action_hint}</div>' if action_hint else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_db_error_banner(error_msg: str):
    """Render error alert when MongoDB operations fail."""
    st.error(
        f"**Database Connection Warning**: Could not connect to local MongoDB server.\n\n"
        f"Details: `{error_msg}`\n\n"
        f"Serving precomputed analytical exports from disk cache."
    )


def render_offline_banner():
    """Render informational badge when operating in offline/cached mode."""
    st.info(" Serving verified precomputed analytical exports from disk cache.")
