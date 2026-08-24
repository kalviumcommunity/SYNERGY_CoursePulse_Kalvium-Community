# -*- coding: utf-8 -*-
"""
Time Series Trend Analysis
Member 2: Sreedhil Pavishanker B - Data Analyst
SYNERGY CoursePulse / Kalvium Community

Responsibilities covered:
- KPIs, EDA, root-cause investigation
- Rolling window smoothing to surface hidden trends
- Period-over-period change (MoM, WoW)
- Cumulative growth tracking
- Business trend interpretation and recommended actions

Business Context:
  Daily revenue shows high noise: $10k one day, $8k the next, $12k the day after.
  This noise masks the true trend. Build rolling averages, compute period-over-period
  changes, and visualise trends alongside raw data. Identify whether business is
  accelerating or declining based on sustainable metrics.

Tasks:
  Task 1: Resample Data by Time Period (weekly / monthly / quarterly)
  Task 2: Compute Rolling Window Average (7-day, 30-day)
  Task 3: Calculate Month-over-Month Percentage Change
  Task 4: Compute Cumulative Sum & Visualise Growth
  Task 5: Identify Trend Pattern and Business Implications
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Force UTF-8 on Windows stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")
os.makedirs("output", exist_ok=True)

# ---------------------------------------------------------------
# 0. Synthetic Daily Revenue Dataset
#    ~2 years of daily data with:
#      - Underlying upward growth trend
#      - Weekly seasonality (weekends dip)
#      - Monthly seasonality (end-of-month spike)
#      - Random noise (~$1-2k daily volatility)
#      - A simulated slowdown window (months 10-13) for realism
# ---------------------------------------------------------------
np.random.seed(42)

date_range = pd.date_range(start="2023-01-01", end="2024-12-31", freq="D")
n = len(date_range)

# Base trend: starts at ~$9k/day, grows to ~$14k/day over 2 years
base_trend = np.linspace(9_000, 14_000, n)

# Weekly seasonality: Mon-Fri up, Sat-Sun down
day_of_week = pd.Series(date_range).dt.dayofweek.values
weekly_factor = np.where(day_of_week < 5, 1.05, 0.70)   # weekdays / weekend

# Monthly seasonality: last 3 days of month get a 15% bump (billing cycle)
day_of_month = pd.Series(date_range).dt.day.values
days_in_month = pd.Series(date_range).dt.days_in_month.values
monthly_factor = np.where(days_in_month - day_of_month <= 2, 1.15, 1.0)

# Simulate a slowdown period: Oct 2023 – Jan 2024
slowdown_mask = (
    (pd.Series(date_range) >= "2023-10-01") &
    (pd.Series(date_range) <= "2024-01-15")
).values
slowdown_factor = np.where(slowdown_mask, 0.82, 1.0)

# Gaussian noise
noise = np.random.normal(0, 1_100, n)

revenue = (base_trend * weekly_factor * monthly_factor * slowdown_factor + noise).clip(min=500)

# Orders: loosely correlated with revenue
orders = (revenue / np.random.uniform(45, 55, n)).astype(int).clip(min=1)

# Customer sign-ups: slight growth trend + noise
signups = (np.linspace(80, 160, n) * np.random.uniform(0.85, 1.15, n)).astype(int)

df = pd.DataFrame({
    "date":     date_range,
    "revenue":  np.round(revenue, 2),
    "orders":   orders,
    "signups":  signups,
})

print("=" * 70)
print("TIME SERIES TREND ANALYSIS - CoursePulse / Kalvium Community")
print("Member 2: Sreedhil Pavishanker B (Data Analyst)")
print("=" * 70)
print(f"Dataset: {len(df):,} daily records | {df['date'].min().date()} to {df['date'].max().date()}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nSummary stats:")
print(df[["revenue", "orders", "signups"]].describe().round(2).to_string())
print()


# ==============================================================
# TASK 1: Resample Data by Time Period
# ==============================================================
print("-" * 60)
print("TASK 1: Resample Data by Time Period")
print("-" * 60)

df_ts = df.set_index("date")

# Weekly aggregations
weekly_revenue = df_ts["revenue"].resample("W").sum()
weekly_count   = df_ts["orders"].resample("W").count()
weekly_avg     = df_ts["revenue"].resample("W").mean()

# Monthly aggregations
monthly_revenue = df_ts["revenue"].resample("ME").sum()
monthly_orders  = df_ts["orders"].resample("ME").sum()
monthly_avg_rev = df_ts["revenue"].resample("ME").mean()

# Quarterly aggregations
quarterly_revenue = df_ts["revenue"].resample("QE").sum()
quarterly_orders  = df_ts["orders"].resample("QE").sum()

print("\n--- Weekly Revenue (sum) ---")
print(weekly_revenue.to_string())

print("\n--- Weekly Order Count ---")
print(weekly_count.to_string())

print("\n--- Weekly Average Revenue ---")
print(weekly_avg.round(2).to_string())

print("\n--- Monthly Revenue (sum) ---")
print(monthly_revenue.round(2).to_string())

print("\n--- Quarterly Revenue (sum) ---")
print(quarterly_revenue.round(2).to_string())

# Which period had the highest revenue?
best_week    = weekly_revenue.idxmax()
best_month   = monthly_revenue.idxmax()
best_quarter = quarterly_revenue.idxmax()

print(f"\nHighest-revenue week    : {best_week.date()}  -> ${weekly_revenue.max():>12,.2f}")
print(f"Highest-revenue month   : {best_month.strftime('%Y-%m')}     -> ${monthly_revenue.max():>12,.2f}")
print(f"Highest-revenue quarter : {best_quarter.strftime('%Y-Q') + str((best_quarter.month-1)//3+1)}"
      f" -> ${quarterly_revenue.max():>12,.2f}")

# Plotly: Weekly vs Monthly resampled revenue
fig1 = make_subplots(
    rows=2, cols=1,
    subplot_titles=["Weekly Total Revenue", "Monthly Total Revenue"],
    shared_xaxes=False,
    vertical_spacing=0.14,
)
fig1.add_trace(
    go.Bar(
        x=weekly_revenue.index, y=weekly_revenue.values,
        name="Weekly Revenue", marker_color="#4C78A8",
        hovertemplate="%{x|%Y-%m-%d}: $%{y:,.0f}<extra></extra>",
    ), row=1, col=1,
)
fig1.add_trace(
    go.Bar(
        x=monthly_revenue.index, y=monthly_revenue.values,
        name="Monthly Revenue", marker_color="#54A24B",
        hovertemplate="%{x|%Y-%m}: $%{y:,.0f}<extra></extra>",
    ), row=2, col=1,
)
fig1.update_layout(
    title="Task 1 — Resampled Revenue: Weekly & Monthly Aggregations",
    template="plotly_dark", height=650, showlegend=True,
)
fig1.write_html("output/task1_resampled_revenue.html")
fig1.write_image("output/task1_resampled_revenue.png", scale=2)
print("\nSaved: output/task1_resampled_revenue.html/.png")


# ==============================================================
# TASK 2: Compute Rolling Window Average
# ==============================================================
print()
print("-" * 60)
print("TASK 2: Rolling Window Average (7-day & 30-day)")
print("-" * 60)

df["revenue_ma7"]  = df["revenue"].rolling(window=7,  min_periods=1).mean()
df["revenue_ma30"] = df["revenue"].rolling(window=30, min_periods=1).mean()

# Where does the 30-day MA reveal hidden trend?
# Find the biggest divergence between raw and MA30
df["ma30_divergence"] = (df["revenue"] - df["revenue_ma30"]).abs()
max_div_date = df.loc[df["ma30_divergence"].idxmax(), "date"]
max_div_val  = df["ma30_divergence"].max()

print(f"\n7-day  MA range : ${df['revenue_ma7'].min():,.0f} - ${df['revenue_ma7'].max():,.0f}")
print(f"30-day MA range : ${df['revenue_ma30'].min():,.0f} - ${df['revenue_ma30'].max():,.0f}")
print(f"Largest raw vs MA30 divergence: ${max_div_val:,.0f} on {max_div_date.date()}")
print("=> On that date, the raw signal was highly noisy, but MA30 showed the true baseline.")

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=df["date"], y=df["revenue"],
    name="Raw Daily Revenue", mode="lines",
    line=dict(color="rgba(100,149,237,0.3)", width=1), opacity=0.4,
))
fig2.add_trace(go.Scatter(
    x=df["date"], y=df["revenue_ma7"],
    name="7-Day Rolling Avg", mode="lines",
    line=dict(color="#F58518", width=2),
))
fig2.add_trace(go.Scatter(
    x=df["date"], y=df["revenue_ma30"],
    name="30-Day Rolling Avg", mode="lines",
    line=dict(color="#E45756", width=2.5),
))
# Annotate the slowdown window (plain strings - kaleido/orjson cannot serialise Timestamps)
fig2.add_vrect(
    x0="2023-10-01", x1="2024-01-15",
    fillcolor="red", opacity=0.07, line_width=0,
    annotation_text="Slowdown Period", annotation_position="top left",
    annotation_font_color="#ff9999",
)
fig2.update_layout(
    title="Task 2 — Raw Revenue vs 7-Day & 30-Day Rolling Averages",
    xaxis_title="Date", yaxis_title="Revenue ($)",
    template="plotly_dark", height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig2.write_html("output/task2_rolling_avg.html")
fig2.write_image("output/task2_rolling_avg.png", scale=2)
print("Saved: output/task2_rolling_avg.html/.png")


# ==============================================================
# TASK 3: Month-over-Month Percentage Change
# ==============================================================
print()
print("-" * 60)
print("TASK 3: Month-over-Month Percentage Change")
print("-" * 60)

monthly_revenue_t3 = df_ts["revenue"].resample("ME").sum()
mom_change = monthly_revenue_t3.pct_change() * 100

print("\nMonthly Revenue & MoM % Change:")
mom_df = pd.DataFrame({
    "month":           monthly_revenue_t3.index.strftime("%Y-%m"),
    "total_revenue":   monthly_revenue_t3.round(2).values,
    "mom_change_pct":  mom_change.round(2).values,
})
print(mom_df.to_string(index=False))

growth_months  = mom_change[mom_change > 0]
decline_months = mom_change[mom_change < 0]
flat_months    = mom_change[mom_change == 0]

print(f"\nGrowth  months ({len(growth_months)}): "
      + ", ".join(growth_months.index.strftime("%Y-%m")))
print(f"Decline months ({len(decline_months)}): "
      + ", ".join(decline_months.index.strftime("%Y-%m")))

avg_growth  = growth_months.mean()
avg_decline = decline_months.mean()
print(f"\nAverage MoM growth  in growth  months : +{avg_growth:.1f}%")
print(f"Average MoM decline in decline months : {avg_decline:.1f}%")

# Pattern interpretation
if len(growth_months) > len(decline_months) * 1.5:
    pattern = "ACCELERATING — more growth months than decline months."
elif len(decline_months) > len(growth_months):
    pattern = "DECLINING — more down months than up months."
else:
    pattern = "MIXED / VOLATILE — growth and decline months roughly balanced."
print(f"\nOverall MoM Pattern: {pattern}")

# Waterfall chart for MoM change
colors_bar = ["#54A24B" if v > 0 else "#E45756" if v < 0 else "#888888"
              for v in mom_change.fillna(0).values]
fig3 = go.Figure()
fig3.add_trace(go.Bar(
    x=mom_change.index.strftime("%Y-%m"),
    y=mom_change.fillna(0).values,
    marker_color=colors_bar,
    text=[f"{v:+.1f}%" for v in mom_change.fillna(0).values],
    textposition="outside",
    name="MoM Change (%)",
    hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
))
fig3.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
fig3.update_layout(
    title="Task 3 — Month-over-Month Revenue % Change",
    xaxis_title="Month", yaxis_title="MoM Change (%)",
    template="plotly_dark", height=480,
)
fig3.write_html("output/task3_mom_change.html")
fig3.write_image("output/task3_mom_change.png", scale=2)
print("Saved: output/task3_mom_change.html/.png")


# ==============================================================
# TASK 4: Cumulative Sum
# ==============================================================
print()
print("-" * 60)
print("TASK 4: Cumulative Sum")
print("-" * 60)

df["cumulative_revenue"] = df["revenue"].cumsum()
df["cumulative_orders"]  = df["orders"].cumsum()
df["cumulative_signups"] = df["signups"].cumsum()

total_revenue = df["cumulative_revenue"].iloc[-1]
total_orders  = df["cumulative_orders"].iloc[-1]
total_signups = df["cumulative_signups"].iloc[-1]

print(f"\nTotal (cumulative) revenue : ${total_revenue:>14,.0f}")
print(f"Total (cumulative) orders  : {total_orders:>14,.0f}")
print(f"Total (cumulative) signups : {total_signups:>14,.0f}")

# Milestones: when did we hit revenue milestones?
milestones = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000]
print("\nRevenue Milestones:")
for m in milestones:
    hit = df[df["cumulative_revenue"] >= m]
    if not hit.empty:
        print(f"  ${m/1_000_000:.0f}M hit on: {hit.iloc[0]['date'].date()}")
    else:
        print(f"  ${m/1_000_000:.0f}M : not yet reached")

# Growth rate over two halves
mid = len(df) // 2
h1_end = df.iloc[mid]["cumulative_revenue"]
h2_gain = total_revenue - h1_end
h1_gain = h1_end
print(f"\nH1 accumulated : ${h1_gain:>12,.0f}")
print(f"H2 accumulated : ${h2_gain:>12,.0f}")
growth_acc = ((h2_gain - h1_gain) / h1_gain) * 100
print(f"H2 vs H1 gain  : {growth_acc:+.1f}%  "
      + ("(accelerating)" if growth_acc > 0 else "(slowing)"))

fig4 = make_subplots(
    rows=2, cols=1,
    subplot_titles=["Cumulative Revenue", "Cumulative Orders & Signups"],
    vertical_spacing=0.14,
)
# Revenue cumulative
fig4.add_trace(go.Scatter(
    x=df["date"], y=df["cumulative_revenue"],
    name="Cumulative Revenue", mode="lines",
    fill="tozeroy", fillcolor="rgba(84,162,75,0.15)",
    line=dict(color="#54A24B", width=2),
    hovertemplate="%{x|%Y-%m-%d}: $%{y:,.0f}<extra></extra>",
), row=1, col=1)
# Milestone annotations (convert Timestamp -> ISO string for kaleido/orjson compat)
for m in milestones:
    hit = df[df["cumulative_revenue"] >= m]
    if not hit.empty:
        fig4.add_annotation(
            x=hit.iloc[0]["date"].isoformat(), y=m,
            text=f"${m/1e6:.0f}M", showarrow=True,
            arrowhead=2, font=dict(size=10, color="white"),
            ax=30, ay=-30, row=1, col=1,
        )
# Orders & signups
fig4.add_trace(go.Scatter(
    x=df["date"], y=df["cumulative_orders"],
    name="Cumulative Orders", mode="lines",
    line=dict(color="#4C78A8", width=2),
), row=2, col=1)
fig4.add_trace(go.Scatter(
    x=df["date"], y=df["cumulative_signups"],
    name="Cumulative Signups", mode="lines",
    line=dict(color="#F58518", width=2),
), row=2, col=1)

fig4.update_layout(
    title="Task 4 — Cumulative Revenue, Orders & Signups Over Time",
    template="plotly_dark", height=680,
)
fig4.write_html("output/task4_cumulative.html")
fig4.write_image("output/task4_cumulative.png", scale=2)
print("Saved: output/task4_cumulative.html/.png")


# ==============================================================
# TASK 5: Identify Trend Pattern and Business Implications
# ==============================================================
print()
print("-" * 60)
print("TASK 5: Trend Pattern & Business Implications")
print("-" * 60)

# Rolling average trend over last 30 data points
recent_ma30     = df["revenue_ma30"].iloc[-30:]
trend_start     = recent_ma30.iloc[0]
trend_end       = recent_ma30.iloc[-1]
trend_direction = "up" if trend_end > trend_start else "down"
trend_magnitude = ((trend_end - trend_start) / trend_start) * 100

# Volatility
revenue_std = df["revenue"].std()
revenue_cv  = (revenue_std / df["revenue"].mean()) * 100  # coefficient of variation

# Last MoM change
last_mom = mom_change.dropna().iloc[-1]

# Longest consecutive growth streak in MoM
streak = 0
max_streak = 0
for v in mom_change.dropna().values:
    if v > 0:
        streak += 1
        max_streak = max(max_streak, streak)
    else:
        streak = 0

# 7-day MA slope in the last 14 days (linear regression)
recent_ma7 = df["revenue_ma7"].iloc[-14:].values
x_idx = np.arange(len(recent_ma7))
slope, _ = np.polyfit(x_idx, recent_ma7, 1)
slope_per_day = slope

if trend_direction == "up" and last_mom > 0:
    overall_signal = "ACCELERATING GROWTH"
    action = ("Maintain current acquisition & retention strategy. "
              "Scale marketing spend — ROI is positive. "
              "Plan capacity for continued demand increase.")
elif trend_direction == "up" and last_mom <= 0:
    overall_signal = "RECOVERING / MIXED"
    action = ("30-day MA is recovering but last month dipped. "
              "Investigate whether the recent MoM decline is seasonal or structural. "
              "Do not cut marketing spend yet — await 2 more monthly data points.")
elif trend_direction == "down" and last_mom < 0:
    overall_signal = "DECLINING MOMENTUM"
    action = ("Both rolling avg and MoM point downward — investigate root cause immediately. "
              "Run churn cohort analysis. "
              "Consider promotional campaigns or product bundling to stimulate demand.")
else:
    overall_signal = "STABILISING"
    action = ("Trend is flattening after a decline — monitor closely. "
              "Focus on customer retention before new acquisition spending.")

analysis = f"""
+------------------------------------------------------------------+
|              TREND ANALYSIS REPORT - CoursePulse                 |
|         Member 2: Sreedhil Pavishanker B (Data Analyst)          |
+------------------------------------------------------------------+

