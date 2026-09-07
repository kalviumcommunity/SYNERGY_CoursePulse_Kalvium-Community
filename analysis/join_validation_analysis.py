# -*- coding: utf-8 -*-
"""
analysis/join_validation_analysis.py
=====================================
SQL Join Strategy & Validation Analysis for CoursePulse / Kalvium Community.

Role     : Data Analyst — Sreedhil Pavishanker B (Member 2)
Branch   : feature/join-validation-analysis

Context
-------
When joining customers (1 000 rows) to orders (5 000 rows) the result can
exceed 1 000 rows because some customers placed multiple orders, and some
order records may reference customer_ids that don't exist in the customers
table (orphaned / "ghost" records).  This script validates every join type
systematically: row counts before and after, unmatched-key investigation,
and documented decisions about what each join type means for analysis.

Tasks Implemented
-----------------
Task 1 : LEFT JOIN with Row Count Validation          (1 mark)
Task 2 : Detect Unmatched Keys                        (1 mark)
Task 3 : Compare Join Types (INNER / LEFT / FULL)     (1 mark)
Task 4 : Multi-Table Join (customers+orders+products) (1 mark)
Task 5 : Document Join Decisions                      (1 mark)

Usage
-----
    python analysis/join_validation_analysis.py

Outputs
-------
    • output/join_validation_report.txt  — Full textual report
    • output/join_type_comparison.csv    — Row-count table for all join types
    • output/unmatched_keys_report.csv   — Customers without orders + orphaned
    • output/multi_table_join_sample.csv — First 50 rows of 3-table join
"""

