# ============================================================
# AeroRoute -- Flight Operations Console Route & Airport Cards
# File : dashboard/components/route_cards.py
# ============================================================

from typing import Any, Dict, Optional
import streamlit as st
from dashboard.components.kpi_cards import format_kpi_value


def render_route_spotlight_card(spotlight_data: Optional[Dict[str, Any]]):
    """
    Render a high-visibility 'Route Spotlight' card showing the busiest directed corridor,
    its reverse-direction activity, asymmetry, and share of total network activity.
    Styled with the Finest AI SaaS Obsidian & Coral theme.
    """
    if not spotlight_data:
        html = """
        <div class="route-spotlight-card" style="background:#171821; border:1px solid #232532; border-radius:18px; padding:20px 24px;">
            <div style="color: #64748B; font-size: 0.76rem; font-weight:700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;">
                * Route Spotlight
            </div>
            <div style="color: #F8FAFC; font-size: 1.15rem; font-weight: 600;">
                No Route Activity Data Available
            </div>
            <div style="color: #94A3B8; font-size: 0.82rem; margin-top: 4px;">
                Execute MongoDB MapReduce Job A (mr_route_activity) to populate corridor telemetry.
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
        return

    route_key = spotlight_data.get("route_key", "—")
    orig = spotlight_data.get("origin", "—")
    dest = spotlight_data.get("dest", "—")
    volume = format_kpi_value(spotlight_data.get("volume"))
    rev_key = spotlight_data.get("reverse_key", "—")
    rev_volume = format_kpi_value(spotlight_data.get("reverse_volume"))
    delta = format_kpi_value(spotlight_data.get("asymmetry_delta"))
    share_pct = spotlight_data.get("share_pct", "—")
    share_str = f"{share_pct:.2f}%" if isinstance(share_pct, (int, float)) else "—"

    region_title = spotlight_data.get("region_title", "National Route Spotlight")
    region_scope = spotlight_data.get("region_scope", "total eligible US")

    html = f"""
    <div class="route-spotlight-card" style="background:linear-gradient(180deg, #1A1B26 0%, #171821 100%); border:1px solid #232532; border-radius:18px; padding:22px 26px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="color: #FF385C; font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                    * {region_title}
                </span>
                <span style="background:rgba(255,56,92,0.12); color:#FF385C; border:1px solid rgba(255,56,92,0.25); font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:12px;">Active Corridors</span>
            </div>
            <span style="background:rgba(34,197,94,0.12); color:#22C55E; border:1px solid rgba(34,197,94,0.25); font-size:0.72rem; font-weight:700; padding:4px 10px; border-radius:12px;">Busiest Directed Corridor</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; align-items: center;">
            <div>
                <div style="color: #64748B; font-size: 0.74rem; font-weight:600; text-transform: uppercase; letter-spacing:0.04em;">Directed Corridor</div>
                <div style="color: #F8FAFC; font-size: 1.6rem; font-weight: 800; font-family: 'Inter', -apple-system, sans-serif; letter-spacing:-0.02em; margin-top:2px;">
                    {orig} <span style="color: #FF385C;">-></span> {dest}
                </div>
                <div style="color: #FFD5C8; font-size: 0.82rem; font-weight:500; margin-top: 4px;">
                    {volume} completed flight operations
                </div>
            </div>
            <div style="border-left: 1px solid #232532; padding-left: 20px;">
                <div style="color: #64748B; font-size: 0.74rem; font-weight:600; text-transform: uppercase; letter-spacing:0.04em;">Reverse Corridor ({rev_key})</div>
                <div style="color: #F8FAFC; font-size: 1.25rem; font-weight: 700; font-family: 'Inter', -apple-system, sans-serif; margin-top:2px;">
                    {rev_volume} flights
                </div>
                <div style="color: #94A3B8; font-size: 0.80rem; margin-top: 4px;">
                    Directional delta: <span style="color: #F59E0B; font-weight:600;">{delta} flights</span>
                </div>
            </div>
            <div style="border-left: 1px solid #232532; padding-left: 20px;">
                <div style="color: #64748B; font-size: 0.74rem; font-weight:600; text-transform: uppercase; letter-spacing:0.04em;">Network Traffic Share</div>
                <div style="color: #FF385C; font-size: 1.5rem; font-weight: 800; font-family: 'Inter', -apple-system, sans-serif; letter-spacing:-0.02em; margin-top:2px;">
                    {share_str}
                </div>
                <div style="color: #94A3B8; font-size: 0.80rem; margin-top: 4px;">
                    Share of {region_scope} flights
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_route_summary_card(route_info: Optional[Dict[str, Any]]):
    """
    Render an operational summary card for a specific selected corridor in Route Explorer.
    """
    if not route_info:
        st.info("Select an Origin and Destination airport above to inspect corridor telemetry.")
        return

    orig = route_info.get("origin", "—")
    dest = route_info.get("dest", "—")
    volume = format_kpi_value(route_info.get("volume"))
    rev_vol = format_kpi_value(route_info.get("reverse_volume"))
    delta = format_kpi_value(route_info.get("asymmetry_delta"))
    carriers = route_info.get("carriers", [])

    carrier_tags = "".join([
        f'<span style="background: #232532; color: #FFD5C8; padding: 4px 10px; border-radius: 8px; font-size: 0.74rem; font-weight:600; margin-right: 6px; display:inline-block; margin-bottom:4px;">{c["carrier"]} ({c["count"]})</span>'
        for c in carriers
    ]) if carriers else '<span style="color: #64748B; font-size: 0.8rem;">No carrier details</span>'

    html = f"""
    <div class="content-panel" style="background:#171821; border:1px solid #232532; border-radius:18px; padding:20px 24px; margin-bottom:18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div style="color: #FF385C; font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing:0.06em;">Corridor Profile</div>
            <span style="background:rgba(255,56,92,0.12); color:#FF385C; border:1px solid rgba(255,56,92,0.25); font-size:0.75rem; font-weight:700; padding:3px 10px; border-radius:12px;">{orig} -> {dest}</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 16px;">
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">FORWARD VOLUME ({orig}->{dest})</div>
                <div style="color: #FF385C; font-size: 1.4rem; font-weight: 800; margin-top:2px;">{volume} flights</div>
            </div>
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">RETURN VOLUME ({dest}->{orig})</div>
                <div style="color: #F8FAFC; font-size: 1.4rem; font-weight: 700; margin-top:2px;">{rev_vol} flights</div>
            </div>
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">DIRECTIONAL DELTA</div>
                <div style="color: #F59E0B; font-size: 1.4rem; font-weight: 700; margin-top:2px;">{delta} flights</div>
            </div>
        </div>
        <div style="border-top:1px solid #232532; padding-top:12px;">
            <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase; margin-bottom: 8px;">OPERATING CARRIERS</div>
            <div>{carrier_tags}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_airport_profile_card(airport_info: Optional[Dict[str, Any]]):
    """
    Render a detailed airport operational profile in Connectivity Map.
    """
    if not airport_info:
        st.info("Select an airport to inspect its network connectivity profile.")
        return

    iata = airport_info.get("iata", "—")
    name = airport_info.get("name", "—")
    city = airport_info.get("city", "—")
    state = airport_info.get("state", "—")
    total_f = format_kpi_value(airport_info.get("total_flights"))
    out_f = format_kpi_value(airport_info.get("outgoing_flights"))
    in_f = format_kpi_value(airport_info.get("incoming_flights"))
    out_deg = format_kpi_value(airport_info.get("out_degree"))
    in_deg = format_kpi_value(airport_info.get("in_degree"))

    html = f"""
    <div class="content-panel" style="background:#171821; border:1px solid #232532; border-radius:18px; padding:20px 24px; margin-bottom:18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div>
                <span style="color: #FF385C; font-size: 1.5rem; font-weight: 800; font-family: 'Inter', -apple-system, sans-serif;">{iata}</span>
                <span style="color: #F8FAFC; font-size: 1.1rem; font-weight: 600; margin-left: 10px;">{name}</span>
            </div>
            <span style="background:rgba(34,197,94,0.12); color:#22C55E; border:1px solid rgba(34,197,94,0.25); font-size:0.75rem; font-weight:700; padding:3px 10px; border-radius:12px;">{city}, {state}</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 14px;">
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">TOTAL FLIGHTS</div>
                <div style="color: #F8FAFC; font-size: 1.35rem; font-weight: 800; margin-top:2px;">{total_f}</div>
            </div>
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">OUTGOING FLIGHTS</div>
                <div style="color: #FF385C; font-size: 1.35rem; font-weight: 800; margin-top:2px;">{out_f}</div>
            </div>
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">INCOMING FLIGHTS</div>
                <div style="color: #FFD5C8; font-size: 1.35rem; font-weight: 800; margin-top:2px;">{in_f}</div>
            </div>
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">OUT-DEGREE (DESTS)</div>
                <div style="color: #22C55E; font-size: 1.35rem; font-weight: 800; margin-top:2px;">{out_deg}</div>
            </div>
            <div>
                <div style="color: #64748B; font-size: 0.72rem; font-weight:600; text-transform:uppercase;">IN-DEGREE (ORIGINS)</div>
                <div style="color: #22C55E; font-size: 1.35rem; font-weight: 800; margin-top:2px;">{in_deg}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
