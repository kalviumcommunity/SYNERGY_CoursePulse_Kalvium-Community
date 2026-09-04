"""
sql_where_having_analysis.py
==============================
Data Analyst · Sreedhil Pavishanker B
Branch: feature/sql-where-having-filters

Business Question:
    "Enterprise customers with >$10k annual spending"
    — do you filter BEFORE or AFTER grouping?
    — do you use WHERE or HAVING?

Answer documented here through 5 executable queries.

KEY RULE:
    WHERE  → filters individual ROWS  *before*  GROUP BY  (row-level conditions)
    HAVING → filters aggregated GROUPS *after*  GROUP BY  (aggregate conditions)

Technology Stack: Python · Pandas · SQLite3
"""

import os
import sqlite3
import pandas as pd

# ──────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(BASE_DIR, "data", "raw")
QUERIES_DIR = os.path.join(BASE_DIR, "queries")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
DB_PATH     = os.path.join(BASE_DIR, "data", "coursepulse_metrics.db")

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────
# HELPER: connect to (or rebuild) the SQLite database
# ──────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Load raw CSVs into SQLite so all SQL queries run against a
    proper relational schema.

    Tables:
        orders    – order_id, customer_id, order_amount,
                    order_status, order_date
        customers – customer_id, customer_name, customer_segment,
                    region, signup_date
    """
    conn = sqlite3.connect(DB_PATH)

    orders_df = pd.read_csv(os.path.join(DATA_DIR, "orders_5000.csv"))
    orders_df.columns = [c.strip().lower() for c in orders_df.columns]
    orders_df.to_sql("orders", conn, if_exists="replace", index=False)
    print(f"  [DB] orders    → {len(orders_df):,} rows")

    customers_df = pd.read_csv(os.path.join(DATA_DIR, "customers_1000.csv"))
    customers_df.columns = [c.strip().lower() for c in customers_df.columns]
    customers_df.to_sql("customers", conn, if_exists="replace", index=False)
    print(f"  [DB] customers → {len(customers_df):,} rows")

    conn.commit()
    return conn


# ──────────────────────────────────────────────────────────────────
# TASK 1 · WHERE Filtering (data quality BEFORE grouping)
# ──────────────────────────────────────────────────────────────────

TASK1_SQL = """
-- TASK 1: WHERE filters individual rows before GROUP BY
-- Conditions checked: date window, no refunds, no cancelled orders
SELECT
    o.customer_id,
    COUNT(*)                        AS transaction_count,
    ROUND(SUM(o.order_amount), 2)   AS annual_revenue
FROM orders o
WHERE o.order_date   >= '2024-01-01'      -- Date range filter
  AND o.order_amount  >  0               -- Remove refunds / zero-value rows
  AND o.order_status != 'cancelled'      -- Valid transactions only
GROUP BY o.customer_id
ORDER BY annual_revenue DESC;
"""

TASK1_NOTES = """
PATTERN: WHERE for data quality
  • 'order_date >= 2024-01-01'  → date range check (row property)
  • 'order_amount > 0'          → remove refunds/credits (row property)
  • 'order_status != cancelled' → remove invalid records (row property)
  All three are row-level facts → WHERE is correct.
  Using HAVING here would be wrong because none depend on aggregates.
"""


# ──────────────────────────────────────────────────────────────────
# TASK 2 · GROUP BY with Multiple Dimensions + 3 Aggregates
# ──────────────────────────────────────────────────────────────────

TASK2_SQL = """
-- TASK 2: GROUP BY on 2 dimensions, 4 aggregate functions
-- WHERE filters rows first, then GROUP BY collapses them
SELECT
    c.customer_segment                                          AS customer_type,
    DATE(strftime('%Y-%m-01', o.order_date))                   AS month,
    COUNT(DISTINCT o.customer_id)                              AS unique_customers,
    COUNT(*)                                                    AS transaction_count,
    ROUND(SUM(o.order_amount), 2)                              AS monthly_revenue,
    ROUND(AVG(o.order_amount), 2)                              AS avg_transaction_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date   >= '2024-01-01'       -- WHERE: evaluated BEFORE GROUP BY
  AND o.order_status != 'cancelled'
