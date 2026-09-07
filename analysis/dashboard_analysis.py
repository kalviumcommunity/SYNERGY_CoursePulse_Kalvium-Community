"""
dashboard_analysis.py
=====================
Data Analyst (Member 2 - Sreedhil Pavishanker B)

Computes all KPIs, trend data, and segment breakdowns required by the
Business Performance Dashboard.

Outputs saved to output/dashboard/:
  - kpi_summary.json          – five Level-1 KPI cards
  - revenue_trend.csv         – monthly revenue for 2024 (Level-2 chart)
  - customer_trend.csv        – monthly active + churned customers (Level-2)
  - order_status_trend.csv    – monthly order-status breakdown (Level-2)
  - revenue_by_segment.csv    – revenue per customer segment (Level-3)
  - region_revenue.csv        – revenue per region (Level-3)
  - detail_records.csv        – full filtered dataset for Level-4 explorer
"""

import json
import os
import sqlite3
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
OUT_DIR  = os.path.join(BASE_DIR, "output", "dashboard")
os.makedirs(OUT_DIR, exist_ok=True)

CUSTOMERS_PATH = os.path.join(DATA_DIR, "customers_1000.csv")
ORDERS_PATH    = os.path.join(DATA_DIR, "orders_5000.csv")

# ── Load Raw Data ─────────────────────────────────────────────────────────────
print("[1/7] Loading raw data …")
customers = pd.read_csv(CUSTOMERS_PATH, parse_dates=["signup_date"])
orders    = pd.read_csv(ORDERS_PATH,    parse_dates=["order_date"])

# Remap segments to task-spec names where needed
segment_map = {
    "Enterprise": "Enterprise",
    "SMB":        "SMB",
    "B2B":        "Mid-Market",
    "B2C":        "Starter",
}
customers["segment"] = customers["customer_segment"].map(segment_map).fillna(customers["customer_segment"])

# Join orders ↔ customers
df = orders.merge(customers[["customer_id", "segment", "region", "signup_date"]],
                  on="customer_id", how="left")

# Only completed / shipped revenue counts
df_rev = df[df["order_status"].isin(["completed", "shipped"])].copy()

# ── Helper: period labelling ──────────────────────────────────────────────────
df_rev["year_month"] = df_rev["order_date"].dt.to_period("M")
df["year_month"]     = df["order_date"].dt.to_period("M")

# ── LEVEL 1 — KPI Summary ────────────────────────────────────────────────────
print("[2/7] Computing KPI cards …")

# Split data into current period (2024-H2) and previous (2024-H1)
mid = pd.Period("2024-07", freq="M")
curr = df_rev[df_rev["year_month"] >= mid]
prev = df_rev[df_rev["year_month"] <  mid]

def pct_change(curr_val, prev_val):
    if prev_val == 0:
        return 0.0
    return round((curr_val - prev_val) / prev_val * 100, 1)

# 1. Total Revenue ($M)
rev_curr = curr["order_amount"].sum() / 1_000_000
rev_prev = prev["order_amount"].sum() / 1_000_000

# 2. Active Customers (unique buyers)
active_curr = curr["customer_id"].nunique()
active_prev = prev["customer_id"].nunique()

# 3. Avg Order Value
aov_curr = curr["order_amount"].mean()
aov_prev = prev["order_amount"].mean()

# 4. Churn Rate proxy – customers who ordered in H1 but NOT in H2
buyers_h1 = set(prev["customer_id"].unique())
buyers_h2 = set(curr["customer_id"].unique())
churned   = buyers_h1 - buyers_h2
churn_rate_curr = len(churned) / len(buyers_h1) * 100 if buyers_h1 else 0

# Prior period churn proxy (H1 vs pre-H1)
pre = df_rev[df_rev["order_date"] < pd.Timestamp("2024-01-01")]
if len(pre):
    buyers_pre = set(pre["customer_id"].unique())
    churn_prev_val = len(buyers_pre - buyers_h1) / len(buyers_pre) * 100
else:
    churn_prev_val = churn_rate_curr

# 5. Conversion Rate (completed orders / total orders)
total_orders = len(df[df["year_month"] >= mid])
comp_orders  = len(curr)
conv_curr = comp_orders / total_orders * 100 if total_orders else 0

total_prev = len(df[df["year_month"] < mid])
comp_prev  = len(prev)
conv_prev  = comp_prev / total_prev * 100 if total_prev else 0

