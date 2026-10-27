# ============================================================
# AeroRoute -- Test Suite: Dashboard Empty States & Resilience
# File : tests/test_dashboard_empty_states.py
# ============================================================

import pytest
import pandas as pd
import plotly.graph_objects as go

from dashboard.components.kpi_cards import format_kpi_value
from dashboard.components.status_pills import get_status_pill_html
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


def test_format_kpi_value_empty_inputs():
    """Verify format_kpi_value returns '—' for missing or invalid inputs."""
    assert format_kpi_value(None) == "—"
    assert format_kpi_value("") == "—"
    assert format_kpi_value("none") == "—"
    assert format_kpi_value("NaN") == "—"
    assert format_kpi_value("null") == "—"


def test_format_kpi_value_valid_numbers():
    """Verify format_kpi_value formats integers and floats cleanly with commas."""
    assert format_kpi_value(100000) == "100,000"
    assert format_kpi_value(97611) == "97,611"
    assert format_kpi_value(0.5451) == "0.55"
    assert format_kpi_value(317.32) == "317.32"


def test_status_pill_resilience():
    """Verify get_status_pill_html handles any status string safely."""
    for s in ["healthy", "warning", "failed", "unverified", "unknown", "", None]:
        html = get_status_pill_html(s)
        assert isinstance(html, str)
        assert "<span" in html
        assert "status-pill" in html


def test_empty_chart_generator():
    """Verify create_empty_chart returns a valid Plotly Figure with annotation."""
    fig = create_empty_chart("Custom test empty message")
    assert isinstance(fig, go.Figure)
    assert len(fig.layout.annotations) > 0
    assert "Custom test empty message" in fig.layout.annotations[0].text


def test_charts_empty_dataframe_resilience():
    """Verify all chart generators handle empty DataFrames gracefully without raising exceptions."""
    empty_df = pd.DataFrame()

    # Bar chart
    fig_bar = create_horizontal_bar_chart(empty_df, x_col="x", y_col="y", title="Test")
    assert isinstance(fig_bar, go.Figure)

    # Time series
    fig_ts = create_time_series_chart(empty_df, x_col="x", y_col="y", title="Test")
    assert isinstance(fig_ts, go.Figure)

    # Weekday bar
    fig_w = create_weekday_bar_chart(empty_df, title="Test")
    assert isinstance(fig_w, go.Figure)

    # Heatmap
    fig_hm = create_month_weekday_heatmap(empty_df, title="Test")
    assert isinstance(fig_hm, go.Figure)

    # PCA scatter
    fig_pca = create_pca_scatter_plot(empty_df, title="Test")
    assert isinstance(fig_pca, go.Figure)

    # Network graph
    fig_net = create_network_graph_figure(empty_df, empty_df, title="Test")
    assert isinstance(fig_net, go.Figure)

    # Geo map
    fig_map = create_geographic_map_figure(empty_df, title="Test")
    assert isinstance(fig_map, go.Figure)
