# -*- coding: utf-8 -*-
"""
Segment Churn Analysis
Member 2: Sreedhil Pavishanker B - Data Analyst
SYNERGY CoursePulse / Kalvium Community

Business Context:
  Aggregate reporting shows "average 7% churn", hiding 3 very different stories:
    - Enterprise  (5%  of customers, ~$150k LTV) -> 1%  churn
    - SMB         (40% of customers, ~$8k   LTV) -> 12% churn
    - Startup     (55% of customers, ~$2k   LTV) -> 8%  churn
  Without segmentation, every intervention is wrong for at least 2 of 3 groups.

Tasks:
  Task 1: Define Segments & Compute 4+ Metrics per Segment
  Task 2: Summary Statistics Table with Rankings
  Task 3: Visual Comparison Heatmap (Plotly)
  Task 4: Top & Bottom Performer Analysis
  Task 5: Business-Facing Segment Insights
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Force UTF-8 stdout on Windows to prevent codec errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")
os.makedirs("output", exist_ok=True)

# ---------------------------------------------------------------
# 0.  Synthetic Customer Dataset
#     Mirrors the stated segment LTV + churn profile precisely:
#       Enterprise : 5%  of customers, 1%  churn, avg $150k LTV
#       SMB        : 40% of customers, 12% churn, avg $8k   LTV
#       Startup    : 55% of customers, 8%  churn, avg $2k   LTV
# ---------------------------------------------------------------
np.random.seed(42)
N = 3000

n_enterprise = int(N * 0.05)          # 150
n_smb        = int(N * 0.40)          # 1200
n_startup    = N - n_enterprise - n_smb  # 1650


def make_segment(n, churn_prob, ltv_mean, ltv_std,
                 ticket_lam, ret_mean, ret_std, ctype):
    rng = np.random.default_rng(seed=abs(hash(ctype)) % (2 ** 31))
    return pd.DataFrame({
        "customer_id":     [f"CUST_{i:05d}" for i in range(n)],   # reassigned below
        "customer_type":   ctype,
        "lifetime_value":  np.clip(rng.normal(ltv_mean, ltv_std, n), 200, None).round(2),
        "churn":           rng.binomial(1, churn_prob, n),
        "support_tickets": rng.poisson(lam=ticket_lam, size=n).astype(int),
        "retention_days":  np.clip(rng.normal(ret_mean, ret_std, n), 1, 1825).round(0).astype(int),
        "monthly_revenue": np.clip(rng.normal(ltv_mean / 24, ltv_mean / 48, n), 10, None).round(2),
    })


df_enterprise = make_segment(n_enterprise, 0.01, 150_000, 30_000,  1,  900, 180, "Enterprise")
df_smb        = make_segment(n_smb,        0.12,   8_000,  2_500,  6,  420, 130, "SMB")
df_startup    = make_segment(n_startup,    0.08,   2_000,    700, 4,   280, 110, "Startup")

df = pd.concat([df_enterprise, df_smb, df_startup], ignore_index=True)
df["customer_id"] = [f"CUST_{i + 1:05d}" for i in range(len(df))]

print("=" * 70)
print("SEGMENT CHURN ANALYSIS — CoursePulse / Kalvium Community")
print("Member 2: Sreedhil Pavishanker B (Data Analyst)")
print("=" * 70)
print(f"Dataset : {len(df):,} customers")
print(f"Segments: {df['customer_type'].unique().tolist()}")
print(f"Columns : {df.columns.tolist()}")
print()
print("Dataset head:")
print(df.head(6).to_string(index=False))
print()
print("Aggregate (misleading) churn rate:", f"{df['churn'].mean():.1%}")
print()


# ==============================================================
# TASK 1: Define Segments & Compute 4+ Metrics per Segment
# ==============================================================
print("-" * 60)
print("TASK 1: Define Segments & Compute Metrics")
print("-" * 60)

segment_metrics = df.groupby("customer_type").agg(
    avg_ltv          = ("lifetime_value",  "mean"),
    churn_rate       = ("churn",           "mean"),
    avg_tickets      = ("support_tickets", "mean"),
    avg_retention    = ("retention_days",  "mean"),
    avg_monthly_rev  = ("monthly_revenue", "mean"),
    count            = ("customer_id",     "count"),
)

print("\nRaw segment_metrics (groupby output):")
print(segment_metrics.round(2).to_string())

print(f"\nSegment sizes (sample counts):")
for seg, row in segment_metrics.iterrows():
    share = row["count"] / len(df) * 100
    print(f"  {seg:<12}: {int(row['count']):>5,} customers  ({share:.1f}% of base)")

print(f"\nAggregate churn (hidden by averaging): {df['churn'].mean():.1%}")
print("True picture per segment:")
for seg, row in segment_metrics.iterrows():
    print(f"  {seg:<12}: {row['churn_rate']:.1%} churn")

# Bar chart: churn rate per segment
fig1 = px.bar(
    segment_metrics.reset_index(),
    x="customer_type",
    y="churn_rate",
    color="customer_type",
    color_discrete_map={"Enterprise": "#2ecc71", "SMB": "#e67e22", "Startup": "#e74c3c"},
    text=segment_metrics["churn_rate"].apply(lambda v: f"{v:.1%}").values,
    title="Task 1 — Churn Rate by Customer Segment (vs Aggregate 7%)",
    labels={"customer_type": "Segment", "churn_rate": "Churn Rate"},
    template="plotly_dark",
)
fig1.add_hline(y=df["churn"].mean(), line_dash="dot", line_color="white",
               annotation_text=f"Aggregate avg {df['churn'].mean():.1%}",
               annotation_position="top right")
fig1.update_traces(textposition="outside")
fig1.update_layout(showlegend=False, yaxis_tickformat=".0%", height=450)
fig1.write_html("output/sca_task1_churn_by_segment.html")
fig1.write_image("output/sca_task1_churn_by_segment.png", scale=2)
print("\nSaved: output/sca_task1_churn_by_segment.html/.png")


# ==============================================================
# TASK 2: Summary Statistics Table with Rankings
# ==============================================================
print()
print("-" * 60)
print("TASK 2: Summary Statistics Table with Rankings")
print("-" * 60)

segment_summary = segment_metrics.copy()

# Rankings
segment_summary["ltv_rank"]       = segment_summary["avg_ltv"].rank(ascending=False).astype(int)
segment_summary["churn_rank"]     = segment_summary["churn_rate"].rank(ascending=True).astype(int)
segment_summary["retention_rank"] = segment_summary["avg_retention"].rank(ascending=False).astype(int)
segment_summary["ticket_rank"]    = segment_summary["avg_tickets"].rank(ascending=True).astype(int)

# Readable formatted display table
display_df = pd.DataFrame({
    "Segment":          segment_summary.index,
    "Customers":        segment_summary["count"].astype(int).apply(lambda x: f"{x:,}"),
    "Avg LTV":          segment_summary["avg_ltv"].apply(lambda x: f"${x:>10,.0f}"),
    "LTV Rank":         segment_summary["ltv_rank"],
    "Churn Rate":       segment_summary["churn_rate"].apply(lambda x: f"{x:.1%}"),
    "Churn Rank":       segment_summary["churn_rank"],
    "Avg Retention":    segment_summary["avg_retention"].apply(lambda x: f"{x:.0f} days"),
    "Retention Rank":   segment_summary["retention_rank"],
    "Avg Tickets":      segment_summary["avg_tickets"].apply(lambda x: f"{x:.2f}"),
    "Ticket Rank":      segment_summary["ticket_rank"],
}).reset_index(drop=True)

print("\nFormatted Segment Summary Table:")
print(display_df.to_string(index=False))

print("\nKey ranking observations:")
best_ltv  = segment_summary["avg_ltv"].idxmax()
worst_churn = segment_summary["churn_rate"].idxmax()
best_ret  = segment_summary["avg_retention"].idxmax()
print(f"  Highest LTV     -> {best_ltv}  (${segment_summary.loc[best_ltv,'avg_ltv']:,.0f})")
print(f"  Highest Churn   -> {worst_churn}  ({segment_summary.loc[worst_churn,'churn_rate']:.1%})")
print(f"  Best Retention  -> {best_ret} ({segment_summary.loc[best_ret,'avg_retention']:.0f} days)")

# Plotly table visualization
header_cols  = list(display_df.columns)
cell_cols    = [display_df[c] for c in header_cols]

row_colors = []
for seg in display_df["Segment"]:
    if seg == "Enterprise":
        row_colors.append("#1a3a1a")
    elif seg == "SMB":
        row_colors.append("#3a2a0a")
    else:
        row_colors.append("#2a1010")

fig2 = go.Figure(data=[go.Table(
    header=dict(
        values=[f"<b>{h}</b>" for h in header_cols],
        fill_color="#1f2c56",
        font=dict(color="white", size=12),
        align="center",
        height=34,
    ),
    cells=dict(
        values=cell_cols,
        fill_color=[row_colors] * len(header_cols),
        font=dict(color="white", size=11),
        align="center",
        height=30,
    ),
)])
fig2.update_layout(
    title="Task 2 — Segment Summary: Absolute Values + Rankings",
    template="plotly_dark",
    margin=dict(l=20, r=20, t=60, b=20),
    height=280,
)
fig2.write_html("output/sca_task2_summary_table.html")
fig2.write_image("output/sca_task2_summary_table.png", scale=2)
print("\nSaved: output/sca_task2_summary_table.html/.png")


# ==============================================================
# TASK 3: Visual Comparison Heatmap
# ==============================================================
print()
print("-" * 60)
print("TASK 3: Visual Comparison Heatmap")
print("-" * 60)

# Normalise each metric to [0, 1] so all columns share the same colour scale
# "better" direction: high LTV = good (green), high churn = bad (red)
heatmap_raw = segment_metrics[["avg_ltv", "churn_rate", "avg_tickets",
                                "avg_retention", "avg_monthly_rev"]].copy()

# For display, flip churn and tickets so green always means "healthy"
heatmap_norm = heatmap_raw.copy()
heatmap_norm["avg_ltv"]         = (heatmap_raw["avg_ltv"]       - heatmap_raw["avg_ltv"].min())       / (heatmap_raw["avg_ltv"].max()       - heatmap_raw["avg_ltv"].min())
heatmap_norm["churn_rate"]      = 1 - (heatmap_raw["churn_rate"] - heatmap_raw["churn_rate"].min())    / (heatmap_raw["churn_rate"].max()     - heatmap_raw["churn_rate"].min())
heatmap_norm["avg_tickets"]     = 1 - (heatmap_raw["avg_tickets"] - heatmap_raw["avg_tickets"].min())  / (heatmap_raw["avg_tickets"].max()    - heatmap_raw["avg_tickets"].min())
heatmap_norm["avg_retention"]   = (heatmap_raw["avg_retention"]  - heatmap_raw["avg_retention"].min()) / (heatmap_raw["avg_retention"].max()  - heatmap_raw["avg_retention"].min())
heatmap_norm["avg_monthly_rev"] = (heatmap_raw["avg_monthly_rev"]- heatmap_raw["avg_monthly_rev"].min())/ (heatmap_raw["avg_monthly_rev"].max()- heatmap_raw["avg_monthly_rev"].min())

col_labels = ["Avg LTV", "Churn Rate\n(inverted)", "Support Tickets\n(inverted)",
              "Avg Retention", "Avg Monthly Rev"]

# Annotation text: raw values formatted
annot = [
    [f"${heatmap_raw.loc[seg,'avg_ltv']:,.0f}",
     f"{heatmap_raw.loc[seg,'churn_rate']:.1%}",
     f"{heatmap_raw.loc[seg,'avg_tickets']:.2f}",
     f"{heatmap_raw.loc[seg,'avg_retention']:.0f}d",
     f"${heatmap_raw.loc[seg,'avg_monthly_rev']:,.0f}"]
    for seg in heatmap_norm.index
]

fig3 = go.Figure(data=go.Heatmap(
    z=heatmap_norm.values,
    x=col_labels,
    y=heatmap_norm.index.tolist(),
    colorscale="RdYlGn",
    zmin=0, zmax=1,
    text=annot,
    texttemplate="%{text}",
    textfont=dict(size=13, color="white"),
    showscale=True,
    colorbar=dict(title="Score<br>(green=healthy)", tickvals=[0, 0.5, 1],
                  ticktext=["Low", "Mid", "High"]),
))
fig3.update_layout(
    title="Task 3 — Segment Comparison Heatmap (green = healthy, red = risk)",
    xaxis_title="Metric",
    yaxis_title="Customer Segment",
    template="plotly_dark",
    height=380,
    margin=dict(l=20, r=20, t=70, b=60),
)
fig3.write_html("output/sca_task3_heatmap.html")
fig3.write_image("output/sca_task3_heatmap.png", scale=2)
print("\nSaved: output/sca_task3_heatmap.html/.png")
print("Heatmap uses RdYlGn scale — GREEN = healthy metric, RED = risk metric.")
print("Churn Rate and Support Tickets are inverted so green = low churn / low tickets.")


# ==============================================================
# TASK 4: Top & Bottom Performer Analysis
# ==============================================================
print()
print("-" * 60)
print("TASK 4: Top & Bottom Performer Analysis")
print("-" * 60)

# Top/bottom by key dimensions
top_ltv_seg      = segment_metrics["avg_ltv"].idxmax()
top_ltv_val      = segment_metrics.loc[top_ltv_seg, "avg_ltv"]

bottom_ltv_seg   = segment_metrics["avg_ltv"].idxmin()
bottom_ltv_val   = segment_metrics.loc[bottom_ltv_seg, "avg_ltv"]

high_churn_seg   = segment_metrics["churn_rate"].idxmax()
high_churn_val   = segment_metrics.loc[high_churn_seg, "churn_rate"]

low_churn_seg    = segment_metrics["churn_rate"].idxmin()
low_churn_val    = segment_metrics.loc[low_churn_seg, "churn_rate"]

best_ret_seg     = segment_metrics["avg_retention"].idxmax()
best_ret_val     = segment_metrics.loc[best_ret_seg, "avg_retention"]

worst_ret_seg    = segment_metrics["avg_retention"].idxmin()
worst_ret_val    = segment_metrics.loc[worst_ret_seg, "avg_retention"]

most_tickets_seg = segment_metrics["avg_tickets"].idxmax()
most_tickets_val = segment_metrics.loc[most_tickets_seg, "avg_tickets"]

# Revenue contribution
segment_metrics["revenue_pct"] = (
    segment_metrics["avg_ltv"] * segment_metrics["count"]
    / (segment_metrics["avg_ltv"] * segment_metrics["count"]).sum() * 100
)

insights_print = f"""
HIGHEST VALUE SEGMENT  : {top_ltv_seg:<12} -> Avg LTV = ${top_ltv_val:>10,.0f}
LOWEST VALUE SEGMENT   : {bottom_ltv_seg:<12} -> Avg LTV = ${bottom_ltv_val:>10,.0f}

