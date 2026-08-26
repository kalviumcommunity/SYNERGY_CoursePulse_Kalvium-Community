# -*- coding: utf-8 -*-
"""
Funnel Drop-Off Analysis
Member 2: Sreedhil Pavishanker B - Data Analyst
SYNERGY CoursePulse / Kalvium Community

Business Context:
  Signup funnel: 10,000 click signup → 8,000 enter email → 6,000 create
  password → 5,000 verify email → 4,000 add payment → 2,000 first purchase.
  Overall conversion = 20%.  Question: WHERE is the biggest leak?

Tasks:
  Task 1: Define Funnel Stages and Count Users
  Task 2: Compute Drop-Off Rate Between Stages
  Task 3: Visualise Funnel (bar chart + Plotly funnel)
  Task 4: Calculate Business Impact of Each Drop-Off
  Task 5: Actionable Recommendation
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend – safe on all systems
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── UTF-8 stdout on Windows ───────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

warnings.filterwarnings("ignore")
os.makedirs("output", exist_ok=True)

print("=" * 70)
print("FUNNEL DROP-OFF ANALYSIS — CoursePulse / Kalvium Community")
print("Member 2: Sreedhil Pavishanker B (Data Analyst)")
print("=" * 70)


# =============================================================================
# 0.  Synthetic Dataset
#     Reflects the stated funnel exactly:
#       10,000  clicked Signup
#        8,000  entered Email
#        6,000  created Password
#        5,000  verified Email
#        4,000  added Payment
#        2,000  made First Purchase
# =============================================================================
np.random.seed(42)
N = 10_000   # total visitors who reached the Signup page

# Each row = one visitor; columns are binary (1 = completed that step)
# Funnel is sequential – a visitor cannot skip a stage.

user_ids = [f"USR_{i:05d}" for i in range(1, N + 1)]

# Stage completion flags (cumulative – if you did step k you also did steps 1..k-1)
signup_completed = np.ones(N, dtype=int)                         # 10,000
email_entered    = np.where(np.arange(N) <  8_000, 1, 0)        #  8,000
password_created = np.where(np.arange(N) <  6_000, 1, 0)        #  6,000
email_verified   = np.where(np.arange(N) <  5_000, 1, 0)        #  5,000
payment_added    = np.where(np.arange(N) <  4_000, 1, 0)        #  4,000
first_purchase   = np.where(np.arange(N) <  2_000, 1, 0)        #  2,000

df = pd.DataFrame({
    "user_id":          user_ids,
    "signup_completed": signup_completed,
    "email_entered":    email_entered,
    "password_created": password_created,
    "email_verified":   email_verified,
    "payment_added":    payment_added,
    "first_purchase":   first_purchase,
})

print(f"\nDataset: {len(df):,} rows x {len(df.columns)} columns")
print(f"Overall conversion rate: {df['first_purchase'].mean():.0%}")
print("\nDataset head:")
print(df.head(8).to_string(index=False))
print()


# =============================================================================
# TASK 1: Define Funnel Stages and Count Users
# =============================================================================
print("-" * 60)
print("TASK 1: Define Funnel Stages and Count Users")
print("-" * 60)

# Count users at each stage (exactly as per rubric)
stage1_signup   = len(df[df['signup_completed'] == 1])
stage2_email    = len(df[df['email_entered']    == 1])
stage3_password = len(df[df['password_created'] == 1])
stage4_verified = len(df[df['email_verified']   == 1])
stage5_payment  = len(df[df['payment_added']    == 1])
stage6_purchase = len(df[df['first_purchase']   == 1])

stages = {
    'Sign Up':          stage1_signup,
    'Email Entered':    stage2_email,
    'Password Created': stage3_password,
    'Email Verified':   stage4_verified,
    'Payment Added':    stage5_payment,
    'First Purchase':   stage6_purchase,
}

print(stages)

print("\nFunnel at a glance:")
for stage, count in stages.items():
    bar = "█" * (count // 200)
    print(f"  {stage:<18}: {count:>6,}  {bar}")

print(f"\nStage progression verified (each stage <= previous): "
      f"{all(list(stages.values())[i] >= list(stages.values())[i+1]
           for i in range(len(stages)-1))}")


# =============================================================================
# TASK 2: Compute Drop-Off Rate Between Stages
# =============================================================================
print()
print("-" * 60)
print("TASK 2: Compute Drop-Off Rate Between Stages")
print("-" * 60)

stage_list  = list(stages.values())
stage_names = list(stages.keys())

drop_off = []
for i in range(len(stage_list) - 1):
    users_before = stage_list[i]
    users_after  = stage_list[i + 1]
    users_lost   = users_before - users_after
    drop_pct     = (users_lost / users_before) * 100

    drop_off.append({
        'from_stage':       stage_names[i],
        'to_stage':         stage_names[i + 1],
        'users_before':     users_before,
        'users_after':      users_after,
        'users_lost':       users_lost,
        'completion_rate':  f'{(users_after / users_before) * 100:.1f}%',
        'drop_rate':        f'{drop_pct:.1f}%',
    })

funnel_df = pd.DataFrame(drop_off)
print("\nFunnel drop-off table:")
print(funnel_df.to_string(index=False))

# Find biggest drop (by users_lost)
biggest_drop_idx = funnel_df['users_lost'].idxmax()
print(f"\nBiggest drop: {funnel_df.loc[biggest_drop_idx].to_dict()}")

print("\nDrop-off summary (sorted by users lost):")
print(funnel_df[['from_stage', 'to_stage', 'users_lost', 'drop_rate']]
      .sort_values('users_lost', ascending=False)
      .to_string(index=False))


# =============================================================================
# TASK 3: Visualise Funnel
# =============================================================================
print()
print("-" * 60)
print("TASK 3: Visualise Funnel")
print("-" * 60)

# ── matplotlib bar chart (as per rubric code) ─────────────────────────────────
colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

fig, ax = plt.subplots(figsize=(12, 6))
ax.bar(stages.keys(), stages.values(), color=colors, edgecolor='white',
       linewidth=0.8, zorder=3)
ax.set_facecolor('#0f172a')
fig.patch.set_facecolor('#0f172a')

ax.set_ylabel('Users', fontsize=12, color='white')
ax.set_xlabel('Stage', fontsize=12, color='white')
ax.set_title('Signup Funnel: Volume by Stage', fontsize=14, color='white',
             fontweight='bold', pad=14)
ax.set_ylim(0, max(stages.values()) * 1.15)
ax.tick_params(colors='white')
ax.yaxis.label.set_color('white')
ax.xaxis.label.set_color('white')
for spine in ax.spines.values():
    spine.set_edgecolor('#334155')
ax.grid(axis='y', color='#334155', linestyle='--', linewidth=0.5, zorder=0)

# Annotate counts
for stage, count in zip(stages.keys(), stages.values()):
    ax.text(stage, count + 150, f"{count:,}", ha='center', va='bottom',
            fontweight='bold', color='white', fontsize=11)

plt.xticks(rotation=45, ha='right', color='white')
plt.tight_layout()
plt.savefig('output/funnel_chart.png', dpi=150, facecolor='#0f172a')
plt.close()
print("Funnel visualization saved: output/funnel_chart.png")

# ── Plotly interactive funnel chart ──────────────────────────────────────────
fig_funnel = go.Figure(go.Funnel(
    y=list(stages.keys()),
    x=list(stages.values()),
    textposition="inside",
    textinfo="value+percent initial+percent previous",
    marker=dict(color=colors),
    connector=dict(line=dict(color='rgba(255,255,255,0.3)', width=1)),
))
fig_funnel.update_layout(
    title="Task 3 — Signup Funnel: Volume by Stage",
    template="plotly_dark",
    height=480,
    margin=dict(l=20, r=20, t=60, b=20),
)
fig_funnel.write_html("output/fa_task3_funnel.html")
fig_funnel.write_image("output/fa_task3_funnel.png", scale=2)
print("Saved: output/fa_task3_funnel.html/.png  (Plotly interactive)")


# =============================================================================
# TASK 4: Calculate Business Impact of Each Drop-Off
# =============================================================================
print()
print("-" * 60)
print("TASK 4: Calculate Business Impact of Each Drop-Off")
print("-" * 60)

# Revenue value per customer who completes the funnel
revenue_per_customer = 100   # $100 per converting customer

impact_analysis = []
for idx, row in funnel_df.iterrows():
    users_lost    = row['users_lost']
    revenue_lost  = users_lost * revenue_per_customer
    impact_analysis.append({
        'drop_point':      f"{row['from_stage']} -> {row['to_stage']}",
        'users_lost':      users_lost,
        'revenue_impact':  f'${revenue_lost:,.0f}',
        'revenue_lost_raw': revenue_lost,
        'priority':        'HIGH' if revenue_lost > 100_000 else 'MEDIUM',
    })

impact_df = pd.DataFrame(impact_analysis)
print("\nBusiness impact analysis (sorted by users lost):")
print(impact_df[['drop_point', 'users_lost', 'revenue_impact', 'priority']]
      .sort_values('users_lost', ascending=False)
      .to_string(index=False))

print(f"\nTotal potential revenue at risk: "
      f"${impact_df['revenue_lost_raw'].sum():,.0f}")
print(f"Highest-priority bottleneck: "
      f"{impact_df.sort_values('revenue_lost_raw', ascending=False).iloc[0]['drop_point']}")

# ── Plotly bar: revenue impact per drop-off ───────────────────────────────────
priority_colors = ['#ef4444' if p == 'HIGH' else '#f59e0b'
                   for p in impact_df['priority']]

fig4 = go.Figure(go.Bar(
    x=impact_df['drop_point'],
    y=impact_df['revenue_lost_raw'],
    marker_color=priority_colors,
    text=impact_df['revenue_impact'],
    textposition='outside',
))
fig4.update_layout(
    title="Task 4 — Revenue Impact of Each Drop-Off ($100 LTV per customer)",
    xaxis_title="Drop-Off Point",
    yaxis_title="Revenue Lost ($)",
    template="plotly_dark",
    height=480,
    xaxis_tickangle=-35,
    yaxis_tickprefix="$",
    margin=dict(l=20, r=20, t=60, b=120),
)

# Legend patches
fig4.add_annotation(text="🔴 HIGH priority  🟡 MEDIUM priority",
                    xref="paper", yref="paper",
                    x=0.01, y=1.06, showarrow=False,
                    font=dict(size=11, color="white"))
fig4.write_html("output/fa_task4_revenue_impact.html")
fig4.write_image("output/fa_task4_revenue_impact.png", scale=2)
print("\nSaved: output/fa_task4_revenue_impact.html/.png")


# =============================================================================
# TASK 5: Actionable Recommendation
# =============================================================================
print()
print("-" * 60)
print("TASK 5: Actionable Recommendation")
print("-" * 60)

highest_impact = funnel_df.loc[funnel_df['users_lost'].idxmax()]

recommendation = f"""
FUNNEL OPTIMIZATION PRIORITY:

