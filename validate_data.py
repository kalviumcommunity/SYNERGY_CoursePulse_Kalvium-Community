"""Validate the cleaned pipeline dataset and fail on schema drift."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["customer_id", "order_id", "amount", "date", "segment"]


def validate(file_path: str | Path, min_rows: int = 100) -> list[str]:
    """Run schema and quality checks; return descriptive errors."""
    path = Path(file_path)
    print(f"Validating: {path}")
    errors: list[str] = []
    try:
        dataframe = pd.read_csv(path)
    except Exception as error:
        return [f"Could not read input: {error}"]

    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
    else:
        print("PASS: All required columns present")

    if "amount" in dataframe.columns:
        if not pd.api.types.is_numeric_dtype(dataframe["amount"]):
            errors.append("Column 'amount' is not numeric")
        else:
            print("PASS: amount column is numeric")
    if "date" in dataframe.columns:
        parsed_dates = pd.to_datetime(dataframe["date"], errors="coerce")
        if parsed_dates.isna().any():
            errors.append(f"Column 'date' contains {int(parsed_dates.isna().sum())} invalid date value(s)")
        else:
            print("PASS: date column is valid")

    if len(dataframe) < min_rows:
        errors.append(f"Row count {len(dataframe)} below minimum {min_rows}")
    else:
        print(f"PASS: Row count {len(dataframe)} meets minimum {min_rows}")

    null_columns = [column for column in dataframe.columns if dataframe[column].isna().all()]
    if null_columns:
        errors.append(f"Fully null columns: {null_columns}")
    else:
        print("PASS: No fully null columns")

    if errors:
        print("\nVALIDATION FAILED:")
        for error in errors:
            print(f"  ERROR: {error}")
    else:
        print("\nALL CHECKS PASSED")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the cleaned pipeline dataset")
    parser.add_argument("file_path", help="CSV file to validate")
    parser.add_argument("--min-rows", type=int, default=100, help="Minimum required row count")
    args = parser.parse_args()
    sys.exit(1 if validate(args.file_path, args.min_rows) else 0)


if __name__ == "__main__":
    main()