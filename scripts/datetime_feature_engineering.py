"""
Datetime Feature Engineering Pipeline for CoursePulse / Kalvium Community Platform.

Purpose:
    Convert raw timestamp strings (e.g., "2025-01-15 14:30:45") to datetime objects
    and extract rich time-based features for churn analysis and temporal analytics.

Pipeline Tasks:
    Task 1: Parse timestamp strings with explicit format '%Y-%m-%d %H:%M:%S'
    Task 2: Extract day-of-week and hour-of-day features
    Task 3: Compute ISO week number and resample to weekly buckets
    Task 4: Compute days-since-last-purchase (recency) per customer
    Task 5: Build time-indexed multi-level aggregations and hour × day pivot table

Format String Used:
    '%Y-%m-%d %H:%M:%S'
    - %Y  : 4-digit year   (e.g., 2025)
    - %m  : 2-digit month  (01–12)
    - %d  : 2-digit day    (01–31)
    - %H  : Hour 24h       (00–23)
    - %M  : Minutes        (00–59)
    - %S  : Seconds        (00–59)
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ── Output directory ────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================================
# SAMPLE DATA GENERATION
# Generate realistic transaction dataset with raw timestamp strings
# ============================================================================
def generate_sample_transactions(n_rows: int = 500, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic transaction data with raw timestamp strings.

    The timestamps are intentionally stored as strings to demonstrate the need
    for explicit datetime parsing before any temporal analysis.

    Args:
        n_rows: Number of transaction rows to generate.
        seed:   Random seed for reproducibility.

    Returns:
        DataFrame with columns:
            transaction_id, customer_id, transaction_date (string),
            amount, product_category, status
    """
    rng = np.random.default_rng(seed)

    # Spread transactions across ~6 months (2025-01-01 to 2025-06-30)
    base_ts = pd.Timestamp("2025-01-01")
    offset_seconds = rng.integers(0, 60 * 60 * 24 * 180, size=n_rows)
    timestamps = [base_ts + pd.Timedelta(seconds=int(s)) for s in offset_seconds]

    # Format as raw strings — exactly as they would appear from a DB export
    timestamp_strings = [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in timestamps]

    customer_ids = [f"CUST_{rng.integers(1, 51):03d}" for _ in range(n_rows)]
    amounts = rng.uniform(10.0, 500.0, size=n_rows).round(2)
    categories = rng.choice(
        ["Subscription", "One-Time", "Add-On", "Refund"], size=n_rows, p=[0.5, 0.3, 0.15, 0.05]
    )
    statuses = rng.choice(["completed", "pending", "failed"], size=n_rows, p=[0.8, 0.15, 0.05])

    df = pd.DataFrame({
        "transaction_id":   [f"TXN_{i+1:05d}" for i in range(n_rows)],
        "customer_id":      customer_ids,
        "transaction_date": timestamp_strings,   # ← raw strings, not datetime
        "amount":           amounts,
        "product_category": categories,
        "status":           statuses,
    })

    print("✓ Sample transaction data generated")
    print(f"  Rows: {df.shape[0]}  |  Columns: {df.shape[1]}")
    print(f"  transaction_date dtype BEFORE parsing: {df['transaction_date'].dtype}")
    print(f"  Sample raw string: '{df['transaction_date'].iloc[0]}'")
    return df