kpi = {
    "revenue": {
        "label": "Revenue",
        "value": f"${rev_curr:.2f}M",
        "raw": rev_curr,
        "delta_pct": pct_change(rev_curr, rev_prev),
        "delta_str": f"+{pct_change(rev_curr, rev_prev)}%" if pct_change(rev_curr, rev_prev) >= 0 else f"{pct_change(rev_curr, rev_prev)}%",
        "trend": "up" if rev_curr >= rev_prev else "down",
        "justification": "Primary business health indicator; answers 'Are we growing revenue?'"
    },
    "active_customers": {
        "label": "Active Customers",
        "value": f"{active_curr:,}",
        "raw": active_curr,
        "delta_pct": pct_change(active_curr, active_prev),
        "delta_str": f"+{pct_change(active_curr, active_prev)}%" if pct_change(active_curr, active_prev) >= 0 else f"{pct_change(active_curr, active_prev)}%",
        "trend": "up" if active_curr >= active_prev else "down",
        "justification": "Measures market traction; answers 'How many customers actually transacted?'"
    },
    "avg_order_value": {
        "label": "Avg Order Value",
        "value": f"${aov_curr:.0f}",
        "raw": aov_curr,
        "delta_pct": pct_change(aov_curr, aov_prev),
        "delta_str": f"+{pct_change(aov_curr, aov_prev)}%" if pct_change(aov_curr, aov_prev) >= 0 else f"{pct_change(aov_curr, aov_prev)}%",
        "trend": "up" if aov_curr >= aov_prev else "down",
        "justification": "Measures spend depth; answers 'Are customers buying more per transaction?'"
    },
    "churn_rate": {
        "label": "Churn Rate",
        "value": f"{churn_rate_curr:.1f}%",
        "raw": churn_rate_curr,
        "delta_pct": pct_change(churn_rate_curr, churn_prev_val),
        "delta_str": f"+{pct_change(churn_rate_curr, churn_prev_val)}%" if pct_change(churn_rate_curr, churn_prev_val) >= 0 else f"{pct_change(churn_rate_curr, churn_prev_val)}%",
        "trend": "down" if churn_rate_curr >= churn_prev_val else "up",   # lower churn = up (good)
        "justification": "Retention metric; answers 'Are we losing customers between periods?'"
    },
    "conversion_rate": {
        "label": "Conversion Rate",
        "value": f"{conv_curr:.1f}%",
        "raw": conv_curr,
        "delta_pct": pct_change(conv_curr, conv_prev),
        "delta_str": f"+{pct_change(conv_curr, conv_prev)}%" if pct_change(conv_curr, conv_prev) >= 0 else f"{pct_change(conv_curr, conv_prev)}%",
        "trend": "up" if conv_curr >= conv_prev else "down",
        "justification": "Operational efficiency metric; answers 'What share of orders are successfully fulfilled?'"
    },
}

with open(os.path.join(OUT_DIR, "kpi_summary.json"), "w") as f:
    json.dump(kpi, f, indent=2)
print("   → kpi_summary.json saved")

# ── LEVEL 2 — Trend Charts ───────────────────────────────────────────────────
print("[3/7] Building trend datasets …")

# Chart 1 – Monthly Revenue Trend
rev_trend = (
    df_rev.groupby("year_month")["order_amount"]
    .sum()
    .reset_index()
)
rev_trend["year_month"] = rev_trend["year_month"].astype(str)
rev_trend.columns = ["month", "revenue"]
rev_trend["revenue_m"] = rev_trend["revenue"] / 1_000_000
rev_trend.to_csv(os.path.join(OUT_DIR, "revenue_trend.csv"), index=False)

# Chart 2 – Active vs Churned Customers per month
monthly_buyers = df_rev.groupby("year_month")["customer_id"].nunique().reset_index()
monthly_buyers.columns = ["year_month", "active_customers"]

# Simple churn proxy: customers present in previous month but not this
periods = sorted(monthly_buyers["year_month"].unique())
churned_list = []
buyer_sets = {
    p: set(df_rev[df_rev["year_month"] == p]["customer_id"].unique())
    for p in periods
}
for i, p in enumerate(periods):
    if i == 0:
        churned_list.append(0)
    else:
        prev_p = periods[i - 1]
        churned_list.append(len(buyer_sets[prev_p] - buyer_sets[p]))

monthly_buyers["churned_customers"] = churned_list
monthly_buyers["year_month"] = monthly_buyers["year_month"].astype(str)
monthly_buyers.to_csv(os.path.join(OUT_DIR, "customer_trend.csv"), index=False)

# Chart 3 – Order Status Breakdown by Month
status_trend = (
    df.groupby(["year_month", "order_status"])
    .size()
    .reset_index(name="count")
)
status_trend["year_month"] = status_trend["year_month"].astype(str)
status_trend.to_csv(os.path.join(OUT_DIR, "order_status_trend.csv"), index=False)

