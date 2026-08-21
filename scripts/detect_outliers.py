"""
scripts/detect_outliers.py
===========================
Outlier Detection and Handling Pipeline for CoursePulse / Kalvium Community.

Purpose:
    Identify extreme values that distort statistical analysis, make explicit
    decisions about how to handle each outlier (cap / flag / remove), and
    produce a cleaning log so every decision is auditable.

Methods:
    Task 1: Z-score detection  — values beyond ±3 standard deviations
    Task 2: IQR detection      — values beyond 1.5 × IQR from Q1/Q3
    Task 3: Cap outliers       — clip to IQR boundary (Winsorisation)
    Task 4: Flag outliers      — binary is_outlier column (union of both methods)
    Task 5: Cleaning log       — structured CSV documenting all decisions

Usage:
    python scripts/detect_outliers.py

Outputs:
    • Console report with before/after statistics
    • output/cleaning_log.csv        — structured audit of all decisions
    • data/processed/outliers_handled.csv — final dataset with capped + flagged columns
"""

import os
import sys
import numpy as np
import pandas as pd
from scipy import stats


# ============================================================================
# TASK 1 — Z-Score Outlier Detection
# ============================================================================
def detect_zscore_outliers(df: pd.DataFrame, column: str, threshold: float = 3.0) -> pd.DataFrame:
    """
    Detect outliers as values whose absolute Z-score exceeds the threshold.

    Z-score = (value - mean) / std_deviation
    A Z-score > 3 means the value is more than 3 standard deviations from
    the mean — statistically extreme in a normal distribution (~0.3% of data).

    Input:
        df        (pd.DataFrame): DataFrame containing the column to analyse.
        column    (str):          Name of the numerical column.
        threshold (float):        Z-score cutoff. Default = 3.0 (industry standard).

    Output:
        pd.DataFrame: df with a new column f'{column}_zscore' added.

    Side effects:
        Prints count and sample of detected outliers.
    """
    zscore_col = f"{column}_zscore"

    # Compute absolute Z-score — handles NaN by producing NaN (skipna behaviour)
    df[zscore_col] = np.abs(stats.zscore(df[column].dropna()))

    # Re-align index after dropna (zscore returns array aligned to non-null index)
    z_series = pd.Series(
        np.abs(stats.zscore(df[column].fillna(df[column].mean()))),
        index=df.index,
    )
    df[zscore_col] = z_series.round(4)

    z_outliers = df[df[zscore_col] > threshold]

    print(f"\n  Z-SCORE DETECTION  ({column}, threshold=±{threshold})")
    print(f"  {'─'*55}")
    print(f"  Mean        : {df[column].mean():.2f}")
    print(f"  Std         : {df[column].std():.2f}")
    print(f"  Z-score outliers found : {len(z_outliers)}")

    if len(z_outliers):
        for _, row in z_outliers.iterrows():
            print(f"    → {row.get('name', row.name)}: {column}={row[column]:.2f}  "
                  f"(z={row[zscore_col]:.2f})")

    return df


# ============================================================================
# TASK 2 — IQR Outlier Detection
# ============================================================================
def detect_iqr_outliers(df: pd.DataFrame, column: str, factor: float = 1.5) -> tuple:
    """
    Detect outliers using the Interquartile Range (IQR) fence method.

    Fences:
        Lower fence = Q1 - factor × IQR
        Upper fence = Q3 + factor × IQR

    Values outside these fences are flagged as outliers.
    IQR method is more robust than Z-score for skewed distributions because
    it does not assume normality — it uses rank-based quartiles.

    Input:
        df     (pd.DataFrame): DataFrame containing the column to analyse.
        column (str):          Name of the numerical column.
        factor (float):        IQR multiplier. 1.5 = standard; 3.0 = extreme only.

    Output:
        (pd.DataFrame, float, float):
            df     — with new column f'is_outlier_iqr_{column}' added (bool).
            lower  — lower IQR fence value.
            upper  — upper IQR fence value.
    """
    Q1    = df[column].quantile(0.25)
    Q3    = df[column].quantile(0.75)
    IQR   = Q3 - Q1
    lower = Q1 - factor * IQR
    upper = Q3 + factor * IQR

    iqr_flag_col = f"is_outlier_iqr"
    df[iqr_flag_col] = (df[column] < lower) | (df[column] > upper)
    iqr_count = int(df[iqr_flag_col].sum())

    print(f"\n  IQR DETECTION  ({column}, factor={factor})")
    print(f"  {'─'*55}")
    print(f"  Q1          : {Q1:.2f}")
    print(f"  Q3          : {Q3:.2f}")
    print(f"  IQR         : {IQR:.2f}")
    print(f"  Lower fence : {lower:.2f}")
    print(f"  Upper fence : {upper:.2f}")
    print(f"  IQR outliers found : {iqr_count}")

    iqr_outliers = df[df[iqr_flag_col]]
    if len(iqr_outliers):
        for _, row in iqr_outliers.iterrows():
            direction = "HIGH" if row[column] > upper else "LOW"
            print(f"    → {row.get('name', row.name)}: {column}={row[column]:.2f}  [{direction}]")

    return df, lower, upper


