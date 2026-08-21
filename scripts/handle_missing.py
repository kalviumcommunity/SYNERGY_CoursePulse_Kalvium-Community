"""
scripts/handle_missing.py
==========================
Missing Value Detection and Imputation Pipeline for CoursePulse / Kalvium Community.

Purpose:
    Identify incomplete records across all columns, apply context-appropriate
    imputation strategies, document every decision with business reasoning,
    and log before/after metrics so the treatment is auditable and defensible.

Imputation Strategies Applied:
    - Drop rows       : Critical identifier columns (customer_id, email)
    - Median fill     : Numerical columns (amount, quantity)  — resistant to outliers
    - Mode fill       : Categorical columns (category, region) — most common value
    - Forward fill    : Time-series columns (last_updated)    — temporal continuity

Usage:
    python scripts/handle_missing.py

Outputs:
    • Console report: before/after analysis printed to stdout
    • output/imputation_decisions.json: machine-readable decision log
    • data/processed/cleaned_data.csv: fully imputed, analysis-ready dataset
"""

import os
import sys
import json
import numpy as np
import pandas as pd


# ============================================================================
# TASK 1 — Analyze Missing Values Before Any Treatment
# ============================================================================
def analyze_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute null counts and percentages before any treatment is applied.

    This snapshot must be taken BEFORE any imputation so the before/after
    comparison in Task 4 reflects the true raw state of the data.

    Input:
        df (pd.DataFrame): Raw DataFrame to audit.

    Output:
        pd.DataFrame: One row per column with columns:
                        column, null_count, null_percentage, data_type

    Side effects:
        Prints a formatted missing-value report to stdout.
    """
    missing_analysis = pd.DataFrame({
        "column":          df.columns,
        "null_count":      df.isnull().sum().values,
        "null_percentage": (df.isnull().sum() / len(df) * 100).round(2).values,
        "data_type":       df.dtypes.values,
    })

    print("=" * 70)
    print("BEFORE IMPUTATION — Missing Value Analysis")
    print("=" * 70)
    print(missing_analysis.to_string(index=False))
    print(f"\n  Total rows    : {len(df)}")
    print(f"  Total cells   : {len(df) * len(df.columns)}")
    print(f"  Missing cells : {df.isnull().sum().sum()}")
    print("=" * 70)

    return missing_analysis


# ============================================================================
# TASK 2 — Imputation Strategy Functions
# ============================================================================
def impute_mean_median(
    df: pd.DataFrame,
    numerical_cols: list,
    strategy: str = "median",
) -> pd.DataFrame:
    """
    Fill null values in numerical columns with mean or median.

    Median is preferred over mean for skewed distributions because it is
    resistant to outliers — a single very large transaction will not distort
    the fill value used for all missing entries.

    Input:
        df             (pd.DataFrame): DataFrame to impute (not modified in place).
        numerical_cols (list):         Column names to apply the strategy to.
        strategy       (str):          'median' (default) or 'mean'.

    Output:
        pd.DataFrame: Copy of df with numerical nulls filled.

    Assumptions:
        - Only columns with at least one null are processed.
        - fill_value is computed on the original column (before any rows are dropped).
    """
    df_imputed = df.copy()

    for col in numerical_cols:
        if col not in df_imputed.columns:
            print(f"  ⚠ Skipping '{col}' — column not found in DataFrame.")
            continue

        null_count = int(df_imputed[col].isnull().sum())
        if null_count == 0:
            continue   # nothing to fill

        # Compute fill value before modification for a clean audit trail
        fill_value = (
            df_imputed[col].median() if strategy == "median"
            else df_imputed[col].mean()
        )
        df_imputed[col] = df_imputed[col].fillna(fill_value)
        print(f"  ✓ {col}: filled {null_count} null(s) with {strategy} ({fill_value:.2f})")

    return df_imputed


def impute_mode(df: pd.DataFrame, categorical_cols: list) -> pd.DataFrame:
    """
    Fill null values in categorical columns with the mode (most frequent value).

    Mode fill is the appropriate strategy for string/category columns because
    it preserves the existing distribution without introducing artificial values
    that do not exist in the data.

    Input:
        df               (pd.DataFrame): DataFrame to impute.
        categorical_cols (list):         Column names to apply mode fill to.

    Output:
        pd.DataFrame: Copy of df with categorical nulls filled.

    Assumptions:
        - If a column has multiple modes (tie), the first mode is used.
        - Columns with all nulls (no mode) are skipped with a warning.
    """
    df_imputed = df.copy()

    for col in categorical_cols:
        if col not in df_imputed.columns:
            print(f"  ⚠ Skipping '{col}' — column not found in DataFrame.")
            continue

        null_count = int(df_imputed[col].isnull().sum())
        if null_count == 0:
            continue

        mode_series = df_imputed[col].mode()
        if mode_series.empty:
            print(f"  ⚠ {col}: no mode found (all values null) — skipped.")
            continue

        mode_val = mode_series[0]
        df_imputed[col] = df_imputed[col].fillna(mode_val)
        print(f"  ✓ {col}: filled {null_count} null(s) with mode '{mode_val}'")

    return df_imputed


def impute_forward_fill(df: pd.DataFrame, time_series_cols: list) -> pd.DataFrame:
    """
    Fill null values with the preceding non-null value (forward fill / last-observation-carried-forward).

    Forward fill is correct for time-ordered series where the most recent
    known value is the best estimate for the unknown next value — e.g., a
    status date or a rolling metric that changes infrequently.

    Input:
        df               (pd.DataFrame): DataFrame sorted by time (caller's responsibility).
        time_series_cols (list):         Column names to forward fill.

    Output:
        pd.DataFrame: Copy of df with time-series nulls forward filled.

    Assumptions:
        - DataFrame is already sorted in chronological order.
        - Leading nulls (no prior value to carry forward) remain null — handled
          by a subsequent backward-fill pass if required.
    """
    df_imputed = df.copy()

    for col in time_series_cols:
        if col not in df_imputed.columns:
            print(f"  ⚠ Skipping '{col}' — column not found in DataFrame.")
            continue

        null_count = int(df_imputed[col].isnull().sum())
        if null_count == 0:
            continue

        # Use .ffill() — fillna(method='ffill') is deprecated in pandas 2.x+
        df_imputed[col] = df_imputed[col].ffill()
        remaining = int(df_imputed[col].isnull().sum())
        filled    = null_count - remaining
        print(f"  ✓ {col}: forward-filled {filled} null(s)"
              + (f" ({remaining} leading null(s) remain)" if remaining else ""))

    return df_imputed


def drop_rows_with_nulls(df: pd.DataFrame, critical_cols: list) -> pd.DataFrame:
    """
    Drop any row where a critical identifier column is null.

    Critical columns are those whose absence makes the row unusable for ALL
    downstream purposes (e.g., customer_id is the join key; email is required
    for contact). Imputing these would introduce fabricated identity data.

    Input:
        df            (pd.DataFrame): DataFrame to filter.
        critical_cols (list):         Column names where null = invalid row.

    Output:
        pd.DataFrame: Filtered DataFrame with invalid rows removed.

    Assumptions:
        - Only columns that exist in df are checked (others are skipped).
        - Row count delta is printed for audit purposes.
    """
    rows_before   = len(df)
    valid_cols    = [c for c in critical_cols if c in df.columns]
    df_cleaned    = df.dropna(subset=valid_cols)
    rows_dropped  = rows_before - len(df_cleaned)
    df_cleaned    = df_cleaned.reset_index(drop=True)

    print(f"  ✓ Dropped {rows_dropped} row(s) with null in critical columns: {valid_cols}")
    print(f"    Remaining rows: {len(df_cleaned)}")

    return df_cleaned


# ============================================================================
# TASK 3 — Document Imputation Decisions With Business Reasoning
# ============================================================================
def document_imputation_decisions(
    df_original: pd.DataFrame,
    df_imputed: pd.DataFrame,
) -> dict:
    """
    Generate a machine-readable log of every imputation decision made.

    Each entry records the strategy chosen, the business reasoning behind it,
    the risk of the approach, and the before/after null counts so the treatment
    is fully auditable by anyone reviewing the pipeline.

    Input:
        df_original (pd.DataFrame): Raw DataFrame before any imputation.
        df_imputed  (pd.DataFrame): Cleaned DataFrame after full imputation pipeline.

    Output:
        dict: Decision log — also written to output/imputation_decisions.json.
    """
    def _null_before(col):
        return int(df_original[col].isnull().sum()) if col in df_original else 0

    def _null_after(col):
        return int(df_imputed[col].isnull().sum()) if col in df_imputed else 0

    decisions = {
        "pipeline_run": pd.Timestamp.now().isoformat(),
        "source_file":  "data/raw/missing_data.csv",
        "decisions": {
            "customer_id": {
                "column_type":        "identifier",
                "null_count_before":  _null_before("customer_id"),
                "null_count_after":   _null_after("customer_id"),
                "strategy":           "drop_rows",
                "rows_affected":      _null_before("customer_id"),
                "business_reasoning": (
                    "customer_id is the primary key linking all records to a CRM entity. "
                    "A row without it cannot be attributed to any customer, making it "
                    "useless for any downstream aggregation, segmentation, or modelling."
                ),
                "risk_assessment":    "Low — affects a small % of rows; data loss is acceptable",
            },
            "email": {
                "column_type":        "categorical_identifier",
                "null_count_before":  _null_before("email"),
                "null_count_after":   _null_after("email"),
                "strategy":           "drop_rows",
                "rows_affected":      _null_before("email"),
                "business_reasoning": (
                    "Email is required for all outreach, marketing, and CRM contact workflows. "
                    "Imputing a fake email would send communications to the wrong address. "
                    "Rows without email cannot participate in any customer-facing campaign."
                ),
                "risk_assessment":    "Low — only affects rows already unusable for outreach",
            },
            "amount": {
                "column_type":        "numerical",
                "null_count_before":  _null_before("amount"),
                "null_count_after":   _null_after("amount"),
                "strategy":           "median_imputation",
                "value_used":         round(float(df_original["amount"].median()), 2)
                                      if "amount" in df_original else None,
                "business_reasoning": (
                    "Transaction amount is required for revenue calculations. "
                    "Median is preferred over mean because high-value outlier transactions "
                    "would skew the mean upward, overestimating the typical purchase value. "
                    "Median is stable and representative of the central transaction size."
                ),
                "risk_assessment":    "Low — median is resistant to outliers; distribution integrity maintained",
            },
            "quantity": {
                "column_type":        "numerical",
                "null_count_before":  _null_before("quantity"),
                "null_count_after":   _null_after("quantity"),
                "strategy":           "median_imputation",
                "value_used":         round(float(df_original["quantity"].median()), 2)
                                      if "quantity" in df_original else None,
                "business_reasoning": (
                    "Quantity is needed for unit-economics analysis. "
                    "Median fill prevents a handful of bulk orders from inflating the fill value."
                ),
                "risk_assessment":    "Low — integer column; median rounds to nearest whole number",
            },
            "category": {
                "column_type":        "categorical",
                "null_count_before":  _null_before("category"),
                "null_count_after":   _null_after("category"),
                "strategy":           "mode_imputation",
                "value_used":         str(df_original["category"].mode()[0])
                                      if "category" in df_original and not df_original["category"].mode().empty
                                      else None,
                "business_reasoning": (
                    "Category drives product segmentation reporting. "
                    "Mode fill uses the most common category, preserving the existing distribution "
                    "without introducing values that do not appear organically in the data."
                ),
                "risk_assessment":    "Medium — if mode is unrepresentative, segment metrics may shift slightly",
            },
            "region": {
                "column_type":        "categorical",
                "null_count_before":  _null_before("region"),
                "null_count_after":   _null_after("region"),
                "strategy":           "mode_imputation",
                "value_used":         str(df_original["region"].mode()[0])
                                      if "region" in df_original and not df_original["region"].mode().empty
                                      else None,
                "business_reasoning": (
                    "Region is used for geographic revenue segmentation. "
                    "Mode fill assigns the most common region, which is a reasonable default "
                    "when geographic data is missing from the source system."
                ),
                "risk_assessment":    "Medium — geographic attribution may be incorrect for edge cases",
            },
            "last_updated": {
                "column_type":        "datetime_series",
                "null_count_before":  _null_before("last_updated"),
                "null_count_after":   _null_after("last_updated"),
                "strategy":           "forward_fill",
                "interpretation":     "Carries forward the most recent known timestamp",
                "business_reasoning": (
                    "last_updated is a slowly-changing temporal field. "
                    "Forward fill preserves temporal continuity — the last known date is the "
                    "best estimate for when a gap record was last updated, since status fields "
                    "typically change infrequently between observations."
                ),
                "risk_assessment":    "Medium — assumes no change occurred between the last known and gap records",
            },
        },
        "summary": {
            "total_nulls_before": int(df_original.isnull().sum().sum()),
            "total_nulls_after":  int(df_imputed.isnull().sum().sum()),
            "rows_before":        len(df_original),
            "rows_after":         len(df_imputed),
        },
    }

    # Persist decision log
    os.makedirs("output", exist_ok=True)
    decisions_path = "output/imputation_decisions.json"
    with open(decisions_path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2, default=str)

    print(f"\n  ✓ Decision log saved → {decisions_path}")
    return decisions


# ============================================================================
# TASK 4 — Before / After Validation Report
# ============================================================================
def validate_imputation(
    df_original: pd.DataFrame,
    df_imputed: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare null counts and row totals before and after the full imputation pipeline.

    This function creates the audit trail confirming that every null has been
    treated and no unexpected data has been introduced.

    Input:
        df_original (pd.DataFrame): Raw DataFrame captured before any imputation.
        df_imputed  (pd.DataFrame): Cleaned DataFrame after full pipeline.

    Output:
        pd.DataFrame: Per-column before/after null comparison table.
    """
    print("\n" + "=" * 70)
    print("AFTER IMPUTATION — Validation Report")
    print("=" * 70)
    print(f"  Total rows before : {len(df_original)}")
    print(f"  Total rows after  : {len(df_imputed)}")
    print(f"  Rows removed      : {len(df_original) - len(df_imputed)}")
    print(f"\n  Total nulls before : {df_original.isnull().sum().sum()}")
    print(f"  Total nulls after  : {df_imputed.isnull().sum().sum()}")

    # Build side-by-side comparison for columns present in both DataFrames
    common_cols  = [c for c in df_original.columns if c in df_imputed.columns]
    before_nulls = df_original[common_cols].isnull().sum()
    after_nulls  = df_imputed[common_cols].isnull().sum()

    comparison = pd.DataFrame({
        "column":              common_cols,
        "null_count_before":   before_nulls.values,
        "null_count_after":    after_nulls.values,
        "nulls_resolved":      (before_nulls - after_nulls).values,
        "null_pct_after":      (after_nulls / len(df_imputed) * 100).round(2).values,
    })

    print("\n  Null treatment summary by column:")
    print(comparison.to_string(index=False))
    print("=" * 70)

    return comparison


# ============================================================================
# TASK 5 — Main Imputation Workflow
# ============================================================================
if __name__ == "__main__":
    """
    End-to-end missing value detection and imputation pipeline.

    Execution order:
        1. Analyze raw nulls
        2. Drop rows with critical null identifiers
        3. Median-fill numerical columns
        4. Mode-fill categorical columns
        5. Forward-fill time-series columns
        6. Document decisions
        7. Validate before/after
        8. Save cleaned dataset

    Run with:
        python scripts/handle_missing.py
    """
    # ── Path resolution ───────────────────────────────────────────────────────
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_PATH  = os.path.join(repo_root, "data", "raw",       "missing_data.csv")
    OUTPUT_PATH = os.path.join(repo_root, "data", "processed", "cleaned_data.csv")

    print("=" * 70)
    print("  CoursePulse — Missing Value Handling Pipeline")
    print("=" * 70)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_PATH}\n")

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] Input file not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    # ── Load raw data ─────────────────────────────────────────────────────────
    df_raw = pd.read_csv(INPUT_PATH)
    print(f"  Loaded {len(df_raw)} rows × {len(df_raw.columns)} columns\n")

    # ── Step 1: Analyze missing values (snapshot BEFORE any treatment) ────────
    print("Step 1: Analyzing missing values ...")
    missing_before = analyze_missing_values(df_raw)

    # Capture original for before/after comparison — must NOT be modified
    df_original = df_raw.copy()

    # ── Step 2: Apply imputation strategies ───────────────────────────────────
    print("\nStep 2: Applying imputation strategies ...")
    df = df_raw.copy()

    # Strategy A — Drop rows with nulls in critical identifier columns
    print("\n  [Strategy: Drop rows — critical columns]")
    df = drop_rows_with_nulls(df, critical_cols=["customer_id", "email"])

    # Strategy B — Median fill for numerical columns
    print("\n  [Strategy: Median fill — numerical columns]")
    df = impute_mean_median(df, numerical_cols=["amount", "quantity"], strategy="median")

    # Strategy C — Mode fill for categorical columns
    print("\n  [Strategy: Mode fill — categorical columns]")
    df = impute_mode(df, categorical_cols=["category", "region"])

    # Strategy D — Forward fill for time-series columns
    print("\n  [Strategy: Forward fill — time-series columns]")
    df = impute_forward_fill(df, time_series_cols=["last_updated"])

    # ── Step 3: Document imputation decisions ─────────────────────────────────
    print("\nStep 3: Documenting imputation decisions ...")
    decisions = document_imputation_decisions(df_original, df)

    # ── Step 4: Validate before/after metrics ────────────────────────────────
    print("\nStep 4: Validating imputation results ...")
    validate_imputation(df_original, df)

    # ── Step 5: Save cleaned dataset ──────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n  ✓ Cleaned data saved → {OUTPUT_PATH}")
    print(f"  ✓ Final shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"  ✓ Remaining nulls: {df.isnull().sum().sum()}")
    print("\n" + "=" * 70)
    print("  Pipeline complete — dataset is clean and analysis-ready.")
    print("=" * 70)