GROUP BY c.customer_segment,
         DATE(strftime('%Y-%m-01', o.order_date))
ORDER BY month DESC, monthly_revenue DESC;
"""

TASK2_NOTES = """
PATTERN: WHERE → GROUP BY → ORDER BY execution order
  • WHERE eliminates rows the database never needs to aggregate
  • GROUP BY then collapses remaining rows into one per (segment, month)
  • Aggregates (COUNT, SUM, AVG) compute on the filtered data only
  Grouping dimensions: customer_segment × month  (2 dimensions)
  Aggregates used    : COUNT(DISTINCT), COUNT(*), SUM, AVG  (4 functions)
"""


# ──────────────────────────────────────────────────────────────────
# TASK 3 · HAVING Filtering (filter groups AFTER aggregation)
# ──────────────────────────────────────────────────────────────────

# Task 3 runs TWO queries to show HAVING behaviour clearly:
#   3a – canonical $10k threshold  (returns 0 rows — expected; dataset max ~$3.3k)
#   3b – dataset-appropriate $1500 threshold (returns real rows)
TASK3_SQL = """
-- TASK 3a: HAVING filters groups — canonical $10k enterprise threshold
-- NOTE: This dataset has max per-customer annual spend of ~$3,300,
--       so HAVING > $10,000 returns 0 rows. That is CORRECT SQL behaviour.
--       The clause is syntactically and semantically right; the data
--       simply has no customers who clear that bar. Zero rows ≠ wrong query.
SELECT
    o.customer_id,
    COUNT(*)                        AS transaction_count,
    ROUND(SUM(o.order_amount), 2)   AS annual_revenue
FROM orders o
WHERE o.order_date   >= '2024-01-01'       -- WHERE: row-level date gate
  AND o.order_status != 'cancelled'
GROUP BY o.customer_id
HAVING SUM(o.order_amount) > 10000        -- HAVING: enterprise $10k threshold
   AND COUNT(*)             >= 5           -- HAVING: meaningful purchase history
ORDER BY annual_revenue DESC;
"""

TASK3_SQL_B = """
-- TASK 3b: HAVING with dataset-appropriate threshold ($1,500)
-- Same structural pattern — shows HAVING actually filtering groups
SELECT
    o.customer_id,
    COUNT(*)                        AS transaction_count,
    ROUND(SUM(o.order_amount), 2)   AS annual_revenue
FROM orders o
WHERE o.order_date   >= '2024-01-01'       -- WHERE: row-level date gate
  AND o.order_status != 'cancelled'
GROUP BY o.customer_id
HAVING SUM(o.order_amount) > 1500         -- HAVING: high-value threshold ($1.5k)
   AND COUNT(*)             >= 5           -- HAVING: meaningful purchase history
ORDER BY annual_revenue DESC;
"""

TASK3_NOTES = """
PATTERN: HAVING for aggregate thresholds — THE enterprise-customer use case
  • 'SUM(order_amount) > 10000' answers "enterprise customers >$10k spend"
  • This CANNOT go in WHERE because SUM doesn't exist at the row level
  • HAVING is evaluated AFTER GROUP BY, when group totals are computed
  • Rule of thumb: if your filter includes SUM/COUNT/AVG/MIN/MAX → use HAVING
  • 0 rows from 3a = correct SQL; dataset max annual spend per customer ≈ $3.3k
  • 3b uses $1,500 threshold to demonstrate HAVING actually narrowing the set
