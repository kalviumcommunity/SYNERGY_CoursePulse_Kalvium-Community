"""Cached, upload-driven reactive KPI dashboard components."""

from __future__ import annotations

import io
import json

import pandas as pd
import plotly.express as px
import streamlit as st


DATE_ALIASES = ("date", "order_date", "timestamp", "created_at")
REVENUE_ALIASES = ("revenue", "amount", "order_amount", "sales")
CUSTOMER_ALIASES = ("customer_id", "user_id", "customer")
SEGMENT_ALIASES = ("segment", "customer_segment", "category", "region")


@st.cache_data(show_spinner=False)
def load_dashboard_data(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    """Load and normalize an upload; cache invalidates when name or bytes change."""
    suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if suffix == "csv":
        dataframe = pd.read_csv(io.BytesIO(file_bytes))
    elif suffix == "json":
        payload = json.loads(file_bytes.decode("utf-8"))
        dataframe = pd.json_normalize(payload if isinstance(payload, list) else payload)
    else:
        raise ValueError("Unsupported file type. Upload a CSV or JSON file.")
    return normalize_dashboard_data(dataframe)


def _find_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    lowered = {column.lower().strip(): column for column in columns}
    return next((lowered[alias] for alias in aliases if alias in lowered), None)


def normalize_dashboard_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Validate required fields and map common names to dashboard fields."""
    if dataframe.empty:
        raise ValueError("The uploaded dataset is empty.")
    dataframe = dataframe.copy()
    date_column = _find_column(list(dataframe.columns), DATE_ALIASES)
    revenue_column = _find_column(list(dataframe.columns), REVENUE_ALIASES)
    if date_column is None or revenue_column is None:
        raise ValueError("Dataset must include a date column and a revenue/amount column.")
    dataframe["dashboard_date"] = pd.to_datetime(dataframe[date_column], errors="coerce")
    dataframe["dashboard_revenue"] = pd.to_numeric(dataframe[revenue_column], errors="coerce")
    dataframe = dataframe.dropna(subset=["dashboard_date", "dashboard_revenue"]).copy()
    if dataframe.empty:
        raise ValueError("No valid date and revenue rows were found in the dataset.")
    customer_column = _find_column(list(dataframe.columns), CUSTOMER_ALIASES)
    segment_column = _find_column(list(dataframe.columns), SEGMENT_ALIASES)
    dataframe["dashboard_customer"] = dataframe[customer_column].fillna("Unknown").astype(str) if customer_column else dataframe.index.astype(str)
    dataframe["dashboard_segment"] = dataframe[segment_column].fillna("Unknown").astype(str) if segment_column else "All"
    return dataframe


def calculate_reactive_kpis(dataframe: pd.DataFrame) -> dict[str, float | int]:
    """Compute five KPIs exclusively from the current filtered DataFrame."""
    total_cells = dataframe.shape[0] * dataframe.shape[1]
    null_percentage = dataframe.isna().sum().sum() / total_cells * 100 if total_cells else 0
    return {
        "revenue": float(dataframe["dashboard_revenue"].sum()),
        "average_order": float(dataframe["dashboard_revenue"].mean()),
        "records": int(len(dataframe)),
        "customers": int(dataframe["dashboard_customer"].nunique()),
        "quality": float(100 - null_percentage),
    }


def render_realtime_dashboard() -> None:
    """Render upload, filters, reactive KPI cards, and three chart types."""
    st.title("Real-Time KPI Dashboard")
    st.write("Upload a dataset, filter it, and inspect KPIs that recalculate from the visible rows.")
    uploaded_file = st.file_uploader("Upload CSV or JSON", type=["csv", "json"])
    if uploaded_file is None:
        st.info("Upload a dataset containing a date and revenue or amount column to begin.")
        return
    try:
        dataframe = load_dashboard_data(uploaded_file.name, uploaded_file.getvalue())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, pd.errors.ParserError) as error:
        st.error(f"Could not load this dataset: {error}")
        return

    st.sidebar.header("Dashboard Filters")
    minimum_date = dataframe["dashboard_date"].min().date()
    maximum_date = dataframe["dashboard_date"].max().date()
    date_input = st.sidebar.date_input("Date Range", value=(minimum_date, maximum_date), min_value=minimum_date, max_value=maximum_date)
    date_range = date_input if isinstance(date_input, tuple) and len(date_input) == 2 else (date_input, date_input)
    segments = sorted(dataframe["dashboard_segment"].unique().tolist())
    selected_segments = st.sidebar.multiselect("Segments", segments, default=segments)
    minimum_revenue = float(dataframe["dashboard_revenue"].min())
    maximum_revenue = float(dataframe["dashboard_revenue"].max())
    revenue_range = st.sidebar.slider("Revenue Range", minimum_revenue, maximum_revenue, (minimum_revenue, maximum_revenue))
    filtered = dataframe[
        (dataframe["dashboard_date"].dt.date >= date_range[0])
        & (dataframe["dashboard_date"].dt.date <= date_range[1])
        & (dataframe["dashboard_segment"].isin(selected_segments))
        & (dataframe["dashboard_revenue"].between(revenue_range[0], revenue_range[1]))
    ].copy()
    st.caption(f"Showing {len(filtered):,} of {len(dataframe):,} uploaded records")
    if filtered.empty:
        st.warning("No data matches the current filters. Broaden your selection.")
        return

    kpis = calculate_reactive_kpis(filtered)
    cards = st.columns(5)
    cards[0].metric("Revenue", f"${kpis['revenue']:,.2f}")
    cards[1].metric("Average Order", f"${kpis['average_order']:,.2f}")
    cards[2].metric("Records", f"{kpis['records']:,}")
    cards[3].metric("Customers", f"{kpis['customers']:,}")
    cards[4].metric("Data Quality", f"{kpis['quality']:.1f}%")

    trend = filtered.assign(period=filtered["dashboard_date"].dt.normalize()).groupby("period", as_index=False)["dashboard_revenue"].sum()
    st.subheader("Revenue Over Time")
    st.line_chart(trend.set_index("period")["dashboard_revenue"])
    segment_revenue = filtered.groupby("dashboard_segment", as_index=False)["dashboard_revenue"].sum()
    st.subheader("Revenue by Segment")
    st.bar_chart(segment_revenue.set_index("dashboard_segment")["dashboard_revenue"])
    st.subheader("Order Value Distribution")
    histogram = px.histogram(filtered, x="dashboard_revenue", nbins=30, title="Filtered Order Value Distribution")
    histogram.update_layout(xaxis_title="Revenue ($)", yaxis_title="Records")
    st.plotly_chart(histogram, use_container_width=True)
