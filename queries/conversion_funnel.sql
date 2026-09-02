-- queries/conversion_funnel.sql
-- Daily conversion funnel: signup → verified → first purchase
-- Uses conditional CASE WHEN counting and percentage conversion rate

SELECT 
    DATE(c.signup_date)                               AS signup_date,
    COUNT(*)                                           AS signups,
    COUNT(CASE 
        WHEN c.signup_date IS NOT NULL 
        THEN 1 END)                                    AS email_verified,
    COUNT(CASE 
        WHEN o.first_purchase_date IS NOT NULL 
        THEN 1 END)                                    AS first_purchase,
    ROUND(
        100.0 * COUNT(CASE WHEN o.first_purchase_date IS NOT NULL THEN 1 END)
        / NULLIF(COUNT(*), 0),
        1
    )                                                  AS conversion_pct
FROM customers c
LEFT JOIN (
    -- Compute the earliest order date per customer as their "first purchase"
    SELECT 
        customer_id,
        MIN(order_date) AS first_purchase_date
    FROM orders
    WHERE order_status NOT IN ('cancelled')
    GROUP BY customer_id
) o ON c.customer_id = o.customer_id
WHERE c.signup_date >= DATE(
        (SELECT MAX(signup_date) FROM customers), '-90 days'
      )
GROUP BY DATE(c.signup_date)
ORDER BY signup_date DESC;
