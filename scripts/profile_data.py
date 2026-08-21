"""
scripts/profile_data.py
========================
Data Profiling and Quality Assessment for CoursePulse / Kalvium Community Platform.

Purpose:
    Evaluate ingested data quality BEFORE any cleaning or transformation.
    Produces a structured JSON quality report that guides all downstream
    cleaning decisions — acting as the diagnostic layer of the pipeline.

Profiling Tasks:
    Task 1: Null percentages and exact-duplicate counts
    Task 2: Numerical column statistical summaries (min, max, mean, median, std)
    Task 3: Categorical column value distributions (unique count, top-N values)
    Task 4: Quality issue detection with severity flags and recommendations
    Task 5: Consolidated JSON report saved to output/profile_report.json

Usage:
    python scripts/profile_data.py

Output:
    • Console summary printed to stdout
    • output/profile_report.json — structured quality report
"""

import os
import sys
import json
import numpy as np
import pandas as pd


# ============================================================================
# TASK 1 — Null and Duplicate Metrics
# ============================================================================
def profile_nulls_and_duplicates(df: pd.DataFrame) -> dict:
    """
    Compute null percentage and duplicate counts across every column.

    Null analysis is done per-column so the caller can decide per-column
    remediation strategies (impute vs. drop vs. flag).

    Input:
        df (pd.DataFrame): Raw DataFrame to profile.

    Output:
        dict with keys:
            null_counts          (dict): {col: int}   — absolute null count per column
            null_percentages     (dict): {col: float} — % of rows that are null per col
            exact_duplicate_count (int): rows where ALL column values are identical
            duplicate_percentage  (float): % of rows that are exact duplicates

    Assumptions:
        - NaN, None, and pd.NaT are all treated as null (standard pandas behaviour).
        - Duplicate detection uses ALL columns (subset=None) to find fully identical rows.
    """
    profile = {
        "null_counts":           {},
        "null_percentages":      {},
        "exact_duplicate_count": 0,
        "duplicate_percentage":  0.0,
    }

    total_rows = len(df)

    for col in df.columns:
        null_count = int(df[col].isna().sum())            # int for JSON serialisation
        null_pct   = (null_count / total_rows) * 100 if total_rows > 0 else 0.0
        profile["null_counts"][col]      = null_count
        profile["null_percentages"][col] = round(null_pct, 2)

    # Count rows where every value matches another row exactly
    dup_count = int(df.duplicated().sum())
    profile["exact_duplicate_count"] = dup_count
    profile["duplicate_percentage"]  = round((dup_count / total_rows) * 100, 2) \
                                        if total_rows > 0 else 0.0

    return profile


