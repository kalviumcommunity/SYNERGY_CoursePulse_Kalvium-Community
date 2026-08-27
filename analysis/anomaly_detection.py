# -*- coding: utf-8 -*-
"""
anomaly_detection.py
=====================
SYNERGY CoursePulse — Kalvium Community

Business Context:
  Daily revenue averages $10,000. On Tuesday it drops to $2,000.
  Is this a data error? A system failure? A real business problem?
  This module provides automated monitoring that flags unusual values,
  categorises severity, and triggers investigation without overwhelming
  teams with false positives.

Tasks:
  Task 1: Threshold-Based Anomaly Detection
  Task 2: Statistical Anomaly Detection with Z-Score
  Task 3: Severity Classification
  Task 4: Anomaly Logging and Audit Trail
  Task 5: Visualisation with Flagged Points
"""

import os
import sys
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
print("ANOMALY DETECTION — CoursePulse / Kalvium Community")
print("=" * 70)


# =============================================================================
# 0.  Synthetic Dataset
#     90 days of daily transactions.  Three deliberate anomaly days injected:
#       Day 30 (Tuesday): revenue crashes to ~$2,000  (system failure scenario)
#       Day 55          : revenue spikes to ~$48,000  (promo/data error scenario)
#       Day 72          : transaction count collapses  (pipeline failure scenario)
# =============================================================================
np.random.seed(42)
N_DAYS = 90
BASE_DATE = pd.Timestamp("2026-06-01")

dates = [BASE_DATE + timedelta(days=i) for i in range(N_DAYS)]

# Normal daily revenue ~ $10,000 ± $1,500
daily_revenue_raw = np.random.normal(10_000, 1_500, N_DAYS).clip(5_500, 18_000)
# Normal transaction count ~ 500 ± 80
daily_txn_raw = np.random.normal(500, 80, N_DAYS).clip(200, 900).astype(int)
# Normal signup rate ~ 80 ± 15
daily_signup_raw = np.random.normal(80, 15, N_DAYS).clip(30, 150).astype(int)

# Inject anomalies
daily_revenue_raw[29] = 2_200      # Day 30: crash
daily_revenue_raw[54] = 47_800     # Day 55: spike
daily_txn_raw[71]     = 35         # Day 72: pipeline failure

df_daily = pd.DataFrame({
    "date":              dates,
    "daily_revenue":     daily_revenue_raw.round(2),
    "transaction_count": daily_txn_raw,
    "signup_rate":       daily_signup_raw,
})
df_daily["date"] = pd.to_datetime(df_daily["date"])

print(f"\nDataset: {len(df_daily)} days  ({df_daily['date'].min().date()} to {df_daily['date'].max().date()})")
print(f"Avg daily revenue    : ${df_daily['daily_revenue'].mean():,.0f}")
print(f"Avg transaction count: {df_daily['transaction_count'].mean():.0f}")
print(f"Avg signup rate      : {df_daily['signup_rate'].mean():.0f}\n")


# =============================================================================
# TASK 1: Threshold-Based Anomaly Detection
# =============================================================================
print("-" * 60)
print("TASK 1: Threshold-Based Anomaly Detection")
print("-" * 60)

alert_rules = {
    "daily_revenue":     {"min": 5_000,  "max": 50_000},
    "transaction_count": {"min": 100,    "max": 10_000},
    "signup_rate":       {"min": 10,     "max": 500},
}


def check_thresholds(metrics: dict, rules: dict) -> list:
    """Alert if metrics fall outside business-defined min/max thresholds.

    Parameters
    ----------
    metrics : {metric_name: current_value}
    rules   : {metric_name: {'min': ..., 'max': ...}}

    Returns
    -------
    list of alert dicts
    """
    alerts = []
    for metric_name, rule in rules.items():
        value = metrics.get(metric_name)
        if value is None:
            continue
        if value < rule["min"]:
            alerts.append({
                "metric":    metric_name,
                "value":     value,
                "threshold": rule["min"],
                "direction": "BELOW_MIN",
                "severity":  "HIGH",
            })
        elif value > rule["max"]:
            alerts.append({
                "metric":    metric_name,
                "value":     value,
                "threshold": rule["max"],
                "direction": "ABOVE_MAX",
                "severity":  "MEDIUM",
            })
    return alerts


# Simulate today = Day 30 (the crash day)
today_metrics = {
    "daily_revenue":     2_200,
    "transaction_count": 50,
    "signup_rate":       5,
}

