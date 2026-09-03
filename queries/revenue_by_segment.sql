-- queries/revenue_by_segment.sql
-- Revenue breakdown by customer segment per month
-- Canonical single-source query: Finance, Sales, Product, and Accounting all use this

SELECT 
    c.customer_segment                                          AS customer_type,
    DATE(strftime('%Y-%m-01', o.order_date))                  AS month,
    COUNT(DISTINCT o.order_id)                                 AS order_count,
    ROUND(SUM(o.order_amount), 2)                             AS monthly_revenue,
    ROUND(AVG(o.order_amount), 2)                             AS avg_order_value,
    COUNT(DISTINCT o.customer_id)                              AS unique_customers,
    ROUND(SUM(o.order_amount) / COUNT(DISTINCT o.customer_id), 2) AS revenue_per_customer
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date >= DATE(
        strftime('%Y-%m-01',
            DATE((SELECT MAX(order_date) FROM orders), '-12 months')
        )
      )
  AND o.order_status NOT IN ('cancelled')
GROUP BY c.customer_segment,
         DATE(strftime('%Y-%m-01', o.order_date))
ORDER BY month DESC, monthly_revenue DESC;