CRITICAL BOTTLENECK:
Stage: {highest_impact['from_stage']} -> {highest_impact['to_stage']}
Users Lost: {highest_impact['users_lost']:,.0f}
Drop Rate: {highest_impact['drop_rate']}
Revenue Impact: ${highest_impact['users_lost'] * revenue_per_customer:,.0f}

ROOT CAUSE INVESTIGATION NEEDED:
- Is step unclear? (Poor UX)
- Is step too complex? (Too many fields)
- Is step optional? (Should be required)
- Is step timing wrong? (Too early/late in funnel)

RECOMMENDED ACTION:
1. A/B test simplified version of step
2. Monitor drop rate before/after
3. Estimate revenue recovery
4. Roll out to 100% if improvement > 5%

EXPECTED IMPACT:
If we improve {highest_impact['from_stage']} -> {highest_impact['to_stage']} completion by 10%:
Additional conversions: {int(highest_impact['users_lost'] * 0.1):,.0f}
Additional revenue: ${int(highest_impact['users_lost'] * 0.1 * revenue_per_customer):,.0f}
"""

print(recommendation)

# Detailed per-stage recommendations
detailed_recs = {
    'Sign Up -> Email Entered': (
        "20% of visitors abandon before entering an email. "
        "Hypothesis: form is too long or asks for information too early. "
        "Action: reduce the initial sign-up form to email-only, gate extra"
        " fields behind step 2."
    ),
    'Email Entered -> Password Created': (
        "25% drop between email and password. "
        "Hypothesis: password policy is too strict or confusing. "
        "Action: show password strength meter in real-time and allow "
        "social/SSO login as an alternative."
    ),
    'Password Created -> Email Verified': (
        "17% drop at email verification. "
        "Hypothesis: verification email lands in spam or takes too long. "
        "Action: send instant, branded verification email; add 'resend' "
        "button prominently; consider magic-link login instead."
    ),
    'Email Verified -> Payment Added': (
        "20% drop before adding payment. "
        "Hypothesis: asking for payment too early creates friction/distrust. "
        "Action: offer a 7-day free trial before requiring payment; add "
        "trust signals (SSL badge, money-back guarantee) near the form."
    ),
    'Payment Added -> First Purchase': (
        "50% drop — the LARGEST revenue leak. "
        "Hypothesis: users added payment but never found a reason to buy, "
        "OR checkout UX has errors/hidden costs. "
        "Action: trigger personalised onboarding email sequence within 1 hour"
        " of payment addition; add 'complete your first order' nudge in-app;"
        " A/B test removing friction from the checkout page."
    ),
}

print("\nPer-stage deep-dive recommendations:")
print("-" * 60)
for transition, rec in detailed_recs.items():
    # Find drop rate for this transition
    match = funnel_df[
        funnel_df.apply(
            lambda r: f"{r['from_stage']} -> {r['to_stage']}" == transition,
            axis=1
        )
    ]
    drop_rate = match['drop_rate'].values[0] if len(match) else "N/A"
    lost      = match['users_lost'].values[0] if len(match) else 0
    print(f"\n  [{transition}]  drop={drop_rate}  lost={lost:,}")
    print(f"  {rec}")

# ── Plotly full dashboard ─────────────────────────────────────────────────────
fig_dash = make_subplots(
    rows=2, cols=2,
    subplot_titles=[
        "Funnel Volume by Stage",
        "Drop-Off Rate (%) Between Stages",
        "Revenue Impact per Drop-Off ($)",
        "Cumulative Users Remaining (%)",
    ],
    vertical_spacing=0.18,
    horizontal_spacing=0.12,
)

stage_keys = list(stages.keys())
stage_vals = list(stages.values())

# (1,1) Bar: volume
fig_dash.add_trace(go.Bar(
    x=stage_keys, y=stage_vals,
    marker_color=colors,
    text=[f"{v:,}" for v in stage_vals],
    textposition="outside",
    showlegend=False,
), row=1, col=1)

# (1,2) Bar: drop rate
drop_rates_num = [
    float(r['drop_rate'].replace('%', '')) for _, r in funnel_df.iterrows()
]
drop_labels = [f"{r['from_stage']}\n→ {r['to_stage']}"
               for _, r in funnel_df.iterrows()]

fig_dash.add_trace(go.Bar(
    x=drop_labels,
    y=drop_rates_num,
    marker_color=['#ef4444' if v == max(drop_rates_num) else '#f59e0b'
                  for v in drop_rates_num],
    text=[f"{v:.1f}%" for v in drop_rates_num],
    textposition="outside",
    showlegend=False,
), row=1, col=2)

# (2,1) Bar: revenue impact
fig_dash.add_trace(go.Bar(
    x=impact_df['drop_point'],
    y=impact_df['revenue_lost_raw'],
    marker_color=priority_colors,
    text=impact_df['revenue_impact'],
    textposition="outside",
    showlegend=False,
), row=2, col=1)

# (2,2) Line: cumulative retention %
retention_pct = [v / stage_vals[0] * 100 for v in stage_vals]
fig_dash.add_trace(go.Scatter(
    x=stage_keys,
    y=retention_pct,
    mode="lines+markers+text",
    text=[f"{v:.0f}%" for v in retention_pct],
    textposition="top center",
    line=dict(color="#3b82f6", width=2),
    marker=dict(size=9, color=colors),
    showlegend=False,
), row=2, col=2)

fig_dash.update_layout(
    title_text=(
        "Funnel Drop-Off Analysis Dashboard — CoursePulse "
        "(Member 2: Sreedhil Pavishanker B)"
    ),
    template="plotly_dark",
    height=820,
)
fig_dash.write_html("output/fa_dashboard.html")
fig_dash.write_image("output/fa_dashboard.png", scale=2)
print("\nSaved: output/fa_dashboard.html/.png")


# ── Save text report ──────────────────────────────────────────────────────────
with open("output/fa_strategy_report.txt", "w", encoding="utf-8") as f:
    f.write("FUNNEL DROP-OFF ANALYSIS — STRATEGY REPORT\n")
    f.write("Member 2: Sreedhil Pavishanker B (Data Analyst)\n")
    f.write("=" * 70 + "\n\n")
    f.write("FUNNEL OVERVIEW\n")
    for stage, cnt in stages.items():
        f.write(f"  {stage:<20}: {cnt:>6,}\n")
    f.write("\n")
    f.write(recommendation)
    f.write("\n\nPER-STAGE RECOMMENDATIONS\n" + "-" * 70 + "\n")
    for transition, rec in detailed_recs.items():
        f.write(f"\n[{transition}]\n{rec}\n")

print("Saved: output/fa_strategy_report.txt")


# =============================================================================
# Final summary
# =============================================================================
print()
print("=" * 70)
print("ANALYSIS COMPLETE — All outputs written to output/")
print("  Task 1 -> stages dict printed to console")
print("  Task 2 -> funnel_df drop-off table printed to console")
print("  Task 3 -> output/funnel_chart.png (matplotlib)")
print("            output/fa_task3_funnel.html/.png (Plotly)")
print("  Task 4 -> output/fa_task4_revenue_impact.html/.png")
print("  Task 5 -> output/fa_strategy_report.txt")
print("  Bonus  -> output/fa_dashboard.html/.png (4-panel)")
print("=" * 70)
