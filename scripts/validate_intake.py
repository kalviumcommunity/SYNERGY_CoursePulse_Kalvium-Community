"""
scripts/validate_intake.py
===========================
Dataset Intake Validation Pipeline for CoursePulse / Kalvium Community Platform.

Purpose:
    Evaluate incoming data files for quality and readiness BEFORE they enter the
    processing pipeline. Acts as a quality firewall — any file that fails
    validation is blocked from downstream analysis.

Validation checks performed:
    Task 1: File existence and non-emptiness + supported format check
    Task 2: Column schema validation (missing / extra columns)
    Task 3: File encoding detection via chardet
    Task 4: Dataset dimensions (row count, column count, file size)
    Task 5: Consolidated JSON intake report saved to output/intake_report.json

Usage:
    python scripts/validate_intake.py

Output:
    • Console report printed to stdout
    • output/intake_report.json — structured validation report
"""

import os
import sys
import json
import pandas as pd
import chardet
from datetime import datetime


# ── Expected schema for data/raw/sample.csv ──────────────────────────────────
# Update this list whenever the upstream data contract changes.
EXPECTED_COLUMNS = [
    "customer_id",
    "customer_name",
    "transaction_amount",
    "transaction_date",
]


# ============================================================================
# TASK 1 — File Existence, Non-Emptiness, and Format
# ============================================================================
def validate_file_exists(filepath: str) -> tuple[bool, str]:
    """
    Check that the file exists on disk and contains at least some bytes.

    Input:
        filepath (str): Path to the file being validated.

    Output:
        (bool, str): (True, success_message) if valid,
                     (False, failure_message) if not.

    Assumptions:
        - An empty file (0 bytes) is treated as an error because it cannot
          be parsed into a DataFrame with any meaningful content.
    """
    # Guard: path must resolve to a real file
    if not os.path.exists(filepath):
        return False, f"File does not exist: {filepath}"

    # Guard: reject zero-byte files — they pass os.path.exists but cannot be parsed
    if os.path.getsize(filepath) == 0:
        return False, f"File is empty (0 bytes): {filepath}"

    return True, "File exists and has content"


def validate_file_format(filepath: str, allowed_formats: list = None) -> tuple[bool, str]:
    """
    Check that the file extension is in the set of supported formats.

    Input:
        filepath        (str):  Path to the file being validated.
        allowed_formats (list): Accepted extensions (default: csv, json, xlsx).

    Output:
        (bool, str): (True, success_message) if extension is allowed,
                     (False, failure_message) otherwise.

    Assumptions:
        - Extension comparison is case-insensitive.
        - Files without an extension (no '.') are treated as unsupported.
    """
    if allowed_formats is None:
        allowed_formats = ["csv", "json", "xlsx"]

    # Extract the extension from the last '.' in the filename
    extension = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""

    if extension not in allowed_formats:
        return False, (
            f"Unsupported format: '.{extension}'. "
            f"Allowed formats: {allowed_formats}"
        )

    return True, f"Format valid: {extension}"


# ============================================================================
# TASK 2 — Column Schema Validation
# ============================================================================
def validate_schema(df: pd.DataFrame, expected_columns: list) -> tuple[bool, str]:
    """
    Compare the DataFrame's columns against an expected schema contract.

    Both missing and extra columns are reported so the caller knows exactly
    how the incoming data diverges from the contract.

    Input:
        df               (pd.DataFrame): Loaded DataFrame to validate.
        expected_columns (list):         Ordered list of required column names.

    Output:
        (bool, str): (True, success_message) if schema matches exactly,
                     (False, combined_issue_message) if columns are missing or extra.

    Assumptions:
        - Column name matching is case-sensitive (follow the data contract exactly).
        - Extra columns are reported as warnings, not hard failures, but the
          function still returns False when they are present to flag the deviation.
    """
    actual_columns = set(df.columns)
    expected_set   = set(expected_columns)

    # Columns the contract requires but the file does not provide
    missing = expected_set - actual_columns

    # Columns the file provides that are not in the contract (potential PII leak, etc.)
    extra   = actual_columns - expected_set

    issues = []
    if missing:
        # Sort for deterministic output across Python versions
        issues.append(f"Missing columns: {sorted(missing)}")
    if extra:
        issues.append(f"Unexpected columns: {sorted(extra)}")

    if not issues:
        return True, f"Schema valid: {len(df.columns)} columns present"

    return False, " | ".join(issues)


