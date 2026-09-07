# CoursePulse Analytics Dashboard

CoursePulse is a Streamlit analytics product for exploring customer orders and
CoursePulse engagement events. It combines upload and filtering workflows,
reactive KPI cards, Plotly charts, threshold alerts, scheduled data processing,
CSV/PDF/HTML exports, and optional email delivery for operations and analytics
stakeholders.

## Dataset

The repository contains two related data domains:

### Orders and customers

- `data/raw/orders_5000.csv`: `order_id`, `customer_id`, `order_amount`,
	`order_status`, and `order_date`.
- `data/raw/customers_1000.csv`: `customer_id`, `customer_name`,
	`customer_segment`, `region`, and `signup_date`.
- Valid revenue uses positive orders with `completed`, `shipped`, or `delivered`
	status. The pipeline normalizes `order_amount` and `order_date` to `amount`
	and `date`, then enriches records with `segment`.

### CoursePulse events

- `data/raw/course_pulse_events.csv`: `event_id`, `user_id`,
	`event_timestamp`, `event_type`, `course_id`, `course_name`, `category`, and
	`search_query`.
- The event workflow writes `output/processed.csv` and derives event-time and
	enrollment fields.

## Getting Started

From a fresh clone, run these commands:

```bash
git clone https://github.com/kalviumcommunity/SYNERGY_CoursePulse_Kalvium-Community.git
cd SYNERGY_CoursePulse_Kalvium-Community
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
streamlit run app.py
```

Windows activation equivalent:

```powershell
.venv\Scripts\activate
```

The app opens with a sidebar containing the dashboard pages. No database server
is required for the standard local workflow.

## Usage Guide

The current Streamlit pages are:

| Page | Purpose |
| --- | --- |
| Overview | High-level application entry point. |
| Interactive Plotly | Hoverable revenue and customer charts with selectors and zoom. |
| KPI Dashboard | Five KPI cards with period comparison and direction-aware status. |
| Upload Preview | Upload CSV/JSON and inspect rows, types, nulls, and statistics. |
| Interactive Filters | Date, segment, revenue, and granularity filters. |
| Session Workflow | Two-step segment analysis persisted through reruns. |
| Real-Time Dashboard | Generic upload-driven cached KPIs and three charts. |
| Export Reports | Generate and download CSV, PDF, HTML, and metadata reports. |
| Insight Sharing | Preview a structured report and send it through configured SMTP. |

For a scheduled order refresh:

```bash
python pipeline.py --input data/raw/orders_5000.csv --customers data/raw/customers_1000.csv --output output/pipeline
python validate_data.py output/pipeline/cleaned_data.csv
```

For local tests:

```bash
python -m unittest discover -s scripts -p 'test_*.py'
```

## Pipeline Architecture

```text
CSV upload or scheduled source
							|
							v
Ingestion: read CSV/JSON and validate file type
							|
							v
Cleaning: normalize aliases, parse dates, coerce amounts,
					remove invalid/non-positive rows, enrich segments
							|
							v
Aggregation: revenue, order count, and average order value by segment
							|
							v
Output: cleaned_data.csv and aggregated_metrics.csv
							|
							v
Dashboard: filters -> reactive KPIs -> charts -> threshold alerts
							|
							v
Delivery: CSV/PDF/HTML export and optional SMTP email report
```

The order pipeline is implemented in `pipeline.py` and accepts CLI paths. The
weekly GitHub Actions workflow in `.github/workflows/pipeline.yml` runs it every
Monday at 06:00 UTC and commits refreshed `output/pipeline/` files. The
validation workflow in `.github/workflows/validate.yml` runs on pushes to
`main`/`develop`, pull requests to `main`, and manual dispatch.

## Derived Features and Data Contracts

