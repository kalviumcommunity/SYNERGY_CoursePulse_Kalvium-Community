"""Build interactive Plotly charts from the real CoursePulse order data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "output" / "interactive_charts"
COLORS = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73"}


def load_orders() -> pd.DataFrame:
    """Load valid orders and customer dimensions with normalized dates."""
    orders = pd.read_csv(DATA_DIR / "orders_5000.csv", parse_dates=["order_date"])
    customers = pd.read_csv(DATA_DIR / "customers_1000.csv", usecols=["customer_id", "customer_segment", "region"])
    orders = orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
    orders = orders[
        orders["order_status"].isin(["completed", "shipped", "delivered"])
        & (orders["order_amount"] > 0)
    ].copy()
    orders["customer_segment"] = orders["customer_segment"].fillna("Unknown")
    return orders


def daily_revenue(orders: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue, order count, and average order value by day."""
    return (
        orders.assign(date=orders["order_date"].dt.normalize())
        .groupby("date", as_index=False)
        .agg(revenue=("order_amount", "sum"), order_count=("order_id", "nunique"), average_order_value=("order_amount", "mean"))
        .sort_values("date")
    )


def revenue_trend(orders: pd.DataFrame) -> go.Figure:
    """Create a daily revenue trend with a multi-field hover tooltip."""
    data = daily_revenue(orders)
    figure = go.Figure(
        go.Scatter(
            x=data["date"],
            y=data["revenue"],
            mode="lines+markers",
            line={"color": COLORS["blue"], "width": 2},
            marker={"size": 7},
            customdata=data[["order_count", "average_order_value"]],
            hovertemplate=(
                "<b>%{x|%Y-%m-%d}</b><br>Revenue: $%{y:,.2f}<br>"
                "Orders: %{customdata[0]:,}<br>Average order: $%{customdata[1]:,.2f}<extra></extra>"
            ),
            name="Revenue",
        )
    )
    figure.update_layout(
        title="Daily Revenue Trend",
        xaxis_title="Date",
        yaxis_title="Revenue ($)",
        hovermode="x unified",
        dragmode="zoom",
        height=500,
        template="plotly_white",
    )
    figure.update_xaxes(
        rangeselector={"buttons": [
            {"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
            {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
            {"count": 1, "label": "YTD", "step": "year", "stepmode": "todate"},
            {"step": "all", "label": "All"},
        ]},
        rangeslider={"visible": True},
    )
    return figure


def segment_performance(orders: pd.DataFrame) -> go.Figure:
    """Create a bar chart with revenue, count, and average-value hover fields."""
    data = (
        orders.groupby("customer_segment", as_index=False)
        .agg(revenue=("order_amount", "sum"), order_count=("order_id", "nunique"), average_order_value=("order_amount", "mean"))
        .sort_values("revenue", ascending=False)
    )
    figure = go.Figure(
        go.Bar(
            x=data["customer_segment"],
            y=data["revenue"],
            marker_color=COLORS["orange"],
            customdata=data[["order_count", "average_order_value"]],
            hovertemplate=(
                "<b>%{x}</b><br>Revenue: $%{y:,.2f}<br>Orders: %{customdata[0]:,}<br>"
                "Average order: $%{customdata[1]:,.2f}<extra></extra>"
            ),
            name="Revenue",
        )
    )
    figure.update_layout(
        title="Revenue by Customer Segment",
        xaxis_title="Customer Segment",
        yaxis_title="Revenue ($)",
        hovermode="closest",
        height=500,
        template="plotly_white",
    )
    return figure


def metric_selector(orders: pd.DataFrame) -> go.Figure:
    """Create one dropdown-controlled chart for revenue, order count, or average value."""
    data = (
        orders.groupby("customer_segment", as_index=False)
        .agg(revenue=("order_amount", "sum"), order_count=("order_id", "nunique"), average_order_value=("order_amount", "mean"))
        .sort_values("revenue", ascending=False)
    )
    metrics = [("Revenue", "revenue", COLORS["blue"], "Revenue ($)"), ("Order Count", "order_count", COLORS["green"], "Orders"), ("Average Order Value", "average_order_value", COLORS["orange"], "Average Order Value ($)")]
    figure = go.Figure()
    for index, (label, field, color, axis_title) in enumerate(metrics):
        figure.add_trace(go.Bar(x=data["customer_segment"], y=data[field], name=label, marker_color=color, visible=index == 0, hovertemplate=f"<b>%{{x}}</b><br>{axis_title}: %{{y:,.2f}}<extra></extra>"))
    buttons = []
    for index, (label, _field, _color, axis_title) in enumerate(metrics):
        visibility = [item == index for item in range(len(metrics))]
        buttons.append({"label": label, "method": "update", "args": [{"visible": visibility}, {"title": f"{label} by Customer Segment", "yaxis": {"title": axis_title}}]})
    figure.update_layout(
        title="Revenue by Customer Segment",
        xaxis_title="Customer Segment",
        yaxis_title="Revenue ($)",
        updatemenus=[{"active": 0, "x": 0, "y": 1.15, "buttons": buttons}],
        height=500,
        template="plotly_white",
    )
    return figure


def interactive_explorer(orders: pd.DataFrame) -> go.Figure:
    """Create a selectable customer explorer with native zoom/pan/reset behavior."""
    data = orders.groupby(["customer_id", "customer_segment"], as_index=False).agg(order_count=("order_id", "nunique"), revenue=("order_amount", "sum"))
    figure = go.Figure(go.Scatter(x=data["order_count"], y=data["revenue"], mode="markers", marker={"color": COLORS["blue"], "size": 10, "opacity": 0.7}, customdata=data[["customer_id", "customer_segment"]], hovertemplate="Customer %{customdata[0]}<br>Segment: %{customdata[1]}<br>Orders: %{x:,}<br>Revenue: $%{y:,.2f}<extra></extra>", name="Customers"))
    figure.update_layout(title="Customer Order Volume Explorer", xaxis_title="Orders per Customer", yaxis_title="Customer Revenue ($)", dragmode="select", hovermode="closest", height=500, template="plotly_white", clickmode="event+select")
    return figure


def export_html(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Export standalone HTML charts that preserve Plotly interactivity."""
    output_dir.mkdir(parents=True, exist_ok=True)
    orders = load_orders()
    figures = {
        "chart1_revenue_trend.html": revenue_trend(orders),
        "chart2_segment_performance.html": segment_performance(orders),
        "chart3_metric_selector.html": metric_selector(orders),
        "chart4_interactive_explorer.html": interactive_explorer(orders),
    }
    paths = []
    for filename, figure in figures.items():
        path = output_dir / filename
        figure.write_html(path, include_plotlyjs=True, full_html=True)
        paths.append(path)
    return paths


if __name__ == "__main__":
    print("Created:", ", ".join(str(path) for path in export_html()))