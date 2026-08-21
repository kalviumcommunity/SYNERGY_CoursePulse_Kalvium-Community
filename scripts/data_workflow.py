"""
scripts/data_workflow.py
========================
Production-ready data pipeline for the CoursePulse / Kalvium Community Platform.

This script replaces notebook-based exploration with a modular, command-line-
executable workflow that separates three distinct concerns:

    1. INGEST  — Load raw data from disk into a Pandas DataFrame.
    2. PROCESS — Clean, transform, and enrich the raw data.
    3. OUTPUT  — Persist analysis-ready results and print execution summary.

Usage:
    python scripts/data_workflow.py

The script reads from data/raw/course_pulse_events.csv (the canonical raw event
log) and writes enriched, deduplicated results to output/processed.csv.
"""

import os
import sys
import pandas as pd


# ============================================================================
# FUNCTION 1 — INGEST
# ============================================================================
def ingest_data(filepath: str) -> pd.DataFrame:
    """
    Load raw data from a CSV file and return a Pandas DataFrame.

    Input:
        filepath (str): Relative or absolute path to the source CSV file.
                        Expected delimiter: comma (,).
                        Expected encoding: UTF-8.

    Output:
        pd.DataFrame: Raw data exactly as stored on disk.
                      No transformations are applied here.

    Assumptions / Constraints:
        - File must exist and be readable; a clear FileNotFoundError is raised
          if it does not.
        - The CSV must have a header row as its first line.
        - Empty files raise a descriptive RuntimeError instead of silently
          returning an empty DataFrame.

    Raises:
        FileNotFoundError: If the file path does not exist.
        RuntimeError:      If the file contains no data rows.
    """
    # Guard: verify the file exists before attempting to read
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"[INGEST] Source file not found: '{filepath}'\n"
            f"  → Make sure the file exists at the expected location."
        )

    # Read the CSV with explicit parameters to avoid silent surprises
    df = pd.read_csv(
        filepath,
        delimiter=",",      # explicit delimiter — never rely on sniffing
        encoding="utf-8",   # explicit encoding — avoids latin-1 corruption
    )

    # Guard: reject empty files immediately with a meaningful message
    if df.empty:
        raise RuntimeError(
            f"[INGEST] File loaded but contains zero rows: '{filepath}'"
        )

    # Audit log — confirms what was loaded before any transformations
    print(f"[INGEST] ✓ Loaded '{filepath}'")
    print(f"         Rows: {df.shape[0]}  |  Columns: {df.shape[1]}")
    print(f"         Columns: {list(df.columns)}")

    return df


