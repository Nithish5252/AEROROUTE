# ============================================================
# AeroRoute -- Flight Operations Console KPI Cards
# File : dashboard/components/kpi_cards.py
# ============================================================

from typing import Any, Dict, List, Optional
import streamlit as st


def format_kpi_value(value: Any) -> str:
    """
    Format a KPI value safely.
    If None, empty string, or NaN, return '—'.
    If integer or float, format with commas.
    """
    if value is None or value == "" or str(value).lower() in ["none", "nan", "null"]:
        return "—"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return f"{value:,.2f}" if abs(value) < 1000 else f"{value:,.0f}"
        return f"{value:,}"
    return str(value)


def render_kpi_card(
    title: str,
    value: Any,
    subtitle: Optional[str] = None,
    badge: Optional[str] = None,
    badge_color: str = "cyan",
):
    """
    Render a single styled Finest AI SaaS KPI card.
    Displays '—' when value is None or unavailable.
    """
    formatted_val = format_kpi_value(value)
    subtitle_html = f'<div class="kpi-subtitle">{subtitle}</div>' if subtitle else ""
    badge_html = f'<span class="status-pill status-{badge_color}">{badge}</span>' if badge else ""

    html = f"""
    <div class="kpi-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
            <div class="kpi-title">{title}</div>
            {badge_html}
        </div>
        <div class="kpi-value">{formatted_val}</div>
        {subtitle_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_kpi_strip(cards: List[Dict[str, Any]]):
    """
    Render a responsive top KPI strip.
    """
    if not cards:
        return

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            render_kpi_card(
                title=card.get("title", ""),
                value=card.get("value"),
                subtitle=card.get("subtitle"),
                badge=card.get("badge"),
                badge_color=card.get("badge_color", "cyan"),
            )


def render_finest_hero_card(
    title: str,
    value: Any,
    subtitle: Optional[str] = "Commercial Airspace Fleet",
    button_left: str = "-> Live Radar",
    button_right: str = "* Route Spotlight",
    left_url: str = "/Live_Tracker",
    right_url: str = "/Network_Pulse",
):
    """
    Renders the exact Coral-Red Gradient Hero Card from 'Finest - AI SAAS Dashboard',
    customized with flight operations branding, actions, and telemetry data.
    """
    formatted_val = format_kpi_value(value)
    sub_html = f'<div style="font-size:0.75rem; color:rgba(255,255,255,0.78); margin-top:-14px; margin-bottom:16px;">{subtitle}</div>' if subtitle else '<div style="margin-bottom:16px;"></div>'
    
    html = f"""
    <div class="finest-hero-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 0.82rem; font-weight: 700; color: rgba(255, 255, 255, 0.95); text-transform: uppercase; letter-spacing:0.04em;">
                {title}
            </span>
            <div style="width: 28px; height: 28px; border-radius: 50%; background: rgba(255, 255, 255, 0.22); display: flex; align-items: center; justify-content: center; font-size: 0.85rem; cursor: pointer;" title="Active Live Radar Telemetry">
                ⟳
            </div>
        </div>
        <div style="font-size: 2.2rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; margin-bottom: 6px; color: #FFFFFF;">
            {formatted_val}
        </div>
        {sub_html}
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <a href="{left_url}" target="_self" style="background: #FFFFFF; color: #171821; font-weight: 700; font-size: 0.80rem; padding: 7px 16px; border-radius: 9999px; display: inline-block; box-shadow: 0 4px 12px rgba(0,0,0,0.18); text-decoration: none;">
                {button_left}
            </a>
            <a href="{right_url}" target="_self" style="background: rgba(0, 0, 0, 0.25); color: #FFFFFF; font-weight: 600; font-size: 0.80rem; padding: 7px 16px; border-radius: 9999px; display: inline-block; border: 1px solid rgba(255, 255, 255, 0.25); text-decoration: none;">
                {button_right}
            </a>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_finest_stat_card(
    category: str,
    value: Any,
    trend_text: str = "↑ 12%",
    is_positive: bool = True,
    icon: str = "↓",
):
    """
    Renders the exact stat cards from 'Finest - AI SAAS Dashboard' (Expenses, Income, AI Enhancements).
    """
    formatted_val = format_kpi_value(value)
    trend_color = "#22C55E" if is_positive else "#FF385C"
    html = f"""
    <div class="kpi-card" style="height: calc(100% - 14px); display: flex; flex-direction: column; justify-content: space-between;">
        <div>
            <div style="display: flex; align-items: center; gap: 6px; color: #8E92A4; font-size: 0.76rem; font-weight: 600; margin-bottom: 14px;">
                <span style="font-size: 0.72rem; color: #8E92A4;">{icon}</span>
                <span>{category}</span>
            </div>
            <div style="font-size: 1.85rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em; margin-bottom: 6px;">
                {formatted_val}
            </div>
        </div>
        <div style="color: {trend_color}; font-size: 0.78rem; font-weight: 700;">
            {trend_text}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_finest_score_card(
    title: str = "Airspace Efficiency Score",
    score_pct: int = 92,
    active_label: str = "Delayed",
    inactive_label: str = "On-Time",
):
    """
    Renders the exact 'Finance Score 92%' segmented horizontal block progress bar card.
    """
    total_blocks = 12
    filled_blocks = int(round((score_pct / 100.0) * total_blocks))
    filled_blocks = max(min(filled_blocks, total_blocks), 1)

    blocks_html = '<div style="display: flex; gap: 5px; height: 26px; margin: 14px 0 16px 0;">'
    for i in range(total_blocks):
        if i < filled_blocks:
            blocks_html += '<div style="flex: 1; background: #FF385C; border-radius: 4px;"></div>'
        else:
            blocks_html += '<div style="flex: 1; background: #252736; border-radius: 4px;"></div>'
    blocks_html += '</div>'

    html = f"""
    <div class="kpi-card" style="height: calc(100% - 14px);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #8E92A4; font-size: 0.78rem; font-weight: 600;">{title}</span>
            <span style="color: #FFFFFF; font-size: 0.95rem; font-weight: 800;">{score_pct}%</span>
        </div>
        {blocks_html}
        <div style="display: flex; gap: 14px; font-size: 0.74rem;">
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: #FF385C; display: inline-block;"></span>
                <span style="color: #8E92A4; font-weight: 500;">{active_label}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: #FFD5C8; display: inline-block;"></span>
                <span style="color: #8E92A4; font-weight: 500;">{inactive_label}</span>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