ROLLING AVERAGE TREND (last 30 days of MA30)
  Direction          : {trend_direction.upper()}
  MA30 start         : ${trend_start:>10,.2f}
  MA30 end           : ${trend_end:>10,.2f}
  Change magnitude   : {trend_magnitude:>+10.1f}%
  MA7 slope (14 days): ${slope_per_day:>+10.2f}/day

MONTHLY METRICS
  Last MoM change    : {last_mom:>+10.1f}%
  Growth months      : {len(growth_months):>10}
  Decline months     : {len(decline_months):>10}
  Longest growth run : {max_streak:>10} consecutive months
  MoM Pattern        : {pattern}

VOLATILITY (Noise Measurement)
  Daily Std Dev      : ${revenue_std:>10,.0f}
  Coefficient of Var : {revenue_cv:>10.1f}%
  Interpretation     : {'High noise - rolling avg essential to read trend' if revenue_cv > 15 else 'Moderate noise - rolling avg helpful but raw usable'}

OVERALL SIGNAL       : {overall_signal}

BUSINESS IMPLICATIONS:
  {action}

RECOMMENDED ACTIONS:
  1. Use 30-day rolling avg (not raw daily) for all executive dashboards.
  2. Flag any week where raw revenue deviates >2x std from MA7.
  3. Set automated alert when MA30 declines for 3 consecutive weeks.
  4. Segment trend analysis by customer_type (Enterprise vs SMB vs Startup).
  5. Re-run this analysis monthly and compare to baseline quarter.
