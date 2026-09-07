"""Generate structured insight reports from the current analysis DataFrame."""

from __future__ import annotations

from datetime import date

import pandas as pd


def generate_report(dataframe: pd.DataFrame, report_date: date) -> str:
    """Return a text report with KPI, finding, and recommended-action sections."""
    if dataframe.empty:
        raise ValueError("Cannot generate a report from an empty analysis result.")
    revenue_column = "dashboard_revenue" if "dashboard_revenue" in dataframe else "order_amount"
    customer_column = "dashboard_customer" if "dashboard_customer" in dataframe else "customer_id"
    segment_column = "dashboard_segment" if "dashboard_segment" in dataframe else "customer_segment"
    revenue = dataframe[revenue_column].sum()
    customers = dataframe[customer_column].nunique()
    average_order = dataframe[revenue_column].mean()
    top_segment = dataframe.groupby(segment_column)[revenue_column].sum().idxmax()
    top_segment_revenue = dataframe.groupby(segment_column)[revenue_column].sum().max()
    lines = [
        "WEEKLY ANALYTICS REPORT",
        f"Date: {report_date}",
        "",
        "== KPI SUMMARY ==",
        f"Total Revenue: ${revenue:,.2f}",
        f"Active Customers: {customers:,}",
        f"Average Order Value: ${average_order:,.2f}",
        "",
        "== KEY FINDING ==",
        f"Top performing segment: {top_segment} (${top_segment_revenue:,.2f} revenue)",
        "",
        "== RECOMMENDED ACTION ==",
        f"Review {top_segment} performance and allocate resources to high-value areas.",
    ]
    return "\n".join(lines)