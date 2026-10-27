# ============================================================
# AeroRoute -- Streamlit Filter & Pagination Utilities
# File : dashboard/services/filter_service.py
# ============================================================

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


def paginate_dataframe(
    df: pd.DataFrame,
    page_number: int = 1,
    page_size: int = 20,
) -> Tuple[pd.DataFrame, int, int]:
    """
    Paginate a Pandas DataFrame safely.
    Returns:
        (page_df, total_rows, total_pages)
    """
    total_rows = len(df)
    if total_rows == 0:
        return df, 0, 1

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page_number = max(1, min(page_number, total_pages))

    start_idx = (page_number - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    return df.iloc[start_idx:end_idx], total_rows, total_pages


def filter_routes(
    routes_df: pd.DataFrame,
    search_query: str = "",
    min_flights: int = 1,
    sort_by: str = "Flights (High to Low)",
) -> pd.DataFrame:
    """
    Filter and sort route records by search term, flight threshold, and ordering.
    """
    if routes_df.empty:
        return routes_df

    filtered = routes_df.copy()

    # Flight count threshold
    if "flight_count" in filtered.columns:
        filtered = filtered[filtered["flight_count"] >= min_flights]

    # Search query across route_key, origin, destination
    if search_query:
        q = search_query.strip().upper()
        mask = (
            filtered["route_key"].astype(str).str.contains(q, case=False, na=False)
            | filtered["origin"].astype(str).str.contains(q, case=False, na=False)
            | filtered["destination"].astype(str).str.contains(q, case=False, na=False)
        )
        filtered = filtered[mask]

    # Sorting
    if sort_by == "Flights (High to Low)" and "flight_count" in filtered.columns:
        filtered = filtered.sort_values(by="flight_count", ascending=False)
    elif sort_by == "Flights (Low to High)" and "flight_count" in filtered.columns:
        filtered = filtered.sort_values(by="flight_count", ascending=True)
    elif sort_by == "Route Key (A-Z)" and "route_key" in filtered.columns:
        filtered = filtered.sort_values(by="route_key", ascending=True)

    return filtered


def filter_airports(
    airports_df: pd.DataFrame,
    search_query: str = "",
    selected_states: Optional[List[str]] = None,
    selected_clusters: Optional[List[int]] = None,
    min_flights: int = 0,
    sort_by: str = "Flights (High to Low)",
) -> pd.DataFrame:
    """
    Filter airport DataFrame by search term, state, cluster tier, and activity.
    """
    if airports_df.empty:
        return airports_df

    filtered = airports_df.copy()

    # Search filter
    if search_query:
        q = search_query.strip().upper()
        mask = (
            filtered["iata"].astype(str).str.contains(q, case=False, na=False)
            | filtered["name"].astype(str).str.contains(q, case=False, na=False)
            | filtered["city"].astype(str).str.contains(q, case=False, na=False)
        )
        filtered = filtered[mask]

    # State filter
    if selected_states and "state" in filtered.columns:
        filtered = filtered[filtered["state"].isin(selected_states)]

    # Cluster filter
    if selected_clusters is not None and len(selected_clusters) > 0 and "cluster_id" in filtered.columns:
        filtered = filtered[filtered["cluster_id"].isin(selected_clusters)]

    # Activity filter
    if min_flights > 0 and "total_flights" in filtered.columns:
        filtered = filtered[filtered["total_flights"] >= min_flights]

    # Sorting
    if sort_by == "Flights (High to Low)" and "total_flights" in filtered.columns:
        filtered = filtered.sort_values(by="total_flights", ascending=False)
    elif sort_by == "Destinations (High to Low)" and "distinct_destinations" in filtered.columns:
        filtered = filtered.sort_values(by="distinct_destinations", ascending=False)
    elif sort_by == "Betweenness Centrality" and "betweenness_centrality" in filtered.columns:
        filtered = filtered.sort_values(by="betweenness_centrality", ascending=False)
    elif sort_by == "IATA Code (A-Z)" and "iata" in filtered.columns:
        filtered = filtered.sort_values(by="iata", ascending=True)

    return filtered