alerts = check_thresholds(today_metrics, alert_rules)
print(f"\nToday's metrics: {today_metrics}")
print(f"\nThreshold alerts ({len(alerts)} triggered):")
for alert in alerts:
    icon = "ALERT" if alert["severity"] == "HIGH" else "WARN"
    print(f"  [{icon}] {alert['metric']} {alert['direction']}: "
          f"{alert['value']} (threshold: {alert['threshold']}, "
          f"severity: {alert['severity']})")

# Run threshold check across all 90 days
all_threshold_alerts = []
for _, row in df_daily.iterrows():
    day_metrics = {
        "daily_revenue":     row["daily_revenue"],
        "transaction_count": row["transaction_count"],
        "signup_rate":       row["signup_rate"],
    }
    day_alerts = check_thresholds(day_metrics, alert_rules)
    for a in day_alerts:
        a["date"] = row["date"].date()
        all_threshold_alerts.append(a)

thresh_df = pd.DataFrame(all_threshold_alerts)
print(f"\nThreshold alerts across 90 days: {len(thresh_df)}")
if len(thresh_df):
    print(thresh_df[["date", "metric", "value", "threshold", "direction", "severity"]]
          .to_string(index=False))


# =============================================================================
# TASK 2: Statistical Anomaly Detection with Z-Score
# =============================================================================
print()
print("-" * 60)
print("TASK 2: Statistical Anomaly Detection (Z-Score)")
print("-" * 60)


def detect_anomalies_zscore(series: pd.Series, threshold: float = 2.0):
    """Flag values more than `threshold` standard deviations from the mean.

    Parameters
    ----------
    series    : numeric pd.Series (indexed by date)
    threshold : z-score cutoff (default 2)

    Returns
    -------
    anomalies : sub-series of flagged values
    z_scores  : full z-score series
    """
    mean     = series.mean()
    std      = series.std()
    z_scores = np.abs((series - mean) / std)
    anomalies = series[z_scores > threshold]
    return anomalies, z_scores


# Use last 30 days as the monitoring window
revenue_series = df_daily.set_index("date")["daily_revenue"]
window_30      = revenue_series.tail(30)

anomalies, z_scores = detect_anomalies_zscore(window_30, threshold=2.0)

print(f"\n30-day window: {window_30.index[0].date()} to {window_30.index[-1].date()}")
print(f"Mean: ${window_30.mean():,.0f}  |  Std: ${window_30.std():,.0f}")
print(f"\nDetected {len(anomalies)} anomaly/anomalies out of {len(window_30)} days:")
for date, value in anomalies.items():
    z = z_scores[date]
    print(f"  {date.date()}: ${value:,.0f}  (z-score: {z:.2f})")

# Also run z-score on transaction count (full 90 days)
txn_series = df_daily.set_index("date")["transaction_count"].astype(float)
txn_anomalies, txn_z = detect_anomalies_zscore(txn_series, threshold=2.0)
print(f"\nTransaction count anomalies (90 days): {len(txn_anomalies)}")
for date, value in txn_anomalies.items():
    print(f"  {date.date()}: {value:.0f}  (z-score: {txn_z[date]:.2f})")


# =============================================================================
# TASK 3: Severity Classification
# =============================================================================
print()
print("-" * 60)
print("TASK 3: Severity Classification")
print("-" * 60)


def classify_severity(value: float, mean: float, std: float) -> str:
    """Classify anomaly severity based on z-score deviation.

    Returns
    -------
    'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
    """
    if std == 0:
        return "LOW"
    z = abs((value - mean) / std)
    if z > 3:
        return "CRITICAL"
    elif z > 2:
        return "HIGH"
    elif z > 1.5:
        return "MEDIUM"
    else:
        return "LOW"


# Classify revenue anomalies (30-day window)
rev_mean = window_30.mean()
rev_std  = window_30.std()

anomaly_severity = []
for date, value in anomalies.items():
    severity = classify_severity(value, rev_mean, rev_std)
    anomaly_severity.append({
        "date":     date.date(),
        "metric":   "daily_revenue",
        "value":    value,
        "z_score":  round(z_scores[date], 3),
        "severity": severity,
    })

# Also classify transaction anomalies
txn_mean = txn_series.mean()
txn_std  = txn_series.std()
for date, value in txn_anomalies.items():
    severity = classify_severity(value, txn_mean, txn_std)
    anomaly_severity.append({
        "date":     date.date(),
        "metric":   "transaction_count",
        "value":    value,
        "z_score":  round(txn_z[date], 3),
        "severity": severity,
    })

severity_df = pd.DataFrame(anomaly_severity).sort_values("z_score", ascending=False)
print("\nAll classified anomalies:")
print(severity_df.to_string(index=False))

