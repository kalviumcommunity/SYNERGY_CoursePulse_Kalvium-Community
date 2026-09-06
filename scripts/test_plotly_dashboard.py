"""Tests for interactive Plotly charts and their interaction configuration."""

import tempfile
import unittest
from pathlib import Path

from interactive_charts.plotly_dashboard import export_html, interactive_explorer, load_orders, metric_selector, revenue_trend, segment_performance


class TestPlotlyDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = load_orders()

    def test_hover_rich_figures_have_expected_traces(self):
        trend = revenue_trend(self.orders)
        segment = segment_performance(self.orders)
        self.assertIn("hovertemplate", trend.data[0])
        self.assertIn("customdata", segment.data[0])
        self.assertEqual(trend.layout.xaxis.rangeslider.visible, True)

    def test_dropdown_and_native_interaction_configuration(self):
        selector = metric_selector(self.orders)
        explorer = interactive_explorer(self.orders)
        self.assertEqual(len(selector.layout.updatemenus[0].buttons), 3)
        self.assertEqual(explorer.layout.dragmode, "select")
        self.assertEqual(explorer.layout.clickmode, "event+select")

    def test_html_exports_are_nonempty(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = export_html(Path(temporary_directory))
            self.assertEqual(len(paths), 4)
            for path in paths:
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 50_000)


if __name__ == "__main__":
    unittest.main()