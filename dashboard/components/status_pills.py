# ============================================================
# AeroRoute -- Status Pills Component
# File : dashboard/components/status_pills.py
# Clean, modern status badges without emojis
# ============================================================

from typing import Optional, List, Tuple
import streamlit as st


def get_status_pill_html(status: str, label: Optional[str] = None) -> str:
    """
    Generate an HTML status pill badge in Finest AI SaaS style.
    Strictly zero emojis; uses clean geometric dot indicators and curated HSL colors.
    """
    clean_status = (status or "unknown").strip().lower()
    display_label = label if label is not None else clean_status.replace("_", " ").capitalize()

    # Color tokens based on status category
    if clean_status in ("healthy", "ready", "active", "online", "pass", "passed", "completed", "verified", "present", "success"):
        bg_color = "rgba(76, 175, 80, 0.12)"
        border_color = "rgba(76, 175, 80, 0.35)"
        text_color = "#4CAF50"
        dot_color = "#4CAF50"
    elif clean_status in ("warning", "degraded", "caution", "running", "in_progress", "stale", "partial"):
        bg_color = "rgba(255, 179, 0, 0.12)"
        border_color = "rgba(255, 179, 0, 0.35)"
        text_color = "#FFB300"
        dot_color = "#FFB300"
    elif clean_status in ("failed", "error", "offline", "critical", "missing", "unhealthy"):
        bg_color = "rgba(255, 56, 92, 0.15)"
        border_color = "rgba(255, 56, 92, 0.40)"
        text_color = "#FF385C"
        dot_color = "#FF385C"
    elif clean_status in ("live", "airborne"):
        bg_color = "rgba(0, 229, 255, 0.12)"
        border_color = "rgba(0, 229, 255, 0.35)"
        text_color = "#00E5FF"
        dot_color = "#00E5FF"
    elif clean_status in ("fallback", "simulation"):
        bg_color = "rgba(156, 39, 176, 0.12)"
        border_color = "rgba(156, 39, 176, 0.35)"
        text_color = "#BA68C8"
        dot_color = "#BA68C8"
    else:  # info, idle, pending, unknown, default
        bg_color = "rgba(142, 146, 164, 0.12)"
        border_color = "rgba(142, 146, 164, 0.30)"
        text_color = "#B0B3C7"
        dot_color = "#8E92A4"

    return (
        f'<span class="status-pill status-pill-{clean_status}" style="'
        f'display: inline-flex; align-items: center; gap: 6px; '
        f'padding: 3px 10px; border-radius: 9999px; '
        f'background: {bg_color}; border: 1px solid {border_color}; '
        f'color: {text_color}; font-size: 0.75rem; font-weight: 600; '
        f'letter-spacing: 0.02em; line-height: 1.4;'
        f'">'
        f'<span style="width: 6px; height: 6px; border-radius: 50%; background: {dot_color}; display: inline-block;"></span>'
        f'{display_label}'
        f'</span>'
    )


def render_status_pill(status: str, label: Optional[str] = None) -> None:
    """Render a status pill badge in the Streamlit UI."""
    st.markdown(get_status_pill_html(status, label), unsafe_allow_html=True)


def render_status_row(items: List[Tuple[str, str, str]]) -> None:
    """
    Render a horizontal row of status badges.
    Each item is a tuple: (title, status, label).
    """
    html_items = []
    for title, status, label in items:
        pill_html = get_status_pill_html(status, label)
        html_items.append(
            f'<div style="display: flex; align-items: center; justify-content: space-between; '
            f'padding: 8px 12px; background: #13151F; border: 1px solid #1D1F2B; border-radius: 8px; margin-bottom: 6px;">'
            f'<span style="color: #8E92A4; font-size: 0.80rem; font-weight: 500;">{title}</span>'
            f'{pill_html}'
            f'</div>'
        )
    container_html = "".join(html_items)
    st.markdown(container_html, unsafe_allow_html=True)
