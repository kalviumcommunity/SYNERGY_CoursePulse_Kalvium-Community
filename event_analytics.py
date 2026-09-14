"""Data-backed computations for the CoursePulse event and revenue pages.

Every number rendered on the Overview, Funnel Analysis, Course Performance,
Category Performance, User Behaviour, Trends and Monitoring, and Root Causes
pages is computed at runtime with pandas/numpy from the repository datasets:

- ``data/raw/course_pulse_events.csv``  (CoursePulse engagement events)
- ``data/raw/orders_5000.csv``          (orders, validated via the pipeline rules)
- ``data/raw/customers_1000.csv``       (customer dimension)

No hardcoded counts or placeholder text remain on those pages.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from alert_config import ALERT_THRESHOLDS
from interactive_charts.plotly_dashboard import COLORS, load_orders

BASE_DIR = Path(__file__).resolve().parent
EVENTS_PATH = BASE_DIR / "data" / "raw" / "course_pulse_events.csv"

FUNNEL_STAGES = ["search", "preview", "enrollment"]


@st.cache_data(show_spinner="Loading CoursePulse events...")
def load_events() -> pd.DataFrame:
    """Load the raw engagement events with derived date fields."""
    events = pd.read_csv(EVENTS_PATH)
    events["event_timestamp"] = pd.to_datetime(events["event_timestamp"])
    events["date"] = events["event_timestamp"].dt.date
    events["hour"] = events["event_timestamp"].dt.hour
    events["weekday"] = events["event_timestamp"].dt.day_name()
    return events


def conversion(numerator: int, denominator: int) -> float:
    """Safe percentage conversion used across all funnel math."""
    return float(numerator / denominator * 100) if denominator else 0.0


@st.cache_data(show_spinner=False)
def funnel_metrics(events: pd.DataFrame) -> dict:
    """Stage counts, unique users, conversion rates, and drop-offs."""
    counts = events["event_type"].value_counts()
    totals = {stage: int(counts.get(stage, 0)) for stage in FUNNEL_STAGES}
    users = {
        stage: int(events.loc[events["event_type"] == stage, "user_id"].nunique())
        for stage in FUNNEL_STAGES
    }
    search_users = set(events.loc[events["event_type"] == "search", "user_id"])
    preview_users = set(events.loc[events["event_type"] == "preview", "user_id"])
    rates = {
        "search_to_preview": conversion(totals["preview"], totals["search"]),
        "preview_to_enrollment": conversion(totals["enrollment"], totals["preview"]),
        "search_to_enrollment": conversion(totals["enrollment"], totals["search"]),
    }
    dropoffs = {
        "search_to_preview": {
            "count": totals["search"] - totals["preview"],
            "percent": conversion(totals["search"] - totals["preview"], totals["search"]),
        },
        "preview_to_enrollment": {
            "count": totals["preview"] - totals["enrollment"],
            "percent": conversion(totals["preview"] - totals["enrollment"], totals["preview"]),
        },
    }
    return {
        "totals": totals,
        "users": users,
        "rates": rates,
        "dropoffs": dropoffs,
        "direct_previews": len(preview_users - search_users),
        "unique_users": int(events["user_id"].nunique()),
    }


@st.cache_data(show_spinner=False)
def course_metrics(events: pd.DataFrame) -> pd.DataFrame:
    """Per-course engagement: previews, enrollments, users, and conversion."""
    course_events = events[events["course_id"].notna()].copy()
    metrics = (
        course_events.groupby(["course_id", "course_name", "category"], as_index=False)
        .agg(
            previews=("event_type", lambda series: int((series == "preview").sum())),
            enrollments=("event_type", lambda series: int((series == "enrollment").sum())),
            events=("event_id", "count"),
            unique_users=("user_id", "nunique"),
        )
    )
    metrics["conversion"] = np.where(
        metrics["previews"] > 0,
        metrics["enrollments"] / metrics["previews"].replace(0, np.nan) * 100,
        np.nan,
    )
    return metrics.sort_values(["conversion", "previews"], ascending=[False, False]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def at_risk_courses(metrics: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Flag high-traffic courses whose conversion underperforms the median."""
    view_threshold = float(metrics["previews"].quantile(0.75))
    conversion_median = float(metrics["conversion"].median())
    flagged = metrics[
        (metrics["previews"] >= view_threshold) & (metrics["conversion"] < conversion_median)
    ].copy()
    criteria = {
        "view_threshold": view_threshold,
        "conversion_median": conversion_median,
    }
    return flagged, criteria


