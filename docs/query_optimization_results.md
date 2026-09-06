# Analytical SQL Query Optimisation Results

The benchmark uses the repository's SQLite CoursePulse dataset: 5,000 orders and 1,000 customers.
SQLite execution time is hardware-dependent; row counts and result-equivalence checks are deterministic.

                               Metric                 Original          Optimized
           Columns selected (Query 1)              all columns 7 explicit columns
            Rows in full orders table                     5000               5000
            Rows after Query 2 filter not measured before join               2830
        Intermediate reduction factor             not measured              1.77x
Filters applied before join (Query 2)                       No                Yes
              Nesting depth (Query 3)          3 nested levels  3 named CTE steps
                   Query 1 elapsed ms                    1.722              1.176
                   Query 2 elapsed ms                     1.28              1.241
                   Query 3 elapsed ms                    2.223              1.929

## Validation
- Query 1 core data matches: PASS
- Query 2 results match: PASS
- Query 3 results match: PASS

## Query 1 improvement
The original SELECT * returned every column. The optimized query selects seven fields that answer order, revenue, customer, segment, and regional reporting questions. This reduces transfer and dataframe memory when the source schema grows.

## Query 2 improvement
The filtered_orders CTE reduces the join input from 5,000 rows to 2,830 rows (1.77x smaller) before the customer join.

## Query 3 improvement
The CTE version names the date filter, customer-level metrics, and segment aggregation. Each stage can be run independently for debugging and validation.

## Follow-up answers
1. An index on a frequently filtered high-cardinality column can locate qualifying rows without scanning the full table. The tradeoff is extra disk space and slower INSERT/UPDATE operations because the index must be maintained. For this dataset, an index on orders(order_date, order_amount) is worth testing with EXPLAIN QUERY PLAN.
2. CTE materialization is database- and version-dependent. SQLite may inline a CTE or materialize it; it does not guarantee caching merely because a CTE is referenced. When repeated reuse matters, inspect the plan and consider MATERIALIZED where supported or a temporary/materialized table.
3. For a still-large filtered dataset, use partitioning by date, materialized views or summary tables, pre-aggregation, covering indexes, and EXPLAIN-based join/order improvements. These reduce the data scanned or recomputed beyond column selection.
