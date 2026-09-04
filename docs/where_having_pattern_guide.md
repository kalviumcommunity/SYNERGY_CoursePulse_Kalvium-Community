# WHERE vs HAVING — Team Filter Pattern Guide

**Author:** Sreedhil Pavishanker B · Data Analyst  
**Branch:** `feature/sql-where-having-filters`  
**File:** `docs/where_having_pattern_guide.md`

---

## The Core Question

> *"Enterprise customers with `>$10k` annual spending" — do you filter **before** or **after** grouping? Do you use `WHERE` or `HAVING`?*

**Answer in one sentence:**

> Use **`HAVING SUM(order_amount) > 10000`** — because the `$10k` threshold applies to the *aggregated total per customer*, not to any individual row. Individual rows don't have an annual total; only groups do.

---

## The Golden Rule

| Clause   | Runs…               | Filters…                     | Use when…                                 |
|----------|---------------------|------------------------------|-------------------------------------------|
| `WHERE`  | **Before** GROUP BY | Individual **rows**          | The condition only references column values (no aggregates) |
| `HAVING` | **After** GROUP BY  | Aggregated **groups**        | The condition references `SUM`, `COUNT`, `AVG`, `MIN`, `MAX` |

---

## SQL Execution Order (Memorise This)

```
FROM → JOIN → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT
```

- **`WHERE`** is step 3 — it sees raw rows, before any grouping.
- **`HAVING`** is step 5 — it sees computed group totals, after grouping.
- You **cannot** use `SUM(...)` in a `WHERE` clause. The database will throw an error.

---

## Quick Decision Checklist

Before writing a filter, ask:

1. **Does my condition reference `SUM`, `COUNT`, `AVG`, `MIN`, or `MAX`?**
   - ✅ Yes → `HAVING`
   - ❌ No  → `WHERE`

2. **Am I filtering on a raw column value (date, status, amount of a single row)?**
   - ✅ Yes → `WHERE`
   - ❌ No  → likely `HAVING`

3. **Am I asking about a group total or group count?**
   - ✅ Yes → `HAVING`
   - ❌ No  → `WHERE`

---

## The 5 Query Tasks Explained

### Task 1 — `WHERE` for Data Quality (filter before grouping)

**Goal:** Sum revenue per customer, but exclude refunds and cancelled orders.

```sql
SELECT customer_id, COUNT(*) AS transaction_count,
       ROUND(SUM(order_amount), 2) AS annual_revenue
FROM orders
WHERE order_date   >= '2024-01-01'    -- row-level: date column
  AND order_amount  > 0              -- row-level: amount column
  AND order_status != 'cancelled'    -- row-level: status column
GROUP BY customer_id
ORDER BY annual_revenue DESC;
```

**Why `WHERE`?** All three conditions check values that exist on each individual row. They don't need any group total to be computed first. Filtering here is also faster — the database discards dirty rows before it does any aggregation work.

---

### Task 2 — GROUP BY on Multiple Dimensions with 3+ Aggregates

**Goal:** Monthly revenue breakdown by customer segment.

```sql
SELECT c.customer_segment AS customer_type,
       DATE(strftime('%Y-%m-01', o.order_date)) AS month,
       COUNT(DISTINCT o.customer_id)  AS unique_customers,   -- aggregate 1
       COUNT(*)                        AS transaction_count,  -- aggregate 2
       ROUND(SUM(o.order_amount), 2)   AS monthly_revenue,    -- aggregate 3
       ROUND(AVG(o.order_amount), 2)   AS avg_transaction_value -- aggregate 4
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date >= '2024-01-01'      -- WHERE filter BEFORE GROUP BY
  AND o.order_status != 'cancelled'
GROUP BY c.customer_segment,
         DATE(strftime('%Y-%m-01', o.order_date))   -- 2 GROUP BY dimensions
ORDER BY month DESC, monthly_revenue DESC;
```

**Key learning:** `WHERE` runs first, discarding old/cancelled rows. Only then does `GROUP BY` collapse the remaining rows into one per `(segment, month)` combination.

---

### Task 3 — `HAVING` for the Enterprise `>$10k` Filter

**Goal:** "Enterprise customers with >$10k annual spending."

