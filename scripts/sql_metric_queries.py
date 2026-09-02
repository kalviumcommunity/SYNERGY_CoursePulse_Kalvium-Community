"""
sql_metric_queries.py
=====================
Data Analyst · Sreedhil Pavishanker B

"Five teams compute Monthly Revenue five different ways.
Write SQL once, store it, everyone uses the same number."

Tasks:
  4 – Load SQL queries from .sql files and execute via pandas + SQLite
  5 – Validate metric results: nulls, ranges, and logical consistency

Technology Stack: Python · Pandas · SQLite3 · SQL (reusable .sql files)
"""

import os
import sqlite3
import pandas as pd

# ──────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERIES_DIR = os.path.join(BASE_DIR, "queries")
DATA_DIR    = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
DB_PATH     = os.path.join(BASE_DIR, "data", "coursepulse_metrics.db")

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# HELPER: Build / connect to SQLite database
# ══════════════════════════════════════════════════════════════

def build_database() -> sqlite3.Connection:
    """
    Load raw CSVs into an in-memory SQLite database so reusable
    SQL queries run against a proper relational schema.

    Tables created:
        customers  – customers_1000.csv  (customer_id, customer_segment, …)
        orders     – orders_5000.csv     (order_id, customer_id, order_amount, …)
    """
    conn = sqlite3.connect(DB_PATH)

    # ── customers ──────────────────────────────────────────────
    customers_path = os.path.join(DATA_DIR, "customers_1000.csv")
    customers_df   = pd.read_csv(customers_path)

    # Normalise column names to what our SQL expects
    customers_df.columns = [c.strip().lower() for c in customers_df.columns]
    # Rename customer_segment → customer_segment (already correct)
    customers_df.to_sql("customers", conn, if_exists="replace", index=False)
    print(f"  [DB] Loaded customers table  → {len(customers_df):,} rows")

    # ── orders ─────────────────────────────────────────────────
    orders_path = os.path.join(DATA_DIR, "orders_5000.csv")
    orders_df   = pd.read_csv(orders_path)
    orders_df.columns = [c.strip().lower() for c in orders_df.columns]
    # Rename columns to match SQL: order_amount, order_date
    orders_df = orders_df.rename(
        columns={"order_amount": "order_amount", "order_date": "order_date"}
    )
    orders_df.to_sql("orders", conn, if_exists="replace", index=False)
    print(f"  [DB] Loaded orders table     → {len(orders_df):,} rows")

    conn.commit()
    return conn


# ══════════════════════════════════════════════════════════════
# TASK 4 · Load and Execute SQL queries from .sql files
# ══════════════════════════════════════════════════════════════

def load_query(query_name: str) -> str:
    """
    Load a SQL query from the queries/ directory by name (no extension needed).

    Args:
        query_name: Filename without .sql extension, e.g. 'monthly_active_users'

    Returns:
        SQL string ready to be passed to pd.read_sql()
    """
    sql_file = os.path.join(QUERIES_DIR, f"{query_name}.sql")
    if not os.path.isfile(sql_file):
        raise FileNotFoundError(
            f"Query file not found: {sql_file}\n"
            f"Available queries: {os.listdir(QUERIES_DIR)}"
        )
    with open(sql_file, "r", encoding="utf-8") as fh:
        return fh.read()