HIGHEST CHURN SEGMENT  : {high_churn_seg:<12} -> Churn Rate = {high_churn_val:.1%}
LOWEST CHURN SEGMENT   : {low_churn_seg:<12} -> Churn Rate = {low_churn_val:.1%}

BEST RETENTION SEGMENT : {best_ret_seg:<12} -> Avg Retention = {best_ret_val:.0f} days
WORST RETENTION SEGMENT: {worst_ret_seg:<12} -> Avg Retention = {worst_ret_val:.0f} days

MOST SUPPORT LOAD      : {most_tickets_seg:<12} -> Avg Tickets = {most_tickets_val:.2f} / customer

REVENUE CONTRIBUTION (LTV × Count):"""

print(insights_print)
for seg, row in segment_metrics.iterrows():
    bar = "█" * int(row["revenue_pct"] / 2)
    print(f"  {seg:<12}: {row['revenue_pct']:>5.1f}%  {bar}")

# Multi-metric bar chart: compare all key metrics across segments
categories = ["Avg LTV (k$)", "Churn %", "Avg Tickets", "Avg Retention (days/10)"]
seg_order   = ["Enterprise", "SMB", "Startup"]
colors_map  = {"Enterprise": "#2ecc71", "SMB": "#e67e22", "Startup": "#e74c3c"}

fig4 = make_subplots(
    rows=2, cols=2,
    subplot_titles=["Avg LTV ($)", "Churn Rate (%)", "Avg Support Tickets", "Avg Retention (days)"],
    vertical_spacing=0.18, horizontal_spacing=0.12,
)

sm = segment_metrics.reset_index()

# (1,1) LTV
fig4.add_trace(go.Bar(
    x=sm["customer_type"], y=sm["avg_ltv"],
    marker_color=[colors_map[t] for t in sm["customer_type"]],
    text=sm["avg_ltv"].apply(lambda v: f"${v:,.0f}"),
    textposition="outside", showlegend=False,
), row=1, col=1)

# (1,2) Churn rate
fig4.add_trace(go.Bar(
    x=sm["customer_type"], y=sm["churn_rate"] * 100,
    marker_color=[colors_map[t] for t in sm["customer_type"]],
    text=sm["churn_rate"].apply(lambda v: f"{v:.1%}"),
    textposition="outside", showlegend=False,
), row=1, col=2)

# (2,1) Support tickets
fig4.add_trace(go.Bar(
    x=sm["customer_type"], y=sm["avg_tickets"],
    marker_color=[colors_map[t] for t in sm["customer_type"]],
    text=sm["avg_tickets"].apply(lambda v: f"{v:.2f}"),
    textposition="outside", showlegend=False,
), row=2, col=1)

# (2,2) Retention days
fig4.add_trace(go.Bar(
    x=sm["customer_type"], y=sm["avg_retention"],
    marker_color=[colors_map[t] for t in sm["customer_type"]],
    text=sm["avg_retention"].apply(lambda v: f"{v:.0f}d"),
    textposition="outside", showlegend=False,
), row=2, col=2)

fig4.update_layout(
    title_text="Task 4 — Top & Bottom Performer Analysis: All Key Metrics",
    template="plotly_dark",
    height=700,
)
fig4.write_html("output/sca_task4_performer_analysis.html")
fig4.write_image("output/sca_task4_performer_analysis.png", scale=2)
print("\nSaved: output/sca_task4_performer_analysis.html/.png")


# ==============================================================
# TASK 5: Business-Facing Segment Insights
# ==============================================================
print()
print("-" * 60)
print("TASK 5: Business-Facing Segment Insights")
print("-" * 60)

# Pull live computed numbers
ent = segment_metrics.loc["Enterprise"]
smb = segment_metrics.loc["SMB"]
sta = segment_metrics.loc["Startup"]

business_summary = f"""
+====================================================================+
|       SEGMENT STRATEGY SUMMARY — CoursePulse / Kalvium            |
|       Member 2: Sreedhil Pavishanker B (Data Analyst)             |
+====================================================================+

