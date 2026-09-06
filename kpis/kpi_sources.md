# KPI Sources and Definitions

The KPI dashboard derives its comparison periods from the latest order month in
the validated CoursePulse data. It never uses the wall-clock month, so historical
or newly uploaded datasets produce non-empty current/prior comparisons without
code changes.

| KPI | Definition | Source and validation |
| --- | --- | --- |
| Revenue | Sum of positive valid order amounts | `agg_daily_revenue`, reconciled to valid orders |
| Active Users | Distinct active customers in the month | `vw_active_customers` activity definition |
| Average Order Value | Mean positive order amount | Validated orders layer |
| Churn Rate | Prior-month customers absent from current month / prior-month customers | Customer activity comparison |
| Customer Satisfaction | Successful fulfillment share multiplied by five | Transparent proxy because source data has no ratings table |

## Directional logic

Revenue, active users, average order value, and satisfaction are positive when
they increase. Churn is inverted: a decrease is green, an increase is red.
Changes within +/-2% are amber and labelled stable. Every card displays the
current value, period-over-period percentage, arrow, status, and source.

## Refresh behavior

The dashboard loads the current CSV-backed clean layer on each Streamlit rerun.
The existing SQL view and aggregate definitions remain the metric contracts;
refreshing the source data automatically changes the latest and prior periods.
In production, this loader would be replaced with the scheduled database/view
refresh while preserving the same KPI definitions.

## Data limitation

The repository has no customer rating field, survey table, or explicit churn
label. The satisfaction card is therefore a clearly labelled fulfillment-quality
proxy, and churn is derived from observed customer activity rather than claimed
as a source-provided label.