"""
scripts/enforce_types.py
=========================
Data Type Standardization Pipeline for CoursePulse / Kalvium Community Platform.

Purpose:
    Enforce correct data types across every column so downstream analysis,
    aggregations, and ML models receive data in the format they expect.
    Logs every conversion so future analysts understand what was standardized.

Conversions applied:
    Task 1: Generic column type casting via explicit type mapping dict
    Task 2: String dates → datetime64 with explicit format (no ambiguity)
    Task 3: Currency strings ("$150.50") → float64 (strip symbols, coerce)
    Task 4: Integer booleans (0/1) or yes/no strings → proper bool type
    Task 5: Before/after dtype comparison report
    Task 6: End-to-end main workflow

Usage:
    python scripts/enforce_types.py

Outputs:
    • Console: full before/after type report
    • output/dtype_conversion_report.csv: machine-readable conversion summary
    • data/processed/typed_data.csv: fully typed, analysis-ready dataset
"""

import os
import sys
import numpy as np
import pandas as pd


# ============================================================================
# TASK 1 — Generic Column Type Casting
# ============================================================================
def cast_columns_to_types(df: pd.DataFrame, type_mapping: dict) -> tuple:
    """
    Explicitly cast columns to correct dtypes using a caller-supplied mapping.

    This is the generic fallback for simple type conversions that do not
    require special parsing logic (e.g., int → float, object → category).
    For dates, currency, and booleans use the dedicated functions below.

    Input:
        df           (pd.DataFrame): Source DataFrame to cast.
        type_mapping (dict):         {column_name: target_dtype_string}
                                     e.g. {'age': 'int32', 'score': 'float64'}

    Output:
        (pd.DataFrame, dict):
            df_typed       — copy of df with requested casts applied.
            conversion_log — {col: {from, to, status, error?}} for each column.

    Assumptions:
        - Columns not present in df are skipped with a warning (not an error).
        - Failed casts raise immediately to prevent silent data corruption.
    """
    df_typed       = df.copy()
    conversion_log = {}

    for col, target_dtype in type_mapping.items():
        if col not in df_typed.columns:
            print(f"  ⚠ Warning: column '{col}' not found — skipped.")
            continue

        original_dtype = str(df_typed[col].dtype)

        try:
            df_typed[col] = df_typed[col].astype(target_dtype)
            conversion_log[col] = {
                "from":   original_dtype,
                "to":     str(target_dtype),
                "status": "success",
            }
            print(f"  ✓ {col}: {original_dtype} → {target_dtype}")

        except Exception as exc:
            conversion_log[col] = {
                "from":   original_dtype,
                "to":     str(target_dtype),
                "status": "failed",
                "error":  str(exc),
            }
            print(f"  ✗ {col}: Conversion failed — {exc}")
            raise   # hard fail: do not allow silently mistyped columns

    return df_typed, conversion_log


# ============================================================================
# TASK 2 — String Dates → Datetime
# ============================================================================
def convert_string_dates_to_datetime(
    df: pd.DataFrame,
    date_columns: list,
    date_format: str = None,
) -> pd.DataFrame:
    """
    Convert string date columns to datetime64 with an explicit format string.

    WHY EXPLICIT FORMAT:
        "01-02-2025" is completely ambiguous — it could be Jan 2 or Feb 1
        depending on locale. Without format=, pandas makes a silent guess
        that may be wrong on some rows. Always specify the format.

    Input:
        df           (pd.DataFrame): Source DataFrame.
        date_columns (list):         Column names that contain date strings.
        date_format  (str | None):   strftime format, e.g. '%Y-%m-%d'.
                                     If None, pandas inference is used with
                                     an explicit warning logged.

    Output:
        pd.DataFrame: Copy of df with date columns converted to datetime64.

    Raises:
        ValueError: If the format string does not match the actual values.

    Assumptions:
        - All values in a date column follow the same format.
        - NaT (not-a-time) is the null equivalent for datetime columns.
    """
    df_typed = df.copy()

    for col in date_columns:
        if col not in df_typed.columns:
            print(f"  ⚠ Warning: column '{col}' not found — skipped.")
            continue

        if date_format is None:
            print(f"  ⚠ {col}: no format specified — using pandas inference (risky!).")

        try:
            df_typed[col] = pd.to_datetime(
                df_typed[col],
                format=date_format,   # explicit format prevents silent misparse
            )
            print(f"  ✓ {col}: string → datetime64 (format='{date_format}')")

        except Exception as exc:
            print(f"  ✗ {col}: Conversion failed — {exc}")
            print(f"    Sample values : {df[col].head(3).tolist()}")
            print(f"    Expected format: {date_format}")
            raise

    return df_typed