import os
import sys
import warnings
from typing import Dict, Optional

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.types import Integer, VARCHAR, Float

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# DIRECTORY SETUP
# ---------------------------------------------------------------------------
os.makedirs("output", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

# ---------------------------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------------------------
DB_PATH = "analytics.db"


def get_engine():
    """Return a SQLAlchemy engine connected to the local analytics.db."""
    return create_engine(f"sqlite:///{DB_PATH}")


def _load_raw_tables(engine) -> None:
    """
    Load customers, orders, order_items, and products into the SQLite DB.
    Uses real CSV files if present; otherwise generates deterministic
    synthetic data that matches the described schema.
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    # Drop tables that exist but are empty (stale from previous broken runs)
    with engine.connect() as conn:
        for tbl in list(existing):
            try:
                cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}"')).scalar()
                if cnt == 0:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{tbl}"'))
                    conn.commit()
                    existing.discard(tbl)
                    print(f"  ⚠  Dropped empty table '{tbl}' — will reload.")
            except Exception:
                pass

    # ── customers ────────────────────────────────────────────────────────
    if "customers" not in existing:
        cust_path = "data/raw/customers_1000.csv"
        if os.path.exists(cust_path):
            df_c = pd.read_csv(cust_path)
            # Normalise column names to the schema used by the tasks
            segment_map = {"Enterprise": "Enterprise", "SMB": "SMB",
                           "B2B": "Enterprise", "B2C": "Startup"}
            df_c["customer_type"] = df_c["customer_segment"].map(
                lambda s: segment_map.get(s, s))
            df_c = df_c.rename(columns={"customer_name": "name"})[
                ["customer_id", "name", "customer_type", "region", "signup_date"]]
        else:
            np.random.seed(42)
            n = 1000
            cids = np.arange(1, n + 1)
            ctypes = np.random.choice(
                ["Enterprise", "SMB", "Startup"], size=n, p=[0.20, 0.45, 0.35])
            dates = pd.date_range("2023-01-01", periods=n, freq="D").astype(str)
            regions = np.random.choice(
                ["North", "South", "East", "West", "Central"], size=n)
            df_c = pd.DataFrame({
                "customer_id": cids,
                "name": [f"Customer_{i}" for i in cids],
                "customer_type": ctypes,
                "region": regions,
                "signup_date": dates,
            })
        df_c.to_sql("customers", engine, if_exists="replace", index=False,
                    dtype={"customer_id": Integer(), "name": VARCHAR(120),
                           "customer_type": VARCHAR(50), "region": VARCHAR(50),
                           "signup_date": VARCHAR(10)})
        print(f"  ✓ Loaded {len(df_c)} rows → 'customers'")

    # ── orders ───────────────────────────────────────────────────────────
    if "orders" not in existing:
        ord_path = "data/raw/orders_5000.csv"
        if os.path.exists(ord_path):
            df_o = pd.read_csv(ord_path)[
                ["order_id", "customer_id", "order_amount",
                 "order_status", "order_date"]]
        else:
            np.random.seed(7)
            # 980 unique customers get at least one order; 20 get none
            # Also inject 20 orphaned orders (customer_id > 1000)
            buying_cids = np.random.choice(np.arange(1, 981), size=4980,
                                           replace=True)
            orphan_cids = np.random.randint(1001, 1025, size=20)
            all_cids = np.concatenate([buying_cids, orphan_cids])
            np.random.shuffle(all_cids)
            df_o = pd.DataFrame({
                "order_id": np.arange(50001, 55001),
                "customer_id": all_cids,
                "order_amount": np.round(
                    np.random.uniform(15, 1500, 5000), 2),
                "order_status": np.random.choice(
                    ["completed", "shipped", "pending", "cancelled"],
                    size=5000, p=[0.55, 0.20, 0.15, 0.10]),
                "order_date": pd.date_range(
                    "2024-01-01", periods=5000, freq="h"
                ).strftime("%Y-%m-%d"),
            })
        df_o.to_sql("orders", engine, if_exists="replace", index=False,
                    dtype={"order_id": Integer(), "customer_id": Integer(),
                           "order_amount": Float(), "order_status": VARCHAR(30),
                           "order_date": VARCHAR(10)})
        print(f"  ✓ Loaded {len(df_o)} rows → 'orders'")

    # ── products ─────────────────────────────────────────────────────────
    if "products" not in existing:
        np.random.seed(11)
        n_prod = 500
        categories = np.random.choice(
            ["SaaS", "Hardware", "Support", "Training", "Consulting"], size=n_prod)
        df_p = pd.DataFrame({
            "product_id": np.arange(1, n_prod + 1),
            "product_name": [f"Product_{i}" for i in range(1, n_prod + 1)],
            "category": categories,
            "unit_price": np.round(np.random.uniform(5, 500, n_prod), 2),
        })
        df_p.to_sql("products", engine, if_exists="replace", index=False,
                    dtype={"product_id": Integer(), "product_name": VARCHAR(120),
                           "category": VARCHAR(60), "unit_price": Float()})
        print(f"  ✓ Loaded {len(df_p)} rows → 'products'")

    # ── order_items ──────────────────────────────────────────────────────
    if "order_items" not in existing:
        np.random.seed(17)
        # Query actual order_ids from DB
        order_ids = pd.read_sql("SELECT order_id FROM orders", engine)[
            "order_id"].values
        product_ids = pd.read_sql("SELECT product_id, unit_price FROM products",
                                  engine)

        # Vectorised generation: assign 1-3 items per order (target ~8 000 rows)
        n_orders = len(order_ids)
        items_per_order = np.random.choice([1, 2, 3], size=n_orders, p=[0.55, 0.30, 0.15])
        repeated_order_ids = np.repeat(order_ids, items_per_order)
        n_items = len(repeated_order_ids)

        # Sample products with replacement for each item
        prod_sample_idx = np.random.randint(0, len(product_ids), size=n_items)
        sampled_products = product_ids.iloc[prod_sample_idx].reset_index(drop=True)

        df_oi = pd.DataFrame({
            "item_id": np.arange(1, n_items + 1),
            "order_id": repeated_order_ids,
            "product_id": sampled_products["product_id"].values,
            "quantity": np.random.randint(1, 6, size=n_items),
            "unit_price": sampled_products["unit_price"].values,
        })

        df_oi.to_sql("order_items", engine, if_exists="replace", index=False,
                     dtype={"item_id": Integer(), "order_id": Integer(),
                            "product_id": Integer(), "quantity": Integer(),
                            "unit_price": Float()})
        print(f"  ✓ Loaded {len(df_oi)} rows → 'order_items'")


# ===========================================================================
# TASK 1 : LEFT JOIN WITH ROW COUNT VALIDATION
# ===========================================================================
def task1_left_join_row_count_validation(engine) -> pd.DataFrame:
    """
    Task 1 — LEFT JOIN with Row Count Validation (1 mark).

    Execute a LEFT JOIN of customers → orders, then compare row counts
    before and after to explain why the result set is larger than the
    customer table.

    Returns
    -------
    pd.DataFrame: Aggregated customer-order summary (one row per customer).
    """
    print("\n" + "=" * 70)
    print("TASK 1: LEFT JOIN WITH ROW COUNT VALIDATION")
    print("=" * 70)

    # ── Before join ──────────────────────────────────────────────────────
    customers_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM customers", engine).iloc[0]["cnt"]
    orders_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM orders", engine).iloc[0]["cnt"]

    print(f"\n[Before Join]")
    print(f"  customers table : {customers_count:,} rows")
    print(f"  orders table    : {orders_count:,} rows")

    # ── Execute LEFT JOIN (raw, unexploded) ───────────────────────────────
    raw_join_query = """
        SELECT
            c.customer_id,
            c.customer_type,
            o.order_id,
            o.order_amount
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
    """
    raw_join = pd.read_sql(raw_join_query, engine)
    raw_join_rows = len(raw_join)

    print(f"\n[After LEFT JOIN — raw (one row per order)]")
    print(f"  Joined rows     : {raw_join_rows:,}")
    multiplication = (raw_join_rows - customers_count) / customers_count * 100
    print(f"  Change          : +{raw_join_rows - customers_count:,} rows "
          f"({multiplication:+.1f}%)")
    print(f"\n  WHY IS THE RESULT LARGER?")
    print(f"  → Each customer appears once per ORDER they placed.")
    print(f"    A customer with 8 orders contributes 8 rows to the join.")
    print(f"    Customers with NO orders contribute exactly 1 row (NULLs).")

    # ── Aggregated view — one row per customer ────────────────────────────
    agg_query = """
        SELECT
            c.customer_id,
            c.customer_type,
            COUNT(DISTINCT o.order_id)    AS order_count,
            SUM(o.order_amount)           AS total_spent
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.customer_type
        ORDER BY total_spent DESC
    """
    joined = pd.read_sql(agg_query, engine)

    print(f"\n[Python Validation]")
    print(f"  Before : {customers_count:,} customers")
    print(f"  After  : {len(joined):,} rows  (aggregated — one row per customer)")
    print(f"  Change : {len(joined) - customers_count:+,} "
          f"({(len(joined) - customers_count)/customers_count*100:+.1f}%)")

    # Assert: aggregated result must equal customer count (LEFT keeps all)
    assert len(joined) == customers_count, (
        f"Aggregated join should have {customers_count} rows, got {len(joined)}")
    print(f"  ✓ Assertion passed: aggregated rows == customers ({customers_count})")

    avg_orders = joined["order_count"].mean()
    max_orders = joined["order_count"].max()
    print(f"\n  Orders per customer : avg={avg_orders:.2f}, max={int(max_orders)}")
    print(f"\nTop 10 customers by total spend:")
    print(joined.head(10).to_string(index=False))

    return joined


# ===========================================================================
# TASK 2 : DETECT UNMATCHED KEYS
# ===========================================================================
def task2_detect_unmatched_keys(engine, customers_count: int) -> Dict[str, pd.DataFrame]:
    """
    Task 2 — Detect Unmatched Keys (1 mark).

    Use LEFT JOIN + IS NULL patterns to find:
      • Customers with NO orders  (active accounts, never purchased)
      • Orphaned orders           (orders referencing non-existent customers)

    Returns
    -------
    dict with keys 'no_orders' and 'orphaned'.
    """
    print("\n" + "=" * 70)
    print("TASK 2: DETECT UNMATCHED KEYS")
    print("=" * 70)

    # ── Customers with NO orders ──────────────────────────────────────────
    no_orders_query = """
        SELECT c.customer_id, c.customer_type, c.signup_date
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        WHERE o.order_id IS NULL
        ORDER BY c.signup_date
    """
    no_orders = pd.read_sql(no_orders_query, engine)

    pct_no_orders = len(no_orders) / customers_count * 100
    print(f"\nCustomers WITHOUT any orders : {len(no_orders):,} "
          f"({pct_no_orders:.1f}% of all customers)")

    if len(no_orders) > 0:
        print(f"  → These are 'zero-spend' customers — signed up but never bought.")
        print(f"     Business implication: activation gap, onboarding failure, or")
        print(f"     window-shopping segment that needs targeted nurture campaigns.")
        print("\n  Sample customers without orders:")
        print(no_orders.head(10).to_string(index=False))
    else:
        print("  ✓ Every customer has at least one order — no activation gap.")

    # ── Orphaned orders (no matching customer) ────────────────────────────
    orphaned_query = """
        SELECT o.order_id, o.customer_id, o.order_date, o.order_amount
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
        ORDER BY o.order_date
    """
    orphaned = pd.read_sql(orphaned_query, engine)

    orders_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM orders", engine).iloc[0]["cnt"]
    pct_orphaned = len(orphaned) / orders_count * 100
    print(f"\nOrphaned orders (no matching customer) : {len(orphaned):,} "
          f"({pct_orphaned:.1f}% of all orders)")

    if len(orphaned) > 0:
        print(f"  ⚠️  Orphaned records found — investigate customer_id mismatch.")
        print(f"     Possible causes:")
        print(f"       • Customer records were deleted after order was placed.")
        print(f"       • Data pipeline ingested orders before customer table was synced.")
        print(f"       • Manually entered test / dummy orders with fake customer IDs.")
        orphaned_revenue = orphaned["order_amount"].sum()
        print(f"     Revenue at risk (orphaned orders): ${orphaned_revenue:,.2f}")
        print("\n  Sample orphaned orders:")
        print(orphaned.head(10).to_string(index=False))
    else:
        print("  ✓ No orphaned orders — referential integrity is intact.")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n[Summary — Unmatched Key Report]")
    print(f"  Customers with no orders      : {len(no_orders):,} "
          f"({pct_no_orders:.1f}%)")
    print(f"  Orphaned orders               : {len(orphaned):,} "
          f"({pct_orphaned:.1f}%)")
    print(f"  Data quality decision: {'INVESTIGATE' if len(orphaned) > 0 else 'CLEAN'}")

    return {"no_orders": no_orders, "orphaned": orphaned}


# ===========================================================================
# TASK 3 : COMPARE JOIN TYPES
# ===========================================================================
def task3_compare_join_types(engine) -> pd.DataFrame:
    """
    Task 3 — Compare Join Types (1 mark).

    Execute INNER JOIN, LEFT JOIN, and FULL OUTER JOIN (simulated via
    UNION in SQLite which doesn't natively support FULL OUTER JOIN).
    Compare row counts and explain what each returns.

    Returns
    -------
    pd.DataFrame: Comparison table of join types and row counts.
    """
    print("\n" + "=" * 70)
    print("TASK 3: COMPARE JOIN TYPES")
    print("=" * 70)

    # ── INNER JOIN ────────────────────────────────────────────────────────
    inner_query = """
        SELECT c.customer_id, o.order_id, o.order_amount
        FROM customers c
        INNER JOIN orders o ON c.customer_id = o.customer_id
    """
    inner = pd.read_sql(inner_query, engine)

    # ── LEFT JOIN ─────────────────────────────────────────────────────────
    left_query = """
        SELECT c.customer_id, o.order_id, o.order_amount
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
    """
    left = pd.read_sql(left_query, engine)

    # ── FULL OUTER JOIN (SQLite workaround: LEFT UNION RIGHT via LEFT) ────
    # SQLite does not support FULL OUTER JOIN natively.
    # Equivalent: LEFT JOIN UNION ALL RIGHT-side orphans.
    full_query = """
        SELECT c.customer_id, o.order_id, o.order_amount
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id

        UNION ALL

        SELECT c2.customer_id, o2.order_id, o2.order_amount
        FROM orders o2
        LEFT JOIN customers c2 ON o2.customer_id = c2.customer_id
        WHERE c2.customer_id IS NULL
    """
    full = pd.read_sql(full_query, engine)

    cust_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM customers", engine).iloc[0]["cnt"]

    print(f"\n  {'Join Type':<12} {'Rows':>8}  What it returns")
    print(f"  {'-'*12} {'-'*8}  {'-'*45}")
    print(f"  {'INNER':<12} {len(inner):>8,}  Only customers who have ≥1 order (matched both sides)")
    print(f"  {'LEFT':<12} {len(left):>8,}  All customers + their orders; NULL for no-order customers")
    print(f"  {'FULL OUTER':<12} {len(full):>8,}  All customers + all orders, including orphaned orders")

    # ── Python assertions ─────────────────────────────────────────────────
    assert len(left) >= len(inner), \
        "LEFT JOIN must return ≥ INNER JOIN rows"
    assert len(full) >= max(len(left), cust_count), \
        "FULL JOIN must return ≥ LEFT JOIN rows"
    print(f"\n  ✓ Assertion passed: INNER ≤ LEFT ≤ FULL OUTER")

    # Customers excluded by INNER JOIN (have no orders)
    lost_by_inner = len(left) - len(inner)
    pct_lost = lost_by_inner / len(left) * 100
    print(f"  Rows excluded by INNER JOIN : {lost_by_inner:,} ({pct_lost:.1f}%)")
    print(f"    → These are customers with no orders — lost if you use INNER JOIN")
    print(f"       for customer-level analysis. Use LEFT JOIN to retain them.")

    # Orphaned orders captured only by FULL OUTER
    extra_by_full = len(full) - len(left)
    print(f"  Extra rows in FULL vs LEFT  : {extra_by_full:,}")
    print(f"    → Orphaned orders with no customer match — data quality issue.")

    comparison_df = pd.DataFrame({
        "join_type": ["INNER JOIN", "LEFT JOIN", "FULL OUTER JOIN"],
        "row_count": [len(inner), len(left), len(full)],
        "description": [
            "Matched customers & orders only",
            "All customers + matched orders (NULLs for 0-order customers)",
            "All customers + all orders (includes orphaned order rows)",
        ]
    })
    print(f"\nJoin Comparison Table:")
    print(comparison_df.to_string(index=False))

    return comparison_df


# ===========================================================================
# TASK 4 : MULTI-TABLE JOIN
# ===========================================================================
def task4_multi_table_join(engine) -> pd.DataFrame:
    """
    Task 4 — Multi-Table Join (1 mark).

    Join 4 tables: customers → orders → order_items → products.
    Filter for Enterprise customers, compute line_total, and validate
    that no unexpected row duplication has occurred.

    Returns
    -------
    pd.DataFrame: Enterprise order line-item detail.
    """
    print("\n" + "=" * 70)
    print("TASK 4: MULTI-TABLE JOIN (4 TABLES)")
    print("=" * 70)

    multi_query = """
        SELECT
            c.customer_id,
            c.customer_type,
            o.order_id,
            o.order_date,
            oi.product_id,
            p.product_name,
            oi.quantity,
            oi.unit_price,
            (oi.quantity * oi.unit_price) AS line_total
        FROM customers c
        LEFT JOIN orders     o  ON c.customer_id = o.customer_id
        LEFT JOIN order_items oi ON o.order_id   = oi.order_id
        LEFT JOIN products   p  ON oi.product_id = p.product_id
        WHERE c.customer_type = 'Enterprise'
        ORDER BY o.order_date DESC
    """
    result = pd.read_sql(multi_query, engine)

    print(f"\n  Tables joined   : customers → orders → order_items → products")
    print(f"  Filter          : customer_type = 'Enterprise'")
    print(f"  Result rows     : {len(result):,}")
    print(f"  Columns         : {list(result.columns)}")

    # ── Validate no unexpected duplication ───────────────────────────────
    # Sum of line_total in the joined result should equal
    # the sum computed directly from order_items for enterprise orders.
    enterprise_oi_total_query = """
        SELECT SUM(oi.quantity * oi.unit_price) AS total
        FROM order_items oi
        JOIN orders      o  ON oi.order_id   = o.order_id
        JOIN customers   c  ON o.customer_id = c.customer_id
        WHERE c.customer_type = 'Enterprise'
    """
    expected_total_row = pd.read_sql(enterprise_oi_total_query, engine)
    expected_total = float(expected_total_row.iloc[0]["total"] or 0)
    result_total = float(result["line_total"].sum())

    diff = abs(result_total - expected_total)
    print(f"\n  Duplication Validation:")
    print(f"    line_total from join  : ${result_total:>14,.2f}")
    print(f"    Expected (direct sum) : ${expected_total:>14,.2f}")
    print(f"    Difference            : ${diff:>14,.4f}")

    assert diff < 0.02, \
        f"Duplication detected in multi-join! Diff = {diff:.4f}"
    print(f"  ✓ Multi-table join validated — no duplication detected.")

    # ── Row count walkthrough ─────────────────────────────────────────────
    ent_customers = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM customers WHERE customer_type='Enterprise'",
        engine).iloc[0]["cnt"]
    ent_orders = pd.read_sql(
        """SELECT COUNT(DISTINCT o.order_id) AS cnt
           FROM orders o JOIN customers c ON o.customer_id=c.customer_id
           WHERE c.customer_type='Enterprise'""",
        engine).iloc[0]["cnt"]
    ent_items = pd.read_sql(
        """SELECT COUNT(*) AS cnt
           FROM order_items oi
           JOIN orders o ON oi.order_id=o.order_id
           JOIN customers c ON o.customer_id=c.customer_id
           WHERE c.customer_type='Enterprise'""",
        engine).iloc[0]["cnt"]

    print(f"\n  Row Count Walkthrough (Enterprise segment):")
    print(f"    Enterprise customers          : {ent_customers:,}")
    print(f"    Enterprise orders             : {ent_orders:,}")
    print(f"    Enterprise order-items (rows) : {ent_items:,}")
    print(f"    Multi-join result rows        : {len(result):,}")
    print(f"\n  → Each order fans out to N items; each item is one result row.")
    print(f"     Aggregating at product/order level keeps revenue sums correct.")

    # Preview
    non_null = result.dropna(subset=["order_id"])
    print(f"\nSample (first 10 Enterprise order lines):")
    print(non_null.head(10).to_string(index=False))

    return result


# ===========================================================================
# TASK 5 : DOCUMENT JOIN DECISIONS
# ===========================================================================
def task5_document_join_decisions(engine,
                                  no_orders_count: int,
                                  orphaned_count: int) -> str:
    """
    Task 5 — Document Join Decisions (1 mark).

    Formally documents the join strategy with table sizes, row count
    changes, unmatched key counts, business rationale, and validation
    confirmation for each join step.

    Returns
    -------
    str: The complete join documentation string.
    """
    print("\n" + "=" * 70)
    print("TASK 5: DOCUMENT JOIN DECISIONS")
    print("=" * 70)

    # Fetch live counts for accuracy
    cust_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM customers", engine).iloc[0]["cnt"]
    ord_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM orders", engine).iloc[0]["cnt"]
    oi_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM order_items", engine).iloc[0]["cnt"]
    prod_count = pd.read_sql(
        "SELECT COUNT(*) AS cnt FROM products", engine).iloc[0]["cnt"]

    # After LEFT JOIN customers→orders (raw, unexploded)
    after_left = pd.read_sql(
        """SELECT COUNT(*) AS cnt FROM customers c
           LEFT JOIN orders o ON c.customer_id=o.customer_id""",
        engine).iloc[0]["cnt"]

    # After customers→orders→order_items
    after_3tbl = pd.read_sql(
        """SELECT COUNT(*) AS cnt FROM customers c
           LEFT JOIN orders o ON c.customer_id=o.customer_id
           LEFT JOIN order_items oi ON o.order_id=oi.order_id""",
        engine).iloc[0]["cnt"]

    documentation = f"""
╔══════════════════════════════════════════════════════════════════════╗
║              JOIN STRATEGY DOCUMENTATION                            ║
║              CoursePulse / Kalvium Community Analytics              ║
║              Author : Sreedhil Pavishanker B (Data Analyst)        ║
╚══════════════════════════════════════════════════════════════════════╝

TABLE INVENTORY
═══════════════
  Table         Rows      Primary Key  Foreign Key(s)
  ─────────     ───────   ──────────── ──────────────────
  customers     {cust_count:>7,}   customer_id  —
  orders        {ord_count:>7,}   order_id     customer_id → customers
  order_items   {oi_count:>7,}   item_id      order_id    → orders
  products      {prod_count:>7,}   product_id   —

─────────────────────────────────────────────────────────────────────
Decision 1: customers LEFT JOIN orders
─────────────────────────────────────────────────────────────────────
  Purpose       : Get all customers with their complete order history.
  Join type     : LEFT (keep all customers, even those with no orders).
  Row count     : {cust_count:,} customers → {after_left:,} rows (one row per order placed).
  Multiplication: Each customer appears N times (N = number of orders).
  Unmatched     : {no_orders_count:,} customers have no orders — retained with NULL order fields.
  Business use  : Customer Lifetime Value calculation, activation-gap
                   segmentation, churn risk identification.
  Risk          : Aggregating SUM(order_amount) with GROUP BY customer_id
                   is safe ONLY after the join; do NOT count rows naively.
  Validation    : Aggregated result = {cust_count:,} rows ✓  (one per customer).

─────────────────────────────────────────────────────────────────────
Decision 2: orders LEFT JOIN order_items
─────────────────────────────────────────────────────────────────────
  Purpose       : Expand orders to their individual line items for
                   product-level revenue and inventory analysis.
  Join type     : LEFT (keep all orders, even those with no items — data
                   quality anomaly alert if such orders exist).
  Row count     : {ord_count:,} orders → {oi_count:,} line items (avg items/order ≈ {oi_count/ord_count:.1f}).
  Unmatched     : Ideally 0 — all orders should have items.
                   If non-zero, flag for data quality investigation.
  Business use  : Product revenue ranking, basket analysis, inventory
                   burn-rate, promotion effectiveness measurement.
  Risk          : Summing order_amount from the 'orders' table after
                   this join WILL overcount; always aggregate at the
                   correct grain (order_items.quantity × unit_price).

─────────────────────────────────────────────────────────────────────
Decision 3: Full 3-table join (customers → orders → order_items)
─────────────────────────────────────────────────────────────────────
  Purpose       : End-to-end customer context — who bought what and
                   how much, at line-item granularity.
  Row count     : {cust_count:,} → {after_left:,} → {after_3tbl:,} rows.
  Risk          : Highest fan-out level. Revenue aggregation MUST use
                   (oi.quantity × oi.unit_price) NOT o.order_amount to
                   avoid double-counting when an order has multiple items.
  Solution      : Always aggregate at the item grain or use sub-queries
                   that pre-aggregate at order level before joining.
  Business use  : Full-funnel attribution, customer-product affinity
                   matrix, cohort revenue waterfall.

─────────────────────────────────────────────────────────────────────
Decision 4: 4-table join (+ products)
─────────────────────────────────────────────────────────────────────
  Purpose       : Enrich line-items with product metadata (name, category,
                   list price) for segment and assortment analysis.
  Join type     : LEFT (retain orphaned items even if product was deleted).
  Row count     : Same as 3-table join ({after_3tbl:,}) — products is a 1-to-N
                   lookup that does not create additional fan-out.
  Risk          : Stale product records; always validate unit_price in
                   order_items vs. products.unit_price for consistency.

─────────────────────────────────────────────────────────────────────
ORPHANED RECORDS ANALYSIS
─────────────────────────────────────────────────────────────────────
  Orphaned orders (no customer match): {orphaned_count:,}
  {'⚠️  ACTION REQUIRED: Investigate missing customer records.' if orphaned_count > 0 else '✓  No orphaned records — referential integrity is intact.'}
  Recommendation: Use FULL OUTER JOIN in ETL validation pipelines to
  surface all orphaned rows automatically before they reach analytics.

─────────────────────────────────────────────────────────────────────
VALIDATION SUMMARY
─────────────────────────────────────────────────────────────────────
  [✓] LEFT JOIN row counts match expectations
  [✓] Aggregated customer count = source customer count ({cust_count:,})
  [✓] INNER ≤ LEFT ≤ FULL OUTER join sizes
  [✓] Multi-table join line_total == direct order_items sum (no duplication)
  [✓] Unmatched keys identified, quantified, and flagged for remediation

═══════════════════════════════════════════════════════════════════════
"""

    print(documentation)
    return documentation


# ===========================================================================
# MAIN PIPELINE
# ===========================================================================
def run_pipeline() -> None:
    """Execute all 5 join validation tasks and write outputs."""
    report_lines = []

    print("\n" + "#" * 70)
    print("  COURSEPULSE / KALVIUM COMMUNITY — JOIN VALIDATION ANALYSIS")
    print("  Role: Data Analyst — Sreedhil Pavishanker B")
    print("  Branch: feature/join-validation-analysis")
    print("#" * 70)

    # ── Database setup ────────────────────────────────────────────────────
    engine = get_engine()
    print("\n[0/5] Loading tables into analytics.db …")
    _load_raw_tables(engine)
    print("  ✓ All tables ready.\n")

    customers_count = int(
        pd.read_sql("SELECT COUNT(*) AS cnt FROM customers", engine).iloc[0]["cnt"])

    # ── Task 1 ────────────────────────────────────────────────────────────
    agg_df = task1_left_join_row_count_validation(engine)
    report_lines.append("TASK 1: LEFT JOIN Row Count Validation → PASSED")
    report_lines.append(f"  Customers: {customers_count:,}")
    report_lines.append(f"  Aggregated after LEFT JOIN: {len(agg_df):,} (same as customers)")

    # ── Task 2 ────────────────────────────────────────────────────────────
    unmatched = task2_detect_unmatched_keys(engine, customers_count)
    no_orders_count = len(unmatched["no_orders"])
    orphaned_count = len(unmatched["orphaned"])
    report_lines.append("\nTASK 2: Unmatched Key Detection → COMPLETED")
    report_lines.append(f"  Customers without orders: {no_orders_count:,}")
    report_lines.append(f"  Orphaned orders: {orphaned_count:,}")

    # ── Task 3 ────────────────────────────────────────────────────────────
    comparison_df = task3_compare_join_types(engine)
    report_lines.append("\nTASK 3: Join Type Comparison → PASSED")
    for _, row in comparison_df.iterrows():
        report_lines.append(f"  {row['join_type']:<18}: {row['row_count']:>8,} rows")

    # ── Task 4 ────────────────────────────────────────────────────────────
    multi_df = task4_multi_table_join(engine)
    report_lines.append("\nTASK 4: Multi-Table Join (4 tables) → VALIDATED")
    report_lines.append(f"  Enterprise line-items: {len(multi_df):,} rows")
    report_lines.append("  Duplication check: PASSED (no double-counting)")

    # ── Task 5 ────────────────────────────────────────────────────────────
    documentation = task5_document_join_decisions(
        engine, no_orders_count, orphaned_count)
    report_lines.append("\nTASK 5: Join Documentation → COMPLETE")

    # ── Write outputs ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("WRITING OUTPUTS")
    print("=" * 70)

    # Full report
    report_path = "output/join_validation_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        f.write("\n\n")
        f.write(documentation)
    print(f"  ✓ {report_path}")

    # Join type comparison CSV
    comp_path = "output/join_type_comparison.csv"
    comparison_df.to_csv(comp_path, index=False)
    print(f"  ✓ {comp_path}")

    # Unmatched keys report
    unmatched_out = pd.concat([
        unmatched["no_orders"].assign(issue="customer_no_orders"),
        unmatched["orphaned"].assign(issue="orphaned_order")
    ], ignore_index=True)
    unmatched_path = "output/unmatched_keys_report.csv"
    unmatched_out.to_csv(unmatched_path, index=False)
    print(f"  ✓ {unmatched_path}")

    # Multi-table join sample
    sample_path = "output/multi_table_join_sample.csv"
    multi_df.dropna(subset=["order_id"]).head(50).to_csv(
        sample_path, index=False)
    print(f"  ✓ {sample_path}")

    print(f"\n  All {len(report_lines)} pipeline steps completed successfully.")
    print("\n" + "#" * 70)
    print("  JOIN VALIDATION ANALYSIS COMPLETE")
    print("#" * 70 + "\n")


if __name__ == "__main__":
    run_pipeline()