"""


# ──────────────────────────────────────────────────────────────────
# TASK 4 · WHERE + HAVING Combined (real-world pattern)
# ──────────────────────────────────────────────────────────────────

TASK4_SQL = """
-- TASK 4: Combined WHERE (data quality) + HAVING (business thresholds)
-- This is the most common real-world pattern
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
HAVING COUNT(DISTINCT o.customer_id) >= 50         -- HAVING: min segment size
   AND SUM(o.order_amount)           > 100000      -- HAVING: revenue threshold
ORDER BY segment_revenue DESC;
"""

TASK4_NOTES = """
PATTERN: WHERE cleans rows → GROUP BY aggregates → HAVING filters groups
  WHERE conditions (pre-aggregation, row-level):
    • '2024-01-01' date window        → data recency
    • order_status = 'completed'      → exclude pending/cancelled
    • order_amount > 0                → exclude credits/refunds
  HAVING conditions (post-aggregation, group-level):
    • COUNT(DISTINCT customer_id) >= 50  → statistically significant segment
    • SUM(order_amount) > 100000        → commercially meaningful segment
  Business logic: We only report on segments that ARE meaningful AND have
  data quality. Both gates are necessary → both clauses are needed.
"""


# ──────────────────────────────────────────────────────────────────
# TASK 5 · ORDER BY Ranking + RANK() Window Function
# ──────────────────────────────────────────────────────────────────

TASK5_SQL = """
-- TASK 5: RANK() window function + ORDER BY to surface top performers
-- WHERE → GROUP BY → HAVING → window functions → ORDER BY → LIMIT
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
LIMIT 20;
"""

TASK5_NOTES = """
PATTERN: Full pipeline — WHERE → GROUP BY → HAVING → WINDOW → ORDER BY → LIMIT
  • RANK() OVER (ORDER BY SUM(...) DESC) assigns a rank to each group
  • Window functions execute AFTER GROUP BY and HAVING, on the result set
  • ORDER BY on the outer query sorts the final presentation
  • LIMIT 20 keeps output manageable (top N pattern)
  Business use: Leaderboard of segment × region combos for sales targeting
