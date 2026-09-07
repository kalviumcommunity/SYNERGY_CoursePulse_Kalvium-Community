"""Tests for the business visualisation assignment outputs."""

import tempfile
import unittest
from pathlib import Path

from scripts.business_visualizations import CHART_FILES, build_charts, load_data


class TestBusinessVisualizations(unittest.TestCase):
    def test_source_data_supports_visualisation_questions(self):
        orders, customers = load_data()
        self.assertGreater(len(orders), 0)
        self.assertGreater(len(customers), 0)
        self.assertIn("customer_segment", orders.columns)
        self.assertIn("order_amount", orders.columns)

    def test_all_five_charts_are_exported_as_nonempty_pngs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = build_charts(Path(temporary_directory))
            self.assertEqual([path.name for path in paths], list(CHART_FILES))
            for path in paths:
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()