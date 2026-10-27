# ============================================================
# AeroRoute -- Flight Operations Console Plotly Visualizations
# File : dashboard/components/charts.py
# ============================================================

from typing import List, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# Finest AI SaaS color tokens
COLOR_BG = "#171821"
COLOR_PLOT_BG = "#0C0D12"
COLOR_TEXT = "#FFFFFF"
COLOR_MUTED = "#8E92A4"
COLOR_GRID = "#232532"
COLOR_CYAN = "#FF385C"  # Primary accent signature coral
COLOR_SKY = "#FFD5C8"   # Secondary soft peach
COLOR_CORAL = "#FF385C"
COLOR_PEACH = "#FFD5C8"
COLOR_PURPLE = "#A855F7"
COLOR_GREEN = "#22C55E"
COLOR_AMBER = "#FACC15"
COLOR_ROSE = "#FF385C"

CLUSTER_PALETTE = {
    0: "#8E92A4",  # Tier 0: Gray (Local Outposts)
    1: "#A855F7",  # Tier 1: Purple (Regional Connectors)
    2: "#FFD5C8",  # Tier 2: Peach (Multi-Hub Connectors)
    3: "#FF385C",  # Tier 3: Coral (Core National Hubs)
}


def _apply_dark_theme(fig: go.Figure, title: Optional[str] = None, height: int = 380) -> go.Figure:
    """Apply consistent Flight Operations dark styling to any Plotly figure."""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>" if title else "",
            font=dict(color=COLOR_TEXT, size=14, family="Inter, sans-serif"),
            x=0.01,
            y=0.96,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_PLOT_BG,
        font=dict(color=COLOR_TEXT, family="Inter, sans-serif", size=11),
        margin=dict(l=40, r=30, t=50, b=40),
        height=height,
        hoverlabel=dict(
            bgcolor=COLOR_BG,
            bordercolor=COLOR_CYAN,
            font=dict(color=COLOR_TEXT, family="JetBrains Mono, monospace", size=12),
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor=COLOR_GRID,
            zerolinecolor=COLOR_GRID,
            tickfont=dict(color=COLOR_MUTED),
            title_font=dict(color=COLOR_MUTED, size=11),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLOR_GRID,
            zerolinecolor=COLOR_GRID,
            tickfont=dict(color=COLOR_MUTED),
            title_font=dict(color=COLOR_MUTED, size=11),
        ),
    )
    return fig