# ============================================================================
# TASK 1: Parse Timestamp Strings with Explicit Format
# ============================================================================
def task1_parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Task 1: Convert string dates to datetime type with explicit format.

    Format string: '%Y-%m-%d %H:%M:%S'
    - Using format= prevents silent corruption from ambiguous dates.
    - Never use pd.to_datetime() without format on production data.

    Args:
        df: DataFrame with 'transaction_date' as raw string column.

    Returns:
        DataFrame with 'transaction_date' converted to datetime64[ns].
    """
    print("\n" + "=" * 60)
    print("TASK 1: Parse Timestamp Strings")
    print("=" * 60)

    # ── EXPLICIT FORMAT PARSING ──────────────────────────────────────────────
    # Format string '%Y-%m-%d %H:%M:%S' matches input like "2025-01-15 14:30:45"
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"],
        format="%Y-%m-%d %H:%M:%S"   # ← explicit format, never omit this
    )

    # ── Verify dtype ──────────────────────────────────────────────────────────
    print(f"  transaction_date dtype AFTER  parsing : {df['transaction_date'].dtype}")
    assert str(df["transaction_date"].dtype).startswith("datetime64"), \
        "FAIL: Column is not datetime64 type!"
    print("  ✓ dtype verified as datetime64[ns]")

    # ── Range check ───────────────────────────────────────────────────────────
    print(f"  Min date : {df['transaction_date'].min()}")
    print(f"  Max date : {df['transaction_date'].max()}")
    print(f"  Span     : {(df['transaction_date'].max() - df['transaction_date'].min()).days} days")

    return df


# ============================================================================
# TASK 2: Extract Day-of-Week and Hour-of-Day
# ============================================================================
def task2_extract_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Task 2: Create time-of-day features for traffic and engagement analysis.

    Extracted features:
        - day_of_week : Readable name (e.g., 'Monday')
        - hour        : Integer hour 0–23

    Args:
        df: DataFrame with parsed 'transaction_date' datetime column.

    Returns:
        DataFrame with 'day_of_week' and 'hour' columns added.
    """
    print("\n" + "=" * 60)
    print("TASK 2: Extract Day-of-Week & Hour-of-Day")
    print("=" * 60)

    # ── Feature extraction ────────────────────────────────────────────────────
    df["day_of_week"] = df["transaction_date"].dt.day_name()    # e.g., 'Monday'
    df["hour"]        = df["transaction_date"].dt.hour          # 0–23

    # ── Hourly volume distribution ────────────────────────────────────────────
    hourly_volume = df.groupby("hour").size().rename("transaction_count")
    print("\n  Hourly Transaction Volume:")
    print(hourly_volume.to_string())

    # ── Day-of-week distribution ──────────────────────────────────────────────
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_volume = (
        df.groupby("day_of_week").size()
          .reindex(day_order)
          .rename("transaction_count")
    )
    print("\n  Day-of-Week Transaction Volume:")
    print(daily_volume.to_string())
    print(f"\n  Busiest hour : {hourly_volume.idxmax()} ({hourly_volume.max()} txns)")
    print(f"  Busiest day  : {daily_volume.idxmax()} ({daily_volume.max()} txns)")

    # ── Plot: hourly histogram ────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("CoursePulse — Transaction Temporal Patterns", fontsize=14, fontweight="bold")

    # Hour distribution
    axes[0].bar(hourly_volume.index, hourly_volume.values, color="#4C72B0", edgecolor="white", linewidth=0.5)
    axes[0].set_title("Transactions by Hour of Day")
    axes[0].set_xlabel("Hour (0–23)")
    axes[0].set_ylabel("Transaction Count")
    axes[0].set_xticks(range(0, 24, 2))
    axes[0].grid(axis="y", alpha=0.3)

    # Day-of-week distribution
    axes[1].bar(daily_volume.index, daily_volume.values, color="#DD8452", edgecolor="white", linewidth=0.5)
    axes[1].set_title("Transactions by Day of Week")
    axes[1].set_xlabel("Day")
    axes[1].set_ylabel("Transaction Count")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "hourly_daily_distribution.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Plot saved → {out_path}")

    return df


