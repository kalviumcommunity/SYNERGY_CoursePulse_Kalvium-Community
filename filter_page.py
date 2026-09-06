"""Streamlit filter workflow and testable order filtering helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from interactive_charts.plotly_dashboard import load_orders


def filter_orders(
    dataframe: pd.DataFrame,
    date_range: tuple[date, date],
    selected_segments: list[str],
    revenue_range: tuple[float, float],
    granularity: str = "Daily",
) -> pd.DataFrame:
    """Apply all filter inputs to an orders DataFrame without mutating it."""
    start_date, end_date = date_range
    filtered = dataframe[
        (dataframe["order_date"].dt.date >= start_date)
        & (dataframe["order_date"].dt.date <= end_date)
        & (dataframe["customer_segment"].isin(selected_segments))
        & (dataframe["order_amount"] >= revenue_range[0])
        & (dataframe["order_amount"] <= revenue_range[1])
    ].copy()
    if granularity == "Weekly":
        filtered["period"] = filtered["order_date"].dt.to_period("W").dt.start_time
    elif granularity == "Monthly":
        filtered["period"] = filtered["order_date"].dt.to_period("M").dt.start_time
    else:
        filtered["period"] = filtered["order_date"].dt.normalize()
    return filtered


def render_filter_page() -> None:
    """Render sidebar widgets and all downstream filtered outputs."""
    st.title("Interactive Order Filters")
    dataframe = load_orders()
    minimum_date = dataframe["order_date"].min().date()
    maximum_date = dataframe["order_date"].max().date()
    minimum_revenue = float(dataframe["order_amount"].min())
    maximum_revenue = float(dataframe["order_amount"].max())

    st.sidebar.header("Filters")
    if st.sidebar.button("Reset Filters"):
        st.rerun()
    date_input = st.sidebar.date_input("Date Range", value=(minimum_date, maximum_date), min_value=minimum_date, max_value=maximum_date)
    date_range = date_input if isinstance(date_input, tuple) and len(date_input) == 2 else (date_input, date_input)
    segments = sorted(dataframe["customer_segment"].dropna().unique().tolist())
    selected_segments = st.sidebar.multiselect("Customer Segments", options=segments, default=segments)
    revenue_range = st.sidebar.slider("Order Revenue Range", min_value=minimum_revenue, max_value=maximum_revenue, value=(minimum_revenue, maximum_revenue))
    granularity = st.sidebar.radio("Trend Granularity", options=["Daily", "Weekly", "Monthly"], index=0)

    filtered = filter_orders(dataframe, date_range, selected_segments, revenue_range, granularity)
    st.caption(f"Showing {len(filtered):,} of {len(dataframe):,} valid orders")
    if filtered.empty:
        st.warning("No data matches the current filters. Try broadening the date, segment, or revenue selection.")
        return

    metric_columns = st.columns(3)
    metric_columns[0].metric("Filtered Orders", f"{len(filtered):,}")
    metric_columns[1].metric("Filtered Revenue", f"${filtered['order_amount'].sum():,.2f}")
    metric_columns[2].metric("Average Order", f"${filtered['order_amount'].mean():,.2f}")

    trend = filtered.groupby("period", as_index=False)["order_amount"].sum().rename(columns={"order_amount": "revenue"})
    st.subheader(f"Revenue Trend ({granularity})")
    st.line_chart(trend.set_index("period")["revenue"])
    st.subheader("Filtered Orders")
    st.dataframe(filtered.sort_values("order_date", ascending=False).head(100), use_container_width=True)