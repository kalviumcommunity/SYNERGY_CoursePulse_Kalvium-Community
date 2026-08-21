"""
scripts/string_cleaning_pipeline.py
=====================================
Reusable String Cleaning Pipeline for CoursePulse / Kalvium Community Platform.

Purpose:
    Standardize all text fields arriving from multiple source systems so they
    are consistent, analysis-ready, and safe for downstream joins and ML models.

Problems solved:
    - Extra whitespace:   " Electronics " → "Electronics"
    - Mixed casing:       "ELECTRONICS", "electronics" → "electronics"
    - Special characters: "São Paulo" → "Sao Paulo" (encoding-safe)
    - Label variations:   "b2b", "B 2 B", "b2 b" → "B2B"

Tasks:
    Task 1: Strip whitespace from all string columns
    Task 2: Normalize casing to lowercase for categorical columns
    Task 3: Remove special / international characters using regex
    Task 4: Standardize categorical labels via mapping dictionary
    Task 5: Reusable clean_text_column() function + edge-case tests

Usage:
    python scripts/string_cleaning_pipeline.py

Output:
    • Console: before/after comparisons for every step
    • data/processed/cleaned_strings.csv: fully standardized dataset
"""

import os
import sys
import pandas as pd
import numpy as np


# ============================================================================
# SEGMENT MAPPING — defined at module level so all functions can reference it
# ============================================================================
# Business decision: Use uppercase abbreviations (B2B, B2C, SMB, Enterprise)
# to match the canonical labels in the CRM system.
# Each variation encountered in the raw data is mapped here.

SEGMENT_MAP = {
    # B2B variants
    "b2b":                   "B2B",
    "b 2 b":                 "B2B",
    "b2 b":                  "B2B",
    "business-to-business":  "B2B",
    "business to business":  "B2B",
    # B2C variants
    "b2c":                   "B2C",
    "b 2 c":                 "B2C",
    "business-to-consumer":  "B2C",
    # SMB variants
    "sme":                   "SMB",
    "smb":                   "SMB",
    "small medium enterprise": "SMB",
    "small and medium business": "SMB",
    # Enterprise variants
    "enterprise":            "Enterprise",
    "ent":                   "Enterprise",
    "large enterprise":      "Enterprise",
}

PRODUCT_MAP = {
    "electronics":    "Electronics",
    "mobile phones":  "Mobile Phones",
    "software":       "Software",
}