# ============================================================================
# TASK 3: Compute Week Number and Resample Data
# ============================================================================
def task3_week_number_and_resample(df: pd.DataFrame) -> pd.DataFrame:
    """
    Task 3: Enable weekly aggregations and trend analysis.

    Steps:
        1. Extract ISO week number via .dt.isocalendar().week
        2. Set datetime as index and resample to weekly ('W') buckets
        3. Compute sum, count, and mean of transaction amounts per week

    Args:
        df: DataFrame with parsed datetime and amount columns.

    Returns:
        DataFrame with 'week_num' column added.
    """
    print("\n" + "=" * 60)
    print("TASK 3: Week Number & Weekly Resampling")
    print("=" * 60)

    # ── ISO week number extraction ─────────────────────────────────────────────
    # .dt.isocalendar().week returns a UInt32 Series of ISO week numbers (1–53)
    df["week_num"] = df["transaction_date"].dt.isocalendar().week.astype(int)

    print(f"  Unique ISO weeks in dataset : {df['week_num'].nunique()}")
    print(f"  Week range                  : {df['week_num'].min()} – {df['week_num'].max()}")

    # ── Resample to weekly buckets ─────────────────────────────────────────────
    # 'W' aligns to Sunday week-end; use 'W-MON' for Monday alignment
    df_ts = df.set_index("transaction_date")

    weekly_stats = df_ts["amount"].resample("W").agg(
        weekly_revenue="sum",
        weekly_count="count",
        weekly_avg="mean"
    ).round(2)

    print("\n  Weekly Revenue Summary (first 8 weeks):")
    print(weekly_stats.head(8).to_string())

    # ── Plot: weekly revenue trend ─────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.fill_between(weekly_stats.index, weekly_stats["weekly_revenue"], alpha=0.25, color="#4C72B0")
    ax.plot(weekly_stats.index, weekly_stats["weekly_revenue"], marker="o", color="#4C72B0",
            linewidth=1.8, markersize=5)
    ax.set_title("Weekly Revenue Trend — CoursePulse Platform", fontsize=13, fontweight="bold")
    ax.set_xlabel("Week Ending")
    ax.set_ylabel("Total Revenue ($)")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(alpha=0.3)
    plt.tight_layout()

    out_path = os.path.join(OUTPUT_DIR, "weekly_revenue_trend.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Plot saved → {out_path}")

    return df


# ============================================================================
# TASK 4: Compute Days-Since-Event (Recency) for Churn Analysis
# ============================================================================
def task4_days_since_last_purchase(df: pd.DataFrame) -> pd.DataFrame:
    """
    Task 4: Build recency metrics for customer churn prediction.

    Recency = number of days between a customer's last purchase and today.
    High recency → customer has not purchased recently → churn risk.

    Steps:
        1. Group by customer_id and find max(transaction_date)
        2. Compute (today - last_purchase).dt.days for each customer
        3. Merge recency back to transaction-level DataFrame
        4. Flag customers with recency > 90 days as high-churn-risk

    Args:
        df: DataFrame with parsed 'transaction_date' and 'customer_id'.

    Returns:
        DataFrame with 'days_since_last_purchase' and 'churn_risk' columns added.
    """
    print("\n" + "=" * 60)
    print("TASK 4: Days-Since-Last-Purchase (Recency)")
    print("=" * 60)

    today = pd.Timestamp.now().normalize()   # today at midnight for consistency
    print(f"  Reference date (today): {today.date()}")

    # ── Per-customer last purchase ─────────────────────────────────────────────
    customer_last_purchase = (
        df.groupby("customer_id")["transaction_date"]
          .max()
          .rename("last_purchase_date")
    )

    # ── Compute recency in days using datetime arithmetic ─────────────────────
    recency_series = (today - customer_last_purchase).dt.days.rename("days_since_last_purchase")

    # Build customer-level recency table
    recency_df = pd.concat([customer_last_purchase, recency_series], axis=1).reset_index()
    recency_df["churn_risk"] = recency_df["days_since_last_purchase"].apply(
        lambda d: "High" if d > 90 else ("Medium" if d > 45 else "Low")
    )

    print("\n  Per-Customer Recency (sample — 10 customers):")
    print(recency_df.head(10).to_string(index=False))

    # ── Merge back to transaction-level df ────────────────────────────────────
    df = df.merge(
        recency_df[["customer_id", "days_since_last_purchase", "churn_risk"]],
        on="customer_id",
        how="left"
    )

    # ── Distribution statistics ────────────────────────────────────────────────
    print("\n  Recency Distribution (days_since_last_purchase):")
    print(df["days_since_last_purchase"].describe().round(1).to_string())

    print(f"\n  Min days since purchase : {df['days_since_last_purchase'].min()}")
    print(f"  Max days since purchase : {df['days_since_last_purchase'].max()}")
    print(f"  Customers with no recent activity (>90 days): "
          f"{(recency_df['churn_risk'] == 'High').sum()} of {len(recency_df)}")

    # ── Plot: recency distribution ─────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(recency_df["days_since_last_purchase"], bins=20,
            color="#55A868", edgecolor="white", linewidth=0.5)
    ax.axvline(90, color="#C44E52", linestyle="--", linewidth=1.5, label="Churn threshold (90 days)")
    ax.axvline(45, color="#DD8452", linestyle="--", linewidth=1.5, label="Medium risk (45 days)")
    ax.set_title("Customer Recency Distribution — Days Since Last Purchase", fontsize=12, fontweight="bold")
    ax.set_xlabel("Days Since Last Purchase")
    ax.set_ylabel("Number of Customers")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()

    out_path = os.path.join(OUTPUT_DIR, "recency_distribution.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Plot saved → {out_path}")

    return df


