-- queries/monthly_active_users.sql
-- Monthly Active Users with segment breakdown
-- One shared query → one consistent number for all teams
-- NOTE: date window is relative to MAX(order_date) in the dataset
--       so this works correctly on both live and historical data.

SELECT 
    DATE(strftime('%Y-%m-01', o.order_date))      AS month,
    COUNT(DISTINCT o.customer_id)                  AS active_users,
    COUNT(DISTINCT CASE 
        WHEN c.customer_segment = 'Enterprise' 
        THEN o.customer_id END)                    AS enterprise_users,
    COUNT(DISTINCT CASE 
        WHEN c.customer_segment = 'SMB' 
        THEN o.customer_id END)                    AS smb_users,
    COUNT(DISTINCT CASE 
        WHEN c.customer_segment = 'B2B' 
        THEN o.customer_id END)                    AS b2b_users,
    COUNT(DISTINCT CASE 
        WHEN c.customer_segment = 'B2C' 
        THEN o.customer_id END)                    AS b2c_users
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date >= DATE(
        strftime('%Y-%m-01',
            DATE((SELECT MAX(order_date) FROM orders), '-12 months')
        )
      )
GROUP BY DATE(strftime('%Y-%m-01', o.order_date))
ORDER BY month DESC;
