# Analysis Report Export Guide

## Run an export

```bash
.venv/bin/python export_functions.py
```

Each run creates `output/reports/YYYY-MM-DD_HHMMSS_analysis/` with four files:

- `cleaned_data.csv`: valid CoursePulse orders for Excel filtering and pivot tables.
- `summary_report.pdf`: portable executive summary for meetings and email.
- `interactive_report.html`: standalone Plotly report with hover, zoom, and controls.
- `README.md`: generation timestamp, record count, columns, range, and chart names.

## Streamlit export

Choose `Export Reports` in the dashboard and click `Export Analysis`. The page
provides CSV, PDF, HTML, and metadata download buttons after generation.

## Schedule and failure handling

`scheduled_export.py` runs one export cycle and verifies every output. Schedule
it with macOS/Linux cron:

```cron
0 17 * * * /absolute/path/.venv/bin/python /absolute/path/scheduled_export.py >> /absolute/path/output/reports/export.log 2>&1
```

Failures are logged with a timestamp and raised so cron or an external monitor
can alert the data team. The next scheduled run retries the export.

## Refresh policy

The recommended delivery is daily at 17:00 plus on-demand exports from
Streamlit. Timestamped folders preserve an audit trail instead of overwriting
prior reports.