# ============================================================================
# TASK 5: Build Time-Indexed Aggregation & Hour × Day Pivot
# ============================================================================
def task5_time_indexed_aggregation(df: pd.DataFrame) -> None:
    """
    Task 5: Enable time-series analysis with multiple temporal dimensions.

    Steps:
        1. Multi-level groupby on [day_of_week, hour] with 3 agg functions
        2. Create hour × day-of-week pivot table for heatmap
        3. Identify peak activity windows

    Args:
        df: DataFrame with all engineered time features.
    """
    print("\n" + "=" * 60)
    print("TASK 5: Time-Indexed Aggregation & Pivot Heatmap")
    print("=" * 60)

    # ── Multi-level groupby: day × hour with 3 aggregation functions ──────────
    hourly_daily = df.groupby(["day_of_week", "hour"]).agg(
        total_revenue=("amount", "sum"),
        transaction_count=("amount", "count"),
        avg_amount=("amount", "mean")
    ).round(2)

    print("\n  Multi-Level Groupby [day_of_week × hour] — first 10 rows:")
    print(hourly_daily.head(10).to_string())

    # ── Pivot table: hour (rows) × day-of-week (columns), values = sum(amount) ─
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    pivot_table = pd.pivot_table(
        df,
        values="amount",
        index="hour",
        columns="day_of_week",
        aggfunc="sum",
        fill_value=0
    )
    # Reorder columns to Mon–Sun
    pivot_table = pivot_table.reindex(columns=[d for d in day_order if d in pivot_table.columns])

    print("\n  Hour × Day-of-Week Revenue Pivot Table ($ sum):")
    print(pivot_table.to_string())

    # ── Identify peak activity windows ────────────────────────────────────────
    peak_idx = pivot_table.stack().idxmax()
    peak_val = pivot_table.stack().max()
    print(f"\n  Peak activity window : Hour {peak_idx[0]}, {peak_idx[1]} (${peak_val:,.2f})")

    # ── Plot: heatmap ─────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 7))
    sns.heatmap(
        pivot_table,
        ax=ax,
        cmap="YlOrRd",
        linewidths=0.4,
        linecolor="white",
        fmt=".0f",
        annot=True,
        annot_kws={"size": 7},
        cbar_kws={"label": "Revenue ($)"}
    )
    ax.set_title("Hour × Day-of-Week Revenue Heatmap — CoursePulse Platform",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Hour of Day (0–23)")
    plt.tight_layout()

    out_path = os.path.join(OUTPUT_DIR, "hour_day_heatmap.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Heatmap saved → {out_path}")

    # Save aggregation table to processed data
    os.makedirs("data/processed", exist_ok=True)
    hourly_daily.to_csv("data/processed/hourly_daily_aggregation.csv")
    pivot_table.to_csv("data/processed/hour_day_pivot.csv")
    print("  ✓ Aggregation tables saved to data/processed/")


# ============================================================================
# TESTING / VALIDATION
# ============================================================================
def run_validation_tests(df: pd.DataFrame) -> None:
    """
    Validation tests verifying all pipeline tasks produced correct outputs.

    Args:
        df: Fully engineered DataFrame after all 5 tasks.
    """
    print("\n" + "=" * 60)
    print("VALIDATION TESTS")
    print("=" * 60)

    # Task 1 — datetime parsing
    assert str(df["transaction_date"].dtype).startswith("datetime64"), \
        "FAIL: transaction_date is not datetime64"
    print(f"  [PASS] Min date          : {df['transaction_date'].min()}")
    print(f"  [PASS] Max date          : {df['transaction_date'].max()}")
    print(f"  [PASS] Days in dataset   : {(df['transaction_date'].max() - df['transaction_date'].min()).days}")

    # Task 2 — time features
    assert "day_of_week" in df.columns, "FAIL: day_of_week column missing"
    assert "hour" in df.columns, "FAIL: hour column missing"
    hours_present = sorted(df["hour"].unique())
    print(f"  [PASS] Hours with data   : {hours_present}")

    # Task 3 — week numbers
    assert "week_num" in df.columns, "FAIL: week_num column missing"
    print(f"  [PASS] Weeks in dataset  : {df['week_num'].nunique()}")

    # Task 4 — recency
    assert "days_since_last_purchase" in df.columns, "FAIL: recency column missing"
    print(f"  [PASS] Min days since purchase : {df['days_since_last_purchase'].min()}")
    print(f"  [PASS] Max days since purchase : {df['days_since_last_purchase'].max()}")

    # Task 5 — features count
    features = ["transaction_date", "day_of_week", "hour", "week_num", "days_since_last_purchase"]
    for feat in features:
        assert feat in df.columns, f"FAIL: {feat} column missing"
    print(f"  [PASS] All {len(features)} engineered features present: {features}")

    print("\n  ✓ ALL VALIDATION TESTS PASSED")


# ============================================================================
# MAIN PIPELINE
# ============================================================================
def main():
    """
    Execute the full Datetime Feature Engineering pipeline.

    Pipeline order:
        Data Generation → Task 1 (Parse) → Task 2 (Day/Hour) →
        Task 3 (Week/Resample) → Task 4 (Recency) → Task 5 (Pivot) → Validation
    """
    print("=" * 60)
    print("CoursePulse — Datetime Feature Engineering Pipeline")
    print("=" * 60)

    # ── 0. Generate sample data ───────────────────────────────────────────────
    df = generate_sample_transactions(n_rows=500, seed=42)

    # ── 1. Parse timestamp strings ────────────────────────────────────────────
    df = task1_parse_timestamps(df)

    # ── 2. Extract day-of-week and hour ───────────────────────────────────────
    df = task2_extract_time_features(df)

    # ── 3. Week number and weekly resampling ──────────────────────────────────
    df = task3_week_number_and_resample(df)

    # ── 4. Recency / days-since-last-purchase ─────────────────────────────────
    df = task4_days_since_last_purchase(df)

    # ── 5. Time-indexed aggregation and heatmap ───────────────────────────────
    task5_time_indexed_aggregation(df)

    # ── Save enriched dataset ─────────────────────────────────────────────────
    os.makedirs("data/processed", exist_ok=True)
    out_csv = "data/processed/transactions_datetime_features.csv"
    df.to_csv(out_csv, index=False)
    print(f"\n✓ Enriched dataset saved → {out_csv}")
    print(f"  Final columns: {list(df.columns)}")

    # ── Validation ────────────────────────────────────────────────────────────
    run_validation_tests(df)

    print("\n" + "=" * 60)
    print("✓ Pipeline complete. Check output/ for all plots.")
    print("=" * 60)


if __name__ == "__main__":
    main()
