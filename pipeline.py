"""Automated ingest, clean, aggregate, and output pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("coursepulse_pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def ingest(file_path: str | Path) -> pd.DataFrame:
    """Stage 1: read raw orders from CSV."""
    LOGGER.info("Ingesting data from %s", file_path)
    dataframe = pd.read_csv(file_path)
    LOGGER.info("Rows ingested: %s", len(dataframe))
    return dataframe


def clean(dataframe: pd.DataFrame, customers_path: str | Path | None = None) -> pd.DataFrame:
    """Stage 2: normalize fields, optionally enrich segments, and remove invalid rows."""
    LOGGER.info("Cleaning and validating data")
    cleaned = dataframe.copy()
    amount_column = next((column for column in ("amount", "order_amount", "transaction_amount", "revenue") if column in cleaned), None)
    date_column = next((column for column in ("date", "order_date", "transaction_date") if column in cleaned), None)
    if amount_column is None or date_column is None:
        raise ValueError("Input must include an amount/revenue column and a date column.")
    cleaned = cleaned.rename(columns={amount_column: "amount", date_column: "date"})
    cleaned["amount"] = pd.to_numeric(cleaned["amount"], errors="coerce")
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    if customers_path and "customer_id" in cleaned.columns and "segment" not in cleaned.columns:
        customers = pd.read_csv(customers_path)
        segment_column = next((column for column in ("segment", "customer_segment") if column in customers), None)
        if segment_column:
            cleaned = cleaned.merge(customers[["customer_id", segment_column]], on="customer_id", how="left")
            cleaned = cleaned.rename(columns={segment_column: "segment"})
    if "segment" not in cleaned.columns:
        cleaned["segment"] = "All"
    initial_rows = len(cleaned)
    cleaned = cleaned.dropna(subset=["amount", "date"])
    cleaned = cleaned[cleaned["amount"] > 0].copy()
    cleaned["segment"] = cleaned["segment"].fillna("Unknown").astype(str)
    LOGGER.info("Cleaned rows: %s -> %s", initial_rows, len(cleaned))
    return cleaned


def aggregate(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Stage 3: compute revenue, order count, and average order by segment."""
    LOGGER.info("Aggregating metrics by segment")
    aggregated = dataframe.groupby("segment", as_index=False).agg(
        total_revenue=("amount", "sum"),
        order_count=("amount", "count"),
        average_order_value=("amount", "mean"),
    )
    LOGGER.info("Aggregated segments: %s", len(aggregated))
    return aggregated


def output(cleaned: pd.DataFrame, aggregated: pd.DataFrame, output_dir: str | Path) -> None:
    """Stage 4: write cleaned and aggregated outputs."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(destination / "cleaned_data.csv", index=False)
    aggregated.to_csv(destination / "aggregated_metrics.csv", index=False)
    LOGGER.info("Pipeline outputs written to %s", destination.resolve())


def run_pipeline(input_path: str | Path, output_dir: str | Path, customers_path: str | Path | None = None) -> None:
    """Run all four pipeline stages in order."""
    raw = ingest(input_path)
    cleaned = clean(raw, customers_path)
    aggregated = aggregate(cleaned)
    output(cleaned, aggregated, output_dir)
    LOGGER.info("Pipeline complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="CoursePulse ingest-clean-aggregate-output pipeline")
    parser.add_argument("--input", required=True, help="Raw input CSV path")
    parser.add_argument("--customers", help="Optional customer CSV for segment enrichment")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()
    run_pipeline(args.input, args.output, args.customers)


if __name__ == "__main__":
    main()