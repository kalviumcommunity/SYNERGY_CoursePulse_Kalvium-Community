"""Tests for configurable threshold alert evaluation."""

import unittest

from alert_config import ALERT_THRESHOLDS
from alert_monitor import check_alerts


class TestAlertMonitor(unittest.TestCase):
    def test_above_and_below_thresholds_trigger_complete_alerts(self):
        alerts = check_alerts({"churn_rate": 8, "average_order": 20, "quality": 90}, ALERT_THRESHOLDS)
        self.assertEqual({alert["key"] for alert in alerts}, {"churn_rate", "average_order", "quality"})
        for alert in alerts:
            self.assertIn("metric", alert)
            self.assertIn("value", alert)
            self.assertIn("threshold", alert)
            self.assertIn("message", alert)

    def test_values_inside_thresholds_do_not_alert(self):
        alerts = check_alerts({"churn_rate": 2, "average_order": 50, "quality": 99}, ALERT_THRESHOLDS)
        self.assertEqual(alerts, [])

    def test_custom_configuration_changes_behavior_without_code_changes(self):
        custom = {"average_order": {**ALERT_THRESHOLDS["average_order"], "threshold": 100}}
        alerts = check_alerts({"average_order": 50}, custom)
        self.assertEqual(len(alerts), 1)

    def test_missing_metrics_are_ignored(self):
        self.assertEqual(check_alerts({"revenue": 100}, ALERT_THRESHOLDS), [])


if __name__ == "__main__":
    unittest.main()