ENTERPRISE  — {int(ent['count']):,} customers  ({ent['count']/len(df)*100:.0f}% of base)
  Avg LTV        : ${ent['avg_ltv']:>10,.0f}   |  Churn Rate  : {ent['churn_rate']:.1%}
  Avg Retention  : {ent['avg_retention']:.0f} days         |  Avg Tickets : {ent['avg_tickets']:.2f}
  Revenue share  : {ent['revenue_pct']:.1f}%

  Observation: Enterprise is the highest-value, lowest-churn segment, averaging
  ${ent['avg_ltv']:,.0f} LTV and retaining customers for {ent['avg_retention']:.0f} days on average.
  Despite being only {ent['count']/len(df)*100:.0f}% of the customer base, they represent
  {ent['revenue_pct']:.1f}% of total estimated revenue.

  Action: Maintain premium support (low ticket volume is a feature, not an accident).
  Invest in dedicated Customer Success Managers. Run quarterly Executive Business
  Reviews to lock in multi-year contracts and grow expansion revenue.

----------------------------------------------------------------------

SMB  — {int(smb['count']):,} customers  ({smb['count']/len(df)*100:.0f}% of base)
  Avg LTV        : ${smb['avg_ltv']:>10,.0f}   |  Churn Rate  : {smb['churn_rate']:.1%}
  Avg Retention  : {smb['avg_retention']:.0f} days         |  Avg Tickets : {smb['avg_tickets']:.2f}
  Revenue share  : {smb['revenue_pct']:.1f}%

  Observation: SMB has the HIGHEST churn at {smb['churn_rate']:.1%} and the most support
  tickets ({smb['avg_tickets']:.2f}/customer), signalling friction in onboarding or product fit.
  Retaining even 2% more of this segment would add significant revenue given
  their {smb['count']/len(df)*100:.0f}% share of the customer base.

  Action: HIGH PRIORITY retention programme. Rebuild the onboarding flow using
  SMB-specific use cases. Introduce a lighter-weight support tier with self-serve
  docs and in-app guidance. Set automated churn-risk alerts at day 60 and day 120
  post sign-up, and trigger proactive outreach before cancellation.

