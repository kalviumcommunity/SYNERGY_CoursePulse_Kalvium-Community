"""Tests for schema drift and data-quality validation."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from validate_data import validate


class TestValidateData(unittest.TestCase):
    def write_csv(self, dataframe: pd.DataFrame, directory: str) -> Path:
        path = Path(directory) / "data.csv"
        dataframe.to_csv(path, index=False)
        return path

    def test_valid_dataset_passes(self):
        dataframe = pd.DataFrame({"customer_id": [1, 2], "order_id": [10, 11], "amount": [20.0, 30.0], "date": ["2024-01-01", "2024-01-02"], "segment": ["A", "B"]})
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(validate(self.write_csv(dataframe, directory), min_rows=2), [])

    def test_missing_columns_and_row_count_fail(self):
        dataframe = pd.DataFrame({"customer_id": [1], "amount": ["bad"]})
        with tempfile.TemporaryDirectory() as directory:
            errors = validate(self.write_csv(dataframe, directory), min_rows=2)
            self.assertTrue(any("Missing required columns" in error for error in errors))
            self.assertTrue(any("below minimum" in error for error in errors))

    def test_invalid_dates_and_fully_null_columns_fail(self):
        dataframe = pd.DataFrame({"customer_id": [1], "order_id": [10], "amount": [20.0], "date": ["not-a-date"], "segment": [None]})
        with tempfile.TemporaryDirectory() as directory:
            errors = validate(self.write_csv(dataframe, directory), min_rows=1)
            self.assertTrue(any("invalid date" in error for error in errors))
            self.assertTrue(any("Fully null" in error for error in errors))


if __name__ == "__main__":
    unittest.main()