"""Benchmark and validate the three analytical SQL optimisations.

The project dataset models transactions as ``orders`` and customer attributes
as ``customers``.  There is no products table, so Query 2 uses the available
orders/customers join while preserving the assignment's early-filter pattern.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = BASE_DIR / "data" / "coursepulse_metrics.db"


ORIGINAL_QUERY_1 = """
SELECT *
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE strftime('%Y', o.order_date) = '2024'
LIMIT 1000;
"""

OPTIMIZED_QUERY_1 = """
SELECT
    o.order_id,                 -- Which order was placed?
    o.order_date,               -- When did it happen?
    o.order_amount,             -- What was its revenue value?
    o.customer_id,              -- Which customer generated it?
    c.customer_name,            -- Who is the customer?
    c.customer_segment,         -- Which customer segment should be reported?
    c.region                    -- Where is the customer located?
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date >= '2024-01-01'
  AND o.order_date < '2025-01-01'
LIMIT 1000;
"""

ORIGINAL_QUERY_2 = """
SELECT o.order_id, o.order_amount, c.customer_name
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date >= '2024-01-01'
  AND o.order_amount > 100
  AND c.region = 'West'
LIMIT 5000;
"""

OPTIMIZED_QUERY_2 = """
WITH filtered_orders AS (
    SELECT order_id, customer_id, order_amount
    FROM orders
    WHERE order_date >= '2024-01-01'
      AND order_amount > 100
)
SELECT fo.order_id, fo.order_amount, c.customer_name
FROM filtered_orders fo
JOIN customers c ON fo.customer_id = c.customer_id
WHERE c.region = 'West'
LIMIT 5000;
"""

ORIGINAL_QUERY_3 = """
SELECT customer_segment, AVG(revenue_per_customer) AS avg_transaction_value
FROM (
    SELECT c.customer_segment, AVG(o.order_amount) AS revenue_per_customer,
           COUNT(DISTINCT o.order_id) AS transaction_count
    FROM (
        SELECT order_id, order_amount, customer_id
        FROM orders
        WHERE order_date >= '2024-01-01'
    ) o
    JOIN customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_segment, c.customer_id
) grouped
GROUP BY customer_segment
ORDER BY avg_transaction_value DESC;
"""

OPTIMIZED_QUERY_3 = """
WITH recent_orders AS (
    -- Step 1: keep only the reporting period and required columns.
    SELECT order_id, order_amount, customer_id
    FROM orders
    WHERE order_date >= '2024-01-01'
),
customer_order_metrics AS (
    -- Step 2: calculate one independently testable row per customer.
    SELECT
        ro.order_id,
        ro.order_amount,
        c.customer_id,
        c.customer_segment
    FROM recent_orders ro
    JOIN customers c ON ro.customer_id = c.customer_id
),
segment_metrics AS (
    -- Step 3: preserve the original average-of-customer-averages semantics.
    SELECT
        customer_segment,
        customer_id,
        AVG(order_amount) AS revenue_per_customer
    FROM customer_order_metrics
    GROUP BY customer_segment, customer_id
)
SELECT
    customer_segment,
    AVG(revenue_per_customer) AS avg_transaction_value
