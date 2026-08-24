# -*- coding: utf-8 -*-
"""
GroupBy Segmentation Analysis
Member 2: Sreedhil Pavishanker B - Data Analyst
SYNERGY CoursePulse / Kalvium Community

Responsibilities covered:
- KPIs, EDA, segmentation, root-cause investigation
- GroupBy multi-dimensional aggregations
- Pivot tables for two-dimensional views
- Ranking top/bottom performers
- Actionable insight surface with CSV export

Business Context:
  Average churn rate is 5%. But:
    - Enterprise  (5%  of base) -> 1%  churn, 70% of revenue
    - SMB         (40% of base) -> 12% churn
    - Startup     (55% of base) -> 8%  churn
  One dataset-wide statistic hides the real story.
  Use groupby to segment and surface actionable insights.

Tasks:
  Task 1: Single-Level GroupBy with Multiple Aggregations
  Task 2: Multi-Level GroupBy (customer_type x product)
  Task 3: Pivot Table (two-dimensional revenue view)
  Task 4: Rank and Identify Top/Bottom Performers
  Task 5: Surface Actionable Segment Insights -> CSV
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Force stdout to UTF-8 on Windows to avoid cp1252 codec errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")
os.makedirs("output", exist_ok=True)

# ---------------------------------------------------------------
# 0. Synthetic Dataset
#    Mirrors the stated segment profile exactly:
#      Enterprise : 5%  of customers, 1%  monthly churn, ~70% revenue
#      SMB        : 40% of customers, 12% monthly churn, mid revenue
#      Startup    : 55% of customers,  8% monthly churn, low revenue
# ---------------------------------------------------------------
np.random.seed(42)

N = 2000

# Segment proportions
n_enterprise = int(N * 0.05)   # 100
n_smb        = int(N * 0.40)   # 800
n_startup    = N - n_enterprise - n_smb  # 1100

# Products offered on the CoursePulse platform
products = ["Core", "Pro", "Enterprise Suite"]

def make_segment(n, churn_prob, rev_mean, rev_std, ctype, prod_weights):
    rng = np.random.default_rng(seed=abs(hash(ctype)) % (2**31))
    return pd.DataFrame({
        "customer_id":      range(n),            # temp; reassigned below
        "customer_type":    ctype,
        "product":          rng.choice(products, size=n, p=prod_weights),
        "churn":            rng.binomial(1, churn_prob, size=n),
        "revenue":          np.clip(rng.normal(rev_mean, rev_std, size=n), 50, None).round(2),
        "support_tickets":  rng.poisson(lam=max(churn_prob * 10, 1), size=n).astype(int),
        "months_active":    rng.integers(1, 37, size=n),
    })

df_enterprise = make_segment(n_enterprise,  0.01,  12_000, 3_000, "Enterprise",
                              [0.05, 0.15, 0.80])
df_smb        = make_segment(n_smb,          0.12,   1_800,   600, "SMB",
                              [0.20, 0.65, 0.15])
df_startup    = make_segment(n_startup,       0.08,     420,   180, "Startup",
                              [0.55, 0.40, 0.05])

df = pd.concat([df_enterprise, df_smb, df_startup], ignore_index=True)
df["customer_id"] = ["CUST_{:04d}".format(i + 1) for i in range(len(df))]

print("=" * 70)
print("GROUPBY SEGMENTATION ANALYSIS - CoursePulse / Kalvium Community")
print("Member 2: Sreedhil Pavishanker B (Data Analyst)")
print("=" * 70)
print("Dataset: {:,} customers | Segments: {}".format(
    len(df), df["customer_type"].unique().tolist()))
print("Columns: {}".format(df.columns.tolist()))
print()


# ==============================================================
# TASK 1: Single-Level GroupBy with Multiple Aggregations
# ==============================================================
print("-" * 60)
print("TASK 1: Single-Level GroupBy with Multiple Aggregations")
print("-" * 60)

segment_metrics = df.groupby("customer_type").agg({
    "churn":            "mean",
    "revenue":          "sum",
    "customer_id":      "count",
    "support_tickets":  "mean",
})

segment_metrics.columns = [
    "churn_rate",
    "total_revenue",
    "customer_count",
    "avg_support_tickets",
]

print("\nsegment_metrics (raw groupby output):")
print(segment_metrics.to_string())

# --- Plotly bar chart: churn rate by segment ---
fig1 = px.bar(
    segment_metrics.reset_index(),
    x="customer_type",
    y="churn_rate",
    color="customer_type",
    color_discrete_map={
        "Enterprise": "#2ecc71",
        "SMB":        "#e67e22",
        "Startup":    "#e74c3c",
    },
    text=segment_metrics["churn_rate"].apply(lambda v: f"{v:.1%}").values,
    title="Task 1 — Churn Rate by Customer Segment",
    labels={"customer_type": "Segment", "churn_rate": "Churn Rate"},
    template="plotly_dark",
)
fig1.update_traces(textposition="outside")
fig1.update_layout(showlegend=False, yaxis_tickformat=".0%")
fig1.write_html("output/task1_churn_by_segment.html")
fig1.write_image("output/task1_churn_by_segment.png", scale=2)
print("\nSaved: output/task1_churn_by_segment.html")
print("Saved: output/task1_churn_by_segment.png")


# ==============================================================
# TASK 2: Multi-Level GroupBy (customer_type x product)
# ==============================================================
print()
print("-" * 60)
print("TASK 2: Multi-Level GroupBy")
print("-" * 60)

# Two dimensions simultaneously
product_segment = df.groupby(["customer_type", "product"]).agg({
    "revenue":     "sum",
    "customer_id": "count",
})

product_segment.columns = ["total_revenue", "customer_count"]

# Unstack for cleaner view
product_segment_pivot = product_segment.unstack()
print("\nproduct_segment_pivot (revenue + count by type × product):")
print(product_segment_pivot.to_string())

# Heatmap: revenue by segment x product
rev_matrix = product_segment["total_revenue"].unstack(fill_value=0)

fig2 = px.imshow(
    rev_matrix,
    text_auto=".2s",
    color_continuous_scale="Blues",
    title="Task 2 — Revenue Heatmap: Customer Type × Product",
    labels={"x": "Product", "y": "Customer Type", "color": "Revenue ($)"},
    template="plotly_dark",
)
fig2.write_html("output/task2_revenue_heatmap.html")
fig2.write_image("output/task2_revenue_heatmap.png", scale=2)
print("\nSaved: output/task2_revenue_heatmap.html")
print("Saved: output/task2_revenue_heatmap.png")


# ==============================================================
# TASK 3: Pivot Table
# ==============================================================
print()
print("-" * 60)
print("TASK 3: Pivot Table")
print("-" * 60)

# Two-dimensional view: customer_type rows, product columns
pivot = pd.pivot_table(
    df,
    values="revenue",
    index="customer_type",
    columns="product",
    aggfunc="sum",
)

print("\nPivot Table — Revenue by customer_type (rows) × product (columns):")
print(pivot.to_string())

# Row totals and column totals
pivot_with_totals = pivot.copy()
pivot_with_totals["TOTAL"] = pivot_with_totals.sum(axis=1)
totals_row = pivot_with_totals.sum(axis=0)
totals_row.name = "TOTAL"
pivot_with_totals = pd.concat([pivot_with_totals, totals_row.to_frame().T])

print("\nPivot with totals:")
print(pivot_with_totals.to_string())

# Grouped bar chart
pivot_reset = pivot.reset_index().melt(
    id_vars="customer_type", var_name="product", value_name="revenue"
)
fig3 = px.bar(
    pivot_reset,
    x="customer_type",
    y="revenue",
    color="product",
    barmode="group",
    title="Task 3 — Pivot Table Visualisation: Revenue by Type × Product",
    labels={"customer_type": "Segment", "revenue": "Total Revenue ($)", "product": "Product"},
    template="plotly_dark",
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig3.write_html("output/task3_pivot_bar.html")
fig3.write_image("output/task3_pivot_bar.png", scale=2)
print("\nSaved: output/task3_pivot_bar.html")
print("Saved: output/task3_pivot_bar.png")


# ==============================================================
# TASK 4: Rank and Identify Top/Bottom Performers
# ==============================================================
print()
print("-" * 60)
print("TASK 4: Rank and Identify Top/Bottom Performers")
print("-" * 60)

# Rank segments by churn
segment_metrics["churn_rank"] = segment_metrics["churn_rate"].rank()

# Revenue contribution %
segment_metrics["revenue_contribution"] = (
    segment_metrics["total_revenue"] / segment_metrics["total_revenue"].sum() * 100
)

# Sort to see worst churn first
worst_first = segment_metrics.sort_values("churn_rate", ascending=False)
print("\nSegments ranked worst churn -> best:")
print(worst_first.to_string())

print("\nRevenue contribution vs churn rate:")
print(segment_metrics[["revenue_contribution", "churn_rate"]].to_string())

# Bubble chart: churn rate vs revenue contribution (bubble = customer count)
bubble_data = segment_metrics.reset_index()
fig4 = px.scatter(
    bubble_data,
    x="churn_rate",
    y="revenue_contribution",
    size="customer_count",
    color="customer_type",
    text="customer_type",
    title="Task 4 — Churn Rate vs Revenue Contribution (bubble = customer count)",
    labels={
        "churn_rate":           "Churn Rate",
        "revenue_contribution": "Revenue Contribution (%)",
        "customer_type":        "Segment",
    },
    template="plotly_dark",
    color_discrete_map={
        "Enterprise": "#2ecc71",
        "SMB":        "#e67e22",
        "Startup":    "#e74c3c",
    },
    size_max=80,
)
fig4.update_traces(textposition="top center")
fig4.update_layout(xaxis_tickformat=".0%")
fig4.write_html("output/task4_rank_bubble.html")
fig4.write_image("output/task4_rank_bubble.png", scale=2)
print("\nSaved: output/task4_rank_bubble.html")
print("Saved: output/task4_rank_bubble.png")


# ==============================================================
# TASK 5: Surface Actionable Segment Insights
# ==============================================================
print()
print("-" * 60)
print("TASK 5: Surface Actionable Segment Insights")
print("-" * 60)

# Create insight summary
insights = []

for segment in segment_metrics.index:
    row = segment_metrics.loc[segment]

    insight = {
        "segment":              segment,
        "customer_count":       int(row["customer_count"]),
        "churn_rate":           f"{row['churn_rate']:.1%}",
        "total_revenue":        f"${row['total_revenue']:,.0f}",
        "revenue_contribution": f"{row['revenue_contribution']:.1f}%",
        "avg_support_tickets":  f"{row['avg_support_tickets']:.2f}",
        "churn_rank":           int(row["churn_rank"]),
        "action":               "",
    }

    # Action thresholds based on churn rate
    if row["churn_rate"] > 0.10:
        insight["action"] = (
            "HIGH PRIORITY: Churn above 10%. Investigate pain points, "
            "offer targeted retention discounts, review onboarding."
        )
    elif row["churn_rate"] < 0.02:
        insight["action"] = (
            "Healthy. Maintain current service level. "
            "Focus on upsell and expansion revenue."
        )
    else:
        insight["action"] = (
            "Monitor. Churn within acceptable range. "
            "Run quarterly NPS surveys and watch for uptick."
        )

    insights.append(insight)

insights_df = pd.DataFrame(insights)

print("\nActionable Segment Insights:")
print(insights_df.to_string(index=False))

# Save to CSV
insights_df.to_csv("output/segment_insights.csv", index=False)
print("\nSaved: output/segment_insights.csv")

# Plotly table for visual output
header_vals  = list(insights_df.columns)
cell_vals    = [insights_df[c] for c in insights_df.columns]

fig5 = go.Figure(data=[go.Table(
    header=dict(
        values=[f"<b>{h.replace('_', ' ').title()}</b>" for h in header_vals],
        fill_color="#1f2c56",
        font=dict(color="white", size=12),
        align="left",
        height=32,
    ),
    cells=dict(
        values=cell_vals,
        fill_color=[
            [
                "#1a6640" if "HIGH" in str(v) else
                "#163060" if "Healthy" in str(v) else
                "#2e2e2e"
                for v in insights_df["action"]
            ]
        ] * len(header_vals),
        font=dict(color="white", size=11),
        align="left",
        height=28,
    ),
)])
fig5.update_layout(
    title="Task 5 — Actionable Segment Insights Table",
    template="plotly_dark",
    margin=dict(l=20, r=20, t=60, b=20),
)
fig5.write_html("output/task5_segment_insights_table.html")
fig5.write_image("output/task5_segment_insights_table.png", scale=2)
print("Saved: output/task5_segment_insights_table.html")
print("Saved: output/task5_segment_insights_table.png")


# ==============================================================
# Summary Dashboard (all 5 tasks in one view)
# ==============================================================
print()
print("-" * 60)
print("BONUS: Combined Summary Dashboard")
print("-" * 60)

fig_dash = make_subplots(
    rows=2, cols=2,
    subplot_titles=[
        "Churn Rate by Segment",
        "Revenue Contribution by Segment",
        "Revenue Heatmap (Type x Product)",
        "Churn Rate vs Revenue Contribution",
    ],
    specs=[
        [{"type": "bar"},      {"type": "pie"}],
        [{"type": "heatmap"},  {"type": "scatter"}],
    ],
)

# -- (1,1) Churn bar
colors_map = {"Enterprise": "#2ecc71", "SMB": "#e67e22", "Startup": "#e74c3c"}
sm = segment_metrics.reset_index()
fig_dash.add_trace(
    go.Bar(
        x=sm["customer_type"],
        y=sm["churn_rate"],
        marker_color=[colors_map[t] for t in sm["customer_type"]],
        text=[f"{v:.1%}" for v in sm["churn_rate"]],
        textposition="outside",
        showlegend=False,
    ),
    row=1, col=1,
)

# -- (1,2) Revenue pie
fig_dash.add_trace(
    go.Pie(
        labels=sm["customer_type"],
        values=sm["total_revenue"],
        marker_colors=[colors_map[t] for t in sm["customer_type"]],
        hole=0.4,
    ),
    row=1, col=2,
)

# -- (2,1) Revenue heatmap
fig_dash.add_trace(
    go.Heatmap(
        z=rev_matrix.values,
        x=rev_matrix.columns.tolist(),
        y=rev_matrix.index.tolist(),
        colorscale="Blues",
        showscale=False,
    ),
    row=2, col=1,
)

# -- (2,2) Bubble scatter
fig_dash.add_trace(
    go.Scatter(
        x=sm["churn_rate"],
        y=sm["revenue_contribution"],
        mode="markers+text",
        marker=dict(
            size=sm["customer_count"] / 10,
            color=[colors_map[t] for t in sm["customer_type"]],
            opacity=0.8,
        ),
        text=sm["customer_type"],
        textposition="top center",
        showlegend=False,
    ),
    row=2, col=2,
)

fig_dash.update_layout(
    title_text="GroupBy Segmentation Dashboard — CoursePulse (Member 2: Sreedhil Pavishanker B)",
    template="plotly_dark",
    height=800,
    showlegend=True,
)
fig_dash.write_html("output/segmentation_dashboard.html")
fig_dash.write_image("output/segmentation_dashboard.png", scale=2)
print("Saved: output/segmentation_dashboard.html")
print("Saved: output/segmentation_dashboard.png")


# ---------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------
print()
print("=" * 70)
print("ANALYSIS COMPLETE - All outputs written to output/")
print("  Task 1 -> output/task1_churn_by_segment.html / .png")
print("  Task 2 -> output/task2_revenue_heatmap.html / .png")
print("  Task 3 -> output/task3_pivot_bar.html / .png")
print("  Task 4 -> output/task4_rank_bubble.html / .png")
print("  Task 5 -> output/task5_segment_insights_table.html / .png")
print("          -> output/segment_insights.csv")
print("  Bonus  -> output/segmentation_dashboard.html / .png")
print("=" * 70)