----------------------------------------------------------------------

STARTUP  — {int(sta['count']):,} customers  ({sta['count']/len(df)*100:.0f}% of base)
  Avg LTV        : ${sta['avg_ltv']:>10,.0f}    |  Churn Rate  : {sta['churn_rate']:.1%}
  Avg Retention  : {sta['avg_retention']:.0f} days         |  Avg Tickets : {sta['avg_tickets']:.2f}
  Revenue share  : {sta['revenue_pct']:.1f}%

  Observation: Startups are the largest segment ({sta['count']/len(df)*100:.0f}% of users) but
  generate the lowest LTV (${sta['avg_ltv']:,.0f}) with a moderate 8% churn rate.
  They retain for only {sta['avg_retention']:.0f} days on average — often outgrowing or abandoning
  before hitting a billing event.

  Action: Shift to self-service and education-first motions — tutorials, certification
  paths, and community resources that add value without adding support costs.
  Introduce usage-based pricing triggers to monetise growth before startups leave.
  Long-term goal: convert high-engagement Startups into SMB accounts as they scale.

----------------------------------------------------------------------

KEY TAKEAWAY:
  Aggregate churn = {df['churn'].mean():.1%}  (masks all three problems)
  Fixing SMB churn alone (even halving it to {smb['churn_rate']/2:.1%}) would improve
  overall churn to ~{(df['churn'].sum() - smb['count'] * (smb['churn_rate'] / 2)) / len(df):.1%}
  — a bigger win than any product feature for the quarter.

