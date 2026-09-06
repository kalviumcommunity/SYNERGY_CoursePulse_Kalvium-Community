"""Focused tests for the analytical SQL optimisation assignment."""

import unittest

from scripts.query_optimization import build_connection, run_benchmark


class TestQueryOptimization(unittest.TestCase):
    def test_queries_return_equivalent_results_and_summary(self):
        connection = build_connection()
        try:
            summary, report = run_benchmark(connection)
        finally:
            connection.close()

        self.assertEqual(len(summary), 9)
        self.assertIn("Query 1 core data matches: PASS", report)
        self.assertIn("Query 2 results match: PASS", report)
        self.assertIn("Query 3 results match: PASS", report)
        self.assertIn("Filters applied before join (Query 2)", summary["Metric"].tolist())


if __name__ == "__main__":
    unittest.main()