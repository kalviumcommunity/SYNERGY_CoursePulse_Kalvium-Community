-- Table: agg_daily_revenue
-- Purpose: Pre-compute daily revenue KPIs for fast dashboard reads.
-- Grain: one row per order date.
-- Refresh strategy: full refresh by the Python pipeline; production can use
-- incremental refresh for newly arrived order dates.

CREATE TABLE agg_daily_revenue (
    aggregation_date TEXT NOT NULL PRIMARY KEY,
    total_revenue REAL NOT NULL,
    order_count INTEGER NOT NULL,
    average_order_value REAL NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO agg_daily_revenue (
    aggregation_date,
    total_revenue,
    order_count,
    average_order_value,
    updated_at
)
SELECT
    DATE(o.order_date) AS aggregation_date,
    ROUND(SUM(o.order_amount), 2) AS total_revenue,
    COUNT(*) AS order_count,
    ROUND(AVG(o.order_amount), 2) AS average_order_value,
    CURRENT_TIMESTAMP AS updated_at
FROM orders o
WHERE o.order_status IN ('completed', 'shipped', 'delivered')
  AND o.order_amount > 0
GROUP BY DATE(o.order_date);