def create_empty_chart(message: str = "No data available for the selected filters") -> go.Figure:
    """Return a styled blank chart displaying an informative user message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color=COLOR_MUTED, size=13, family="Inter, sans-serif"),
    )
    return _apply_dark_theme(fig, height=280)


def create_horizontal_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    color_bar: str = COLOR_CYAN,
    height: int = 380,
) -> go.Figure:
    """Render a horizontal bar chart sorted descending (e.g., top routes, top hubs)."""
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return create_empty_chart(f"No records available for {title}")

    # Plotly renders bottom-to-top on horizontal bars, so reverse DataFrame
    plot_df = df.iloc[::-1]

    fig = go.Figure(
        go.Bar(
            x=plot_df[x_col],
            y=plot_df[y_col],
            orientation="h",
            marker=dict(
                color=color_bar,
                line=dict(color="rgba(255,255,255,0.1)", width=1),
            ),
            hovertemplate="<b>%{y}</b><br>Flights: %{x:,}<extra></extra>",
        )
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_time_series_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    line_color: str = COLOR_CYAN,
    height: int = 340,
) -> go.Figure:
    """Render a time series line & area chart."""
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return create_empty_chart(f"No temporal data available for {title}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[x_col],
            y=df[y_col],
            mode="lines+markers",
            line=dict(color=line_color, width=2.5),
            marker=dict(size=7, color=COLOR_SKY),
            fill="tozeroy",
            fillcolor="rgba(34, 211, 238, 0.08)",
            hovertemplate="<b>%{x}</b><br>Flight Volume: %{y:,}<extra></extra>",
        )
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_weekday_bar_chart(
    df: pd.DataFrame,
    x_col: str = "day_name",
    y_col: str = "flights",
    title: str = "Flight Operations by Day of Week",
    height: int = 340,
) -> go.Figure:
    """Render a vertical bar chart for Monday-Sunday operations."""
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return create_empty_chart(f"No weekday data available for {title}")

    fig = go.Figure(
        go.Bar(
            x=df[x_col],
            y=df[y_col],
            marker=dict(
                color=COLOR_SKY,
                line=dict(color="rgba(255,255,255,0.1)", width=1),
            ),
            hovertemplate="<b>%{x}</b><br>Flights: %{y:,}<extra></extra>",
        )
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_month_weekday_heatmap(
    matrix_df: pd.DataFrame,
    title: str = "Month vs. Weekday Traffic Density",
    height: int = 360,
) -> go.Figure:
    """Render a cross-tabulated heatmap of operations."""
    if matrix_df.empty:
        return create_empty_chart("No month-weekday matrix data available")

    fig = go.Figure(
        go.Heatmap(
            z=matrix_df.values,
            x=matrix_df.columns.tolist(),
            y=matrix_df.index.tolist(),
            colorscale=[
                [0.0, "#0B1220"],
                [0.2, "#111A2B"],
                [0.5, "#0E7490"],
                [0.8, "#06B6D4"],
                [1.0, "#22D3EE"],
            ],
            hovertemplate="Day: %{y}<br>Month: %{x}<br>Flights: %{z:,}<extra></extra>",
            colorbar=dict(
                tickfont=dict(color=COLOR_MUTED),
                outlinecolor=COLOR_GRID,
                title=dict(text="Flights", font=dict(color=COLOR_MUTED, size=10)),
            ),
        )
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_pca_scatter_plot(
    pca_df: pd.DataFrame,
    title: str = "Airport Archetype Clusters (2D PCA Projection)",
    height: int = 420,
) -> go.Figure:
    """Render a 2D PCA cluster projection colored by the 4 discovered tiers."""
    if pca_df.empty:
        return create_empty_chart("No clustering results available to project")

    x_col = "pca_x" if "pca_x" in pca_df.columns else pca_df.columns[0]
    y_col = "pca_y" if "pca_y" in pca_df.columns else pca_df.columns[1]

    fig = go.Figure()
    clusters = sorted(pca_df["cluster"].unique()) if "cluster" in pca_df.columns else [0]

    for c in clusters:
        sub = pca_df[pca_df["cluster"] == c] if "cluster" in pca_df.columns else pca_df
        c_name = sub["cluster_name"].iloc[0] if "cluster_name" in sub.columns else f"Cluster {c}"
        color = CLUSTER_PALETTE.get(c, COLOR_CYAN)

        fig.add_trace(
            go.Scatter(
                x=sub[x_col],
                y=sub[y_col],
                mode="markers",
                name=f"Tier {c}: {c_name}",
                marker=dict(size=8, color=color, opacity=0.85, line=dict(color="#0B1220", width=1)),
                text=sub.get("airport", sub.index),
                hovertemplate="<b>Airport: %{text}</b><br>Tier: " + str(c) + "<br>PC1: %{x:.2f}<br>PC2: %{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            font=dict(color=COLOR_TEXT, size=10),
        ),
        xaxis_title="Principal Component 1 (Size / Volume Dimension)",
        yaxis_title="Principal Component 2 (Connectivity Ratio Dimension)",
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_network_graph_figure(
    nodes_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    title: str = "Airport Network Topology (Sub-graph)",
    height: int = 450,
) -> go.Figure:
    """Render a 2D network graph connecting top hubs."""
    if nodes_df.empty or edges_df.empty:
        return create_empty_chart("No network graph data available")

    # Generate circular or geo layout
    import math
    n = len(nodes_df)
    pos = {}
    for idx, row in nodes_df.reset_index().iterrows():
        apt = row["airport"]
        angle = 2 * math.pi * idx / max(n, 1)
        pos[apt] = (math.cos(angle), math.sin(angle))

    edge_x = []
    edge_y = []
    for _, edge in edges_df.iterrows():
        u, v = edge["source"], edge["target"]
        if u in pos and v in pos:
            edge_x.extend([pos[u][0], pos[v][0], None])
            edge_y.extend([pos[u][1], pos[v][1], None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.6, color="rgba(56, 189, 248, 0.25)"),
        hoverinfo="none",
        mode="lines",
    )

    node_x = [pos[row["airport"]][0] for _, row in nodes_df.iterrows()]
    node_y = [pos[row["airport"]][1] for _, row in nodes_df.iterrows()]
    node_text = [f"<b>{row['airport']}</b><br>Flights: {row['total_flights']:,}" for _, row in nodes_df.iterrows()]
    node_sizes = [max(8, min(24, int(row["total_flights"] / 500))) for _, row in nodes_df.iterrows()]

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=nodes_df["airport"],
        textposition="top center",
        textfont=dict(color=COLOR_CYAN, size=9),
        hovertext=node_text,
        hoverinfo="text",
        marker=dict(
            size=node_sizes,
            color=COLOR_CYAN,
            line=dict(color="#0B1220", width=1.5),
        ),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_geographic_map_figure(
    airports_df: pd.DataFrame,
    region: Optional[str] = None,
    title: str = "Geographic Distribution of Commercial Airports",
    height: int = 420,
) -> go.Figure:
    """Render a Plotly Scattergeo map with region-appropriate scope (India or USA)."""
    if airports_df.empty:
        return create_empty_chart("No airport records available for map rendering")

    df = airports_df.copy()
    if "latitude" not in df.columns and "lat" in df.columns:
        df["latitude"] = df["lat"]
    if "longitude" not in df.columns and "lon" in df.columns:
        df["longitude"] = df["lon"]

    if "latitude" not in df.columns or "longitude" not in df.columns:
        return create_empty_chart("No geographic coordinates available for map rendering")

    geo_df = df.dropna(subset=["latitude", "longitude"])
    if geo_df.empty:
        return create_empty_chart("No valid coordinates found in dataset")

    # Determine region
    if region:
        reg = region.upper()
    else:
        # Infer region from longitude coordinates
        mean_lon = geo_df["longitude"].mean()
        reg = "INDIA" if 65.0 <= mean_lon <= 100.0 else "US"

    text_col = "airport" if "airport" in geo_df.columns else ("iata" if "iata" in geo_df.columns else "iata_code")
    marker_text = geo_df.get(text_col, "Airport")

    fig = go.Figure(
        go.Scattergeo(
            lon=geo_df["longitude"],
            lat=geo_df["latitude"],
            text=marker_text,
            mode="markers",
            marker=dict(
                size=geo_df.get("marker_size", 7),
                color=COLOR_CYAN,
                opacity=0.85,
                line=dict(width=0.8, color="#0B1220"),
            ),
            hovertemplate="<b>%{text}</b><br>Lat: %{lat:.2f}<br>Lon: %{lon:.2f}<extra></extra>",
        )
    )

    if reg == "INDIA":
        fig.update_geos(
            scope="asia",
            center=dict(lat=22.0, lon=79.0),
            projection_scale=4.2,
            fitbounds="locations",
            bgcolor=COLOR_PLOT_BG,
            lakecolor="#0B1220",
            landcolor="#111A2B",
            subunitcolor="#1E293B",
            countrycolor="#38BDF8",
            showcountries=True,
            showsubunits=True,
            showland=True,
        )
    else:
        fig.update_geos(
            scope="usa",
            bgcolor=COLOR_PLOT_BG,
            lakecolor="#0B1220",
            landcolor="#111A2B",
            subunitcolor="#1E293B",
            countrycolor="#1E293B",
            showsubunits=True,
            showland=True,
        )
    return _apply_dark_theme(fig, title=title, height=height)


# ------------------------------------------------------------
# Backward-Compatible Chart Helpers
# ------------------------------------------------------------

def get_aviation_layout(title: str = "", height: int = 380) -> dict:
    """Return dict of aviation dark layout tokens."""
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_PLOT_BG,
        height=height,
        title=title,
        font=dict(color=COLOR_TEXT, family="Inter, sans-serif"),
    )


def create_donut_chart(
    df: pd.DataFrame,
    names_col: str = "route_key",
    values_col: str = "flight_count",
    title: str = "",
    height: int = 350,
) -> go.Figure:
    """Render a donut chart with hole=0.55."""
    if df.empty or names_col not in df.columns or values_col not in df.columns:
        return create_empty_chart("No data for donut chart")
    fig = go.Figure(
        go.Pie(
            labels=df[names_col],
            values=df[values_col],
            hole=0.55,
            marker=dict(colors=[COLOR_CYAN, COLOR_SKY, COLOR_GREEN, COLOR_AMBER, COLOR_ROSE]),
        )
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_scatter_plot(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str = "",
    height: int = 350,
) -> go.Figure:
    """Render a basic scatter plot."""
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return create_empty_chart("No data for scatter plot")
    fig = go.Figure(
        go.Scatter(
            x=df[x_col],
            y=df[y_col],
            mode="markers",
            marker=dict(color=COLOR_CYAN, size=7),
        )
    )
    return _apply_dark_theme(fig, title=title, height=height)


def create_us_airport_map(
    df: pd.DataFrame,
    color_col: Optional[str] = None,
    size_col: Optional[str] = None,
    title: str = "US Airport Map",
    height: int = 420,
) -> go.Figure:
    """Render US scattergeo map."""
    if df.empty:
        return create_empty_chart("No airports to map")
    lat_col = "lat" if "lat" in df.columns else "latitude"
    lon_col = "lon" if "lon" in df.columns else "longitude"
    plot_df = df.dropna(subset=[lat_col, lon_col]) if lat_col in df.columns and lon_col in df.columns else pd.DataFrame()
    if plot_df.empty:
        fig = go.Figure()
        fig.update_geos(scope="usa")
        return _apply_dark_theme(fig, title=title, height=height)

    fig = go.Figure(
        go.Scattergeo(
            locationmode="USA-states",
            lon=plot_df[lon_col],
            lat=plot_df[lat_col],
            text=plot_df.get("iata", "Airport"),
            mode="markers",
            marker=dict(
                size=6 if not size_col or size_col not in plot_df.columns else 8,
                color=COLOR_CYAN,
            ),
        )
    )
    fig.update_geos(scope="usa", bgcolor=COLOR_PLOT_BG)
    return _apply_dark_theme(fig, title=title, height=height)


def create_finest_stacked_flow_chart(
    months: Optional[List[str]] = None,
    primary_vals: Optional[List[float]] = None,
    secondary_vals: Optional[List[float]] = None,
    primary_label: str = "Delayed Operations",
    secondary_label: str = "On-Time Airspace Flow",
    height: int = 340,
) -> go.Figure:
    """
    Renders the exact Two-Tone Stacked Bar Chart from the 'Finest - AI SAAS Dashboard' template.
    Uses signature Coral Red (#FF385C) and Soft Warm Peach (#FFD5C8).
    """
    if not months:
        months = ["Jan", "Mar", "Apr", "Jun", "Jul", "Sep", "Oct", "Nov", "Dec"]
    if not primary_vals:
        primary_vals = [42, 36, 18, 44, 46, 32, 28, 14, 18]
    if not secondary_vals:
        secondary_vals = [24, 38, 30, 26, 24, 22, 18, 26, 34]

    fig = go.Figure()

    # Bottom Layer - Coral Red
    fig.add_trace(go.Bar(
        x=months,
        y=primary_vals,
        name=primary_label,
        marker=dict(
            color="#FF385C",
            line=dict(width=0),
        ),
        hovertemplate=f"<b>%{{x}}</b><br>{primary_label}: %{{y}}k flt<extra></extra>",
    ))

    # Top Layer - Soft Warm Peach
    fig.add_trace(go.Bar(
        x=months,
        y=secondary_vals,
        name=secondary_label,
        marker=dict(
            color="#FFD5C8",
            line=dict(width=0),
        ),
        hovertemplate=f"<b>%{{x}}</b><br>{secondary_label}: %{{y}}k flt<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=20, b=35),
        showlegend=False,
        bargap=0.38,
        font=dict(family="Plus Jakarta Sans, sans-serif", color="#8E92A4", size=11),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(color="#8E92A4", size=11),
            linecolor="#232532",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#1D1F2B",
            zeroline=True,
            zerolinecolor="#232532",
            tickfont=dict(color="#8E92A4", size=11),
            ticksuffix="K",
        ),
    )
    return fig