def run_queries(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Execute the three canonical metric queries.
    All teams share the same .sql files → one number, one truth.
    """
    # ── Monthly Active Users ───────────────────────────────────
    mau_query = load_query("monthly_active_users")
    mau        = pd.read_sql(mau_query, conn)
    print("\n" + "═" * 60)
    print("📊  Monthly Active Users  (last 12 months)")
    print("═" * 60)
    print(mau.to_string(index=False))

    # ── Revenue by Segment ────────────────────────────────────
    revenue_query = load_query("revenue_by_segment")
    revenue        = pd.read_sql(revenue_query, conn)
    print("\n" + "═" * 60)
    print("💰  Revenue by Segment  (last 12 months, excl. cancelled)")
    print("═" * 60)
    print(revenue.to_string(index=False))

    # ── Conversion Funnel ─────────────────────────────────────
    funnel_query = load_query("conversion_funnel")
    funnel        = pd.read_sql(funnel_query, conn)
    print("\n" + "═" * 60)
    print("🔁  Conversion Funnel  (last 90 days, daily)")
    print("═" * 60)
    print(funnel.to_string(index=False))

    return mau, revenue, funnel


# ══════════════════════════════════════════════════════════════
# TASK 5 · Validate Metric Results
# ══════════════════════════════════════════════════════════════

def validate_metrics(
    mau_df:     pd.DataFrame,
    revenue_df: pd.DataFrame,
    funnel_df:  pd.DataFrame,
) -> bool:
    """
    Validate computed metric DataFrames for correctness.

    Checks:
      1. Null values   – no column should contain NaN
      2. Value ranges  – revenue > 0, conversion_pct in [0, 100]
      3. Logical consistency – every row must have order_count > 0 and revenue > 0
    """
    print("\n" + "═" * 60)
    print("✅  Validating Metrics …")
    print("═" * 60)

    errors: list[str] = []

    # ── 1. Null Check ─────────────────────────────────────────
    def _check_nulls(df: pd.DataFrame, name: str) -> None:
        null_count = df.isnull().sum().sum()
        if null_count > 0:
            errors.append(f"{name} has {null_count} null value(s):\n{df.isnull().sum()}")
        else:
            print(f"  [✔] {name:<30} – no null values")

    _check_nulls(mau_df,     "MAU DataFrame")
    _check_nulls(revenue_df, "Revenue DataFrame")
    _check_nulls(funnel_df,  "Funnel DataFrame")

    # ── 2. Value Range Checks ──────────────────────────────────
    if "monthly_revenue" in revenue_df.columns:
        bad = revenue_df[revenue_df["monthly_revenue"] <= 0]
        if not bad.empty:
            errors.append(f"Revenue ≤ 0 found in {len(bad)} row(s):\n{bad}")
        else:
            print("  [✔] Revenue values                – all > 0")

    if "conversion_pct" in funnel_df.columns:
        out_of_range = funnel_df[
            (funnel_df["conversion_pct"] < 0) | (funnel_df["conversion_pct"] > 100)
        ]
        if not out_of_range.empty:
            errors.append(
                f"conversion_pct out of [0,100] in {len(out_of_range)} row(s):\n{out_of_range}"
            )
        else:
            print("  [✔] Conversion percentages        – all in [0, 100]")

    if "active_users" in mau_df.columns:
        bad_users = mau_df[mau_df["active_users"] <= 0]
        if not bad_users.empty:
            errors.append(f"active_users ≤ 0 in {len(bad_users)} row(s)")
        else:
            print("  [✔] Active user counts            – all > 0")

    # ── 3. Logical Consistency ────────────────────────────────
    if "order_count" in revenue_df.columns and "monthly_revenue" in revenue_df.columns:
        for idx, row in revenue_df.iterrows():
            if row["order_count"] <= 0:
                errors.append(f"Row {idx}: order_count = {row['order_count']} (must be > 0)")
            if row["monthly_revenue"] <= 0:
                errors.append(f"Row {idx}: monthly_revenue = {row['monthly_revenue']} (must be > 0)")
        if not errors:
            print("  [✔] Revenue row consistency       – order_count & revenue > 0 on all rows")

    # ── Summary ───────────────────────────────────────────────
    print()
    if errors:
        for err in errors:
            print(f"  [✗] {err}")
        raise AssertionError(f"Validation failed with {len(errors)} error(s). See above.")

    print("  🎉  All metrics validated successfully!")
    return True


# ══════════════════════════════════════════════════════════════
# SAVE OUTPUTS
# ══════════════════════════════════════════════════════════════

def save_outputs(
    mau_df:     pd.DataFrame,
    revenue_df: pd.DataFrame,
    funnel_df:  pd.DataFrame,
) -> None:
    """Persist query results to CSV for downstream consumption."""
    mau_df.to_csv(    os.path.join(OUTPUT_DIR, "sql_monthly_active_users.csv"),  index=False)
    revenue_df.to_csv(os.path.join(OUTPUT_DIR, "sql_revenue_by_segment.csv"),    index=False)
    funnel_df.to_csv( os.path.join(OUTPUT_DIR, "sql_conversion_funnel.csv"),     index=False)
    print("\n  [💾] Outputs saved to output/")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 60)
    print("  CoursePulse · SQL Metric Queries")
    print("  Analyst: Sreedhil Pavishanker B")
    print("=" * 60)

    # Step 1 – Build SQLite DB from raw CSVs
    print("\n[1] Building database …")
    conn = build_database()

    # Step 2 – Load .sql files and execute (Task 4)
    print("\n[2] Running queries from queries/ …")
    mau, revenue, funnel = run_queries(conn)

    # Step 3 – Validate results (Task 5)
    print("\n[3] Validating results …")
    validate_metrics(mau, revenue, funnel)

    # Step 4 – Save outputs
    print("\n[4] Saving outputs …")
    save_outputs(mau, revenue, funnel)

    conn.close()
    print("\n✅ Done. One definition. One truth. All teams aligned.\n")


if __name__ == "__main__":
    main()