# ============================================================================
# TASK 3 — Currency Strings → Float
# ============================================================================
def convert_currency_to_float(df: pd.DataFrame, currency_columns: list) -> pd.DataFrame:
    """
    Strip currency symbols and whitespace, then convert to float64.

    Example transformations:
        '$150.50'  → 150.50
        '$1,200.00' → 1200.00
        '€ 75.25'  → 75.25

    Input:
        df               (pd.DataFrame): Source DataFrame.
        currency_columns (list):         Column names containing currency strings.

    Output:
        pd.DataFrame: Copy of df with currency columns as float64.

    Assumptions:
        - Handles $, €, £, ¥, and comma thousands-separators.
        - Values that cannot be parsed after symbol removal → NaN (errors='coerce').
        - New NaNs created by coerce are reported as failed conversions.
    """
    df_typed = df.copy()

    for col in currency_columns:
        if col not in df_typed.columns:
            print(f"  ⚠ Warning: column '{col}' not found — skipped.")
            continue

        try:
            # Capture original null count before any transformation
            nulls_before = int(df_typed[col].isnull().sum())

            # Step 1: coerce to string (handles existing NaN safely as 'nan')
            # Step 2: strip all currency symbols and thousands-separators
            # Step 3: strip whitespace
            df_typed[col] = (
                df_typed[col]
                .astype(str)
                .str.replace(r"[$€£¥,]", "", regex=True)
                .str.strip()
                .replace("nan", None)   # restore NaN that was stringified
            )

            # Step 4: convert to numeric; non-parseable → NaN
            df_typed[col] = pd.to_numeric(df_typed[col], errors="coerce")

            # Detect values that failed conversion (new NaNs beyond original)
            nulls_after   = int(df_typed[col].isnull().sum())
            failed_count  = max(0, nulls_after - nulls_before)

            if failed_count > 0:
                print(f"  ⚠ {col}: {failed_count} value(s) could not be converted to numeric")

            print(f"  ✓ {col}: currency string → float64 (symbols stripped)")

        except Exception as exc:
            print(f"  ✗ {col}: Conversion failed — {exc}")
            raise

    return df_typed


# ============================================================================
# TASK 4 — Integer / String Booleans → bool
# ============================================================================
def convert_integers_to_boolean(df: pd.DataFrame, boolean_columns: list) -> pd.DataFrame:
    """
    Convert binary integer (0/1) or string (yes/no, true/false) columns to bool.

    Using Python's native bool dtype makes the column's intent explicit and
    prevents accidental arithmetic operations on what is conceptually a flag.

    Input:
        df              (pd.DataFrame): Source DataFrame.
        boolean_columns (list):         Column names with binary values.

    Output:
        pd.DataFrame: Copy of df with boolean columns as dtype bool.

    Assumptions:
        - Accepted truthy values  : 1, '1', 'yes', 'y', 'true',  True
        - Accepted falsy values   : 0, '0', 'no',  'n', 'false', False
        - Unrecognised values     → NaN (does not raise, but is reported)
        - Comparison is case-insensitive for string inputs.
    """
    df_typed = df.copy()

    # Comprehensive mapping covering all common boolean representations
    BOOL_MAP = {
        "yes": True,  "no": False,
        "y":   True,  "n":  False,
        "true": True, "false": False,
        "1":   True,  "0":  False,
        1:     True,  0:    False,
        True:  True,  False: False,
    }

    for col in boolean_columns:
        if col not in df_typed.columns:
            print(f"  ⚠ Warning: column '{col}' not found — skipped.")
            continue

        unique_vals = df_typed[col].unique()
        print(f"    {col} unique values: {unique_vals}")

        try:
            if df_typed[col].dtype == object:
                # Normalise string case before mapping
                df_typed[col] = (
                    df_typed[col]
                    .astype(str)
                    .str.lower()
                    .map(BOOL_MAP)
                )
            else:
                # Integer / float column — direct bool cast (0 → False, nonzero → True)
                df_typed[col] = df_typed[col].astype(bool)

            unmapped = int(df_typed[col].isnull().sum())
            if unmapped > 0:
                print(f"  ⚠ {col}: {unmapped} value(s) could not be mapped to bool → NaN")

            print(f"  ✓ {col}: {df[col].dtype} → bool")

        except Exception as exc:
            print(f"  ✗ {col}: Conversion failed — {exc}")
            raise

    return df_typed


