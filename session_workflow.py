"""Session-state-backed multi-step segment analysis workflow."""

from __future__ import annotations

from datetime import date
from typing import MutableMapping

import pandas as pd
import streamlit as st

from interactive_charts.plotly_dashboard import load_orders


WORKFLOW_KEYS = [
    "selected_segment",
    "workflow_step",
    "analysis_result",
    "filter_date_start",
    "filter_date_end",
]


def initialize_workflow_state(state: MutableMapping[str, object]) -> None:
    """Initialize workflow keys once, preserving values across reruns."""
    # selected_segment stores the Step 1 choice so other widget reruns retain it.
    if "selected_segment" not in state:
        state["selected_segment"] = "All"
    # workflow_step controls whether the dependent Step 2 analysis is visible.
    if "workflow_step" not in state:
        state["workflow_step"] = 1
    # analysis_result caches the latest Step 2 result for continuity and display.
    if "analysis_result" not in state:
        state["analysis_result"] = None
    # filter_date_start/end preserve Step 2's date context across reruns.
    if "filter_date_start" not in state:
        state["filter_date_start"] = None
    if "filter_date_end" not in state:
        state["filter_date_end"] = None


def confirm_segment(state: MutableMapping[str, object], segment: str) -> None:
    """Persist the Step 1 segment and unlock Step 2."""
    state["selected_segment"] = segment
    state["workflow_step"] = 2


def reset_workflow(state: MutableMapping[str, object]) -> None:
    """Clear workflow-only values; unrelated session state remains untouched."""
    for key in WORKFLOW_KEYS:
        state.pop(key, None)
    initialize_workflow_state(state)


def calculate_segment_analysis(
    orders: pd.DataFrame,
    selected_segment: str,
    start_date: date,
    end_date: date,
) -> dict[str, float | int | str]:
    """Calculate Step 2 metrics using the segment confirmed in Step 1."""
    filtered = orders[
        (orders["order_date"].dt.date >= start_date)
        & (orders["order_date"].dt.date <= end_date)
    ]
    if selected_segment != "All":
        filtered = filtered[filtered["customer_segment"] == selected_segment]
    result = {
        "segment": selected_segment,
        "orders": int(len(filtered)),
        "customers": int(filtered["customer_id"].nunique()),
        "revenue": float(filtered["order_amount"].sum()),
    }
    return result


def render_workflow_page() -> None:
    """Render the persistent two-step workflow in Streamlit."""
    initialize_workflow_state(st.session_state)
    orders = load_orders()
    segments = ["All"] + sorted(orders["customer_segment"].unique().tolist())

    st.title("Persistent Segment Analysis Workflow")
    if st.sidebar.button("Reset Workflow"):
        reset_workflow(st.session_state)
        st.rerun()

    st.header("Step 1: Select Segment")
    current_segment = st.session_state["selected_segment"]
    selected_index = segments.index(current_segment) if current_segment in segments else 0
    segment = st.selectbox("Choose a segment", segments, index=selected_index, key="segment_selector")
    if st.button("Confirm Segment"):
        confirm_segment(st.session_state, segment)
        st.rerun()

    if st.session_state["workflow_step"] < 2:
        st.info("Confirm a segment to unlock Step 2 analysis.")
        return

    st.header("Step 2: Segment Analysis")
    chosen_segment = st.session_state["selected_segment"]
    st.write(f"Analyzing confirmed segment: **{chosen_segment}**")
    minimum_date = orders["order_date"].min().date()
    maximum_date = orders["order_date"].max().date()
    if st.session_state["filter_date_start"] is None:
        st.session_state["filter_date_start"] = minimum_date
    if st.session_state["filter_date_end"] is None:
        st.session_state["filter_date_end"] = maximum_date
    start_date, end_date = st.date_input(
        "Analysis Date Range",
        value=(st.session_state["filter_date_start"], st.session_state["filter_date_end"]),
        min_value=minimum_date,
        max_value=maximum_date,
        key="analysis_date_range",
    )
    st.session_state["filter_date_start"] = start_date
    st.session_state["filter_date_end"] = end_date
    result = calculate_segment_analysis(orders, chosen_segment, start_date, end_date)
    st.session_state["analysis_result"] = result
    columns = st.columns(3)
    columns[0].metric("Orders", f"{result['orders']:,}")
    columns[1].metric("Customers", f"{result['customers']:,}")
    columns[2].metric("Revenue", f"${result['revenue']:,.2f}")