```sql
SELECT customer_id, COUNT(*) AS transaction_count,
       ROUND(SUM(order_amount), 2) AS annual_revenue
FROM orders
WHERE order_date   >= '2024-01-01'     -- WHERE: quality gate on rows
  AND order_status != 'cancelled'
GROUP BY customer_id
HAVING SUM(order_amount) > 10000      -- HAVING: $10k enterprise threshold
   AND COUNT(*)           >= 5        -- HAVING: meaningful history
ORDER BY annual_revenue DESC;
```

**Why `HAVING` (NOT `WHERE`)?**
- `SUM(order_amount)` is an aggregate — it doesn't exist until after `GROUP BY` runs.
- `WHERE SUM(order_amount) > 10000` is a **syntax error** in standard SQL.
- `HAVING` is evaluated *after* each customer's annual total has been computed.

---

### Task 4 — `WHERE` + `HAVING` Combined (real-world pattern)

**Goal:** High-value segments with ≥50 customers and ≥$100k revenue, from valid 2024 completed orders.

```sql
SELECT c.customer_segment AS customer_type,
       COUNT(DISTINCT o.customer_id)  AS segment_customers,
       ROUND(SUM(o.order_amount), 2)  AS segment_revenue,
       ROUND(AVG(o.order_amount), 2)  AS avg_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date   >= '2024-01-01'         -- WHERE: date window
  AND o.order_status  = 'completed'          -- WHERE: data quality
  AND o.order_amount  > 0                    -- WHERE: logical validity
GROUP BY c.customer_segment
HAVING COUNT(DISTINCT o.customer_id) >= 50   -- HAVING: segment must be significant
   AND SUM(o.order_amount) > 100000          -- HAVING: commercially meaningful
ORDER BY segment_revenue DESC;
```

**Pattern:** `WHERE` cleans the data; `HAVING` enforces business thresholds. Both are needed in most real-world queries.

---

### Task 5 — `ORDER BY` Ranking with `RANK()` Window Function

**Goal:** Top 20 segment × region combinations by revenue, with rank labels.

```sql
SELECT c.customer_segment AS customer_type, c.region,
       COUNT(DISTINCT o.customer_id) AS customers,
       ROUND(SUM(o.order_amount), 2) AS total_revenue,
       ROUND(AVG(o.order_amount), 2) AS avg_order,
       RANK() OVER (ORDER BY SUM(o.order_amount) DESC) AS revenue_rank
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date   >= '2024-01-01'
  AND o.order_status != 'cancelled'
GROUP BY c.customer_segment, c.region
HAVING COUNT(DISTINCT o.customer_id) >= 10
ORDER BY total_revenue DESC
LIMIT 20;
```

**Window function note:** `RANK() OVER (...)` runs *after* `GROUP BY` and `HAVING` have produced the final groups. The outer `ORDER BY` sorts the presentation. `LIMIT 20` keeps it to the top performers.

---

## Common Mistakes to Avoid

| ❌ Wrong                                          | ✅ Correct                                          | Why                                        |
|---------------------------------------------------|-----------------------------------------------------|--------------------------------------------|
| `WHERE SUM(amount) > 10000`                       | `HAVING SUM(amount) > 10000`                        | Aggregates can't be in WHERE               |
| `HAVING order_date >= '2024-01-01'`               | `WHERE order_date >= '2024-01-01'`                  | Raw column values belong in WHERE          |
| `HAVING order_status = 'completed'`               | `WHERE order_status = 'completed'`                  | Status is a row property, not a group property |
| Skipping `WHERE` and only using `HAVING`          | Use `WHERE` for row quality, `HAVING` for thresholds | Better performance; semantic clarity       |

---

## File Map

```
queries/where_having_filter_patterns.sql   ← All 5 SQL queries (standalone, run in DB browser)
scripts/sql_where_having_analysis.py       ← Python pipeline: runs queries + validates + saves CSVs
docs/where_having_pattern_guide.md         ← This guide (team reference documentation)
output/task1_where_filtering.csv           ← Task 1 results
output/task2_groupby_aggregation.csv       ← Task 2 results
output/task3_having_filtering.csv          ← Task 3 results (enterprise >$10k)
output/task4_where_having_combined.csv     ← Task 4 results
output/task5_ranking.csv                   ← Task 5 results
```

---

## How to Run

```bash
# From repo root
python scripts/sql_where_having_analysis.py
```

All results are printed to the console with pattern notes, then saved as CSVs to `output/`.