+====================================================================+
"""

print(business_summary)

# Save text report
with open("output/sca_segment_strategy_report.txt", "w", encoding="utf-8") as f:
    f.write(business_summary)
print("Saved: output/sca_segment_strategy_report.txt")

# ----- Plotly full-dashboard combining all tasks -----
fig_dash = make_subplots(
    rows=2, cols=2,
    subplot_titles=[
        "Churn Rate by Segment (vs Aggregate Avg)",
        "Revenue Contribution by Segment",
        "Segment Comparison Heatmap",
        "LTV vs Churn — Bubble = Customer Count",
    ],
    specs=[
        [{"type": "bar"},     {"type": "pie"}],
        [{"type": "heatmap"}, {"type": "scatter"}],
    ],
    vertical_spacing=0.16,
    horizontal_spacing=0.08,
)

# (1,1) Churn bar with aggregate line
fig_dash.add_trace(go.Bar(
    x=sm["customer_type"],
    y=sm["churn_rate"],
    marker_color=[colors_map[t] for t in sm["customer_type"]],
    text=sm["churn_rate"].apply(lambda v: f"{v:.1%}"),
    textposition="outside",
    showlegend=False,
), row=1, col=1)

# (1,2) Revenue pie
fig_dash.add_trace(go.Pie(
    labels=sm["customer_type"],
    values=sm["avg_ltv"] * sm["count"],
    marker_colors=[colors_map[t] for t in sm["customer_type"]],
    hole=0.4,
    textinfo="label+percent",
    name="Revenue",
), row=1, col=2)

# (2,1) Heatmap
fig_dash.add_trace(go.Heatmap(
    z=heatmap_norm.values,
    x=["Avg LTV", "Churn (inv)", "Tickets (inv)", "Retention", "Monthly Rev"],
    y=heatmap_norm.index.tolist(),
    colorscale="RdYlGn",
    zmin=0, zmax=1,
    text=annot,
    texttemplate="%{text}",
    textfont=dict(size=10),
    showscale=False,
), row=2, col=1)

# (2,2) LTV vs Churn bubble
fig_dash.add_trace(go.Scatter(
    x=sm["churn_rate"],
    y=sm["avg_ltv"],
    mode="markers+text",
    marker=dict(
        size=sm["count"] / 15,
        color=[colors_map[t] for t in sm["customer_type"]],
        opacity=0.85,
        line=dict(width=1, color="white"),
    ),
    text=sm["customer_type"],
    textposition="top center",
    showlegend=False,
), row=2, col=2)

fig_dash.update_layout(
    title_text=(
        "Segment Churn Analysis Dashboard — CoursePulse "
        "(Member 2: Sreedhil Pavishanker B)"
    ),
    template="plotly_dark",
    height=820,
    showlegend=True,
)
fig_dash.write_html("output/sca_segment_dashboard.html")
fig_dash.write_image("output/sca_segment_dashboard.png", scale=2)
print("Saved: output/sca_segment_dashboard.html/.png")


# ---------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------
print()
print("=" * 70)
print("ANALYSIS COMPLETE — All outputs written to output/")
print("  Task 1 -> output/sca_task1_churn_by_segment.html / .png")
print("  Task 2 -> output/sca_task2_summary_table.html / .png")
print("  Task 3 -> output/sca_task3_heatmap.html / .png")
print("  Task 4 -> output/sca_task4_performer_analysis.html / .png")
print("  Task 5 -> output/sca_segment_strategy_report.txt")
print("  Bonus  -> output/sca_segment_dashboard.html / .png")
print("=" * 70)
