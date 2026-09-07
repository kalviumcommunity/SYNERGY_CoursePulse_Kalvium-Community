"""Tests for CSV/JSON upload parsing and preview profiling."""

import unittest

import pandas as pd

from upload_preview import column_summary, load_uploaded_dataframe


class TestUploadPreview(unittest.TestCase):
    def test_csv_upload_is_parsed(self):
        dataframe = load_uploaded_dataframe("sample.csv", b"name,amount\nA,10\nB,20\n")
        self.assertEqual(dataframe.shape, (2, 2))
        self.assertEqual(dataframe["amount"].tolist(), [10, 20])

    def test_json_array_and_nested_records_are_parsed(self):
        dataframe = load_uploaded_dataframe("sample.json", b'[{"name":"A","meta":{"score":4}}]')
        self.assertEqual(dataframe.loc[0, "meta.score"], 4)

    def test_summary_reports_nulls_and_types(self):
        dataframe = pd.DataFrame({"amount": [1, None], "name": ["A", "B"]})
        summary = column_summary(dataframe)
        amount_row = summary[summary["Column"] == "amount"].iloc[0]
        self.assertEqual(amount_row["Null Count"], 1)
        self.assertEqual(amount_row["Null %"], 50.0)

    def test_invalid_and_empty_uploads_raise_clear_errors(self):
        with self.assertRaisesRegex(ValueError, "Unsupported file type"):
            load_uploaded_dataframe("sample.txt", b"data")
        with self.assertRaisesRegex(ValueError, "empty"):
            load_uploaded_dataframe("sample.csv", b"name,amount\n")
        with self.assertRaisesRegex(ValueError, "JSON"):
            load_uploaded_dataframe("sample.json", b"not-json")


if __name__ == "__main__":
    unittest.main()