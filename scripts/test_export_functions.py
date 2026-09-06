"""Tests for multi-format report generation and export verification."""

import tempfile
import unittest
from pathlib import Path

from export_functions import build_default_report, verify_exports


class TestExportFunctions(unittest.TestCase):
    def test_default_report_creates_all_required_formats(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_dir = build_default_report(Path(temporary_directory))
            sizes = verify_exports(report_dir)
            self.assertEqual(set(sizes), {"cleaned_data.csv", "summary_report.pdf", "interactive_report.html", "README.md"})
            self.assertGreater(sizes["summary_report.pdf"], 500)
            self.assertIn("plotly", (report_dir / "interactive_report.html").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()