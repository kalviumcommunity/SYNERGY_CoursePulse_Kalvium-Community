"""
scripts/validate_rules.py
==========================
Data Validation & Rule Enforcement Pipeline for CoursePulse / Kalvium Community.

Purpose:
    Enforce multi-layer data validation rules before downstream analysis:
    - Task 1: Range checks (age, price, birth_date bounds)
    - Task 2: Null constraints (customer_id, email presence)
    - Task 3: Format pattern validation (email regex, 10-digit phone regex)
    - Task 4: Business rule validation (end_date >= start_date)
    - Task 5: Structured validation report & failure isolation

Usage:
    python scripts/validate_rules.py

Outputs:
    • Console: full validation breakdown per rule
    • output/validation_failures.csv     — isolated invalid records for review
    • output/validation_summary.json      — machine-readable pass/fail metrics
    • data/processed/validated_clean_data.csv — clean dataset passing all checks
"""

import os
import sys
import json
import pandas as pd
import numpy as np


# ============================================================================
# TASK 1 — Range Checks
# ============================================================================
def validate_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate numerical and date bounds.

    Rules:
        - valid_age   : 0 <= age <= 150 (biological human range)
        - valid_price : price >= 0 (no negative pricing allowed)
        - valid_date  : 1920-01-01 <= birth_date <= current_timestamp (no future birth dates)

    Returns:
        pd.DataFrame with boolean check columns added.
    """
    df = df.copy()

    # Age range check
    df['valid_age'] = (df['age'] >= 0) & (df['age'] <= 150)

    # Price non-negativity check
    df['valid_price'] = df['price'] >= 0

    # Birth date range check
    # Ensure birth_date is parsed to datetime for accurate comparison
    birth_dt = pd.to_datetime(df['birth_date'], errors='coerce')
    now = pd.Timestamp.now()
    min_date = pd.Timestamp('1920-01-01')
    df['valid_date'] = birth_dt.notna() & (birth_dt >= min_date) & (birth_dt <= now)

    print("\n" + "=" * 65)
    print("TASK 1 — Range Checks")
    print("=" * 65)
    print(f"  Invalid ages (<0 or >150)           : {(~df['valid_age']).sum()}")
    print(f"  Invalid prices (<0)                 : {(~df['valid_price']).sum()}")
    print(f"  Invalid birth dates (<1920 or >now) : {(~df['valid_date']).sum()}")

    return df


# ============================================================================
# TASK 2 — Null Constraints
# ============================================================================
def validate_null_constraints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure mandatory identifier and contact columns are non-null.

    Rules:
        - valid_customer_id : customer_id is not null/empty
        - valid_email       : email is not null/empty

    Returns:
        pd.DataFrame with boolean check columns added.
    """
    df = df.copy()

    df['valid_customer_id'] = df['customer_id'].notna() & (df['customer_id'].astype(str).str.strip() != '')
    df['valid_email'] = df['email'].notna() & (df['email'].astype(str).str.strip() != '')

    print("\n" + "=" * 65)
    print("TASK 2 — Null Constraints")
    print("=" * 65)
    print(f"  Missing customer IDs : {(~df['valid_customer_id']).sum()}")
    print(f"  Missing emails       : {(~df['valid_email']).sum()}")

    return df


# ============================================================================
# TASK 3 — Format Pattern Validation
# ============================================================================
def validate_format_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate string formats using regex patterns.

    Rules:
        - valid_email_format : contains '@' and basic email structure
        - valid_phone        : exactly 10 digits (e.g. ^\\d{10}$)

    Returns:
        pd.DataFrame with boolean check columns added.
    """
    df = df.copy()

    # Email format check (contains '@' and non-empty)
    df['valid_email_format'] = df['email'].astype(str).str.contains('@', na=False) & df['valid_email']

    # Phone number format check (10 digits exactly)
    phone_clean = df['phone'].astype(str).str.strip()
    df['valid_phone'] = phone_clean.str.match(r'^\d{10}$', na=False)

    print("\n" + "=" * 65)
    print("TASK 3 — Format Pattern Validation")
    print("=" * 65)
    print(f"  Invalid emails (missing '@' or empty) : {(~df['valid_email_format']).sum()}")
    print(f"  Invalid phone numbers (not 10 digits) : {(~df['valid_phone']).sum()}")

    return df


# ============================================================================
# TASK 4 — Business Rule Validation
# ============================================================================
def validate_business_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate domain-specific multi-column relationships.

    Rules:
        - valid_date_order : end_date >= start_date (campaign/event cannot end before starting)

    Returns:
        pd.DataFrame with boolean check columns added.
    """
    df = df.copy()

    start_dt = pd.to_datetime(df['start_date'], errors='coerce')
    end_dt = pd.to_datetime(df['end_date'], errors='coerce')

    df['valid_date_order'] = start_dt.notna() & end_dt.notna() & (end_dt >= start_dt)

    print("\n" + "=" * 65)
    print("TASK 4 — Business Rule Validation")
    print("=" * 65)
    print(f"  Invalid date ranges (end_date < start_date) : {(~df['valid_date_order']).sum()}")

    return df