# ============================================================================
# TASK 1 — Strip Whitespace Consistently
# ============================================================================
def strip_all_strings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove leading and trailing whitespace from every string (object) column.

    WHY: " Electronics " and "Electronics" would be counted as two different
    categories in groupby/value_counts — this inflates unique counts and
    breaks joins with reference tables.

    Input:
        df (pd.DataFrame): Raw DataFrame with potentially padded string values.

    Output:
        pd.DataFrame: Copy of df with whitespace stripped from all object columns.

    Side effects:
        Prints per-column before/after unique-value counts showing consolidation.
    """
    print("=" * 65)
    print("TASK 1 — Strip Whitespace from All String Columns")
    print("=" * 65)

    df_clean = df.copy()
    # select_dtypes with include=["object", "string"] covers both pandas 2 and 3
    string_cols = df_clean.select_dtypes(include=["object", "string"]).columns
    total_fixed = 0

    for col in string_cols:
        before_unique = df_clean[col].nunique()

        # Count values that have leading or trailing whitespace
        has_whitespace = df_clean[col].dropna().str.match(r"^\s+|\s+$")
        ws_count = int(has_whitespace.sum())

        df_clean[col] = df_clean[col].str.strip()
        after_unique  = df_clean[col].nunique()
        total_fixed  += ws_count

        status = f"  ✓ {col:<15} unique: {before_unique} → {after_unique}"
        if ws_count:
            status += f"  (stripped {ws_count} value(s) with whitespace)"
        print(status)

    print(f"\n  Total whitespace issues fixed : {total_fixed}")

    # Before/after value_counts for two key columns
    print("\n  ── product value_counts after strip ──")
    print(df_clean["product"].value_counts().to_string())
    print("\n  ── segment value_counts after strip ──")
    print(df_clean["segment"].value_counts().to_string())

    return df_clean


# ============================================================================
# TASK 2 — Normalize Casing to Consistent Standard
# ============================================================================
def normalize_casing(df: pd.DataFrame, columns_to_lower: list) -> pd.DataFrame:
    """
    Convert specified categorical text columns to lowercase.

    Business decision: Use lowercase as the internal standard.
    Rationale — lowercase is the most portable format across SQL, Python,
    and ML pipelines. Proper-case labels are restored in Task 4 via mapping.

    Columns normalised (at least 3 with casing inconsistencies):
        - name    : "DAVE LEE" / "dave lee" / "Dave Lee" → "dave lee"
        - product : "ELECTRONICS" / "electronics" → "electronics"
        - segment : "B2B" / "b2b" / "B 2 B" → "b2b" / "b 2 b"
        - location: "LONDON" / "London" → "london"

    Input:
        df                (pd.DataFrame): DataFrame after whitespace strip.
        columns_to_lower  (list):         Column names to lowercase.

    Output:
        pd.DataFrame: Copy with specified columns lowercased.
    """
    print("\n" + "=" * 65)
    print("TASK 2 — Normalize Casing to Lowercase")
    print("=" * 65)
    print("  Business decision: lowercase as internal standard.")
    print("  Proper-case canonical labels restored in Task 4 via mapping.\n")

    df_clean = df.copy()

    for col in columns_to_lower:
        if col not in df_clean.columns:
            print(f"  ⚠ '{col}' not found — skipped.")
            continue

        # Sample 3 rows before for display
        sample_before = df_clean[col].dropna().head(3).tolist()
        df_clean[col] = df_clean[col].str.lower()
        sample_after  = df_clean[col].dropna().head(3).tolist()

        print(f"  ✓ {col}")
        print(f"      Before : {sample_before}")
        print(f"      After  : {sample_after}")

    print("\n  ── Sample rows after casing normalisation ──")
    print(df_clean[columns_to_lower].head(5).to_string(index=False))

    return df_clean


# ============================================================================
# TASK 3 — Remove Special Characters Using Regex
# ============================================================================
def remove_special_characters(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Remove non-alphanumeric characters (except spaces) from specified columns.

    Regex pattern: [^a-zA-Z0-9 ]
    Explanation:
        [^  ...]  — match any character NOT in the set
        a-zA-Z    — standard ASCII letters (upper and lower)
        0-9       — digits
        (space)   — preserve word spacing
    Result: international diacritics, accents, punctuation, and symbols are stripped.

    Examples:
        "São Paulo"  → "Sao Paulo"  (ã removed)
        "Montréal"   → "Montral"    (é removed)   [known trade-off]
        "Zürich"     → "Zrich"      (ü removed)

    Input:
        df      (pd.DataFrame): DataFrame (after casing normalisation).
        columns (list):         Column names containing international text.

    Output:
        pd.DataFrame: Copy with special characters removed from target columns.

    Trade-off note:
        Removing diacritics may alter meaning in some languages. For analytics
        pipelines where location is used only for grouping (not display), this
        is acceptable. Use a transliteration library (e.g., unidecode) if
        character meaning must be preserved.
    """
    print("\n" + "=" * 65)
    print("TASK 3 — Remove Special / International Characters (Regex)")
    print("=" * 65)
    print("  Pattern: [^a-zA-Z0-9 ]  — removes anything not a-z, A-Z, 0-9, or space\n")

    df_clean = df.copy()
    PATTERN  = r"[^a-zA-Z0-9 ]"

    for col in columns:
        if col not in df_clean.columns:
            print(f"  ⚠ '{col}' not found — skipped.")
            continue

        # Capture unique values with special chars before cleaning
        has_special = df_clean[col].dropna().str.contains(PATTERN, regex=True)
        affected    = df_clean[col][has_special].unique().tolist()

        df_clean[col] = df_clean[col].str.replace(PATTERN, "", regex=True)

        after_vals = [df_clean[col][df_clean[col].str.contains(v[:3], na=False)].iloc[0]
                      if not df_clean[col][df_clean[col].str.contains(v[:3], na=False)].empty else "?"
                      for v in affected[:3]]

        print(f"  ✓ {col} — {len(affected)} value(s) had special characters")
        for orig, cleaned in zip(affected[:3], after_vals):
            print(f"      '{orig}' → '{cleaned}'")

    print("\n  ── location value_counts after special char removal ──")
    print(df_clean["location"].value_counts().to_string())

    return df_clean


