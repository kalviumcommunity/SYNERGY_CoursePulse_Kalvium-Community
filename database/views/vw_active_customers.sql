-- View: vw_active_customers
-- Purpose: One customer-activity definition for retention and engagement dashboards.
-- Grain: one row per customer; activity is measured in the 30 days before the
-- latest order in this dataset so local runs remain reproducible.
-- Updated: automatically whenever the view is queried.

CREATE VIEW vw_active_customers AS
SELECT
    c.customer_id,
    c.customer_name,
    c.customer_segment,
    COUNT(DISTINCT o.order_id) AS order_count_30d,
    COALESCE(ROUND(SUM(o.order_amount), 2), 0.0) AS revenue_30d,
    MAX(o.order_date) AS last_order_date,
    CASE
        WHEN MAX(o.order_date) IS NULL THEN NULL
        ELSE CAST(julianday((SELECT MAX(order_date) FROM orders)) - julianday(MAX(o.order_date)) AS INTEGER)
    END AS days_since_order
FROM customers c
LEFT JOIN orders o
    ON c.customer_id = o.customer_id
   AND o.order_status IN ('completed', 'shipped', 'delivered')
   AND o.order_date >= date((SELECT MAX(order_date) FROM orders), '-30 days')
GROUP BY c.customer_id, c.customer_name, c.customer_segment;