# ============================================================================
# TASK 5 — Validation Report & Failure Isolation
# ============================================================================
def generate_validation_report(df: pd.DataFrame) -> tuple:
    """
    Combine all validation checks, isolate failed records, and export reports.

    Returns:
        (df_clean, failures, summary_dict)
    """
    validation_cols = [
        'valid_age',
        'valid_price',
        'valid_date',
        'valid_customer_id',
        'valid_email',
        'valid_email_format',
        'valid_phone',
        'valid_date_order',
    ]

    df = df.copy()
    df['passes_all_checks'] = df[validation_cols].all(axis=1)

    # Isolate failures
    failures = df[~df['passes_all_checks']].copy()
    df_clean = df[df['passes_all_checks']].copy()

    # Rule failure breakdown
    rule_breakdown = {}
    for col in validation_cols:
        invalid_count = int((~df[col]).sum())
        rule_breakdown[col] = {
            "invalid_count": invalid_count,
            "pass_rate_pct": round(((len(df) - invalid_count) / len(df)) * 100, 2) if len(df) > 0 else 0
        }

    summary = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "total_records": len(df),
        "passed_records": int(df['passes_all_checks'].sum()),
        "failed_records": int((~df['passes_all_checks']).sum()),
        "overall_pass_rate_pct": round((df['passes_all_checks'].sum() / len(df)) * 100, 2) if len(df) > 0 else 0,
        "rules_evaluated": len(validation_cols),
        "rule_breakdown": rule_breakdown
    }

    # Save outputs
    os.makedirs('output', exist_ok=True)
    failures.to_csv('output/validation_failures.csv', index=False)

    with open('output/validation_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 65)
    print("TASK 5 — Validation Summary Report")
    print("=" * 65)
    print(f"  Total Records Evaluated : {summary['total_records']}")
    print(f"  Passed All Checks       : {summary['passed_records']} ({summary['overall_pass_rate_pct']}%)")
    print(f"  Failed >=1 Check        : {summary['failed_records']}")
    print(f"\n  Breakdown by Rule:")
    for rule, info in rule_breakdown.items():
        status = "✓ PASS" if info['invalid_count'] == 0 else f"✗ FAIL ({info['invalid_count']} records)"
        print(f"    - {rule:<22} : {status}")

    print(f"\n  ✓ Isolated failures saved → output/validation_failures.csv")
    print(f"  ✓ Summary report saved   → output/validation_summary.json")

    return df_clean, failures, summary


# ============================================================================
# MAIN PIPELINE
# ============================================================================
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_PATH = os.path.join(repo_root, "data", "raw", "raw_validation_data.csv")
    OUTPUT_CLEAN_PATH = os.path.join(repo_root, "data", "processed", "validated_clean_data.csv")

    print("=" * 65)
    print("  CoursePulse — Data Validation & Rule Enforcement Pipeline")
    print("=" * 65)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_CLEAN_PATH}")

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] File not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    df_raw = pd.read_csv(INPUT_PATH)
    print(f"\n  Loaded {len(df_raw)} records × {len(df_raw.columns)} columns")

    # Step 1: Range Checks
    df = validate_ranges(df_raw)

    # Step 2: Null Constraints
    df = validate_null_constraints(df)

    # Step 3: Format Pattern Validation
    df = validate_format_patterns(df)

    # Step 4: Business Rule Validation
    df = validate_business_rules(df)

    # Step 5: Report & Failure Isolation
    df_clean, failures, summary = generate_validation_report(df)

    # Save cleaned dataset
    os.makedirs(os.path.dirname(OUTPUT_CLEAN_PATH), exist_ok=True)
    df_clean.to_csv(OUTPUT_CLEAN_PATH, index=False)
    print(f"\n  ✓ Clean validated dataset saved → {OUTPUT_CLEAN_PATH}")
    print(f"  ✓ Clean shape: {len(df_clean)} rows × {len(df_clean.columns)} columns")
    print("=" * 65)
    print("  Validation pipeline complete.")
    print("=" * 65)