# ============================================================================
# TASK 4 — Standardize Categorical Labels Using Mapping Dictionary
# ============================================================================
def standardize_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Consolidate spelling variations and abbreviations into canonical forms.

    Business decisions documented:
        B2B       : uppercase abbreviation — matches CRM system field standard
        B2C       : uppercase abbreviation — same rationale
        SMB       : "SMB" preferred over "SME" — aligns with Kalvium internal taxonomy
        Enterprise: proper case — distinguishes from the abbreviation "Ent"
        Electronics / Mobile Phones / Software: title case — matches product catalogue

    Mapping dictionaries defined at module level (SEGMENT_MAP, PRODUCT_MAP).

    Input:
        df (pd.DataFrame): DataFrame after whitespace, casing, and special char steps.

    Output:
        pd.DataFrame: Copy with segment and product columns standardized.
    """
    print("\n" + "=" * 65)
    print("TASK 4 — Standardize Categorical Labels via Mapping")
    print("=" * 65)

    df_clean = df.copy()

    # ── Segment mapping ───────────────────────────────────────────────────────
    print("\n  SEGMENT_MAP (canonical B2B/B2C/SMB/Enterprise):")
    for k, v in SEGMENT_MAP.items():
        print(f"    '{k}' → '{v}'")

    seg_before = df_clean["segment"].value_counts()
    df_clean["segment"] = df_clean["segment"].map(SEGMENT_MAP)
    seg_after  = df_clean["segment"].value_counts()

    print("\n  segment — before mapping:")
    print(seg_before.to_string())
    print("\n  segment — after mapping:")
    print(seg_after.to_string())

    unmapped_seg = df_clean["segment"].isnull().sum()
    if unmapped_seg:
        print(f"  ⚠  {unmapped_seg} segment value(s) not in map — check SEGMENT_MAP")

    # ── Product mapping ───────────────────────────────────────────────────────
    print("\n  PRODUCT_MAP (title-case canonical names):")
    for k, v in PRODUCT_MAP.items():
        print(f"    '{k}' → '{v}'")

    prod_before = df_clean["product"].value_counts()
    df_clean["product"] = df_clean["product"].map(PRODUCT_MAP)
    prod_after  = df_clean["product"].value_counts()

    print("\n  product — before mapping:")
    print(prod_before.to_string())
    print("\n  product — after mapping:")
    print(prod_after.to_string())

    return df_clean


# ============================================================================
# TASK 5 — Reusable clean_text_column() Function
# ============================================================================
def clean_text_column(
    series: pd.Series,
    lowercase: bool = True,
    strip: bool = True,
    remove_special: bool = False,
    mapping: dict = None,
) -> pd.Series:
    """
    Single reusable function that applies any combination of text cleaning steps.

    Parameters:
        series         (pd.Series): Input string series (any column).
        lowercase      (bool):      If True, apply .str.lower(). Default True.
        strip          (bool):      If True, apply .str.strip(). Default True.
        remove_special (bool):      If True, remove [^a-zA-Z0-9 ] via regex. Default False.
        mapping        (dict|None): If provided, apply .map(mapping). Default None.

    Returns:
        pd.Series: Cleaned series with same index as input.

    Null handling:
        - All str accessor methods (.str.*) propagate NaN automatically.
        - .map() leaves NaN as NaN for values not present in the dict
          (only applies if mapping is provided).
        - A warning is printed if nulls are detected so the caller knows.

    Usage examples:
        # Name column: strip and lowercase only
        df['name'] = clean_text_column(df['name'], lowercase=True, strip=True)

        # Location: strip, lowercase, remove special chars
        df['location'] = clean_text_column(df['location'], remove_special=True)

        # Segment: strip + lowercase then remap to canonical labels
        df['segment'] = clean_text_column(df['segment'], mapping=SEGMENT_MAP)
    """
    result = series.copy()

    # Null detection — warn but do not raise; nulls pass through unchanged
    null_count = result.isna().sum()
    if null_count > 0:
        print(f"  ⚠ Warning: {null_count} null value(s) in '{series.name}' — preserved as NaN")

    if strip:
        result = result.str.strip()

    if lowercase:
        result = result.str.lower()

    if remove_special:
        result = result.str.replace(r"[^a-zA-Z0-9 ]", "", regex=True)

    if mapping is not None:
        result = result.map(mapping)

    return result


def run_edge_case_tests() -> None:
    """
    Verify clean_text_column() handles all edge cases correctly.

    Edge cases tested:
        - Leading / trailing spaces
        - All-caps input
        - Special / underscore character
        - None (null)
        - Empty string
    """
    print("\n" + "=" * 65)
    print("TASK 5 — Edge Case Tests for clean_text_column()")
    print("=" * 65)

    test_cases = [
        "  Product A  ",   # leading/trailing spaces
        "PRODUCT B",       # all caps
        "Product_C",       # special char (underscore)
        None,              # null value
        "",                # empty string
    ]

    test_series = pd.Series(test_cases, name="test_input")
    result      = clean_text_column(
        test_series,
        lowercase=True,
        strip=True,
        remove_special=True,
    )

    print("\n  Input → Output:")
    for orig, cleaned in zip(test_cases, result):
        print(f"    {repr(orig):<25} → {repr(cleaned)}")

    print("\n  ✓ Edge case tests complete")


# ============================================================================
# MAIN PIPELINE
# ============================================================================
if __name__ == "__main__":
    """
    Execute the full string cleaning pipeline.

    Run with:
        python scripts/string_cleaning_pipeline.py
    """
    # ── Path resolution ───────────────────────────────────────────────────────
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_PATH  = os.path.join(repo_root, "data", "raw",       "messy_strings.csv")
    OUTPUT_PATH = os.path.join(repo_root, "data", "processed", "cleaned_strings.csv")

    print("=" * 65)
    print("  CoursePulse — String Cleaning Pipeline")
    print("=" * 65)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_PATH}")
    print("=" * 65)

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] Input file not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    # ── Load raw data ─────────────────────────────────────────────────────────
    df = pd.read_csv(INPUT_PATH)
    print(f"\n  Loaded {len(df)} rows × {len(df.columns)} columns")
    print(f"\n  RAW SAMPLE (first 3 rows):")
    print(df.head(3).to_string(index=False))

    df_original = df.copy()

    # ── Task 1: Strip whitespace from all string columns ──────────────────────
    df = strip_all_strings(df)

    # ── Task 2: Normalize casing ──────────────────────────────────────────────
    # Columns with confirmed casing inconsistencies (≥2 distinct cases in raw data):
    # name, product, segment, location
    df = normalize_casing(df, columns_to_lower=["name", "product", "segment", "location"])

    # ── Task 3: Remove special / international characters ─────────────────────
    # Applied to location — contains São Paulo, Montréal, Zürich, Buenos Aires
    df = remove_special_characters(df, columns=["location", "name"])

    # ── Task 4: Standardize categorical labels ─────────────────────────────────
    df = standardize_labels(df)

    # ── Task 5: Demonstrate reusable function + edge-case tests ───────────────
    print("\n" + "=" * 65)
    print("TASK 5 — Reusable clean_text_column() Applied to Multiple Columns")
    print("=" * 65)

    # email: strip and lowercase only — no special char removal (@ must be preserved)
    df["email"] = clean_text_column(df["email"], lowercase=True, strip=True, remove_special=False)
    print("  ✓ email  : strip=True, lowercase=True, remove_special=False")

    # name: strip + lowercase + remove special chars (already done above, demonstrates reuse)
    df["name"] = clean_text_column(df["name"], lowercase=True, strip=True, remove_special=True)
    print("  ✓ name   : strip=True, lowercase=True, remove_special=True")

    # location: full clean (already done above, shows reusability with mapping=None)
    df["location"] = clean_text_column(df["location"], lowercase=True, strip=True, remove_special=True)
    print("  ✓ location: strip=True, lowercase=True, remove_special=True")

    # Run edge-case tests
    run_edge_case_tests()

    # ── Final state ───────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("FINAL CLEANED DATASET")
    print("=" * 65)
    print(df.to_string(index=False))
    print(f"\n  Remaining nulls : {df.isnull().sum().sum()}")

    # ── Save output ───────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\n  ✓ Cleaned dataset saved → {OUTPUT_PATH}")
    print("\n" + "=" * 65)
    print("  String cleaning pipeline complete.")
    print("=" * 65)