# ============================================================================
# FUNCTION 2 — PROCESS
# ============================================================================
def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw CoursePulse event data into an analysis-ready format.

    This function applies a sequence of deterministic transformations. Each
    step is documented inline so future maintainers understand the intent
    without needing to read external notebooks.

    Input:
        df (pd.DataFrame): Raw DataFrame returned by ingest_data().
                           Expected columns (from course_pulse_events.csv):
                             event_id, user_id, event_timestamp, event_type,
                             course_id, course_name, category, search_query

    Output:
        pd.DataFrame: Cleaned and enriched DataFrame with:
                        - Duplicates removed
                        - Null values handled
                        - event_timestamp parsed to datetime
                        - Derived features: hour_of_day, day_of_week, is_enrollment

    Assumptions / Constraints:
        - event_timestamp strings follow the format '%Y-%m-%d %H:%M:%S'.
        - event_type column exists; 'enrollment' events are flagged.
        - Rows with a missing event_id are considered corrupt and dropped.
    """
    print(f"\n[PROCESS] Starting transformations on {len(df)} rows ...")
    rows_before = len(df)

    # ── Step 1: Remove exact duplicate rows ──────────────────────────────────
    # Duplicates can arise from repeated ETL runs or double-logging in the app.
    df = df.drop_duplicates()
    dropped_dupes = rows_before - len(df)
    print(f"[PROCESS] Step 1 — Removed {dropped_dupes} duplicate row(s). "
          f"Remaining: {len(df)}")

    # ── Step 2: Drop rows with a missing event_id (corrupt records) ───────────
    # event_id is the primary key; any row without it cannot be reliably used.
    before = len(df)
    df = df.dropna(subset=["event_id"])
    print(f"[PROCESS] Step 2 — Dropped {before - len(df)} row(s) with null event_id.")

    # ── Step 3: Fill missing string columns with a sentinel placeholder ───────
    # Keeps downstream groupby/pivot operations stable (NaN breaks string ops).
    # Use include=["object", "string"] for compatibility with both pandas 2 and 3
    string_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    for col in string_cols:
        # Only fill columns that actually have nulls to avoid unnecessary writes
        if df[col].isnull().any():
            df[col] = df[col].fillna("N/A")
            print(f"[PROCESS] Step 3 — Filled nulls in '{col}' with 'N/A'.")

    # ── Step 4: Parse event_timestamp from string to datetime ─────────────────
    # Explicit format prevents silent date corruption on ambiguous values.
    if "event_timestamp" in df.columns:
        df["event_timestamp"] = pd.to_datetime(
            df["event_timestamp"],
            format="%Y-%m-%d %H:%M:%S",   # format must match source string exactly
        )
        print(f"[PROCESS] Step 4 — Parsed 'event_timestamp' → datetime64.")

    # ── Step 5: Extract temporal features for downstream analysis ─────────────
    # These features enable hourly/daily segmentation without re-parsing later.
    if "event_timestamp" in df.columns and pd.api.types.is_datetime64_any_dtype(df["event_timestamp"]):
        df["hour_of_day"] = df["event_timestamp"].dt.hour          # integer 0–23
        df["day_of_week"] = df["event_timestamp"].dt.day_name()    # e.g., 'Monday'
        print("[PROCESS] Step 5 — Extracted 'hour_of_day' and 'day_of_week'.")

    # ── Step 6: Flag enrollment events for churn analysis ────────────────────
    # is_enrollment = 1 means the user committed to a course (high-value signal).
    if "event_type" in df.columns:
        df["is_enrollment"] = (df["event_type"] == "enrollment").astype(int)
        enrollment_count = df["is_enrollment"].sum()
        print(f"[PROCESS] Step 6 — Flagged {enrollment_count} enrollment event(s) "
              f"('is_enrollment' column added).")

    # ── Step 7: Reset index after all row-dropping operations ────────────────
    # Ensures the output index is 0-based and contiguous — avoids confusion in
    # downstream code that relies on positional indexing.
    df = df.reset_index(drop=True)

    print(f"[PROCESS] ✓ Transformations complete. "
          f"Final shape: {df.shape[0]} rows × {df.shape[1]} columns.")
    return df


# ============================================================================
# FUNCTION 3 — OUTPUT
# ============================================================================
def output_results(df: pd.DataFrame, output_path: str) -> None:
    """
    Persist the processed DataFrame to disk and print an execution summary.

    Input:
        df          (pd.DataFrame): Analysis-ready DataFrame from process_data().
        output_path (str):          Destination file path for the CSV output.
                                    Parent directory is created if it does not exist.

    Output:
        None — side effects only:
            • CSV written to output_path (index column excluded).
            • Execution summary printed to stdout.

    Assumptions / Constraints:
        - If output_path already exists it will be overwritten.
        - Parent directories in output_path are created automatically.
    """
    # Create the output directory if it does not already exist
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Write the processed DataFrame to CSV without the pandas integer index
    df.to_csv(output_path, index=False)

    # ── Execution summary printed to stdout ───────────────────────────────────
    # This output is captured by the caller and saved as output/sample_run.txt
    print("\n" + "=" * 55)
    print("  PIPELINE EXECUTION SUMMARY")
    print("=" * 55)
    print(f"  ✓ Data successfully processed")
    print(f"  ✓ Rows processed    : {len(df)}")
    print(f"  ✓ Columns output    : {df.shape[1]}")
    print(f"  ✓ Output saved to   : {output_path}")
    if "event_type" in df.columns:
        # Show a quick event-type breakdown for quick sanity-check
        counts = df["event_type"].value_counts()
        print(f"\n  Event-Type Breakdown:")
        for event, count in counts.items():
            print(f"    {event:<12}: {count}")
    if "is_enrollment" in df.columns:
        print(f"\n  Enrollment events   : {df['is_enrollment'].sum()}")
    print("=" * 55)
    print("  ✓ Pipeline complete — no errors.")
    print("=" * 55)


# ============================================================================
# MAIN EXECUTION BLOCK
# ============================================================================
if __name__ == "__main__":
    """
    Entry point for command-line execution.

    Run with:
        python scripts/data_workflow.py

    Paths are resolved relative to the repository root.  If the script is
    invoked from inside the scripts/ directory, the paths are adjusted
    automatically so the script always works from either location.
    """
    # ── Resolve paths relative to repo root regardless of CWD ────────────────
    # This allows both:  `python scripts/data_workflow.py`  (from repo root)
    #              and:  `cd scripts && python data_workflow.py`
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root  = os.path.dirname(script_dir)   # scripts/../ == repo root

    INPUT_PATH  = os.path.join(repo_root, "data", "raw", "course_pulse_events.csv")
    OUTPUT_PATH = os.path.join(repo_root, "output", "processed.csv")

    print("=" * 55)
    print("  CoursePulse — Data Workflow Pipeline")
    print("=" * 55)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_PATH}")
    print("=" * 55)

    try:
        # Stage 1: Ingest raw data
        raw_df = ingest_data(INPUT_PATH)

        # Stage 2: Apply transformations
        processed_df = process_data(raw_df)

        # Stage 3: Write results and print summary
        output_results(processed_df, OUTPUT_PATH)

    except (FileNotFoundError, RuntimeError) as exc:
        # Surface a clean, actionable error message instead of a traceback
        print(f"\n[ERROR] Pipeline failed:\n  {exc}", file=sys.stderr)
        sys.exit(1)
