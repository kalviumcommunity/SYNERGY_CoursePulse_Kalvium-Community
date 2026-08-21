"""
scripts/deduplicate_data.py
============================
Duplicate Detection and Deduplication Pipeline for CoursePulse / Kalvium Community.

Purpose:
    Identify and remove exact and near-duplicate records from ingested datasets.
    Every removed record is logged to an audit file so deletions are recoverable
    and compliant with data governance requirements.

Deduplication approach:
    Task 1: Exact duplicate detection — all column values identical
    Task 2: Near-duplicate detection — same key columns, different other fields
    Task 3: Exact duplicate removal with keep strategy (first / last / False)
    Task 4: Near-duplicate removal with most_complete / first / last strategy
    Task 5: Audit log of every removed record → output/removed_duplicates_audit.csv
    Task 6: Before/after comparison → output/dedup_summary.json
    Task 7: End-to-end main workflow

Usage:
    python scripts/deduplicate_data.py

Outputs:
    • Console report
    • output/removed_duplicates_audit.csv — every removed row, for compliance
    • output/dedup_audit_summary.json    — removal metadata
    • output/dedup_summary.json          — before/after row/null counts
    • data/processed/deduplicated_data.csv — final clean dataset
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime


# ============================================================================
# TASK 1 — Detect Exact Duplicates
# ============================================================================
def detect_exact_duplicates(df: pd.DataFrame) -> tuple:
    """
    Find rows where ALL column values are identical to another row.

    An exact duplicate is a row that has been imported twice — either from
    overlapping source files or repeated ETL runs. It inflates every count-based
    metric (customer count, transaction count, revenue sum).

    Input:
        df (pd.DataFrame): Raw DataFrame to audit.

    Output:
        (int, pd.DataFrame):
            exact_count — number of rows that are duplicates (not counting the kept copy).
            dup_rows    — all rows that participate in a duplicate group (incl. originals),
                          sorted so matching rows appear adjacent.

    Assumptions:
        - Comparison uses all columns — even a single field difference = not an exact dup.
        - keep=False in dup_rows shows ALL members of a duplicate group for review.
    """
    # Count rows that would be dropped (the copies, not the originals)
    exact_count = int(df.duplicated().sum())

    # Retrieve every row that participates in at least one exact duplicate group
    dup_rows = df[df.duplicated(keep=False)].sort_values(by=df.columns.tolist())

    print("\nEXACT DUPLICATE DETECTION")
    print("=" * 60)
    print(f"  Exact duplicates found            : {exact_count}")
    print(f"  Rows in duplicate groups (total)  : {len(dup_rows)}")

    if len(dup_rows) > 0:
        print(f"\n  Sample duplicate rows:")
        print(dup_rows.head(10).to_string(index=True))

    return exact_count, dup_rows


# ============================================================================
# TASK 2 — Detect Near-Duplicates Using Key Columns
# ============================================================================
def detect_near_duplicates(df: pd.DataFrame, key_columns: list) -> pd.DataFrame:
    """
    Find rows that share the same business-key values but differ on other fields.

    Near-duplicates arise when the same transaction is imported from multiple
    source systems (e.g., CRM + billing) and one system has a slightly different
    amount or status. The key identifies what SHOULD be unique.

    Input:
        df          (pd.DataFrame): Raw DataFrame to audit.
        key_columns (list):         Columns that together define a unique record
                                    (e.g., ['customer_id', 'transaction_date']).

    Output:
        pd.DataFrame: All rows that share at least one key combination with
                      another row (i.e., key-level near-duplicates).

    Assumptions:
        - Near-duplicate detection runs AFTER exact duplicate removal.
        - Rows where key columns are null are excluded from groupby (pandas default).
    """
    # Filter to rows whose key combination appears more than once
    duplicate_keys = df[df.duplicated(subset=key_columns, keep=False)]

    print("\nNEAR-DUPLICATE DETECTION")
    print("=" * 60)
    print(f"  Records with duplicate key values          : {len(duplicate_keys)}")
    print(f"  Unique key combinations with duplicates    : "
          f"{duplicate_keys.groupby(key_columns).ngroups}")

    # Show up to 3 sample groups so the analyst can see what's conflicting
    if len(duplicate_keys) > 0:
        print(f"\n  Sample groups with duplicate keys:")
        for keys, group in list(duplicate_keys.groupby(key_columns))[:3]:
            print(f"\n    Key: {keys}")
            print(f"    Records in group: {len(group)}")
            print(group.to_string(index=True))

    return duplicate_keys


# ============================================================================
# TASK 3 — Remove Exact Duplicates With Keep Strategy
# ============================================================================
def remove_exact_duplicates(df: pd.DataFrame, keep: str = "first") -> pd.DataFrame:
    """
    Remove rows where all column values are identical, keeping one copy.

    Input:
        df   (pd.DataFrame): DataFrame possibly containing exact duplicates.
        keep (str | False):  Which copy to retain:
                               'first' — keep the earliest-indexed occurrence
                               'last'  — keep the latest-indexed occurrence
                               False   — remove ALL members of any duplicate group

    Output:
        pd.DataFrame: Deduplicated DataFrame with row counts logged.

    Assumptions:
        - Index order reflects ingestion order (i.e., 'first' = earliest import).
        - Using keep=False removes ALL occurrences including the original — use only
          when you have another source to recover the data from.
    """
    rows_before  = len(df)
    df_dedup     = df.drop_duplicates(keep=keep)
    rows_after   = len(df_dedup)
    rows_removed = rows_before - rows_after
    removal_pct  = (rows_removed / rows_before) * 100 if rows_before > 0 else 0

    print("\nEXACT DUPLICATE REMOVAL")
    print("=" * 60)
    print(f"  Keep strategy : {keep}")
    print(f"  Rows before   : {rows_before:,}")
    print(f"  Rows after    : {rows_after:,}")
    print(f"  Rows removed  : {rows_removed:,} ({removal_pct:.2f}%)")

    return df_dedup


# ============================================================================
# TASK 4 — Remove Near-Duplicates With Custom Logic
# ============================================================================
def remove_near_duplicates(
    df: pd.DataFrame,
    key_columns: list,
    keep_strategy: str = "most_complete",
) -> pd.DataFrame:
    """
    Resolve near-duplicate groups by selecting the best representative record.

    Three strategies:
        'most_complete' — keep the row with the fewest null values (most data)
        'last'          — keep the last row by index (most recently ingested)
        'first'         — keep the first row by index (earliest ingested)

    Input:
        df            (pd.DataFrame): DataFrame after exact dedup (near-dups still present).
        key_columns   (list):         Business key defining uniqueness.
        keep_strategy (str):          Which record wins in a near-duplicate group.

    Output:
        pd.DataFrame: Deduplicated DataFrame — one record per unique key combination.

    Assumptions:
        - 'most_complete' uses null count per row as the selection criterion.
        - Ties in null count are broken by index order (first occurrence wins).
    """
    rows_before = len(df)

    if keep_strategy == "most_complete":
        # Score each row by how many nulls it has — lowest score wins
        null_counts = df.isnull().sum(axis=1)
        df_scored   = df.assign(_null_score=null_counts)

        # Within each key group keep the row with the minimum null score
        # (stable sort ensures tie-breaking by original index = first occurrence)
        df_sorted = df_scored.sort_values("_null_score", kind="stable")
        df_dedup  = (
            df_sorted
            .drop_duplicates(subset=key_columns, keep="first")
            .drop(columns=["_null_score"])
        )

    elif keep_strategy == "last":
        df_dedup = df.drop_duplicates(subset=key_columns, keep="last")

    else:   # 'first'
        df_dedup = df.drop_duplicates(subset=key_columns, keep="first")

    rows_after   = len(df_dedup)
    rows_removed = rows_before - rows_after
    removal_pct  = (rows_removed / rows_before) * 100 if rows_before > 0 else 0

    print("\nNEAR-DUPLICATE REMOVAL")
    print("=" * 60)
    print(f"  Keep strategy : {keep_strategy}")
    print(f"  Key columns   : {key_columns}")
    print(f"  Rows before   : {rows_before:,}")
    print(f"  Rows after    : {rows_after:,}")
    print(f"  Rows removed  : {rows_removed:,} ({removal_pct:.2f}%)")

    return df_dedup.reset_index(drop=True)


# ============================================================================
# TASK 5 — Log Removed Records for Audit
# ============================================================================
def log_removed_duplicates(
    df_original: pd.DataFrame,
    df_dedup: pd.DataFrame,
) -> tuple:
    """
    Identify every row removed during deduplication and save to an audit file.

    The audit file allows:
        • Compliance review — prove what was deleted and why
        • Data recovery    — restore records if dedup logic is found to be wrong
        • Root-cause analysis — trace duplicates back to their source system

    Input:
        df_original (pd.DataFrame): Raw DataFrame before ANY deduplication.
        df_dedup    (pd.DataFrame): Final deduplicated DataFrame.

    Output:
        (pd.DataFrame, dict):
            removed_records — DataFrame of all rows that were removed.
            audit_summary   — metadata dict also written to dedup_audit_summary.json.

    Assumptions:
        - Matching is done by original index — requires df_original index to be intact
          (i.e., not reset between load and this call).
        - df_dedup index may have been reset; the method reconstructs removed rows
          from the set difference of original values.
    """
    os.makedirs("output", exist_ok=True)

    # Reconstruct removed rows by merging on all columns and flagging non-matches
    # Using a left join + indicator to identify rows present in original but not dedup
    indicator_col = "_merge_indicator"
    merged = df_original.merge(
        df_dedup,
        how="left",
        on=list(df_original.columns),
        indicator=indicator_col,
    )
    removed_records = (
        merged[merged[indicator_col] == "left_only"]
        .drop(columns=[indicator_col])
        .reset_index(drop=True)
    )

    print("\nAUDIT LOGGING")
    print("=" * 60)
    print(f"  Total records removed : {len(removed_records)}")

    # Save the full removed-records table for forensic/recovery purposes
    audit_csv = "output/removed_duplicates_audit.csv"
    removed_records.to_csv(audit_csv, index=False)
    print(f"  ✓ Removed records saved → {audit_csv}")

    # Build concise audit metadata
    audit_summary = {
        "removal_timestamp": datetime.now().isoformat(),
        "total_removed":     int(len(removed_records)),
        "reason":            "Duplicate detection and deduplication",
        "audit_file":        audit_csv,
        "audit_note":        (
            "All removed records logged for compliance and recovery if needed. "
            "Do not delete this file without data governance approval."
        ),
    }

    audit_json = "output/dedup_audit_summary.json"
    with open(audit_json, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2, default=str)
    print(f"  ✓ Audit summary saved  → {audit_json}")
    print("=" * 60)

    return removed_records, audit_summary


# ============================================================================
# TASK 6 — Compare Before and After Metrics
# ============================================================================
def compare_before_after(df_original: pd.DataFrame, df_dedup: pd.DataFrame) -> dict:
    """
    Log before/after row counts and null totals confirming deduplication effect.

    Input:
        df_original (pd.DataFrame): Raw DataFrame before deduplication.
        df_dedup    (pd.DataFrame): Final DataFrame after all dedup steps.

    Output:
        dict: Comparison metrics — also written to output/dedup_summary.json.
    """
    rows_before    = len(df_original)
    rows_after     = len(df_dedup)
    rows_removed   = rows_before - rows_after
    removal_pct    = round((rows_removed / rows_before) * 100, 2) if rows_before > 0 else 0
    nulls_before   = int(df_original.isnull().sum().sum())
    nulls_after    = int(df_dedup.isnull().sum().sum())

    comparison = {
        "rows_before":        rows_before,
        "rows_after":         rows_after,
        "rows_removed":       rows_removed,
        "removal_percentage": removal_pct,
        "columns":            len(df_original.columns),
        "nulls_before":       nulls_before,
        "nulls_after":        nulls_after,
        "null_change":        nulls_before - nulls_after,
        "timestamp":          datetime.now().isoformat(),
    }

    print("\n" + "=" * 70)
    print("DEDUPLICATION FINAL SUMMARY")
    print("=" * 70)
    print(f"  Rows before  : {rows_before:,}")
    print(f"  Rows after   : {rows_after:,}")
    print(f"  Removed      : {rows_removed:,} ({removal_pct}%)")
    print(f"\n  Nulls before : {nulls_before:,}")
    print(f"  Nulls after  : {nulls_after:,}")
    print(f"  Null change  : {nulls_before - nulls_after:,}")
    print("=" * 70)

    os.makedirs("output", exist_ok=True)
    with open("output/dedup_summary.json", "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print("  ✓ Summary saved → output/dedup_summary.json")

    return comparison


# ============================================================================
# TASK 7 — End-to-End Main Workflow
# ============================================================================
if __name__ == "__main__":
    """
    End-to-end duplicate detection and deduplication pipeline.

    Run with:
        python scripts/deduplicate_data.py
    """
    # ── Path resolution ───────────────────────────────────────────────────────
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_PATH  = os.path.join(repo_root, "data", "raw",       "data_with_dupes.csv")
    OUTPUT_PATH = os.path.join(repo_root, "data", "processed", "deduplicated_data.csv")

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] Input file not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    # ── Load raw data — preserve original for audit comparison ────────────────
    df_original = pd.read_csv(INPUT_PATH)
    df          = df_original.copy()

    print("\n" + "=" * 70)
    print("STARTING DEDUPLICATION WORKFLOW")
    print("=" * 70)
    print(f"  Input file           : {INPUT_PATH}")
    print(f"  Initial record count : {len(df):,}")
    print(f"  Columns              : {list(df.columns)}")
    print("=" * 70)

    # ── Step 1: Detect exact duplicates ───────────────────────────────────────
    print("\n[Step 1/4] Detecting exact duplicates ...")
    exact_count, exact_rows = detect_exact_duplicates(df)

    # ── Step 2: Detect near-duplicates by business key ────────────────────────
    print("\n[Step 2/4] Detecting near-duplicates by key columns ...")
    near_dups = detect_near_duplicates(df, key_columns=["customer_id", "transaction_date"])

    # ── Step 3: Remove exact duplicates (keep first occurrence) ───────────────
    print("\n[Step 3/4] Removing exact duplicates (keep='first') ...")
    df = remove_exact_duplicates(df, keep="first")

    # ── Step 4: Remove near-duplicates (keep most complete record) ────────────
    print("\n[Step 4/4] Removing near-duplicates (keep_strategy='most_complete') ...")
    df = remove_near_duplicates(
        df,
        key_columns=["customer_id", "transaction_date"],
        keep_strategy="most_complete",
    )

    # ── Audit: log every removed record ──────────────────────────────────────
    print("\n[Audit] Logging removed records for compliance ...")
    removed_records, audit_summary = log_removed_duplicates(df_original, df)

    # ── Validation: before/after comparison ──────────────────────────────────
    compare_before_after(df_original, df)

    # ── Save deduplicated dataset ──────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\n  ✓ Deduplicated data saved → {OUTPUT_PATH}")
    print(f"  ✓ Final shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"  ✓ Remaining nulls: {df.isnull().sum().sum()}")
    print("\n" + "=" * 70)
    print("  Deduplication pipeline complete.")
    print("=" * 70)