+------------------------------------------------------------------+
"""

print(analysis)

# Save trend report
with open("output/trend_report.txt", "w", encoding="utf-8") as f:
    f.write(analysis)
print("Saved: output/trend_report.txt")


# ==============================================================
# BONUS: Comprehensive 4-Panel Dashboard
# ==============================================================
print()
print("-" * 60)
print("BONUS: Combined Trend Dashboard")
print("-" * 60)

fig_dash = make_subplots(
    rows=2, cols=2,
    subplot_titles=[
        "Raw Daily vs Rolling Averages (7d & 30d)",
        "Month-over-Month Revenue % Change",
        "Monthly Aggregated Revenue",
        "Cumulative Revenue with Milestones",
    ],
    vertical_spacing=0.14,
    horizontal_spacing=0.08,
)

# (1,1) Rolling averages
fig_dash.add_trace(go.Scatter(
    x=df["date"], y=df["revenue"],
    name="Raw Daily", mode="lines",
    line=dict(color="rgba(100,149,237,0.25)", width=1),
    showlegend=True,
), row=1, col=1)
fig_dash.add_trace(go.Scatter(
    x=df["date"], y=df["revenue_ma7"],
    name="7-Day MA", mode="lines",
    line=dict(color="#F58518", width=2),
), row=1, col=1)
fig_dash.add_trace(go.Scatter(
    x=df["date"], y=df["revenue_ma30"],
    name="30-Day MA", mode="lines",
    line=dict(color="#E45756", width=2.5),
), row=1, col=1)

# (1,2) MoM waterfall
fig_dash.add_trace(go.Bar(
    x=mom_change.index.strftime("%Y-%m"),
    y=mom_change.fillna(0).values,
    marker_color=colors_bar,
    name="MoM %",
    showlegend=True,
    hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
), row=1, col=2)

# (2,1) Monthly bar
fig_dash.add_trace(go.Bar(
    x=monthly_revenue.index.strftime("%Y-%m"),
    y=monthly_revenue.values,
    name="Monthly Revenue",
    marker_color="#4C78A8",
    hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
), row=2, col=1)

# (2,2) Cumulative revenue
fig_dash.add_trace(go.Scatter(
    x=df["date"], y=df["cumulative_revenue"],
    name="Cumulative Revenue", mode="lines",
    fill="tozeroy", fillcolor="rgba(84,162,75,0.12)",
    line=dict(color="#54A24B", width=2),
    hovertemplate="%{x|%Y-%m-%d}: $%{y:,.0f}<extra></extra>",
), row=2, col=2)

fig_dash.update_layout(
    title_text=(
        "Time Series Trend Dashboard — CoursePulse "
        "(Member 2: Sreedhil Pavishanker B)"
    ),
    template="plotly_dark",
    height=800,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig_dash.write_html("output/trend_dashboard.html")
fig_dash.write_image("output/trend_dashboard.png", scale=2)
print("Saved: output/trend_dashboard.html/.png")


# ---------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------
print()
print("=" * 70)
print("ANALYSIS COMPLETE - All outputs written to output/")
print("  Task 1 -> output/task1_resampled_revenue.html / .png")
print("  Task 2 -> output/task2_rolling_avg.html / .png")
print("  Task 3 -> output/task3_mom_change.html / .png")
print("  Task 4 -> output/task4_cumulative.html / .png")
print("  Task 5 -> output/trend_report.txt")
print("  Bonus  -> output/trend_dashboard.html / .png")
print("=" * 70)