# Filter to actionable (HIGH+)
critical = severity_df[severity_df["severity"].isin(["CRITICAL", "HIGH"])]
print(f"\n{len(critical)} anomalie(s) require immediate investigation (HIGH / CRITICAL)")
print(critical.to_string(index=False))

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# =============================================================================
# TASK 4: Anomaly Logging and Audit Trail
# =============================================================================
print()
print("-" * 60)
print("TASK 4: Anomaly Logging and Audit Trail")
print("-" * 60)

anomaly_log = []
detection_ts = pd.Timestamp.now()

# Revenue anomalies (30-day window)
for date, value in anomalies.items():
    severity = classify_severity(value, rev_mean, rev_std)
    lo = rev_mean - 2 * rev_std
    hi = rev_mean + 2 * rev_std
    anomaly_log.append({
        "logged_at":      detection_ts,
        "anomaly_date":   date.date(),
        "metric":         "daily_revenue",
        "value":          round(value, 2),
        "expected_min":   round(lo, 2),
        "expected_max":   round(hi, 2),
        "expected_range": f"${lo:,.0f} - ${hi:,.0f}",
        "z_score":        round(z_scores[date], 3),
        "severity":       severity,
        "status":         "OPEN",   # OPEN | INVESTIGATED | RESOLVED
        "notes":          "",
    })

# Transaction count anomalies (90-day)
for date, value in txn_anomalies.items():
    severity = classify_severity(value, txn_mean, txn_std)
    lo = txn_mean - 2 * txn_std
    hi = txn_mean + 2 * txn_std
    anomaly_log.append({
        "logged_at":      detection_ts,
        "anomaly_date":   date.date(),
        "metric":         "transaction_count",
        "value":          round(value, 0),
        "expected_min":   round(lo, 2),
        "expected_max":   round(hi, 2),
        "expected_range": f"{lo:.0f} - {hi:.0f}",
        "z_score":        round(txn_z[date], 3),
        "severity":       severity,
        "status":         "OPEN",
        "notes":          "",
    })

# Threshold anomalies not yet in log
logged_keys = {(r["anomaly_date"], r["metric"]) for r in anomaly_log}
for _, row in thresh_df.iterrows():
    key = (row["date"], row["metric"])
    if key not in logged_keys:
        anomaly_log.append({
            "logged_at":      detection_ts,
            "anomaly_date":   row["date"],
            "metric":         row["metric"],
            "value":          row["value"],
            "expected_min":   alert_rules[row["metric"]]["min"],
            "expected_max":   alert_rules[row["metric"]]["max"],
            "expected_range": (
                f"{alert_rules[row['metric']]['min']} - "
                f"{alert_rules[row['metric']]['max']}"
            ),
            "z_score":        None,
            "severity":       row["severity"],
            "status":         "OPEN",
            "notes":          "threshold-breach only",
        })
        logged_keys.add(key)

anomalies_df = pd.DataFrame(anomaly_log).sort_values(
    ["severity", "anomaly_date"],
    key=lambda col: col.map(SEVERITY_ORDER) if col.name == "severity" else col,
)

log_path = "output/anomalies_log.csv"
anomalies_df.to_csv(log_path, index=False)
print(f"\nLogged {len(anomalies_df)} anomalies to {log_path}")
print(anomalies_df[["anomaly_date", "metric", "value", "z_score",
                     "severity", "status"]].to_string(index=False))


# =============================================================================
# TASK 5: Visualisation with Flagged Points
# =============================================================================
print()
print("-" * 60)
print("TASK 5: Visualisation with Flagged Points")
print("-" * 60)

# ── matplotlib: 90-day revenue + anomalies ───────────────────────────────────
fig_mpl, ax = plt.subplots(figsize=(16, 6))
ax.set_facecolor("#0f172a")
fig_mpl.patch.set_facecolor("#0f172a")

# Raw line
ax.plot(df_daily["date"], df_daily["daily_revenue"],
        color="#3b82f6", linewidth=1.8, marker="o", markersize=3,
        label="Daily Revenue", zorder=3)

# 7-day rolling average
rolling_avg = df_daily["daily_revenue"].rolling(window=7, center=True).mean()
ax.plot(df_daily["date"], rolling_avg,
        color="#10b981", linewidth=2.5, linestyle="--",
        label="7-day Moving Avg", zorder=4)

# Expected range (mean ± 2σ) across full 90 days
full_mean = df_daily["daily_revenue"].mean()
full_std  = df_daily["daily_revenue"].std()
ax.fill_between(df_daily["date"],
                full_mean - 2 * full_std,
                full_mean + 2 * full_std,
                alpha=0.18, color="#6366f1",
                label="Expected Range ±2σ", zorder=2)