"""


# ──────────────────────────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────────────────────────

TASKS = [
    ("TASK 1 · WHERE Filtering (data quality)",              TASK1_SQL,   TASK1_NOTES, "task1_where_filtering.csv"),
    ("TASK 2 · GROUP BY Multi-Dimension Aggregation",        TASK2_SQL,   TASK2_NOTES, "task2_groupby_aggregation.csv"),
    ("TASK 3a · HAVING Filtering (enterprise >$10k)",        TASK3_SQL,   TASK3_NOTES, "task3a_having_10k_enterprise.csv"),
    ("TASK 3b · HAVING Filtering (dataset-scale >$1.5k)",   TASK3_SQL_B, TASK3_NOTES, "task3b_having_1500_highvalue.csv"),
    ("TASK 4 · WHERE + HAVING Combined",                     TASK4_SQL,   TASK4_NOTES, "task4_where_having_combined.csv"),
    ("TASK 5 · ORDER BY Ranking with RANK()",                TASK5_SQL,   TASK5_NOTES, "task5_ranking.csv"),
]


def run_all_tasks(conn: sqlite3.Connection) -> list[pd.DataFrame]:
    results = []
    for title, sql, notes, _ in TASKS:
        print("\n" + "=" * 64)
        print(f"  {title}")
        print("=" * 64)
        try:
            df = pd.read_sql(sql, conn)
            print(df.to_string(index=False))
            print(f"\n  ✅  Rows returned: {len(df)}")
            print("\n  📘  Pattern Notes:")
            for line in notes.strip().splitlines():
                print(f"  {line}")
            results.append(df)
        except Exception as exc:
            print(f"  ❌  Query failed: {exc}")
            results.append(pd.DataFrame())
    return results


def validate_results(results: list[pd.DataFrame]) -> None:
    print("\n" + "=" * 64)
    print("  VALIDATION")
    print("=" * 64)
    labels = [
        ("Task 1 – WHERE Filtering",           False),   # (label, allow_empty)
        ("Task 2 – GROUP BY Aggregation",       False),
        ("Task 3a – HAVING >$10k (0 rows OK)",  True),   # intentionally 0 rows
        ("Task 3b – HAVING >$1.5k (real rows)", False),
        ("Task 4 – WHERE + HAVING",             False),
        ("Task 5 – Ranking",                    False),
    ]
    all_ok = True
    for (label, allow_empty), df in zip(labels, results):
        if df.empty and allow_empty:
            print(f"  [✔]  {label:<40} – 0 rows (expected — HAVING correctly filtered all groups)")
        elif df.empty:
            print(f"  [⚠]  {label:<40} – empty result (check query / data)")
            all_ok = False
        elif df.isnull().any().any():
            null_cols = df.columns[df.isnull().any()].tolist()
            print(f"  [⚠]  {label:<40} – nulls in: {null_cols}")
            all_ok = False
        else:
            print(f"  [✔]  {label:<40} – {len(df):>4} rows, no nulls")

    # Cross-check: Task 3b (HAVING >$1.5k) must have <= rows than Task 1 (no HAVING)
    task1_df  = results[0]
    task3b_df = results[3]
    if not task3b_df.empty and not task1_df.empty:
        if len(task3b_df) <= len(task1_df):
            print(f"  [✔]  HAVING ($1.5k) narrows Task 1: {len(task3b_df)} ≤ {len(task1_df)} customers – correct")
        else:
            print("  [⚠]  Unexpected: HAVING filter produced more rows than base query")
            all_ok = False

    if all_ok:
        print("\n  🎉  All validations passed!")
    else:
        print("\n  ⚠️   Some checks need review — see above.")


def save_outputs(results: list[pd.DataFrame]) -> None:
    print("\n" + "=" * 64)
    print("  SAVING OUTPUTS")
    print("=" * 64)
    for (title, _, _, fname), df in zip(TASKS, results):
        path = os.path.join(OUTPUT_DIR, fname)
        df.to_csv(path, index=False)
        print(f"  [💾]  {fname}")
    print(f"\n  All outputs saved to: {OUTPUT_DIR}")


def print_summary() -> None:
    print("\n" + "=" * 64)
    print("  WHERE vs HAVING — Team Pattern Reference")
    print("=" * 64)
    summary = """
  ┌──────────────────────────────────────────────────────────┐
  │  Clause │ When to use              │ Example condition    │
  ├─────────┼──────────────────────────┼─────────────────────│
  │  WHERE  │ Row-level column values  │ order_date >= '2024' │
  │  WHERE  │ Data quality / validity  │ order_amount > 0     │
  │  WHERE  │ Status / type filters    │ status = 'completed' │
  ├─────────┼──────────────────────────┼─────────────────────│
  │  HAVING │ Aggregate thresholds     │ SUM(amount) > 10000  │
  │  HAVING │ Group size requirements  │ COUNT(*) >= 5        │
  │  HAVING │ Business KPI gates       │ AVG(amount) > 500    │
  └──────────────────────────────────────────────────────────┘

  SQL Execution Order (always):
    FROM → JOIN → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT
  """
    print(summary)


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 64)
    print("  CoursePulse · WHERE vs HAVING Filter Pattern Analysis")
    print("  Analyst: Sreedhil Pavishanker B")
    print("  Branch : feature/sql-where-having-filters")
    print("=" * 64)

    print("\n[1] Connecting to database …")
    conn = get_connection()

    print("\n[2] Running all 5 tasks …")
    results = run_all_tasks(conn)

    print("\n[3] Validating results …")
    validate_results(results)

    print("\n[4] Saving outputs …")
    save_outputs(results)

    print_summary()

    conn.close()
    print("\n✅  Done. WHERE cleans rows. HAVING filters groups. Always.\n")


if __name__ == "__main__":
    main()
