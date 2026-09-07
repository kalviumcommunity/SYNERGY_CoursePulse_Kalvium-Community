"""Tests for the automated ingest-clean-aggregate-output pipeline."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline import aggregate, clean, output, run_pipeline


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.raw = pd.DataFrame(
            {
                "order_id": [1, 2, 3],
                "customer_id": [10, 11, 12],
                "order_amount": [100, -2, "bad"],
                "order_date": ["2024-01-01", "2024-01-02", "invalid"],
            }
        )

    def test_clean_and_aggregate_remove_invalid_rows(self):
        cleaned = clean(self.raw)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(aggregate(cleaned).iloc[0]["total_revenue"], 100)

    def test_pipeline_writes_expected_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "input.csv"
            output_path = Path(temporary_directory) / "outputs"
            self.raw.to_csv(input_path, index=False)
            run_pipeline(input_path, output_path)
            self.assertTrue((output_path / "cleaned_data.csv").exists())
            self.assertTrue((output_path / "aggregated_metrics.csv").exists())
            self.assertEqual(len(pd.read_csv(output_path / "cleaned_data.csv")), 1)


if __name__ == "__main__":
    unittest.main()