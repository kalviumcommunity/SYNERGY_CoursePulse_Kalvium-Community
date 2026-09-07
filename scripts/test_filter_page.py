"""Tests for the Streamlit filter chain."""

import unittest
from datetime import date

from filter_page import filter_orders
from interactive_charts.plotly_dashboard import load_orders


class TestFilterPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = load_orders()
        cls.start = cls.orders["order_date"].min().date()
        cls.end = cls.orders["order_date"].max().date()
        cls.segments = sorted(cls.orders["customer_segment"].unique().tolist())
        cls.revenue_range = (float(cls.orders["order_amount"].min()), float(cls.orders["order_amount"].max()))

    def test_full_defaults_preserve_all_orders(self):
        filtered = filter_orders(self.orders, (self.start, self.end), self.segments, self.revenue_range)
        self.assertEqual(len(filtered), len(self.orders))

    def test_date_segment_and_revenue_filters_chain(self):
        selected_segment = [self.segments[0]]
        minimum_revenue = 100.0
        filtered = filter_orders(self.orders, (date(2024, 1, 1), self.end), selected_segment, (minimum_revenue, self.revenue_range[1]), "Monthly")
        self.assertTrue((filtered["customer_segment"] == selected_segment[0]).all())
        self.assertTrue((filtered["order_amount"] >= minimum_revenue).all())
        self.assertTrue(filtered["period"].dt.day.eq(1).all())

    def test_impossible_filters_return_empty_dataframe(self):
        filtered = filter_orders(self.orders, (date(2030, 1, 1), date(2030, 1, 2)), self.segments, self.revenue_range)
        self.assertTrue(filtered.empty)


if __name__ == "__main__":
    unittest.main()