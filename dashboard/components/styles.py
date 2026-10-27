# ============================================================
# AeroRoute -- Flight Operations Console Visual Style System
# File : dashboard/components/styles.py
# Implements the 'Finest - AI SAAS Dashboard' Design Language:
#   - Deep Obsidian Canvas: #0C0D12
#   - Matte Charcoal Panels: #171821
#   - Hairline Structural Borders: #232532
#   - Hero Vibrant Coral Brand: #FF385C (Gradient: #FF385C -> #FF5A6E)
#   - Soft Warm Peach Contrast: #FFD5C8
#   - Glowing Violet AI Accent: #A855F7
#   - High-Contrast White Text: #FFFFFF
#   - Subtle Muted Gray Labels: #8E92A4
#   - Emerald Green Success: #22C55E
# ============================================================

import streamlit as st


def apply_custom_css():
    """
    Injects the exact 'Finest - AI SAAS Dashboard' design system into Streamlit.
    """
    custom_css = """
    <style>
    /* Google Fonts: Inter and Plus Jakarta Sans */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global reset and modern typography */
    html, body, [class*="css"], [class*="st-"] {
        font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        letter-spacing: -0.01em;
    }

    /* Main application background - Deep Obsidian Canvas */
    .stApp {
        background-color: #0C0D12 !important;
        color: #FFFFFF !important;
    }

    /* Streamlit sidebar background & borders */
    section[data-testid="stSidebar"] {
        background-color: #111218 !important;
        border-right: 1px solid #1D1F2B !important;
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #FFFFFF !important;
    }

    /* Sidebar Navigation Links (Finest AI SaaS Style) */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a {
        border-radius: 12px !important;
        margin: 2px 8px !important;
        padding: 8px 14px !important;
        color: #8E92A4 !important;
        font-weight: 500 !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a:hover {
        background-color: #1A1B24 !important;
        color: #FFFFFF !important;
    }

    /* Active Navigation Pill - Signature Coral Red */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a[aria-current="page"] {
        background: #FF385C !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 16px rgba(255, 56, 92, 0.35) !important;
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a[aria-current="page"] span {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Finest AI KPI & Card Panels */
    .kpi-card {
        background: #171821;
        border: 1px solid #232532;
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 14px;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .kpi-card:hover {
        border-color: rgba(255, 56, 92, 0.35);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    .kpi-title {
        color: #8E92A4;
        font-size: 0.74rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 6px;
    }
    .kpi-value {
        color: #FFFFFF;
        font-size: 1.85rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.1;
        margin-bottom: 6px;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .kpi-subtitle {
        color: #8E92A4;
        font-size: 0.76rem;
        font-weight: 500;
    }

    /* Finest Hero Coral Card */
    .finest-hero-card {
        background: linear-gradient(135deg, #FF385C 0%, #FF5A6E 100%);
        border-radius: 20px;
        padding: 22px 24px;
        color: #FFFFFF;
        box-shadow: 0 10px 30px rgba(255, 56, 92, 0.35);
        margin-bottom: 14px;
        position: relative;
        overflow: hidden;
    }

    /* Status Pills */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .status-healthy {
        background-color: rgba(34, 197, 94, 0.14);
        color: #22C55E;
        border: 1px solid rgba(34, 197, 94, 0.35);
    }
    .status-warning {
        background-color: rgba(250, 204, 21, 0.14);
        color: #FACC15;
        border: 1px solid rgba(250, 204, 21, 0.35);
    }
    .status-failed {
        background-color: rgba(255, 56, 92, 0.14);
        color: #FF385C;
        border: 1px solid rgba(255, 56, 92, 0.35);
    }
    .status-cyan {
        background-color: rgba(255, 213, 200, 0.14);
        color: #FFD5C8;
        border: 1px solid rgba(255, 213, 200, 0.3);
    }

    /* Content Panels */
    .content-panel {
        background-color: #171821;
        border: 1px solid #232532;
        border-radius: 18px;
        padding: 20px 24px;
        margin-bottom: 18px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }

    /* Streamlit Containers with border */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px !important;
        border-color: #232532 !important;
        background-color: #171821 !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2) !important;
    }

    /* Page headers */
    .page-title {
        color: #FFFFFF;
        font-size: 1.95rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .page-subtitle {
        color: #8E92A4;
        font-size: 0.90rem;
        font-weight: 400;
        margin-bottom: 22px;
    }

    /* Section divider & subheaders */
    .section-header {
        color: #FFFFFF;
        font-size: 1.12rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin-top: 18px;
        margin-bottom: 14px;
        border-bottom: 1px solid #232532;
        padding-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Buttons (Finest Coral Style) */
    button[kind="primary"], div.stButton > button:first-child[kind="primary"] {
        background: linear-gradient(135deg, #FF385C 0%, #FF5A6E 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 9px 20px !important;
        box-shadow: 0 4px 14px rgba(255, 56, 92, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(255, 56, 92, 0.5) !important;
    }

    button[kind="secondary"], div.stButton > button:first-child {
        background-color: #1F202B !important;
        color: #FFFFFF !important;
        border: 1px solid #2B2D3C !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    button[kind="secondary"]:hover, div.stButton > button:first-child:hover {
        border-color: #FF385C !important;
        background-color: #262837 !important;
        color: #FFFFFF !important;
    }

    /* Form Inputs and Select Boxes */
    div[data-baseweb="select"] > div {
        background-color: #171821 !important;
        border: 1px solid #232532 !important;
        border-radius: 12px !important;
        color: #FFFFFF !important;
    }
    div[data-baseweb="select"] > div:hover {
        border-color: #FF385C !important;
    }
    div[data-baseweb="input"] input {
        background-color: #171821 !important;
        border: 1px solid #232532 !important;
        border-radius: 12px !important;
        color: #FFFFFF !important;
    }
    div[data-baseweb="input"] input:focus {
        border-color: #FF385C !important;
    }

    /* Metric Display */
    div[data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 800 !important;
        font-size: 1.8rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #8E92A4 !important;
        font-size: 0.74rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        font-weight: 600 !important;
    }

    /* Streamlit Tabs */
    div[data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #232532;
        padding-bottom: 4px;
    }
    button[data-baseweb="tab"] {
        border-radius: 10px !important;
        color: #8E92A4 !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 8px 16px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FFFFFF !important;
        background-color: #1F202B !important;
        border-bottom: 2px solid #FF385C !important;
    }

    /* Streamlit Expander */
    div[data-testid="stExpander"] {
        background-color: #171821 !important;
        border: 1px solid #232532 !important;
        border-radius: 14px !important;
        margin-bottom: 12px !important;
    }

    /* Code Blocks */
    pre, code {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: #111218 !important;
        border: 1px solid #232532 !important;
        color: #FFD5C8 !important;
        border-radius: 6px !important;
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0C0D12;
    }
    ::-webkit-scrollbar-thumb {
        background: #232532;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #FF385C;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
