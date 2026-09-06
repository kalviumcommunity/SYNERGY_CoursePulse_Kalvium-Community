-- View: vw_revenue_by_region
-- Purpose: Answer "Which regions generate the most valid order revenue?"
-- Grain: one row per customer region and segment.
-- Used by: sales performance and operations dashboards.
-- Revenue excludes cancelled orders and non-positive amounts.

CREATE VIEW vw_revenue_by_region AS
SELECT
    c.region,
    c.customer_segment,
    COUNT(DISTINCT o.order_id) AS order_count,
    ROUND(SUM(o.order_amount), 2) AS total_revenue,
    ROUND(AVG(o.order_amount), 2) AS average_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status IN ('completed', 'shipped', 'delivered')
  AND o.order_amount > 0
GROUP BY c.region, c.customer_segment;