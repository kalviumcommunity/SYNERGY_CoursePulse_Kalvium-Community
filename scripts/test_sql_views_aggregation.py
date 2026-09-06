"""Tests for the SQL views and pre-aggregated dashboard layer."""

import unittest

from scripts.query_optimization import build_connection
from scripts.sql_views_aggregation import create_data_layer, query_dashboard_layer, validate_data_layer


class TestSqlViewsAggregation(unittest.TestCase):
    def test_views_and_aggregation_are_queryable(self):
        connection = build_connection()
        try:
            create_data_layer(connection)
            results = query_dashboard_layer(connection)
            validate_data_layer(connection, results)
        finally:
            connection.close()

        self.assertFalse(results["active_customers"].empty)
        self.assertFalse(results["revenue_by_region"].empty)
        self.assertFalse(results["daily_revenue"].empty)

    def test_aggregation_matches_valid_order_total(self):
        connection = build_connection()
        try:
            create_data_layer(connection)
            aggregated_total = connection.execute(
                "SELECT ROUND(SUM(total_revenue), 2) FROM agg_daily_revenue"
            ).fetchone()[0]
            source_total = connection.execute(
                """
                SELECT ROUND(SUM(order_amount), 2) FROM orders
                WHERE order_status IN ('completed', 'shipped', 'delivered')
                  AND order_amount > 0
                """
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(aggregated_total, source_total)


if __name__ == "__main__":
    unittest.main()