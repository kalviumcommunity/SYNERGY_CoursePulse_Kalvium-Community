"""Compute and render five data-driven KPI cards for the Streamlit dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from interactive_charts.plotly_dashboard import load_orders


GREEN = "#10b981"
RED = "#ef4444"
AMBER = "#f59e0b"


@dataclass(frozen=True)
class KPI:
    """A KPI value, comparison, and business-direction status."""

    name: str
    current: float
    prior: float
    unit: str
    change_pct: float
    arrow: str
    color: str
    delta_display: str
    source: str


def percentage_change(current: float, prior: float) -> float:
    """Return safe period-over-period percentage change."""
    if prior == 0:
        return 0.0 if current == 0 else 100.0
    return ((current - prior) / abs(prior)) * 100


def trend_indicator(change_pct: float, metric_name: str) -> tuple[str, str]:
    """Return arrow and status color; lower churn is positive."""
    favorable_increase = metric_name != "Churn Rate"
    if abs(change_pct) <= 2:
        return "→", AMBER
    is_good = change_pct > 0 if favorable_increase else change_pct < 0
    return ("↑" if change_pct > 0 else "↓"), (GREEN if is_good else RED)


def period_values(orders: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, str]:
    """Split valid orders into the latest and immediately previous calendar month."""
    latest_period = orders["order_date"].dt.to_period("M").max()
    prior_period = latest_period - 1
    two_periods_back = latest_period - 2
    current = orders[orders["order_date"].dt.to_period("M") == latest_period].copy()
    prior = orders[orders["order_date"].dt.to_period("M") == prior_period].copy()
    two_periods_back_orders = orders[orders["order_date"].dt.to_period("M") == two_periods_back].copy()
    return current, prior, two_periods_back_orders, str(latest_period), str(prior_period)


def churn_rate(current: pd.DataFrame, prior: pd.DataFrame) -> tuple[float, float]:
    """Measure customers active in the prior month who did not return this month."""
    prior_customers = set(prior["customer_id"])
    current_customers = set(current["customer_id"])
    if not prior_customers:
        return 0.0, 0.0
    current_rate = len(prior_customers - current_customers) / len(prior_customers) * 100
    return current_rate, current_rate


def compute_kpis(orders: pd.DataFrame) -> tuple[list[KPI], str, str]:
    """Compute the five assignment KPIs from validated, positive orders."""
    current, prior, two_periods_back, current_label, prior_label = period_values(orders)
    current_churn, prior_churn = churn_rate(current, prior)
    _, prior_churn = churn_rate(prior, two_periods_back)
    metrics = [
        ("Revenue", current["order_amount"].sum(), prior["order_amount"].sum(), "$", "agg_daily_revenue"),
        ("Active Users", current["customer_id"].nunique(), prior["customer_id"].nunique(), "count", "vw_active_customers"),
        ("Average Order Value", current["order_amount"].mean(), prior["order_amount"].mean(), "$", "orders validation layer"),
        ("Churn Rate", current_churn, prior_churn, "%", "customer activity comparison"),
        ("Customer Satisfaction", fulfillment_score(current), fulfillment_score(prior), "/5", "fulfillment-quality proxy"),
    ]
    kpis = []
    for name, current_value, prior_value, unit, source in metrics:
        change = percentage_change(current_value, prior_value)
        arrow, color = trend_indicator(change, "Churn Rate" if name == "Churn Rate" else name)
        kpis.append(KPI(name, float(current_value), float(prior_value), unit, change, arrow, color, f"{arrow} {change:+.1f}%", source))
    return kpis, current_label, prior_label


def fulfillment_score(period: pd.DataFrame) -> float:
    """Map successful fulfillment share to a transparent five-point proxy score."""
    if period.empty:
        return 0.0
    successful = period["order_status"].isin(["completed", "shipped", "delivered"]).mean()
    return round(float(successful * 5), 2)


def format_value(kpi: KPI) -> str:
    """Format the current value for a compact KPI card."""
    if kpi.unit == "$":
        return f"${kpi.current:,.2f}"
    if kpi.unit == "%":
        return f"{kpi.current:.1f}%"
    if kpi.unit == "/5":
        return f"{kpi.current:.2f}/5"
    return f"{kpi.current:,.0f}"


def render_kpi_cards(kpis: list[KPI]) -> None:
    """Render a five-column KPI row with accessible status text."""
    columns = st.columns(5)
    for column, kpi in zip(columns, kpis):
        with column:
            st.metric(kpi.name, format_value(kpi), kpi.delta_display, delta_color="off")
            st.markdown(
                f'<div style="color:{kpi.color};font-weight:700;font-size:1.05rem">'
                f'{kpi.arrow} {"On track" if kpi.color == GREEN else "Investigate" if kpi.color == RED else "Stable"}'
                f'</div><small>Source: {kpi.source}</small>',
                unsafe_allow_html=True,
            )


def render_dashboard() -> None:
    """Render the KPI dashboard header and a supporting data-lineage table."""
    orders = load_orders()
    kpis, current_label, prior_label = compute_kpis(orders)
    st.title("Executive KPI Dashboard")
    st.caption(f"Current period: {current_label} | Comparison period: {prior_label}")
    render_kpi_cards(kpis)
    st.divider()
    st.subheader("KPI Data Lineage")
    st.dataframe(pd.DataFrame([{"Metric": kpi.name, "Current": format_value(kpi), "Prior": kpi.prior, "Change": kpi.delta_display, "Source": kpi.source} for kpi in kpis]), hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_dashboard()