FROM segment_metrics
GROUP BY customer_segment
ORDER BY avg_transaction_value DESC;
"""


def build_connection() -> sqlite3.Connection:
    """Load the project CSVs into a repeatable SQLite database connection."""
    connection = sqlite3.connect(DB_PATH)
    customers = pd.read_csv(DATA_DIR / "customers_1000.csv")
    orders = pd.read_csv(DATA_DIR / "orders_5000.csv")
    customers.to_sql("customers", connection, if_exists="replace", index=False)
    orders.to_sql("orders", connection, if_exists="replace", index=False)
    return connection


def execute_timed(query: str, connection: sqlite3.Connection) -> tuple[pd.DataFrame, float]:
    """Execute SQL and return its result plus elapsed wall-clock milliseconds."""
    started = time.perf_counter()
    result = pd.read_sql_query(query, connection)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return result, elapsed_ms


def compare_frames(original: pd.DataFrame, optimized: pd.DataFrame) -> bool:
    """Compare result sets without depending on row order or pandas dtypes."""
    left = original.sort_values(list(original.columns)).reset_index(drop=True)
    right = optimized.sort_values(list(optimized.columns)).reset_index(drop=True)
    return left.equals(right)


def run_benchmark(connection: sqlite3.Connection) -> tuple[pd.DataFrame, str]:
    """Run all assignment tasks and return the summary table and report text."""
    q1_original, q1_original_ms = execute_timed(ORIGINAL_QUERY_1, connection)
    q1_optimized, q1_optimized_ms = execute_timed(OPTIMIZED_QUERY_1, connection)
    q2_original, q2_original_ms = execute_timed(ORIGINAL_QUERY_2, connection)
    q2_optimized, q2_optimized_ms = execute_timed(OPTIMIZED_QUERY_2, connection)
    q3_original, q3_original_ms = execute_timed(ORIGINAL_QUERY_3, connection)
    q3_optimized, q3_optimized_ms = execute_timed(OPTIMIZED_QUERY_3, connection)

    transactions_count = int(pd.read_sql_query("SELECT COUNT(*) AS count FROM orders", connection).iloc[0, 0])
    filtered_count = int(pd.read_sql_query(
        "SELECT COUNT(*) AS count FROM orders WHERE order_date >= '2024-01-01' AND order_amount > 100",
        connection,
    ).iloc[0, 0])
    reduction_factor = transactions_count / filtered_count if filtered_count else float("inf")

    # SELECT * contains two customer_id columns after the join. Select by
    # position here so pandas does not interpret the duplicate label twice.
    q1_original_core = q1_original.iloc[:, [0, 4, 2, 1, 6, 7, 8]].copy()
    q1_original_core.columns = q1_optimized.columns
    checks = {
        "Query 1 core data matches": q1_original_core.equals(q1_optimized),
        "Query 2 results match": compare_frames(q2_original, q2_optimized),
        "Query 3 results match": compare_frames(q3_original, q3_optimized),
    }
    if not all(checks.values()):
        raise AssertionError(f"Result equivalence failed: {checks}")

    summary = pd.DataFrame({
        "Metric": [
            "Columns selected (Query 1)", "Rows in full orders table", "Rows after Query 2 filter",
            "Intermediate reduction factor", "Filters applied before join (Query 2)",
            "Nesting depth (Query 3)", "Query 1 elapsed ms", "Query 2 elapsed ms", "Query 3 elapsed ms",
        ],
        "Original": ["all columns", transactions_count, "not measured before join", "not measured", "No", "3 nested levels", round(q1_original_ms, 3), round(q2_original_ms, 3), round(q3_original_ms, 3)],
        "Optimized": ["7 explicit columns", transactions_count, filtered_count, f"{reduction_factor:.2f}x", "Yes", "3 named CTE steps", round(q1_optimized_ms, 3), round(q2_optimized_ms, 3), round(q3_optimized_ms, 3)],
    })
    report = "\n".join([
        "# Analytical SQL Query Optimisation Results",
        "",
        "The benchmark uses the repository's SQLite CoursePulse dataset: 5,000 orders and 1,000 customers.",
        "SQLite execution time is hardware-dependent; row counts and result-equivalence checks are deterministic.",
        "",
        summary.to_string(index=False),
        "",
        "## Validation",
        *[f"- {name}: PASS" for name in checks],
        "",
        "## Query 1 improvement",
        "The original SELECT * returned every column. The optimized query selects seven fields that answer order, revenue, customer, segment, and regional reporting questions. This reduces transfer and dataframe memory when the source schema grows.",
        "",
        "## Query 2 improvement",
        f"The filtered_orders CTE reduces the join input from {transactions_count:,} rows to {filtered_count:,} rows ({reduction_factor:.2f}x smaller) before the customer join.",
        "",
        "## Query 3 improvement",
        "The CTE version names the date filter, customer-level metrics, and segment aggregation. Each stage can be run independently for debugging and validation.",
        "",
        "## Follow-up answers",
        "1. An index on a frequently filtered high-cardinality column can locate qualifying rows without scanning the full table. The tradeoff is extra disk space and slower INSERT/UPDATE operations because the index must be maintained. For this dataset, an index on orders(order_date, order_amount) is worth testing with EXPLAIN QUERY PLAN.",
        "2. CTE materialization is database- and version-dependent. SQLite may inline a CTE or materialize it; it does not guarantee caching merely because a CTE is referenced. When repeated reuse matters, inspect the plan and consider MATERIALIZED where supported or a temporary/materialized table.",
        "3. For a still-large filtered dataset, use partitioning by date, materialized views or summary tables, pre-aggregation, covering indexes, and EXPLAIN-based join/order improvements. These reduce the data scanned or recomputed beyond column selection.",
    ])
    return summary, report


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    connection = build_connection()
    try:
        summary, report = run_benchmark(connection)
        summary.to_csv(OUTPUT_DIR / "query_optimization_comparison.csv", index=False)
        (BASE_DIR / "docs" / "query_optimization_results.md").write_text(report + "\n", encoding="utf-8")
        print(report)
    finally:
        connection.close()


if __name__ == "__main__":
    main()