# ============================================================================
# TASK 3 — File Encoding Detection
# ============================================================================
def detect_encoding(filepath: str) -> tuple[str, str]:
    """
    Detect the character encoding of a file using the chardet library.

    Reads up to the first 10,000 bytes (sufficient for encoding sniffing)
    to avoid loading large files entirely into memory.

    Input:
        filepath (str): Path to the file whose encoding should be detected.

    Output:
        (encoding, message):
            encoding (str): Detected encoding name (e.g., 'utf-8', 'ISO-8859-1').
            message  (str): Human-readable detection result including confidence.

    Assumptions:
        - If chardet cannot determine encoding, 'utf-8' is used as a safe default.
        - Confidence below 70% is flagged as low-confidence in the message.
    """
    # Read a sample of the file in binary mode for encoding sniffing
    with open(filepath, "rb") as f:
        raw_sample = f.read(10_000)   # 10 KB is sufficient for chardet heuristics

    result     = chardet.detect(raw_sample)
    encoding   = result.get("encoding") or "utf-8"       # fallback if None
    confidence = result.get("confidence") or 0.0

    # Flag low-confidence detections so the engineer knows to verify manually
    confidence_note = " ⚠ LOW CONFIDENCE" if confidence < 0.70 else ""
    message = f"Detected: {encoding} (confidence: {confidence:.1%}){confidence_note}"

    return encoding, message


# ============================================================================
# TASK 4 — Row Count and File Size Capture
# ============================================================================
def capture_dataset_stats(filepath: str, df: pd.DataFrame) -> dict:
    """
    Log baseline dataset dimensions and file size metrics.

    These metrics become the reference point for detecting data drift — if
    next week's file has dramatically fewer rows, the pipeline can alert.

    Input:
        filepath (str):          Path to the source file (for size measurement).
        df       (pd.DataFrame): Loaded DataFrame (for row/column count).

    Output:
        dict with keys:
            rows         (int):   Number of data rows (header excluded).
            columns      (int):   Number of columns.
            file_size_mb (float): File size rounded to 4 decimal places (MB).
            bytes        (int):   Raw file size in bytes.

    Assumptions:
        - File size is measured on the raw file, not the in-memory DataFrame.
        - MB is calculated as bytes / 1,048,576 (binary, not SI).
    """
    file_bytes   = os.path.getsize(filepath)
    file_size_mb = round(file_bytes / (1024 * 1024), 4)   # MiB

    return {
        "rows":         len(df),
        "columns":      len(df.columns),
        "file_size_mb": file_size_mb,
        "bytes":        file_bytes,
    }


