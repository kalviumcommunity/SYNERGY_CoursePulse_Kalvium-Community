"""Tests for cached loading, schema validation, and reactive KPI calculations."""

import unittest

import pandas as pd

from realtime_dashboard import calculate_reactive_kpis, load_dashboard_data


class TestRealtimeDashboard(unittest.TestCase):
    def test_csv_aliases_are_normalized(self):
        dataframe = load_dashboard_data("orders.csv", b"date,amount,customer_id,segment\n2024-01-01,10,1,A\n2024-01-02,20,2,B\n")
        self.assertEqual(dataframe["dashboard_revenue"].tolist(), [10, 20])
        self.assertEqual(dataframe["dashboard_segment"].tolist(), ["A", "B"])

    def test_json_upload_and_reactive_kpis(self):
        dataframe = load_dashboard_data("orders.json", b'[{"timestamp":"2024-01-01","revenue":100,"user_id":"u1"}]')
        kpis = calculate_reactive_kpis(dataframe)
        self.assertEqual(kpis["records"], 1)
        self.assertEqual(kpis["customers"], 1)
        self.assertEqual(kpis["revenue"], 100)

    def test_missing_required_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "date.*revenue"):
            load_dashboard_data("invalid.csv", b"name,value\nA,1\n")

    def test_empty_filtered_frame_kpis_are_safe(self):
        dataframe = load_dashboard_data("orders.csv", b"date,amount\n2024-01-01,10\n")
        empty = dataframe.iloc[0:0]
        kpis = calculate_reactive_kpis(empty)
        self.assertEqual(kpis["records"], 0)
        self.assertEqual(kpis["quality"], 100)


if __name__ == "__main__":
    unittest.main()