# ============================================================================
# TASK 5 — Before / After dtype Comparison
# ============================================================================
def compare_dtypes(df_original: pd.DataFrame, df_typed: pd.DataFrame) -> pd.DataFrame:
    """
    Produce a side-by-side dtype comparison report for every column.

    Saves the report as output/dtype_conversion_report.csv so it can be
    committed to git as evidence that all types were deliberately enforced.

    Input:
        df_original (pd.DataFrame): Raw DataFrame before type enforcement.
        df_typed    (pd.DataFrame): Cleaned DataFrame after type enforcement.

    Output:
        pd.DataFrame: Comparison table with columns:
                        column, dtype_before, dtype_after, changed (bool)

    Side effects:
        Writes output/dtype_conversion_report.csv.
    """
    comparison = pd.DataFrame({
        "column":       df_original.columns,
        "dtype_before": [str(t) for t in df_original.dtypes.values],
        "dtype_after":  [str(df_typed[c].dtype) if c in df_typed else "N/A"
                         for c in df_original.columns],
        "changed":      (df_original.dtypes != df_typed[df_original.columns].dtypes).values,
    })

    print("\n" + "=" * 70)
    print("DTYPE CONVERSION SUMMARY")
    print("=" * 70)
    print(comparison.to_string(index=False))
    changed_count = comparison["changed"].sum()
    print(f"\n  {changed_count} column(s) changed type.")

    # Persist report
    os.makedirs("output", exist_ok=True)
    report_path = "output/dtype_conversion_report.csv"
    comparison.to_csv(report_path, index=False)
    print(f"  Report saved → {report_path}")
    print("=" * 70)

    return comparison


# ============================================================================
# TASK 6 — End-to-End Main Workflow
# ============================================================================
if __name__ == "__main__":
    """
    End-to-end data type enforcement pipeline.

    Execution order:
        1. Load raw untyped CSV
        2. Print before-state (dtypes + sample)
        3. Convert string dates → datetime64
        4. Convert currency strings → float64
        5. Convert 0/1 integers → bool
        6. Print after-state (dtypes + sample)
        7. Generate dtype comparison report
        8. Save typed dataset

    Run with:
        python scripts/enforce_types.py
    """
    # ── Path resolution ───────────────────────────────────────────────────────
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_PATH  = os.path.join(repo_root, "data", "raw",       "untyped_data.csv")
    OUTPUT_PATH = os.path.join(repo_root, "data", "processed", "typed_data.csv")

    print("=" * 70)
    print("  CoursePulse — Data Type Enforcement Pipeline")
    print("=" * 70)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_PATH}")
    print("=" * 70)

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] Input file not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    # ── Load raw data ─────────────────────────────────────────────────────────
    df = pd.read_csv(INPUT_PATH)

    print("\nBEFORE TYPE CONVERSION")
    print("=" * 70)
    print(df.dtypes.to_string())
    print(f"\nSample data (first 3 rows):")
    print(df.head(3).to_string(index=False))

    df_typed = df.copy()

    # ── Step 1: Convert date columns ──────────────────────────────────────────
    print("\n1. Converting date columns ...")
    df_typed = convert_string_dates_to_datetime(
        df_typed,
        date_columns=["transaction_date", "signup_date"],
        date_format="%Y-%m-%d",   # ALWAYS specify — prevents silent misparse
    )

    # ── Step 2: Convert currency columns ─────────────────────────────────────
    print("\n2. Converting currency columns ...")
    df_typed = convert_currency_to_float(
        df_typed,
        currency_columns=["amount", "revenue"],
    )

    # ── Step 3: Convert boolean columns ──────────────────────────────────────
    print("\n3. Converting boolean columns ...")
    df_typed = convert_integers_to_boolean(
        df_typed,
        boolean_columns=["is_active", "is_premium"],
    )

    # ── After-state snapshot ──────────────────────────────────────────────────
    print("\nAFTER TYPE CONVERSION")
    print("=" * 70)
    print(df_typed.dtypes.to_string())
    print(f"\nSample data (first 3 rows):")
    print(df_typed.head(3).to_string(index=False))

    # ── Step 4: Dtype comparison report ──────────────────────────────────────
    print("\n4. Comparing before/after types ...")
    compare_dtypes(df, df_typed)

    # ── Step 5: Save typed dataset ────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df_typed.to_csv(OUTPUT_PATH, index=False)

    print(f"\n  ✓ Typed data saved → {OUTPUT_PATH}")
    print(f"  ✓ Shape: {df_typed.shape[0]} rows × {df_typed.shape[1]} columns")
    print("\n" + "=" * 70)
    print("  Type enforcement complete — all columns correctly typed.")
    print("=" * 70)
