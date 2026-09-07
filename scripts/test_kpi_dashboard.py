"""Tests for KPI calculations, directional status, and period comparisons."""

import unittest

from interactive_charts.plotly_dashboard import load_orders
from kpis.kpi_dashboard import compute_kpis, trend_indicator


class TestKpiDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = load_orders()

    def test_five_kpis_are_computed_from_available_periods(self):
        kpis, current_label, prior_label = compute_kpis(self.orders)
        self.assertEqual(len(kpis), 5)
        self.assertNotEqual(current_label, prior_label)
        self.assertTrue(all(kpi.source for kpi in kpis))
        self.assertTrue(all(kpi.delta_display for kpi in kpis))

    def test_churn_direction_is_inverted(self):
        self.assertEqual(trend_indicator(-5, "Churn Rate")[1], "#10b981")
        self.assertEqual(trend_indicator(5, "Churn Rate")[1], "#ef4444")
        self.assertEqual(trend_indicator(5, "Revenue")[1], "#10b981")


if __name__ == "__main__":
    unittest.main()