ax.axhline(full_mean, color="#94a3b8", linewidth=1,
           linestyle=":", label=f"Mean ${full_mean:,.0f}", zorder=2)

# Mark anomaly days (from severity_df)
rev_anom_dates = [pd.Timestamp(r["date"]) for _, r in severity_df.iterrows()
                  if r["metric"] == "daily_revenue"]
rev_anom_vals  = [df_daily.set_index("date").loc[d, "daily_revenue"]
                  for d in rev_anom_dates]

sev_colors = {"CRITICAL": "#ef4444", "HIGH": "#f97316",
              "MEDIUM": "#facc15", "LOW": "#a3e635"}
for d, v in zip(rev_anom_dates, rev_anom_vals):
    sev = severity_df[
        (severity_df["metric"] == "daily_revenue") &
        (severity_df["date"] == d.date())
    ]["severity"].values[0]
    color = sev_colors.get(sev, "#ef4444")
    ax.scatter(d, v, color=color, s=260, marker="X", zorder=6, linewidths=1.5)
    ax.annotate(
        f"{sev}\n${v:,.0f}",
        xy=(d, v),
        xytext=(0, 18 if v < full_mean else -28),
        textcoords="offset points",
        ha="center", fontsize=8.5, fontweight="bold", color=color,
        arrowprops=dict(arrowstyle="->", color=color, lw=1.2),
    )

# Styling
ax.set_xlabel("Date", color="white", fontsize=11)
ax.set_ylabel("Revenue ($)", color="white", fontsize=11)
ax.set_title("Daily Revenue with Anomalies Flagged", color="white",
             fontsize=14, fontweight="bold", pad=14)
ax.tick_params(colors="white")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.xticks(rotation=45, ha="right", color="white")
for spine in ax.spines.values():
    spine.set_edgecolor("#334155")
ax.grid(axis="both", color="#1e293b", linewidth=0.7, zorder=0)
legend = ax.legend(facecolor="#1e293b", edgecolor="#334155",
                   labelcolor="white", fontsize=9.5)
plt.tight_layout()
mpl_path = "output/anomaly_detection.png"
plt.savefig(mpl_path, dpi=150, facecolor="#0f172a")
plt.close()
print(f"Saved: {mpl_path}")

# ── Plotly: interactive 4-panel dashboard ────────────────────────────────────
fig_dash = make_subplots(
    rows=2, cols=2,
    subplot_titles=[
        "Daily Revenue — Anomalies Flagged (90 days)",
        "Z-Score: 30-Day Revenue Window",
        "Transaction Count — Anomalies Flagged",
        "Anomaly Severity Breakdown",
    ],
    vertical_spacing=0.20,
    horizontal_spacing=0.12,
)

# Convert dates to ISO strings for kaleido JSON serialisation
dates_str    = df_daily["date"].dt.strftime("%Y-%m-%d").tolist()
rolling_str  = df_daily["date"].dt.strftime("%Y-%m-%d").tolist()

# (1,1) Revenue time-series with anomaly markers
fig_dash.add_trace(go.Scatter(
    x=dates_str, y=df_daily["daily_revenue"].tolist(),
    mode="lines+markers",
    line=dict(color="#3b82f6", width=1.5),
    marker=dict(size=3),
    name="Daily Revenue",
    showlegend=True,
), row=1, col=1)
fig_dash.add_trace(go.Scatter(
    x=rolling_str,
    y=rolling_avg.tolist(),
    mode="lines",
    line=dict(color="#10b981", width=2, dash="dot"),
    name="7-day MA",
), row=1, col=1)
# Expected band
fig_dash.add_trace(go.Scatter(
    x=dates_str + dates_str[::-1],
    y=[full_mean + 2*full_std]*len(df_daily) + [full_mean - 2*full_std]*len(df_daily),
    fill="toself", fillcolor="rgba(99,102,241,0.15)",
    line=dict(color="rgba(0,0,0,0)"),
    name="±2σ band",
    showlegend=True,
), row=1, col=1)
# Anomaly scatter
for d, v in zip(rev_anom_dates, rev_anom_vals):
    fig_dash.add_trace(go.Scatter(
        x=[d.strftime("%Y-%m-%d")], y=[v],
        mode="markers",
        marker=dict(symbol="x", size=14, color="#ef4444",
                    line=dict(width=2, color="#ef4444")),
        name="Anomaly",
        showlegend=False,
    ), row=1, col=1)

