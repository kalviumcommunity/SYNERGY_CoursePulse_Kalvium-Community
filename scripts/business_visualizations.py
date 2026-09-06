"""Create labelled, accessible business visualisations from CoursePulse data."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "output"

PALETTE = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "black": "#222222",
    "grid": "#D9E2EC",
}
SEGMENT_COLORS = [PALETTE["blue"], PALETTE["orange"], PALETTE["green"], PALETTE["red"], PALETTE["purple"]]
CHART_FILES = (
    "chart1_revenue_by_segment.png",
    "chart2_revenue_trend.png",
    "chart3_order_value_distribution.png",
    "chart4_revenue_composition.png",
    "chart5_customer_orders_vs_revenue.png",
)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and prepare the real CoursePulse orders and customer dimensions."""
    orders = pd.read_csv(DATA_DIR / "orders_5000.csv", parse_dates=["order_date"])
    customers = pd.read_csv(DATA_DIR / "customers_1000.csv")
    orders["order_amount"] = pd.to_numeric(orders["order_amount"], errors="coerce")
    orders = orders.dropna(subset=["order_date", "order_amount", "customer_id"])
    orders = orders[orders["order_amount"] > 0].copy()
    orders = orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
    orders["customer_segment"] = orders["customer_segment"].fillna("Unknown")
    return orders, customers