# ============================================================================
# TASK 3 — Cap Outliers at IQR Boundaries (Winsorisation)
# ============================================================================
def cap_outliers(df: pd.DataFrame, column: str, lower: float, upper: float) -> pd.DataFrame:
    """
    Replace extreme outlier values with the IQR fence boundaries (capping/Winsorisation).

    Capping preserves the row and its other columns in the dataset while
    constraining the extreme value to the boundary. This is preferred over
    row deletion when:
        - The row contains valid non-outlier data in other columns
        - Sample size is small and losing rows is costly
        - The outlier is likely a data entry error, not a real extreme event

    Input:
        df     (pd.DataFrame): DataFrame with original and IQR columns.
        column (str):          Name of the numerical column to cap.
        lower  (float):        Lower IQR fence — values below this → lower.
        upper  (float):        Upper IQR fence — values above this → upper.

    Output:
        pd.DataFrame: df with new column f'{column}_capped' added.
    """
    capped_col = f"{column}_capped"
    df[capped_col] = df[column].clip(lower=lower, upper=upper)

    print(f"\n  CAPPING  ({column}  →  {capped_col})")
    print(f"  {'─'*55}")
    print(f"  Before → min: {df[column].min():.2f}   max: {df[column].max():.2f}")
    print(f"  After  → min: {df[capped_col].min():.2f}   max: {df[capped_col].max():.2f}")
    capped_count = (df[column] != df[capped_col]).sum()
    print(f"  Values capped : {capped_count}")

    return df


# ============================================================================
# TASK 4 — Flag Outliers with Binary Column
# ============================================================================
def flag_outliers(df: pd.DataFrame, column: str, zscore_threshold: float = 3.0) -> pd.DataFrame:
    """
    Create a combined is_outlier flag using the union of Z-score and IQR methods.

    Flagging (instead of deleting) preserves all data while marking anomalies
    so downstream analysis can:
        • Filter to normal records only:  df[~df['is_outlier']]
        • Weight outliers differently in models
        • Investigate anomalies separately for fraud / data quality review

    Input:
        df               (pd.DataFrame): DataFrame with z-score and IQR columns.
        column           (str):          Column name (used to identify z-score col).
        zscore_threshold (float):        Z-score cutoff used in Task 1.

    Output:
        pd.DataFrame: df with 'is_outlier' (bool) column added.
    """
    zscore_col = f"{column}_zscore"
    iqr_col    = "is_outlier_iqr"

    # Union: flagged by EITHER method
    df["is_outlier"] = (df[zscore_col] > zscore_threshold) | df[iqr_col]

    normal    = df[~df["is_outlier"]]
    anomalies = df[df["is_outlier"]]

    print(f"\n  OUTLIER FLAGGING  (union of Z-score + IQR)")
    print(f"  {'─'*55}")
    print(f"  Normal records    : {len(normal):,}")
    print(f"  Anomaly records   : {len(anomalies):,}")
    print(f"\n  Anomaly details:")
    for _, row in anomalies.iterrows():
        print(f"    → {row.get('name', row.name)}: {column}={row[column]:.2f}  "
              f"z={row[zscore_col]:.2f}  iqr_flag={row[iqr_col]}")

    return df


