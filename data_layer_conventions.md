# Clean Data Layer Naming Conventions

## Views

- Prefix: `vw_`
- Pattern: `vw_[business_entity]_[metric]`
- `vw_active_customers`: customer-level rolling activity and revenue.
- `vw_revenue_by_region`: valid revenue and order KPIs by region and segment.

## Pre-Aggregated Tables

- Prefix: `agg_`
- Pattern: `agg_[grain]_[subject]`
- `agg_daily_revenue`: one row per order date for dashboard revenue KPIs.
- Every aggregate includes its time grain, `order_count`, and `updated_at`.

## Data Layer Rules

- Shared metric definitions live in `database/views/` or `database/aggregations/`.
- Dashboards query views and aggregate tables instead of rebuilding raw-table joins.
- Valid revenue excludes cancelled orders and non-positive amounts.
- View definitions are version-controlled and refreshed automatically by the runner.

## Refresh Strategy

The assignment runner performs a full refresh of `agg_daily_revenue`, which is
simple and reliable for this dataset. A production pipeline should incrementally
refresh new order dates and retain `updated_at` so dashboards can expose data
freshness. A view recalculates from current source rows whenever it is queried.

## Follow-up Answers

1. Dashboards querying a view use the updated definition after the database view
   is replaced because the view stores logic rather than a snapshot of rows.
2. An hourly aggregate does not include records arriving after its last refresh.
   Use incremental refreshes for recent dates or a small real-time query layered
   on top of the latest aggregate.
3. Test row counts, column contracts, known totals, null behavior, duplicate
   grain keys, and source-to-aggregate reconciliation before release.