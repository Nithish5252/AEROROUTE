# ============================================================
# AeroRoute -- Tables Component
# File : dashboard/components/tables.py
# Safe DataFrame rendering component for Streamlit
# ============================================================

from typing import Optional, Any
import streamlit as st
import pandas as pd


def safe_dataframe(
    df: Any,
    use_container_width: bool = True,
    height: Optional[int] = None,
    hide_index: bool = True,
    column_config: Optional[dict] = None,
    **kwargs
) -> None:
    """
    Safely render a pandas DataFrame in Streamlit without crashes or ugly unhandled exceptions.
    Handles None, empty DataFrames, and mixed-type Arrow serialization gracefully.
    """
    if df is None:
        st.markdown(
            """
            <div style="padding: 18px; border-radius: 8px; background: #13151F; border: 1px dashed #1D1F2B; text-align: center;">
                <span style="color: #8E92A4; font-size: 0.85rem; font-weight: 500;">No data records available to display.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except Exception:
            st.error("Unable to format data into tabular structure.")
            return

    if df.empty:
        st.markdown(
            """
            <div style="padding: 18px; border-radius: 8px; background: #13151F; border: 1px dashed #1D1F2B; text-align: center;">
                <span style="color: #8E92A4; font-size: 0.85rem; font-weight: 500;">Dataset contains 0 rows matching query criteria.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    try:
        # Convert object columns that might have complex nested types or mixed formats
        render_df = df.copy()
        st.dataframe(
            render_df,
            use_container_width=use_container_width,
            height=height,
            hide_index=hide_index,
            column_config=column_config,
            **kwargs
        )
    except Exception as e:
        # Fallback to string-coerced rendering if pyarrow serialization fails on mixed types
        try:
            fallback_df = df.astype(str)
            st.dataframe(
                fallback_df,
                use_container_width=use_container_width,
                height=height,
                hide_index=hide_index,
                column_config=column_config,
                **kwargs
            )
        except Exception:
            st.error(f"Error rendering table: {str(e)}")