# ============================================================================
# TASK 5 — Generate and Save Intake Validation Report
# ============================================================================
def generate_intake_report(filepath: str, expected_columns: list) -> dict:
    """
    Run all validation checks and consolidate results into a structured report.

    The report is saved as output/intake_report.json so it can be:
        • Audited by a data engineer after each ingestion run
        • Committed to git to track data quality over time
        • Consumed by CI/CD systems to gate pipeline execution

    Input:
        filepath         (str):  Path to the raw data file to validate.
        expected_columns (list): Required column names (the data contract).

    Output:
        dict: Complete validation report with timestamps, results, and statistics.
              Also written to output/intake_report.json as a side effect.

    Validation short-circuits:
        If the file does not exist, remaining checks are skipped (nothing to load).
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "filepath":  filepath,
        "validations": {},
        "statistics": {},
        "overall_status": "UNKNOWN",
    }

    # Keep track of any failed checks so we can set overall status at the end
    all_passed = True

    # ── Check 1: File existence ───────────────────────────────────────────────
    file_exists, msg = validate_file_exists(filepath)
    report["validations"]["file_exists"] = {
        "status": "PASS" if file_exists else "FAIL",
        "message": msg,
    }
    print(f"  [{'PASS' if file_exists else 'FAIL'}] File exists     : {msg}")

    if not file_exists:
        # Cannot proceed without a file — short-circuit here
        report["overall_status"] = "FAIL"
        _save_report(report)
        return report

    # ── Check 2: File format ──────────────────────────────────────────────────
    format_valid, msg = validate_file_format(filepath)
    report["validations"]["format"] = {
        "status": "PASS" if format_valid else "FAIL",
        "message": msg,
    }
    print(f"  [{'PASS' if format_valid else 'FAIL'}] File format     : {msg}")
    all_passed = all_passed and format_valid

    # ── Load DataFrame for schema and stats checks ────────────────────────────
    # Only CSV is handled here; extend with json/xlsx branches as needed.
    df = pd.read_csv(filepath, encoding="utf-8")

    # ── Check 3: Schema validation ────────────────────────────────────────────
    schema_valid, msg = validate_schema(df, expected_columns)
    report["validations"]["schema"] = {
        "status": "PASS" if schema_valid else "FAIL",
        "message": msg,
    }
    print(f"  [{'PASS' if schema_valid else 'FAIL'}] Schema          : {msg}")
    all_passed = all_passed and schema_valid

    # ── Check 4: Encoding detection ───────────────────────────────────────────
    encoding, msg = detect_encoding(filepath)
    report["validations"]["encoding"] = {
        "status": "PASS",          # detection always succeeds; result is informational
        "message": msg,
        "detected_encoding": encoding,
    }
    print(f"  [INFO] Encoding         : {msg}")

    # ── Check 5: Dataset statistics ───────────────────────────────────────────
    stats = capture_dataset_stats(filepath, df)
    report["statistics"] = stats
    print(f"  [INFO] Rows             : {stats['rows']}")
    print(f"  [INFO] Columns          : {stats['columns']}")
    print(f"  [INFO] File size        : {stats['file_size_mb']} MB ({stats['bytes']} bytes)")

    # ── Set overall status ─────────────────────────────────────────────────────
    report["overall_status"] = "PASS" if all_passed else "FAIL"

    # ── Persist the report to disk ────────────────────────────────────────────
    _save_report(report)

    return report


def _save_report(report: dict) -> None:
    """
    Write the validation report to output/intake_report.json.

    Creates the output/ directory if it does not already exist.

    Input:
        report (dict): The fully assembled validation report dictionary.

    Output:
        None — writes file to disk as a side effect.
    """
    os.makedirs("output", exist_ok=True)
    report_path = "output/intake_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        # default=str handles datetime objects and other non-serialisable types
        json.dump(report, f, indent=2, default=str)

    print(f"\n  ✓ Intake report saved → {report_path}")


# ============================================================================
# MAIN EXECUTION BLOCK
# ============================================================================
if __name__ == "__main__":
    """
    Entry point for command-line execution.

    Run with:
        python scripts/validate_intake.py

    Paths are resolved relative to the repository root so the script works
    regardless of whether it is invoked from the repo root or scripts/ dir.
    """
    # ── Resolve paths relative to repo root ───────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root  = os.path.dirname(script_dir)

    TARGET_FILE      = os.path.join(repo_root, "data", "raw", "sample.csv")
    SCHEMA_CONTRACT  = EXPECTED_COLUMNS

    print("=" * 60)
    print("  CoursePulse — Dataset Intake Validation")
    print("=" * 60)
    print(f"  Target file      : {TARGET_FILE}")
    print(f"  Expected columns : {SCHEMA_CONTRACT}")
    print("=" * 60)
    print()

    # Change working directory to repo root so relative output paths resolve
    os.chdir(repo_root)

    report = generate_intake_report(TARGET_FILE, SCHEMA_CONTRACT)

    # ── Final summary ─────────────────────────────────────────────────────────
    status = report["overall_status"]
    print()
    print("=" * 60)
    print(f"  OVERALL STATUS : {status}")
    print("=" * 60)

    # Exit with non-zero code on failure so CI/CD pipelines can gate on this
    if status == "FAIL":
        sys.exit(1)