# (1,2) Z-score bar – 30-day window
z_colors = ["#ef4444" if z > 2 else "#3b82f6" for z in z_scores.values]
fig_dash.add_trace(go.Bar(
    x=[d.strftime("%Y-%m-%d") for d in window_30.index],
    y=z_scores.values.tolist(),
    marker_color=z_colors,
    name="Z-Score",
    showlegend=False,
), row=1, col=2)
fig_dash.add_hline(y=2, line_dash="dash", line_color="#f59e0b",
                   annotation_text="Threshold 2σ", row=1, col=2)

# (2,1) Transaction count
txn_colors_ts = [
    "#ef4444" if txn_z.get(d, 0) > 2 else "#10b981"
    for d in df_daily["date"]
]
fig_dash.add_trace(go.Bar(
    x=dates_str, y=df_daily["transaction_count"].tolist(),
    marker_color=txn_colors_ts,
    name="Txn Count",
    showlegend=False,
), row=2, col=1)

# (2,2) Severity bar (Pie traces are incompatible with make_subplots row/col)
sev_counts  = severity_df["severity"].value_counts()
sev_palette = {"CRITICAL": "#ef4444", "HIGH": "#f97316",
               "MEDIUM": "#facc15", "LOW": "#a3e635"}
fig_dash.add_trace(go.Bar(
    x=sev_counts.index.tolist(),
    y=sev_counts.values.tolist(),
    marker_color=[sev_palette.get(s, "#94a3b8") for s in sev_counts.index],
    text=[str(v) for v in sev_counts.values],
    textposition="outside",
    name="Severity",
    showlegend=False,
), row=2, col=2)

fig_dash.update_layout(
    title_text="Anomaly Detection Dashboard — CoursePulse",
    template="plotly_dark",
    height=860,
    margin=dict(l=20, r=20, t=80, b=30),
)
fig_dash.write_html("output/anomaly_dashboard.html")
fig_dash.write_image("output/anomaly_dashboard.png", scale=2)
print("Saved: output/anomaly_dashboard.html/.png")

# ── Plotly: single focused revenue chart (matches Task 5 spec exactly) ────────
fig_rev = go.Figure()
fig_rev.add_trace(go.Scatter(
    x=dates_str, y=df_daily["daily_revenue"].tolist(),
    mode="lines+markers", name="Daily Revenue",
    line=dict(color="#3b82f6", width=2), marker=dict(size=4),
))
fig_rev.add_trace(go.Scatter(
    x=dates_str, y=rolling_avg.tolist(),
    mode="lines", name="7-day MA",
    line=dict(color="#10b981", width=2.5, dash="dot"),
))
fig_rev.add_trace(go.Scatter(
    x=dates_str + dates_str[::-1],
    y=([full_mean + 2*full_std] * len(df_daily) +
       [full_mean - 2*full_std] * len(df_daily)),
    fill="toself", fillcolor="rgba(99,102,241,0.15)",
    line=dict(color="rgba(0,0,0,0)"),
    name="Expected Range ±2σ",
))
for d, v in zip(rev_anom_dates, rev_anom_vals):
    fig_rev.add_trace(go.Scatter(
        x=[d.strftime("%Y-%m-%d")], y=[v], mode="markers+text",
        marker=dict(symbol="x", size=16, color="#ef4444",
                    line=dict(width=3, color="#ef4444")),
        text=["ANOMALY"], textposition="top center",
        textfont=dict(color="#ef4444", size=11, family="monospace"),
        showlegend=False,
    ))
fig_rev.update_layout(
    title="Task 5 — Daily Revenue with Anomalies Flagged",
    xaxis_title="Date", yaxis_title="Revenue ($)",
    yaxis_tickprefix="$",
    template="plotly_dark",
    height=480,
    legend=dict(orientation="h", y=-0.15),
    margin=dict(l=20, r=20, t=60, b=60),
)
fig_rev.write_html("output/ad_task5_revenue_flagged.html")
fig_rev.write_image("output/ad_task5_revenue_flagged.png", scale=2)
print("Saved: output/ad_task5_revenue_flagged.html/.png")


# =============================================================================
# Final summary
# =============================================================================
print()
print("=" * 70)
print("ANALYSIS COMPLETE — All outputs written to output/")
print("  Task 1 -> threshold alerts printed to console")
print("  Task 2 -> z-score anomalies printed to console")
print("  Task 3 -> severity_df printed to console")
print("  Task 4 -> output/anomalies_log.csv")
print("  Task 5 -> output/anomaly_detection.png (matplotlib)")
print("            output/ad_task5_revenue_flagged.html/.png (Plotly)")
print("  Bonus  -> output/anomaly_dashboard.html/.png (4-panel)")
print("=" * 70)