# ============================================================================
# TASK 2 — Numerical Column Profiling
# ============================================================================
def profile_numerical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarise all numerical columns with descriptive statistical measures.

    Provides the five-number summary plus standard deviation so the analyst
    can spot outliers, skewness, and scale issues before cleaning.

    Input:
        df (pd.DataFrame): Raw DataFrame to profile.

    Output:
        pd.DataFrame: One row per numerical column, columns:
                        min, max, mean, median, std, null_count

    Assumptions:
        - Uses numpy dtype detection (int, float); boolean columns are excluded.
        - All statistics ignore NaN values (skipna=True, the pandas default).
        - Values rounded to 2 decimal places for readability.
    """
    # Select only genuinely numeric columns (excludes bool, datetime, object)
    numerical_cols = df.select_dtypes(include=[np.number]).columns

    stats = {}
    for col in numerical_cols:
        series = df[col]
        stats[col] = {
            "min":        round(float(series.min()),    2),
            "max":        round(float(series.max()),    2),
            "mean":       round(float(series.mean()),   2),
            "median":     round(float(series.median()), 2),
            "std":        round(float(series.std()),    2),
            "null_count": int(series.isnull().sum()),
        }

    if not stats:
        # Return an empty DataFrame with expected columns if no numeric data exists
        return pd.DataFrame(columns=["min", "max", "mean", "median", "std", "null_count"])

    return pd.DataFrame(stats).T


# ============================================================================
# TASK 3 — Categorical Column Profiling
# ============================================================================
def profile_categorical_columns(df: pd.DataFrame, top_n: int = 5) -> dict:
    """
    Summarise categorical (string/object) columns with value distributions.

    Reveals whether categories contain expected values or have corruption,
    typos, encoding artifacts, or suspicious concentrations.

    Input:
        df    (pd.DataFrame): Raw DataFrame to profile.
        top_n (int):          Number of most-frequent values to return per column.
                              Default: 5.

    Output:
        dict: {col_name: {'unique_count', 'top_values', 'null_count'}}
            unique_count (int):  Number of distinct non-null values.
            top_values   (dict): {value: count} for the top_n most frequent values.
            null_count   (int):  Number of null/NaN entries in the column.

    Assumptions:
        - Only columns with pandas dtype 'object' or 'string' are profiled.
        - value_counts() excludes NaN by default, which is the intended behaviour.
    """
    categorical_cols = df.select_dtypes(include=["object", "string"]).columns

    profile = {}
    for col in categorical_cols:
        profile[col] = {
            "unique_count": int(df[col].nunique()),
            "top_values":   df[col].value_counts().head(top_n).to_dict(),
            "null_count":   int(df[col].isnull().sum()),
        }

    return profile


# ============================================================================
# TASK 4 — Quality Issue Identification
# ============================================================================
def identify_quality_issues(
    df: pd.DataFrame,
    null_threshold: float = 30.0,
    duplicate_threshold: float = 5.0,
) -> list:
    """
    Flag data quality problems based on configurable thresholds.

    Three categories of issues are detected:
        1. High null rate per column (default threshold: >30%)
        2. High duplicate row rate   (default threshold: >5%)
        3. Invalid ranges — negative values in columns whose name contains 'amount'

    Input:
        df                   (pd.DataFrame): Raw DataFrame to audit.
        null_threshold       (float): % null above which a column is flagged. Default 30.
        duplicate_threshold  (float): % duplicates above which rows are flagged. Default 5.

    Output:
        list of dicts, each with keys:
            type           (str): Short category label.
            column         (str): Affected column name (or 'Full row' for row-level issues).
            severity       (str): 'HIGH' or 'MEDIUM'.
            value          (str): Observed problematic value/metric.
            recommendation (str): Suggested remediation action.

    Assumptions:
        - Issues list is ordered: nulls first, then duplicates, then range checks.
        - An empty list means no issues were detected (clean data).
    """
    issues = []
    total_rows = len(df)

    # ── Check 1: High null rate per column ───────────────────────────────────
    null_pcts = (df.isnull().sum() / total_rows) * 100
    for col, pct in null_pcts.items():
        if pct > null_threshold:
            issues.append({
                "type":           "High nulls",
                "column":         col,
                "severity":       "HIGH",
                "value":          f"{pct:.1f}% missing",
                "recommendation": "Consider imputation or column exclusion",
            })

    # ── Check 2: High duplicate row rate ─────────────────────────────────────
    dup_count = df.duplicated().sum()
    dup_pct   = (dup_count / total_rows) * 100 if total_rows > 0 else 0.0
    if dup_pct > duplicate_threshold:
        issues.append({
            "type":           "High duplicates",
            "column":         "Full row",
            "severity":       "HIGH",
            "value":          f"{dup_pct:.1f}% duplicated",
            "recommendation": "Deduplication required before analysis",
        })

    # ── Check 3: Invalid ranges — negative amounts ───────────────────────────
    for col in df.select_dtypes(include=[np.number]).columns:
        if "amount" in col.lower() and (df[col] < 0).any():
            neg_count = int((df[col] < 0).sum())
            issues.append({
                "type":           "Invalid range",
                "column":         col,
                "severity":       "MEDIUM",
                "value":          f"Contains {neg_count} negative value(s)",
                "recommendation": "Investigate negative entries — may indicate refunds or data errors",
            })

    return issues


# ============================================================================
# TASK 5 — Structured Quality Report Generation
# ============================================================================
def generate_profile_report(df: pd.DataFrame, filepath: str) -> dict:
    """
    Combine all profiling functions into a single structured quality report.

    The report is saved as output/profile_report.json so it can be:
        • Reviewed before any cleaning decisions are made
        • Committed to git to track data quality over time
        • Consumed by downstream validation gates

    Input:
        df       (pd.DataFrame): Raw DataFrame to profile.
        filepath (str):          Source file path (for labelling in the report).

    Output:
        dict: Complete profile report.
              Also written to output/profile_report.json as a side effect.
    """
    # ── Build the report dictionary ───────────────────────────────────────────
    numerical_stats_df = profile_numerical_columns(df)

    report = {
        "dataset":             filepath,
        "record_count":        len(df),
        "column_count":        len(df.columns),
        "columns":             list(df.columns),
        "nulls_and_duplicates": profile_nulls_and_duplicates(df),
        "numerical_stats":     numerical_stats_df.to_dict(),
        "categorical_stats":   profile_categorical_columns(df),
        "quality_issues":      identify_quality_issues(df),
    }

    # ── Save to JSON ──────────────────────────────────────────────────────────
    os.makedirs("output", exist_ok=True)
    report_path = "output/profile_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        # default=str handles numpy int64/float64 and other non-serialisable types
        json.dump(report, f, indent=2, default=str)

    # ── Console summary ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"DATA QUALITY PROFILE: {filepath}")
    print(f"{'='*60}")
    print(f"Records : {report['record_count']}")
    print(f"Columns : {report['column_count']}  →  {report['columns']}")

    print(f"\n── Null & Duplicate Summary {'─'*32}")
    nd = report["nulls_and_duplicates"]
    for col in df.columns:
        pct = nd["null_percentages"][col]
        cnt = nd["null_counts"][col]
        bar = "⚠" if pct > 30 else " "
        print(f"  {bar} {col:<25} nulls: {cnt:>3}  ({pct:.1f}%)")
    print(f"  Duplicate rows : {nd['exact_duplicate_count']} ({nd['duplicate_percentage']}%)")

    if not numerical_stats_df.empty:
        print(f"\n── Numerical Column Stats {'─'*34}")
        print(numerical_stats_df.to_string())

    cat_profile = report["categorical_stats"]
    if cat_profile:
        print(f"\n── Categorical Column Summary {'─'*30}")
        for col, info in cat_profile.items():
            print(f"  {col}: {info['unique_count']} unique  |  nulls: {info['null_count']}")
            for val, count in list(info["top_values"].items())[:3]:
                print(f"      '{val}': {count}")

    print(f"\n── Quality Issues Found: {len(report['quality_issues'])} {'─'*33}")
    if report["quality_issues"]:
        for issue in report["quality_issues"]:
            print(f"  [{issue['severity']:>6}] {issue['type']} → {issue['column']}")
            print(f"           {issue['value']}")
            print(f"           → {issue['recommendation']}")
    else:
        print("  No issues detected.")

    print(f"\n  ✓ Profile report saved → {report_path}")
    print(f"{'='*60}\n")

    return report


# ============================================================================
# MAIN EXECUTION BLOCK
# ============================================================================
if __name__ == "__main__":
    """
    Entry point for command-line execution.

    Run with:
        python scripts/profile_data.py

    Paths resolve relative to the repository root regardless of invocation dir.
    """
    # ── Resolve repo root ─────────────────────────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root  = os.path.dirname(script_dir)
    os.chdir(repo_root)   # ensure relative output paths (output/) resolve correctly

    TARGET_FILE = os.path.join(repo_root, "data", "raw", "quality_test.csv")

    print("=" * 60)
    print("  CoursePulse — Data Profiling & Quality Assessment")
    print("=" * 60)
    print(f"  Input : {TARGET_FILE}")
    print("=" * 60)

    # ── Load data ─────────────────────────────────────────────────────────────
    if not os.path.exists(TARGET_FILE):
        print(f"[ERROR] File not found: {TARGET_FILE}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(TARGET_FILE)
    print(f"\n  Loaded {len(df)} rows × {len(df.columns)} columns from source file.")

    # ── Generate full quality report ──────────────────────────────────────────
    report = generate_profile_report(df, TARGET_FILE)

    # Exit 1 if HIGH severity issues found (useful for CI/CD gating)
    high_issues = [i for i in report["quality_issues"] if i["severity"] == "HIGH"]
    if high_issues:
        print(f"  ⚠  {len(high_issues)} HIGH severity issue(s) found — review before processing.")
        sys.exit(0)   # exit 0: issues reported but not blocking (report is the output)