@st.cache_data(show_spinner=False)
def category_metrics(events: pd.DataFrame) -> pd.DataFrame:
    """Per-category views, enrollments, users, and conversion."""
    course_events = events[events["category"].notna()].copy()
    metrics = (
        course_events.groupby("category", as_index=False)
        .agg(
            views=("event_type", lambda series: int((series == "preview").sum())),
            enrollments=("event_type", lambda series: int((series == "enrollment").sum())),
            unique_users=("user_id", "nunique"),
        )
    )
    metrics["conversion"] = np.where(
        metrics["views"] > 0,
        metrics["enrollments"] / metrics["views"].replace(0, np.nan) * 100,
        np.nan,
    )
    return metrics.sort_values("views", ascending=False).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def user_segments(events: pd.DataFrame) -> pd.DataFrame:
    """Behaviour-based segments computed per user from observed event types."""
    per_user = events.groupby("user_id")["event_type"].agg(set).rename("event_types")
    users = events.groupby("user_id", as_index=False).agg(events=("event_id", "count"))
    users = users.merge(per_user.reset_index(), on="user_id")

    def label(types: set) -> str:
        if "enrollment" in types:
            return "Committed (enrolled)"
        if "preview" in types and "search" in types:
            return "Explorers (search + preview)"
        if "preview" in types:
            return "Direct previews (no search)"
        return "Searchers (search only)"

    users["segment"] = users["event_types"].apply(label)
    users["enrolled"] = users["event_types"].apply(lambda types: "enrollment" in types)
    return users.drop(columns="event_types")


@st.cache_data(show_spinner=False)
def segment_summary(users: pd.DataFrame) -> pd.DataFrame:
    """Counts and enrollment share per behaviour segment."""
    return (
        users.groupby("segment", as_index=False)
        .agg(
            users=("user_id", "count"),
            avg_events=("events", "mean"),
            enrolled_users=("enrolled", "sum"),
        )
        .assign(enrollment_share=lambda data: data["enrolled_users"] / data["users"] * 100)
        .sort_values("users", ascending=False)
        .reset_index(drop=True)
    )


@st.cache_data(show_spinner=False)
def hourly_activity(events: pd.DataFrame) -> pd.DataFrame:
    """Event counts by hour of day with a rolling smoothing window."""
    hourly = events.groupby("hour", as_index=False).agg(events=("event_id", "count"))
    hourly["rolling_3h"] = hourly["events"].rolling(3, min_periods=1).mean()
    return hourly


@st.cache_data(show_spinner=False)
def top_searches(events: pd.DataFrame) -> pd.DataFrame:
    """Most frequent non-empty search queries."""
    queries = events.loc[events["search_query"].notna(), "search_query"].str.strip()
    queries = queries[queries != ""]
    return queries.value_counts().rename_axis("search_query").reset_index(name="count")


@st.cache_data(show_spinner=False)
def daily_event_trends(events: pd.DataFrame) -> pd.DataFrame:
    """Daily volume per event type plus daily conversion rates."""
    daily = (
        events.groupby(["date", "event_type"], as_index=False)
        .agg(events=("event_id", "count"))
        .pivot(index="date", columns="event_type", values="events")
        .fillna(0)
        .reset_index()
    )
    for stage in FUNNEL_STAGES:
        if stage not in daily.columns:
            daily[stage] = 0
    daily["search_to_preview"] = daily.apply(
        lambda row: conversion(row["preview"], row["search"]), axis=1
    )
    daily["preview_to_enrollment"] = daily.apply(
        lambda row: conversion(row["enrollment"], row["preview"]), axis=1
    )
    return daily


