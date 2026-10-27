# ============================================================
# AeroRoute -- Dashboard Components Package
# File : dashboard/components/__init__.py
# ============================================================

from dashboard.components.styles import apply_custom_css
from dashboard.components.kpi_cards import render_kpi_card, render_kpi_strip, format_kpi_value
from dashboard.components.status_pills import render_status_pill, get_status_pill_html, render_status_row
from dashboard.components.route_cards import render_route_spotlight_card, render_route_summary_card, render_airport_profile_card
from dashboard.components.charts import (
    create_empty_chart,
    create_horizontal_bar_chart,
    create_time_series_chart,
    create_weekday_bar_chart,
    create_month_weekday_heatmap,
    create_pca_scatter_plot,
    create_network_graph_figure,
    create_geographic_map_figure,
)
from dashboard.components.tables import safe_dataframe

__all__ = [
    "safe_dataframe",
    "apply_custom_css",
    "render_kpi_card",
    "render_kpi_strip",
    "format_kpi_value",
    "render_status_pill",
    "get_status_pill_html",
    "render_status_row",
    "render_route_spotlight_card",
    "render_route_summary_card",
    "render_airport_profile_card",
    "create_empty_chart",
    "create_horizontal_bar_chart",
    "create_time_series_chart",
    "create_weekday_bar_chart",
    "create_month_weekday_heatmap",
    "create_pca_scatter_plot",
    "create_network_graph_figure",
    "create_geographic_map_figure",
]