# ============================================================================
# TASK 5 — Cleaning Log
# ============================================================================
def create_cleaning_log(
    df: pd.DataFrame,
    column: str,
    lower: float,
    upper: float,
    zscore_col: str,
    zscore_threshold: float = 3.0,
) -> pd.DataFrame:
    """
    Produce a structured CSV log documenting every outlier handling decision.

    The log records:
        - Which column was analysed
        - What method was used (Z-score / IQR)
        - What action was taken (cap / flag)
        - The threshold values used
        - How many rows were affected
        - When the cleaning was performed

    This log satisfies data governance requirements — future analysts can
    reproduce the exact cleaning steps from the log alone.

    Input:
        df               (pd.DataFrame): Fully processed DataFrame.
        column           (str):          Column that was cleaned.
        lower / upper    (float):        IQR fence values.
        zscore_col       (str):          Name of the Z-score column.
        zscore_threshold (float):        Z-score cutoff used.

    Output:
        pd.DataFrame: Cleaning log — also written to output/cleaning_log.csv.
    """
    cleaning_log = [
        {
            "column":            column,
            "method":            "Z-score",
            "action":            "flag",
            "threshold_lower":   -zscore_threshold,
            "threshold_upper":   zscore_threshold,
            "affected_rows":     int((df[zscore_col] > zscore_threshold).sum()),
            "business_reasoning":"Values beyond ±3 std devs are statistically extreme. "
                                  "Flagged for review — not removed as they may be valid "
                                  "high-value customers.",
            "date":              pd.Timestamp.now().isoformat(),
        },
        {
            "column":            column,
            "method":            "IQR",
            "action":            "cap",
            "threshold_lower":   round(lower, 4),
            "threshold_upper":   round(upper, 4),
            "affected_rows":     int(df["is_outlier_iqr"].sum()),
            "business_reasoning":"IQR capping (Winsorisation) preserves row count while "
                                  "constraining extreme values to fence boundaries. "
                                  "Preferred over deletion for small datasets.",
            "date":              pd.Timestamp.now().isoformat(),
        },
        {
            "column":            "age",
            "method":            "domain_rule",
            "action":            "flag",
            "threshold_lower":   0,
            "threshold_upper":   120,
            "affected_rows":     int((df["age"] > 120).sum()),
            "business_reasoning":"Age > 120 is biologically impossible. "
                                  "Flagged as data entry error. "
                                  "Recommend correction from source system before analysis.",
            "date":              pd.Timestamp.now().isoformat(),
        },
    ]

    log_df = pd.DataFrame(cleaning_log)

    os.makedirs("output", exist_ok=True)
    log_df.to_csv("output/cleaning_log.csv", index=False)

    print(f"\n  CLEANING LOG")
    print(f"  {'─'*55}")
    print(log_df.to_string(index=False))
    print(f"\n  ✓ Cleaning log saved → output/cleaning_log.csv")

    return log_df


# ============================================================================
# MAIN PIPELINE
# ============================================================================
if __name__ == "__main__":
    """
    End-to-end outlier detection and handling pipeline.

    Run with:
        python scripts/detect_outliers.py
    """
    # ── Path resolution ───────────────────────────────────────────────────────
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_PATH  = os.path.join(repo_root, "data", "raw",       "customer_revenue.csv")
    OUTPUT_PATH = os.path.join(repo_root, "data", "processed", "outliers_handled.csv")

    print("=" * 65)
    print("  CoursePulse — Outlier Detection & Handling Pipeline")
    print("=" * 65)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_PATH}")
    print("=" * 65)

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] File not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(INPUT_PATH)
    print(f"\n  Loaded {len(df)} rows × {len(df.columns)} columns")

    # ── Before-state snapshot ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("BEFORE — Revenue Statistics")
    print("=" * 65)
    print(df["revenue"].describe().round(2).to_string())

    COLUMN    = "revenue"
    THRESHOLD = 3.0

    # ── Task 1: Z-score detection ─────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("TASK 1 — Z-Score Outlier Detection")
    print("=" * 65)
    df = detect_zscore_outliers(df, column=COLUMN, threshold=THRESHOLD)

    # ── Task 2: IQR detection ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("TASK 2 — IQR Outlier Detection")
    print("=" * 65)
    df, lower, upper = detect_iqr_outliers(df, column=COLUMN, factor=1.5)

    # ── Task 3: Cap outliers ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("TASK 3 — Cap Outliers at IQR Boundaries")
    print("=" * 65)
    df = cap_outliers(df, column=COLUMN, lower=lower, upper=upper)

    # ── Task 4: Flag outliers ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("TASK 4 — Flag Outliers (Combined Z-score + IQR)")
    print("=" * 65)
    df = flag_outliers(df, column=COLUMN, zscore_threshold=THRESHOLD)

    # ── Task 5: Cleaning log ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("TASK 5 — Cleaning Log")
    print("=" * 65)
    log_df = create_cleaning_log(
        df, COLUMN, lower, upper,
        zscore_col=f"{COLUMN}_zscore",
        zscore_threshold=THRESHOLD,
    )

    # ── After-state snapshot ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("AFTER — Revenue Capped Statistics")
    print("=" * 65)
    print(df["revenue_capped"].describe().round(2).to_string())

    # ── Age domain-rule check ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("BONUS — Age Domain Rule (impossible values > 120)")
    print("=" * 65)
    age_impossible = df[df["age"] > 120]
    print(f"  Age > 120 found : {len(age_impossible)} record(s)")
    for _, row in age_impossible.iterrows():
        print(f"    → {row['name']}: age={row['age']}  [DATA ENTRY ERROR]")

    # ── Save output ───────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\n  ✓ Handled dataset saved → {OUTPUT_PATH}")
    print(f"  ✓ Columns in output: {list(df.columns)}")
    print("\n" + "=" * 65)
    print("  Outlier detection and handling pipeline complete.")
    print("=" * 65)