@st.cache_data(show_spinner=False)
def revenue_trends() -> pd.DataFrame:
    """Validated order revenue by day with a 7-day rolling average."""
    orders = load_orders()
    daily = (
        orders.assign(date=orders["order_date"].dt.normalize())
        .groupby("date", as_index=False)
        .agg(revenue=("order_amount", "sum"), orders=("order_id", "nunique"))
        .sort_values("date")
    )
    daily["rolling_7d"] = daily["revenue"].rolling(7, min_periods=3).mean()
    return daily


@st.cache_data(show_spinner=False)
def monthly_revenue() -> pd.DataFrame:
    """Monthly revenue with month-over-month percentage change."""
    orders = load_orders()
    monthly = (
        orders.assign(month=orders["order_date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month", as_index=False)
        .agg(revenue=("order_amount", "sum"), orders=("order_id", "nunique"))
        .sort_values("month")
    )
    monthly["mom_change"] = monthly["revenue"].pct_change() * 100
    return monthly


@st.cache_data(show_spinner=False)
def revenue_anomalies() -> pd.DataFrame:
    """Days whose revenue deviates more than 2 standard deviations from the rolling trend."""
    daily = revenue_trends()
    rolling_mean = daily["revenue"].rolling(30, min_periods=10).mean()
    rolling_std = daily["revenue"].rolling(30, min_periods=10).std()
    daily["z_score"] = (daily["revenue"] - rolling_mean) / rolling_std
    return daily[daily["z_score"].abs() > 2].dropna(subset=["z_score"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def segment_churn() -> pd.DataFrame:
    """Activity-based churn proxy by customer segment (README definition).

    A customer counts as churned when their most recent order is more than
    90 days older than the newest order in the dataset.
    """
    orders = load_orders()
    customers = pd.read_csv(
        BASE_DIR / "data" / "raw" / "customers_1000.csv",
        usecols=["customer_id", "customer_segment"],
    )
    window_end = orders["order_date"].max()
    last_order = orders.groupby("customer_id", as_index=False)["order_date"].max()
    last_order["inactive_days"] = (window_end - last_order["order_date"]).dt.days
    last_order["churned"] = last_order["inactive_days"] > 90
    merged = last_order.merge(customers, on="customer_id", how="left", validate="one_to_one")
    merged["customer_segment"] = merged["customer_segment"].fillna("Unknown")
    churn = (
        merged.groupby("customer_segment", as_index=False)
        .agg(
            customers=("customer_id", "count"),
            churned_customers=("churned", "sum"),
            avg_recency_days=("inactive_days", "mean"),
        )
    )
    churn["churn_rate"] = churn["churned_customers"] / churn["customers"] * 100
    return churn.sort_values("churn_rate", ascending=False).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def alert_status() -> pd.DataFrame:
    """Evaluate the configured business thresholds against live computed KPIs."""
    orders = load_orders()
    churn = segment_churn()
    kpis = {
        "average_order": float(orders["order_amount"].mean()),
        "churn_rate": float(churn["churn_rate"].mean()),
    }
    rows = []
    for key, config in ALERT_THRESHOLDS.items():
        value = kpis.get(key)
        if value is None:
            continue
        breached = (
            value < config["threshold"]
            if config["direction"] == "below"
            else value > config["threshold"]
        )
        rows.append(
            {
                "metric": config["metric"],
                "value": round(value, 2),
                "threshold": config["threshold"],
                "direction": config["direction"],
                "severity": config["severity"],
                "status": "BREACH" if breached else "OK",
                "message": config["message"] if breached else "",
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def weekday_revenue() -> pd.DataFrame:
    """Revenue by weekday from validated orders (root-cause evidence)."""
    orders = load_orders()
    weekday = (
        orders.assign(weekday=orders["order_date"].dt.day_name())
        .groupby("weekday", as_index=False)
        .agg(revenue=("order_amount", "sum"), orders=("order_id", "nunique"))
    )
    order_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday["weekday"] = pd.Categorical(weekday["weekday"], categories=order_names, ordered=True)
    return weekday.sort_values("weekday").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def benchmark_profiles(metrics: pd.DataFrame) -> pd.DataFrame:
    """Median feature profile of bottom-half vs top-half courses by conversion."""
    sorted_metrics = metrics.dropna(subset=["conversion"]).sort_values("conversion")
    middle = max(1, len(sorted_metrics) // 2)
    under = sorted_metrics.head(middle)
    benchmark = sorted_metrics.tail(middle)
    profile = pd.DataFrame(
        {
            "Underperformers (median)": under[["previews", "enrollments", "unique_users", "conversion"]].median(),
            "Better performers (median)": benchmark[["previews", "enrollments", "unique_users", "conversion"]].median(),
        }
    )
    profile.index.name = "metric"
    return profile.reset_index()


def funnel_figure(totals: dict) -> go.Figure:
    """Plotly funnel of the observed Search -> Preview -> Enrollment stages."""
    figure = go.Figure(
        go.Funnel(
            y=["Search", "Preview", "Enrollment"],
            x=[totals["search"], totals["preview"], totals["enrollment"]],
            textinfo="value+percent initial",
            marker={"color": [COLORS["blue"], COLORS["orange"], COLORS["green"]]},
            hoverinfo="percent initial+percent previous",
        )
    )
    figure.update_layout(title="CoursePulse Engagement Funnel", template="plotly_white", height=380)
    return figure


def revenue_anomaly_figure() -> go.Figure:
    """Daily revenue with rolling average and >2-sigma anomaly markers."""
    daily = revenue_trends()
    anomalies = revenue_anomalies()
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=daily["date"], y=daily["revenue"], mode="lines", name="Daily revenue",
            line={"color": COLORS["blue"], "width": 1.5},
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Revenue: $%{y:,.2f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=daily["date"], y=daily["rolling_7d"], mode="lines", name="7-day rolling",
            line={"color": COLORS["orange"], "width": 2.5},
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>7-day avg: $%{y:,.2f}<extra></extra>",
        )
    )
    if not anomalies.empty:
        figure.add_trace(
            go.Scatter(
                x=anomalies["date"], y=anomalies["revenue"], mode="markers", name="Anomaly (>2σ)",
                marker={"color": "red", "size": 9, "symbol": "x"},
                customdata=anomalies[["z_score"]],
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Revenue: $%{y:,.2f}<br>Z-score: %{customdata[0]:.2f}<extra></extra>",
            )
        )
    figure.update_layout(
        title="Daily Revenue with Anomaly Detection",
        xaxis_title="Date", yaxis_title="Revenue ($)",
        template="plotly_white", height=420, hovermode="x unified",
        legend={"orientation": "h", "y": -0.2},
    )
    return figure


def overview_insight(funnel: dict, courses: pd.DataFrame, categories: pd.DataFrame) -> str:
    """Auto-generated primary observation for the Overview page."""
    totals = funnel["totals"]
    rates = funnel["rates"]
    weakest_stage = (
        "Preview -> Enrollment"
        if rates["preview_to_enrollment"] <= rates["search_to_preview"]
        else "Search -> Preview"
    )
    weakest_rate = min(rates["preview_to_enrollment"], rates["search_to_preview"])
    best_course = ""
    if not courses.dropna(subset=["conversion"]).empty:
        top = courses.sort_values("conversion", ascending=False).iloc[0]
        best_course = f" The strongest course is **{top['course_name']}** at {top['conversion']:.1f}% conversion."
    weakest_category = ""
    if not categories.empty:
        cat = categories.sort_values("conversion").iloc[0]
        weakest_category = f" The weakest category is **{cat['category']}** at {cat['conversion']:.1f}% conversion."
    return (
        f"{funnel['unique_users']} users generated {totals['search'] + totals['preview'] + totals['enrollment']} events: "
        f"{totals['search']} searches, {totals['preview']} previews, and {totals['enrollment']} enrollments. "
        f"The biggest friction point is **{weakest_stage}** at {weakest_rate:.1f}% conversion."
        + best_course
        + weakest_category
        + f" {funnel['direct_previews']} of {funnel['users']['preview']} previewing users arrived directly (no search first), "
        f"so browse-driven discovery matters as much as search."
    )


def observed_patterns(
    funnel: dict, courses: pd.DataFrame, categories: pd.DataFrame, churn: pd.DataFrame
) -> list[str]:
    """Evidence-based pattern bullets for the Root Causes page."""
    patterns = []
    drop_preview = funnel["dropoffs"]["preview_to_enrollment"]
    patterns.append(
        f"**Enrollment drop-off dominates:** {drop_preview['count']} of {funnel['totals']['preview']} previews "
        f"({drop_preview['percent']:.1f}%) never convert to enrollment."
    )
    patterns.append(
        f"**Browse-driven discovery:** {funnel['direct_previews']} of {funnel['users']['preview']} preview users "
        f"never searched first — direct navigation delivers a large share of previews."
    )
    convertible = courses.dropna(subset=["conversion"])
    if not convertible.empty:
        worst = convertible.sort_values("conversion").iloc[0]
        patterns.append(
            f"**Weakest course:** {worst['course_name']} converts {worst['conversion']:.1f}% of "
            f"{int(worst['previews'])} previews."
        )
    if not categories.empty:
        weakest_cat = categories.sort_values("conversion").iloc[0]
        patterns.append(
            f"**Weakest category:** {weakest_cat['category']} converts {weakest_cat['conversion']:.1f}% of "
            f"{int(weakest_cat['views'])} views."
        )
    if not churn.empty:
        worst_segment = churn.iloc[0]
        patterns.append(
            f"**Churn risk segment:** {worst_segment['customer_segment']} shows {worst_segment['churn_rate']:.1f}% "
            f"activity churn ({int(worst_segment['churned_customers'])} of {int(worst_segment['customers'])} "
            "customers inactive 90+ days)."
        )
    return patterns


def recommended_actions(funnel: dict, courses: pd.DataFrame, churn: pd.DataFrame, alerts: pd.DataFrame) -> str:
    """Prioritized, data-derived recommended actions."""
    actions = [
        f"1. **Fix preview→enrollment friction** ({funnel['rates']['preview_to_enrollment']:.1f}% today): add clear "
        "pricing, syllabus, and a one-click enroll action on the preview page. Owner: product. Expected impact: "
        f"recover part of the {funnel['dropoffs']['preview_to_enrollment']['count']}-preview drop-off."
    ]
    convertible = courses.dropna(subset=["conversion"])
    if not convertible.empty:
        worst = convertible.sort_values("conversion").iloc[0]
        actions.append(
            f"2. **Audit {worst['course_name']}** ({worst['conversion']:.1f}% conversion): benchmark its preview page "
            "against the top course and A/B test the layout. Owner: course ops."
        )
    if not churn.empty:
        worst_segment = churn.iloc[0]
        actions.append(
            f"3. **Retention program for {worst_segment['customer_segment']}** ({worst_segment['churn_rate']:.1f}% churn): "
            "win-back offers targeting the 90+ day inactive cohort. Owner: CRM."
        )
    breaches = alerts[alerts["status"] == "BREACH"] if not alerts.empty else alerts
    for _, row in breaches.iterrows():
        actions.append(
            f"4. **Alert breach:** {row['metric']} is {row['value']} (threshold {row['direction']} {row['threshold']}). {row['message']}"
        )
    return "\n\n".join(actions)
