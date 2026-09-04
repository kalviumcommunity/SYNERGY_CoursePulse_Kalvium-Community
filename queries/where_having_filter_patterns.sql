-- ============================================================
-- queries/where_having_filter_patterns.sql
-- ============================================================
-- Data Analyst · Sreedhil Pavishanker B
-- Branch : feature/sql-where-having-filters
-- Purpose: Demonstrate correct WHERE vs HAVING usage across
--          five real-world business queries on the CoursePulse
--          orders + customers schema.
--
-- KEY PATTERN RULE (memorise this):
--   WHERE  → filters individual ROWS  before  GROUP BY runs
--   HAVING → filters aggregated GROUPS after  GROUP BY runs
--
-- When to use which:
--   ┌──────────────────────────────────────────────────────────┐
--   │  Scenario                          │ Clause to Use       │
--   ├──────────────────────────────────────────────────────────│
--   │  Remove bad/invalid raw rows       │ WHERE               │
--   │  Date range / status filter        │ WHERE               │
--   │  Filter on a computed aggregate    │ HAVING              │
--   │  Enterprise customers > $10k spend │ HAVING SUM(amount)  │
--   │  Combined data quality + threshold │ WHERE … HAVING …    │
--   └──────────────────────────────────────────────────────────┘
-- ============================================================


-- ============================================================
-- TASK 1 · WHERE Filtering  (data quality before grouping)
-- ============================================================
-- Business goal: Count per-customer revenue for 2024,
-- excluding refunds and invalid transactions.
--
-- WHY WHERE (not HAVING)?
-- These conditions check individual row-level column values —
-- they do NOT depend on an aggregate such as SUM or COUNT.
-- Applying them in WHERE lets the database skip dirty rows
-- entirely, making GROUP BY cheaper.
-- ============================================================

SELECT
    o.customer_id,
    COUNT(*)                        AS transaction_count,
    ROUND(SUM(o.order_amount), 2)   AS annual_revenue
FROM orders o
WHERE o.order_date    >= '2024-01-01'          -- Date range filter
  AND o.order_amount  >  0                     -- Remove refunds / zero-value rows
  AND o.order_status  != 'cancelled'           -- Valid transactions only
GROUP BY o.customer_id
ORDER BY annual_revenue DESC;


-- ============================================================
-- TASK 2 · GROUP BY with Multiple Dimensions + 3 Aggregates
-- ============================================================
-- Business goal: Monthly revenue breakdown per customer
-- segment and per month, showing volume and value KPIs.
--
-- WHY WHERE first?
-- We restrict to 2024 data BEFORE grouping so the GROUP BY
-- engine never touches older records → faster and cleaner.
-- ============================================================

SELECT
    c.customer_segment                                          AS customer_type,
    DATE(strftime('%Y-%m-01', o.order_date))                   AS month,
    COUNT(DISTINCT o.customer_id)                              AS unique_customers,
    COUNT(*)                                                    AS transaction_count,
    ROUND(SUM(o.order_amount), 2)                              AS monthly_revenue,
    ROUND(AVG(o.order_amount), 2)                              AS avg_transaction_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date   >= '2024-01-01'           -- WHERE filters rows BEFORE GROUP BY
  AND o.order_status != 'cancelled'
GROUP BY c.customer_segment,
         DATE(strftime('%Y-%m-01', o.order_date))
ORDER BY month DESC, monthly_revenue DESC;


-- ============================================================
-- TASK 3 · HAVING Filtering  (filter groups after aggregation)
-- ============================================================
-- Business goal: "Enterprise customers with >$10k annual
-- spending" — the $10k threshold is an AGGREGATE condition, so
-- it MUST go in HAVING, not WHERE.
--
-- WHY HAVING (not WHERE)?
-- You cannot reference SUM(order_amount) in a WHERE clause
-- because aggregates are computed AFTER WHERE is evaluated.
-- HAVING is evaluated AFTER GROUP BY, when the group totals
-- are available.
-- ============================================================

SELECT
    o.customer_id,
    COUNT(*)                        AS transaction_count,
    ROUND(SUM(o.order_amount), 2)   AS annual_revenue
FROM orders o
WHERE o.order_date   >= '2024-01-01'           -- WHERE: row-level date gate
  AND o.order_status != 'cancelled'
GROUP BY o.customer_id
HAVING SUM(o.order_amount)  > 10000           -- HAVING: high-value customers filter
   AND COUNT(*)              >= 5             -- HAVING: at least 5 purchases
ORDER BY annual_revenue DESC;


-- ============================================================
-- TASK 4 · WHERE + HAVING Combined  (real-world pattern)
-- ============================================================
-- Business goal: Identify high-value customer segments —
-- segments with ≥ 50 unique customers AND total segment
-- revenue > $100k, using only valid 2024 orders.
--
-- Pattern: WHERE cleans the data; HAVING enforces business
-- thresholds on the cleaned, aggregated groups.
-- ============================================================

SELECT
    c.customer_segment                              AS customer_type,
    COUNT(DISTINCT o.customer_id)                  AS segment_customers,
    ROUND(SUM(o.order_amount), 2)                  AS segment_revenue,
    ROUND(AVG(o.order_amount), 2)                  AS avg_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date   >= '2024-01-01'               -- WHERE: valid date window
  AND o.order_status  = 'completed'                -- WHERE: data quality gate
  AND o.order_amount  > 0                          -- WHERE: logical validity
GROUP BY c.customer_segment
HAVING COUNT(DISTINCT o.customer_id) >= 50         -- HAVING: minimum segment size
   AND SUM(o.order_amount)           > 100000      -- HAVING: business revenue threshold
ORDER BY segment_revenue DESC;


-- ============================================================
-- TASK 5 · ORDER BY Ranking + RANK() Window Function
-- ============================================================
-- Business goal: Surface the top 20 customer-segment ×
-- region combinations by revenue, with an explicit rank label.
--
-- RANK() is a window function — it runs AFTER GROUP BY and
-- ORDER BY on the result set.  The outer ORDER BY sorts
-- the final presentation.
-- ============================================================

SELECT
    c.customer_segment                                AS customer_type,
    c.region,
    COUNT(DISTINCT o.customer_id)                     AS customers,
    ROUND(SUM(o.order_amount), 2)                     AS total_revenue,
    ROUND(AVG(o.order_amount), 2)                     AS avg_order,
    RANK() OVER (ORDER BY SUM(o.order_amount) DESC)   AS revenue_rank
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date   >= '2024-01-01'               -- WHERE: row-level filter
  AND o.order_status != 'cancelled'
GROUP BY c.customer_segment, c.region
HAVING COUNT(DISTINCT o.customer_id) >= 10         -- HAVING: minimum group size
ORDER BY total_revenue DESC
LIMIT 20;                                          -- Top 20 segments only
