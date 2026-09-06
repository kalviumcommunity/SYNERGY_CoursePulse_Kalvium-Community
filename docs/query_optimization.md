# Analytical SQL Query Optimisation

This submission implements the three optimisation patterns from the assignment against the repository's actual CoursePulse schema. The available tables are `orders` and `customers`; the assignment's illustrative `transactions` and `products` names do not exist in this dataset.

## Run

```bash
python scripts/query_optimization.py
python -m unittest scripts/test_query_optimization.py
```

The runner writes `output/query_optimization_comparison.csv` and the measured report `docs/query_optimization_results.md`.

## Refactoring summary

| Task | Original issue | Refactoring | Validation |
| --- | --- | --- | --- |
| 1 | `SELECT *` fetched all columns | Selected seven business fields explicitly | Core order/customer data is equivalent |
| 2 | Joins occurred before order-row filters | `filtered_orders` CTE applies date and amount filters first | Row counts and final results are compared |
| 3 | Nested subqueries obscured each logical stage | `recent_orders`, `customer_order_metrics`, and `segment_metrics` CTEs | CTE query matches the original result |

## Follow-up answers

An index on a high-cardinality filter column lets the database seek to qualifying rows rather than scan the entire table. It consumes storage and makes writes more expensive because the index must be updated. Index usefulness should be confirmed with `EXPLAIN QUERY PLAN` on production-shaped data.

CTEs are not universally cached. SQLite and other databases may inline or materialize them depending on the optimizer and query shape. Repeated intermediate results should be checked with the execution plan; explicit materialization or a temporary table is appropriate when repeated computation is costly.

If filtering still leaves 100 million rows, use date partitioning, materialized views, pre-aggregated reporting tables, covering indexes, and execution-plan-guided join/order changes.