| Field | Type | Description | Example |
| --- | --- | --- | --- |
| `amount` | float | Normalized positive order/transaction value. | `125.50` |
| `date` | datetime | Normalized order or transaction date. | `2024-01-15` |
| `segment` | string | Customer segment enriched from the customer dimension or `All`/`Unknown`. | `Enterprise` |
| `dashboard_date` | datetime | Generic upload dashboard date field after alias normalization. | `2024-01-15` |
| `dashboard_revenue` | float | Generic upload dashboard revenue field after numeric coercion. | `125.50` |
| `dashboard_customer` | string | Generic customer/user identifier used for distinct-customer KPIs. | `customer-42` |
| `dashboard_segment` | string | Generic segment/category field used by filters and charts. | `SMB` |
| `period` | datetime | Daily, weekly, or monthly period selected by the filter workflow. | `2024-01-01` |
| `order_count_30d` | integer | Orders for a customer in the rolling activity window. | `4` |
| `revenue_30d` | float | Valid revenue for a customer in the rolling activity window. | `4523.50` |
| `days_since_order` | integer | Days since the latest observed order in the active-customer view. | `12` |
| `total_revenue` | float | Aggregated revenue by segment or day. | `125000.00` |
| `average_order_value` | float | Mean valid order amount at the selected aggregation grain. | `48.20` |
| `hour_of_day` | integer | Hour extracted from an event timestamp. | `14` |
| `day_of_week` | string | Weekday extracted from an event timestamp. | `Monday` |
| `is_enrollment` | boolean | Whether an event represents an enrollment. | `True` |

## KPI Definitions

- **Revenue:** sum of positive valid order amounts from the current filtered
	data.
- **Active Users:** distinct customers/users present in the selected period.
- **Average Order Value:** mean positive order amount.
- **Churn Rate:** prior-period active customers absent from the current period;
	this is derived activity churn, not a source-provided label.
- **Customer Satisfaction:** five-point fulfillment-quality proxy because the
	repository does not contain a rating or survey field.
- **Data Quality:** 100 minus the percentage of null cells in the filtered
	uploaded data.

SQL view and aggregate definitions live under `database/views/` and
`database/aggregations/`. Their naming and refresh rules are documented in
`data_layer_conventions.md`.

## Configuration and Delivery

Copy `.env.example` to `.env` only when email delivery is needed, then provide
SMTP credentials through environment variables. Never commit `.env` or real
passwords. The export runner is:

```bash
python export_functions.py
```

The scheduled export entry point is `scheduled_export.py`; macOS/Linux cron can
invoke it daily at 17:00. Email failures are logged and do not crash the
dashboard. Alert thresholds are configured in `alert_config.py`, separate from
display logic.

## Validation and Quality Gates

The validator checks required columns, numeric amounts, valid dates, minimum row
count, and fully-null columns:

```bash
python validate_data.py output/pipeline/cleaned_data.csv
```

It prints a PASS/ERROR report and exits with status `1` when validation fails,
which fails the GitHub Actions job and can block a protected-branch merge.

## Known Limitations

- The repository has both an event-oriented workflow and an order-oriented
	pipeline; they use different source schemas and are documented separately.
- Several legacy analysis navigation pages are scaffolds with placeholder text;
	the data-backed pages listed above are the maintained product surfaces.
- The default scheduled pipeline is weekly, while the Streamlit upload dashboard
	is interactive rather than a continuously running data refresh service.
- Revenue excludes cancelled/non-positive orders, and refunds are not modeled
	as a separate net-revenue adjustment.
- Segment classification comes from the supplied customer dimension; the
	product does not infer behavioral segments.
- Churn is inferred from activity windows, and satisfaction is a fulfillment
	proxy because source churn/rating fields are unavailable.
- Alert thresholds are static configuration values and do not yet adjust for
	seasonality or historical variance.
- Email delivery requires valid SMTP credentials and provider permissions; when
	credentials are absent, report files and the dashboard remain available but
	no email is sent.
- Generic uploads must contain a recognizable date and revenue/amount column;
	otherwise the dashboard shows a validation message instead of guessing.

## Repository Map

- `app.py`: Streamlit navigation and page composition.
- `pipeline.py`: CLI ingest-clean-aggregate-output pipeline.
- `validate_data.py`: schema and quality gate.
- `interactive_charts/`: Plotly figures and standalone HTML exports.
- `kpis/`: KPI computation and dashboard cards.
- `database/`: version-controlled SQL views and aggregations.
- `output/`: generated analysis artifacts and pipeline outputs.
- `.github/workflows/`: scheduled pipeline and validation workflows.