def money_axis(value: float, _position: int) -> str:
    """Format large currency values without hiding their units."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def style_axes(ax: plt.Axes) -> None:
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def chart1_revenue_by_segment(orders: pd.DataFrame, output_dir: Path) -> None:
    """Bar chart: compare valid revenue across customer segments."""
    cutoff = orders["order_date"].max() - pd.Timedelta(days=90)
    data = (
        orders[orders["order_date"] >= cutoff]
        .groupby("customer_segment", as_index=False)["order_amount"]
        .sum()
        .sort_values("order_amount")
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(data["customer_segment"], data["order_amount"], color=SEGMENT_COLORS[: len(data)])
    ax.set_title("Revenue by Customer Segment: Latest 90 Days", fontsize=15, fontweight="bold")
    ax.set_xlabel("Revenue ($)")
    ax.set_ylabel("Customer Segment")
    ax.xaxis.set_major_formatter(FuncFormatter(money_axis))
    for bar, value in zip(bars, data["order_amount"]):
        ax.text(value, bar.get_y() + bar.get_height() / 2, f" ${value:,.0f}", va="center", fontsize=9)
    peak = data.iloc[-1]
    ax.annotate(
        f"Highest segment\n${peak['order_amount']:,.0f}",
        xy=(peak["order_amount"], peak["customer_segment"]),
        xytext=(-105, 24), textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": PALETTE["red"]},
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": PALETTE["red"]},
    )
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output_dir / CHART_FILES[0], dpi=300, bbox_inches="tight")
    plt.close(fig)


def chart2_revenue_trend(orders: pd.DataFrame, output_dir: Path) -> None:
    """Line chart: show the latest 12 monthly segment revenue trends."""
    latest_month = orders["order_date"].max().to_period("M")
    first_month = latest_month - 11
    recent = orders[orders["order_date"].dt.to_period("M") >= first_month].copy()
    monthly = recent.assign(month=recent["order_date"].dt.to_period("M").dt.to_timestamp())
    monthly = monthly.groupby(["month", "customer_segment"], as_index=False)["order_amount"].sum()
    top_segments = monthly.groupby("customer_segment")["order_amount"].sum().nlargest(3).index.tolist()
    fig, ax = plt.subplots(figsize=(11, 6))
    for index, segment in enumerate(top_segments):
        series = monthly[monthly["customer_segment"] == segment].sort_values("month")
        ax.plot(series["month"], series["order_amount"], marker="o", linewidth=2.2, label=segment, color=SEGMENT_COLORS[index])
    peak = monthly[monthly["customer_segment"].isin(top_segments)].loc[monthly["order_amount"].idxmax()]
    ax.annotate(
        f"Peak: ${peak['order_amount']:,.0f}",
        xy=(peak["month"], peak["order_amount"]), xytext=(10, 15), textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": PALETTE["red"]},
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": PALETTE["red"]},
    )
    ax.set_title("Monthly Revenue Trend by Top Three Segments", fontsize=15, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue ($)")
    ax.yaxis.set_major_formatter(FuncFormatter(money_axis))
    ax.legend(title="Customer Segment", loc="upper left")
    ax.grid(axis="both", color=PALETTE["grid"], linewidth=0.8, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / CHART_FILES[1], dpi=300, bbox_inches="tight")
    plt.close(fig)


def chart3_order_value_distribution(orders: pd.DataFrame, output_dir: Path) -> None:
    """Histogram: show the distribution and median of positive order values."""
    median = orders["order_amount"].median()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(orders["order_amount"], bins=20, color=PALETTE["blue"], edgecolor="white", alpha=0.9)
    ax.axvline(median, color=PALETTE["red"], linestyle="--", linewidth=2, label=f"Median: ${median:,.2f}")
    ax.annotate(
        f"Median order\n${median:,.2f}", xy=(median, ax.get_ylim()[1] * 0.72), xytext=(35, 0),
        textcoords="offset points", arrowprops={"arrowstyle": "->", "color": PALETTE["red"]},
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": PALETTE["red"]},
    )
    ax.set_title("Distribution of Positive Order Values", fontsize=15, fontweight="bold")
    ax.set_xlabel("Order Value ($)")
    ax.set_ylabel("Number of Orders")
    ax.xaxis.set_major_formatter(FuncFormatter(money_axis))
    ax.legend(loc="upper right")
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output_dir / CHART_FILES[2], dpi=300, bbox_inches="tight")
    plt.close(fig)


def chart4_revenue_composition(orders: pd.DataFrame, output_dir: Path) -> None:
    """Stacked bar: show quarterly revenue composition by segment."""
    data = orders.assign(quarter=orders["order_date"].dt.to_period("Q").astype(str))
    pivot = data.pivot_table(index="quarter", columns="customer_segment", values="order_amount", aggfunc="sum", fill_value=0).sort_index()
    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = np.zeros(len(pivot))
    for index, segment in enumerate(pivot.columns):
        values = pivot[segment].to_numpy()
        ax.bar(pivot.index, values, bottom=bottom, label=segment, color=SEGMENT_COLORS[index % len(SEGMENT_COLORS)])
        bottom += values
    largest_quarter = pivot.sum(axis=1).idxmax()
    ax.annotate(
        f"Largest quarter\n${pivot.loc[largest_quarter].sum():,.0f}",
        xy=(list(pivot.index).index(largest_quarter), pivot.loc[largest_quarter].sum()), xytext=(0, 15),
        textcoords="offset points", ha="center", arrowprops={"arrowstyle": "->", "color": PALETTE["red"]},
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": PALETTE["red"]},
    )
    ax.set_title("Quarterly Revenue Composition by Customer Segment", fontsize=15, fontweight="bold")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Revenue ($)")
    ax.yaxis.set_major_formatter(FuncFormatter(money_axis))
    ax.legend(title="Customer Segment", loc="upper left", ncol=2)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output_dir / CHART_FILES[3], dpi=300, bbox_inches="tight")
    plt.close(fig)


def chart5_customer_correlation(orders: pd.DataFrame, output_dir: Path) -> None:
    """Scatter plot: test whether order volume relates to customer revenue."""
    data = orders.groupby(["customer_id", "customer_name"], as_index=False).agg(
        order_count=("order_id", "nunique"), customer_revenue=("order_amount", "sum")
    )
    correlation = data["order_count"].corr(data["customer_revenue"])
    slope, intercept = np.polyfit(data["order_count"], data["customer_revenue"], 1)
    x_values = np.linspace(data["order_count"].min(), data["order_count"].max(), 100)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(data["order_count"], data["customer_revenue"], color=PALETTE["blue"], alpha=0.55, edgecolors="white", label="Customer")
    ax.plot(x_values, slope * x_values + intercept, color=PALETTE["red"], linewidth=2, label=f"Trend line (r={correlation:.2f})")
    outlier = data.loc[data["customer_revenue"].idxmax()]
    ax.annotate(
        f"Highest revenue\n{outlier['customer_name']}", xy=(outlier["order_count"], outlier["customer_revenue"]),
        xytext=(-90, -35), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": PALETTE["red"]},
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": PALETTE["red"]},
    )
    ax.set_title("Customer Order Volume and Revenue Relationship", fontsize=15, fontweight="bold")
    ax.set_xlabel("Number of Orders per Customer")
    ax.set_ylabel("Customer Revenue ($)")
    ax.yaxis.set_major_formatter(FuncFormatter(money_axis))
    ax.legend(loc="upper left")
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(output_dir / CHART_FILES[4], dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_charts(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Build all five required charts and return their output paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    orders, _customers = load_data()
    chart1_revenue_by_segment(orders, output_dir)
    chart2_revenue_trend(orders, output_dir)
    chart3_order_value_distribution(orders, output_dir)
    chart4_revenue_composition(orders, output_dir)
    chart5_customer_correlation(orders, output_dir)
    return [output_dir / filename for filename in CHART_FILES]


if __name__ == "__main__":
    paths = build_charts()
    print(f"Created {len(paths)} charts in {OUTPUT_DIR}")