"""Scheduled export entry point for cron or an external scheduler.

Example macOS/Linux crontab entry for a daily 17:00 export:
0 17 * * * /path/to/repo/.venv/bin/python /path/to/repo/scheduled_export.py >> /path/to/repo/output/reports/export.log 2>&1
"""

import logging
from datetime import datetime

from export_functions import build_default_report, verify_exports


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_scheduled_export() -> None:
    """Run one export cycle and log failures for the next scheduled retry."""
    try:
        report_dir = build_default_report()
        verify_exports(report_dir)
        logging.info("Export complete: %s", report_dir)
    except Exception:
        logging.exception("Scheduled export failed at %s; the next schedule will retry", datetime.now().isoformat())
        raise


if __name__ == "__main__":
    run_scheduled_export()