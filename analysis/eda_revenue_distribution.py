# -*- coding: utf-8 -*-
"""
EDA - Revenue Distribution Analysis
Member 2: Sreedhil Pavishanker B - Data Analyst
SYNERGY CoursePulse / Kalvium Community

Responsibilities covered:
- KPIs, EDA, funnel analysis, segmentation, root-cause investigation
- Statistical validation: skewness, kurtosis, percentile analysis
- Matplotlib distribution plots
- Business interpretation connected to statistical findings

Tasks:
  Task 1: Distribution Plots (Histogram + KDE)
  Task 2: Compute Skewness and Kurtosis
  Task 3: Identify Abnormal Patterns (bimodality, percentile gaps)
  Task 4: Compare Segment Distributions (high-value vs low-value)
  Task 5: Business Interpretation and Recommended Actions
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from scipy import stats

# Force stdout to UTF-8 on Windows to avoid cp1252 codec errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

matplotlib.use("Agg")   # Non-interactive backend - safe for CI/pipeline runs
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------
# 0. Setup & synthetic data (mirrors stated statistical profile)
#    Revenue: mean ~450, skewness ~2.5 (highly right-skewed)
# ---------------------------------------------------------------
np.random.seed(42)
os.makedirs("output", exist_ok=True)

N = 2000

# Build a right-skewed revenue column via a mixture:
#   80% small customers  (log-normal centred ~250)
#   20% enterprise accounts (log-normal centred ~2500)
small_segment   = np.random.lognormal(mean=5.3,  sigma=0.5, size=int(N * 0.80))
enterprise_seg  = np.random.lognormal(mean=7.8,  sigma=0.6, size=int(N * 0.20))
revenue_raw     = np.concatenate([small_segment, enterprise_seg])

# Clip to realistic bounds and rescale so mean lands near 450
revenue_clipped = np.clip(revenue_raw, 10, 15_000)
scale_factor    = 450 / revenue_clipped.mean()
revenue         = np.round(revenue_clipped * scale_factor, 2)

df = pd.DataFrame({
    "customer_id": range(1, N + 1),
    "revenue":     revenue,
    "segment":     (["Small"] * int(N * 0.80)) + (["Enterprise"] * int(N * 0.20)),
})

print("=" * 60)
print("REVENUE DISTRIBUTION EDA - CoursePulse / Kalvium Community")
print("Member 2: Sreedhil Pavishanker B (Data Analyst)")
print("=" * 60)
print("Dataset: {:,} customers | {}".format(len(df), df.columns.tolist()))
print()


# ==============================================================
# TASK 1 - Distribution Plots: Histogram + KDE
# ==============================================================
print("-" * 50)
print("TASK 1: Distribution Plots")
print("-" * 50)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Revenue Distribution - CoursePulse Customers", fontsize=14, fontweight="bold")

mean_rev   = df["revenue"].mean()
median_rev = df["revenue"].median()

# Histogram
axes[0].hist(df["revenue"], bins=50, edgecolor="black", color="#4C72B0", alpha=0.85)
axes[0].axvline(mean_rev,   color="red",   linestyle="--", linewidth=1.5,
                label="Mean = ${:.0f}".format(mean_rev))
axes[0].axvline(median_rev, color="green", linestyle="--", linewidth=1.5,
                label="Median = ${:.0f}".format(median_rev))
axes[0].set_title("Revenue Distribution (Histogram)")
axes[0].set_xlabel("Revenue ($)")
axes[0].set_ylabel("Frequency")
axes[0].legend()

# KDE
df["revenue"].plot(kind="density", ax=axes[1], color="#DD8452", linewidth=2)
axes[1].axvline(mean_rev,   color="red",   linestyle="--", linewidth=1.5,
                label="Mean = ${:.0f}".format(mean_rev))
axes[1].axvline(median_rev, color="green", linestyle="--", linewidth=1.5,
                label="Median = ${:.0f}".format(median_rev))
axes[1].set_title("Revenue Distribution (KDE)")
axes[1].set_xlabel("Revenue ($)")
axes[1].legend()

plt.tight_layout()
plt.savefig("output/revenue_distribution.png", dpi=150)
plt.close()
print("Saved: output/revenue_distribution.png")
print("  Mean   = ${:.2f}".format(mean_rev))
print("  Median = ${:.2f}".format(median_rev))
print("  Std    = ${:.2f}".format(df["revenue"].std()))


# ==============================================================
# TASK 2 - Compute Skewness and Kurtosis
# ==============================================================
print()
print("-" * 50)
print("TASK 2: Skewness and Kurtosis")
print("-" * 50)

skewness = stats.skew(df["revenue"])
kurtosis  = stats.kurtosis(df["revenue"])   # Fisher's definition (excess kurtosis, normal=0)

print("Skewness : {:.4f}".format(skewness))
print("Kurtosis : {:.4f}  (excess/Fisher; normal = 0)".format(kurtosis))

if abs(skewness) > 1:
    print("=> Highly skewed - use MEDIAN, not MEAN, as the central tendency measure.")
elif abs(skewness) > 0.5:
    print("=> Moderately skewed - mean still usable but median preferred for revenue.")
else:
    print("=> Approximately symmetric - mean is a reliable central tendency.")

if kurtosis > 3:
    print("=> Leptokurtic (fat tails relative to normal) - expect extreme outliers.")
elif kurtosis > 0:
    print("=> Slight positive excess kurtosis - mild tail behaviour.")
else:
    print("=> Platykurtic or near-normal - light tails.")


# ==============================================================
# TASK 3 - Identify Abnormal Patterns (bimodality / percentile gaps)
# ==============================================================
print()
print("-" * 50)
print("TASK 3: Abnormal Pattern Detection")
print("-" * 50)

print("\nDescriptive Statistics:")
print(df["revenue"].describe().to_string())

percentile_levels = [0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
percentiles = df["revenue"].quantile(percentile_levels)
print("\nPercentile Analysis:")
for p, v in percentiles.items():
    print("  P{:>3} = ${:>10,.2f}".format(int(p * 100), v))

# Gap analysis: look for large jumps between percentile bands
gap_75_90 = percentiles[0.90] - percentiles[0.75]
gap_90_95 = percentiles[0.95] - percentiles[0.90]
gap_50_75 = percentiles[0.75] - percentiles[0.50]

print("\nGap P50->P75 : ${:>10,.2f}".format(gap_50_75))
print("Gap P75->P90 : ${:>10,.2f}".format(gap_75_90))
print("Gap P90->P95 : ${:>10,.2f}".format(gap_90_95))

if gap_75_90 > 2 * gap_50_75:
    print("=> Large gap P75->P90 detected: BIMODAL distribution likely - two distinct customer groups.")
else:
    print("=> Gaps are proportional - no strong bimodality signal in upper percentiles.")

# Z-score outlier count
z_scores    = np.abs(stats.zscore(df["revenue"]))
n_outliers  = int((z_scores > 3).sum())
outlier_pct = n_outliers / len(df) * 100
print("\nOutliers (|z| > 3) : {} customers ({:.1f}%)".format(n_outliers, outlier_pct))


# ==============================================================
# TASK 4 - Compare Segment Distributions: High-Value vs Low-Value
# ==============================================================
print()
print("-" * 50)
print("TASK 4: Segment Distribution Comparison")
print("-" * 50)

q75 = df["revenue"].quantile(0.75)
q25 = df["revenue"].quantile(0.25)

high_value = df[df["revenue"] >  q75]
low_value  = df[df["revenue"] <  q25]
mid_value  = df[(df["revenue"] >= q25) & (df["revenue"] <= q75)]

print("High-Value customers (>P75 = ${:.0f}) : {:>5,} | mean=${:.0f}  median=${:.0f}".format(
    q75, len(high_value), high_value["revenue"].mean(), high_value["revenue"].median()))
print("Mid-Value  customers (P25-P75)         : {:>5,} | mean=${:.0f}  median=${:.0f}".format(
    len(mid_value), mid_value["revenue"].mean(), mid_value["revenue"].median()))
print("Low-Value  customers (<P25 = ${:.0f}) : {:>5,} | mean=${:.0f}  median=${:.0f}".format(
    q25, len(low_value), low_value["revenue"].mean(), low_value["revenue"].median()))

# Revenue share
total_rev = df["revenue"].sum()
hv_share  = high_value["revenue"].sum() / total_rev * 100
lv_share  = low_value["revenue"].sum()  / total_rev * 100
print("\nRevenue share - High-Value : {:.1f}%".format(hv_share))
print("Revenue share - Low-Value  : {:.1f}%".format(lv_share))

# Visualise
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Revenue: High-Value vs Low-Value Customers", fontsize=14, fontweight="bold")

axes[0].hist(high_value["revenue"], bins=30, alpha=0.75,
             label="High-Value (n={:,})".format(len(high_value)), color="#2ca02c")
axes[0].hist(low_value["revenue"],  bins=30, alpha=0.75,
             label="Low-Value  (n={:,})".format(len(low_value)),  color="#d62728")
axes[0].legend()
axes[0].set_title("Overlapping Histograms")
axes[0].set_xlabel("Revenue ($)")
axes[0].set_ylabel("Count")

# Box-plots side by side
segment_groups = [low_value["revenue"], mid_value["revenue"], high_value["revenue"]]
axes[1].boxplot(segment_groups,
                labels=["Low-Value\n(<P25)", "Mid-Value\n(P25-P75)", "High-Value\n(>P75)"],
                patch_artist=True,
                boxprops=dict(facecolor="#AEC6CF", color="navy"),
                medianprops=dict(color="red", linewidth=2))
axes[1].set_title("Revenue Box-Plot by Segment")
axes[1].set_ylabel("Revenue ($)")

plt.tight_layout()
plt.savefig("output/revenue_segment_comparison.png", dpi=150)
plt.close()
print("Saved: output/revenue_segment_comparison.png")


# ==============================================================
# TASK 5 - Business Interpretation
# ==============================================================
print()
print("-" * 50)
print("TASK 5: Business Interpretation")
print("-" * 50)

skew_label = "Highly right-skewed" if skewness > 1 else "Moderate"
kurt_label = "Fat tails / outliers" if kurtosis > 0 else "Light tails"

interpretation = """
+--------------------------------------------------------------+
|       REVENUE DISTRIBUTION - BUSINESS INTERPRETATION         |
+--------------------------------------------------------------+
|  STATISTICAL FINDINGS                                        |
|  Skewness : {skew:>7.2f}  -> {sk_lbl:<22}               |
|  Kurtosis : {kurt:>7.2f}  -> {ku_lbl:<22}               |
|                                                              |
|  Mean     : ${mean:>8,.0f}  <- MISLEADING (pulled by big accounts)   |
|  Median   : ${med:>8,.0f}  <- BETTER central measure for revenue     |
|  Max      : ${mx:>8,.0f}                                              |
|  Top 1%   : ${p99:>8,.0f}                                              |
|                                                              |
|  BUSINESS INSIGHTS                                           |
|  1. Most ({sm:,}) customers are small/individual learners.      |
|     A few ({en:,}) enterprise accounts drive disproportionate   |
|     revenue -- classic 80/20 (Pareto) pattern.               |
|                                                              |
|  2. Mean revenue (${mean2:,.0f}) is inflated vs median (${med2:,.0f}).  |
|     Reporting the mean overstates typical customer value.    |
|                                                              |
|  3. High-value segment ({hv:.0f}% of revenue) needs dedicated  |
|     account management, retention programmes, upsell paths.  |
|                                                              |
|  RECOMMENDED ACTIONS                                         |
|  A. Segment marketing into Small vs Enterprise tiers.        |
|  B. Prioritise enterprise onboarding & CSM resources.        |
|  C. Use median (not mean) in public-facing revenue reports.  |
|  D. Set churn alerts for top-1% accounts (>${p99b:,.0f}/yr).       |
|  E. Design low-cost entry products to convert small users.   |
+--------------------------------------------------------------+
""".format(
    skew=skewness,     sk_lbl=skew_label,
    kurt=kurtosis,     ku_lbl=kurt_label,
    mean=mean_rev,     med=median_rev,
    mx=df["revenue"].max(),
    p99=df["revenue"].quantile(0.99),
    sm=int(N * 0.80),  en=int(N * 0.20),
    mean2=mean_rev,    med2=median_rev,
    hv=hv_share,
    p99b=df["revenue"].quantile(0.99),
)

print(interpretation)

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
print("=" * 60)
print("EDA COMPLETE - Output files written to output/")
print("  * output/revenue_distribution.png")
print("  * output/revenue_segment_comparison.png")
print("=" * 60)