print("   → revenue_trend.csv, customer_trend.csv, order_status_trend.csv saved")

# ── LEVEL 3 — Segment Charts ─────────────────────────────────────────────────
print("[4/7] Building segment datasets …")

# Revenue by Customer Segment
seg_rev = (
    df_rev.groupby("segment")["order_amount"]
    .sum()
    .reset_index()
)
seg_rev.columns = ["segment", "revenue"]
seg_rev["revenue_m"] = seg_rev["revenue"] / 1_000_000
seg_rev = seg_rev.sort_values("revenue_m", ascending=False)
seg_rev.to_csv(os.path.join(OUT_DIR, "revenue_by_segment.csv"), index=False)

# Revenue by Region
region_rev = (
    df_rev.groupby("region")["order_amount"]
    .sum()
    .reset_index()
)
region_rev.columns = ["region", "revenue"]
region_rev["revenue_m"] = region_rev["revenue"] / 1_000_000
region_rev = region_rev.sort_values("revenue_m", ascending=False)
region_rev.to_csv(os.path.join(OUT_DIR, "region_revenue.csv"), index=False)

print("   → revenue_by_segment.csv, region_revenue.csv saved")

# ── LEVEL 4 — Detail Dataset ─────────────────────────────────────────────────
print("[5/7] Building detail explorer dataset …")

detail = df[["order_id", "customer_id", "segment", "region",
             "order_amount", "order_status", "order_date"]].copy()
detail["order_date"] = detail["order_date"].dt.date
detail["churn_risk"] = detail["customer_id"].apply(
    lambda cid: "High" if cid in churned else "Low"
)
detail.to_csv(os.path.join(OUT_DIR, "detail_records.csv"), index=False)
print("   → detail_records.csv saved")

# ── Static Plotly PNG charts (for validation) ────────────────────────────────
print("[6/7] Generating static Plotly charts …")

# Revenue Trend
fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=rev_trend["month"], y=rev_trend["revenue_m"],
    mode="lines+markers", name="Revenue",
    line=dict(color="#4F8EF7", width=3),
    marker=dict(size=7)
))
fig1.add_hline(y=rev_trend["revenue_m"].mean(), line_dash="dash",
               line_color="#2CA02C",
               annotation_text=f"Avg: ${rev_trend['revenue_m'].mean():.2f}M",
               annotation_position="top right")
fig1.update_layout(
    title="Monthly Revenue Trend (2024)", template="plotly_dark",
    xaxis_title="Month", yaxis_title="Revenue ($M)",
    font=dict(family="Inter", size=13)
)
fig1.write_image(os.path.join(OUT_DIR, "revenue_trend.png"))

# Customer Trend
fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=monthly_buyers["year_month"], y=monthly_buyers["active_customers"],
    mode="lines+markers", name="Active Customers",
    line=dict(color="#4F8EF7", width=2.5)
))
fig2.add_trace(go.Scatter(
    x=monthly_buyers["year_month"], y=monthly_buyers["churned_customers"],
    mode="lines+markers", name="Churned Customers",
    line=dict(color="#E15759", width=2.5, dash="dot")
))
fig2.update_layout(
    title="Active vs Churned Customers by Month", template="plotly_dark",
    xaxis_title="Month", yaxis_title="Customers",
    font=dict(family="Inter", size=13)
)
fig2.write_image(os.path.join(OUT_DIR, "customer_trend.png"))

# Revenue by Segment
fig3 = px.bar(
    seg_rev.sort_values("revenue_m"),
    x="revenue_m", y="segment", orientation="h",
    color="segment",
    color_discrete_sequence=["#4F8EF7", "#F28E2B", "#59A14F", "#E15759"],
    text="revenue_m",
    title="Revenue by Customer Segment"
)
fig3.update_traces(texttemplate="$%{text:.2f}M", textposition="outside")
fig3.update_layout(template="plotly_dark", showlegend=False,
                   xaxis_title="Revenue ($M)", yaxis_title="Segment",
                   font=dict(family="Inter", size=13))
fig3.write_image(os.path.join(OUT_DIR, "revenue_by_segment.png"))

print("   → PNG charts saved to output/dashboard/")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n[7/7] Dashboard analysis complete.")
print(f"      All outputs written to: {OUT_DIR}")
print("─" * 60)
print("KPI SUMMARY")
print("─" * 60)
for k, v in kpi.items():
    print(f"  {v['label']:<22} {v['value']:<12}  Δ {v['delta_str']:<10}  ({v['trend']})")
print("─" * 60)
