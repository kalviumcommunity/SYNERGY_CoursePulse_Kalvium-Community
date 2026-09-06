"""Tests for session-state workflow transitions and dependent analysis."""

import unittest
from datetime import date

from interactive_charts.plotly_dashboard import load_orders
from session_workflow import calculate_segment_analysis, confirm_segment, initialize_workflow_state, reset_workflow


class TestSessionWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = load_orders()
        cls.start = cls.orders["order_date"].min().date()
        cls.end = cls.orders["order_date"].max().date()

    def test_initialization_is_safe_and_descriptive(self):
        state = {}
        initialize_workflow_state(state)
        state["selected_segment"] = "Enterprise"
        initialize_workflow_state(state)
        self.assertEqual(state["selected_segment"], "Enterprise")
        self.assertEqual(state["workflow_step"], 1)
        self.assertIn("analysis_result", state)

    def test_confirmation_unlocks_dependent_analysis(self):
        state = {}
        initialize_workflow_state(state)
        confirm_segment(state, "Enterprise")
        result = calculate_segment_analysis(self.orders, state["selected_segment"], self.start, self.end)
        self.assertEqual(state["workflow_step"], 2)
        self.assertEqual(result["segment"], "Enterprise")
        self.assertGreater(result["orders"], 0)

    def test_reset_returns_workflow_to_initial_state(self):
        state = {"selected_segment": "Enterprise", "workflow_step": 2, "analysis_result": {"revenue": 4}, "unrelated": "keep"}
        reset_workflow(state)
        self.assertEqual(state["selected_segment"], "All")
        self.assertEqual(state["workflow_step"], 1)
        self.assertIsNone(state["analysis_result"])
        self.assertEqual(state["unrelated"], "keep")


if __name__ == "__main__":
    unittest.main()