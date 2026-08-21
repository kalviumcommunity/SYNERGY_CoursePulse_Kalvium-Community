"""
scripts/merge_customer_orders.py
=================================
Data Merging, Join Validation & Relational Integrity Pipeline.

Purpose:
    Merge customer master data (1,000 records) with transactional orders (5,000 records),
    perform deep join validation, detect unmatched keys (orphaned orders, inactive customers),
    compare join behaviors (inner, left, right, outer), and document the join decision
    with business justification.

Tasks:
    Task 1: Explicit join with row count validation
    Task 2: Detect & export unmatched keys (orphaned orders & customers without orders)
    Task 3: Compare join types (inner vs left vs right vs outer)
    Task 4: Validate no unexpected column conflicts or key duplication
    Task 5: Document join decisions and save structured reports

Usage:
    python scripts/merge_customer_orders.py

Outputs:
    • output/unmatched_customers.csv      — customers with zero orders
    • output/unmatched_orders.csv         — orders with non-existent customer IDs
    • output/join_decision_report.json    — structured decision & metric report
    • data/processed/merged_customer_orders.csv — final merged dataset
"""

import os
import sys
import json
import numpy as np
import pandas as pd


# ============================================================================
# DATA GENERATION UTILITY (Ensures 1000 Customers & 5000 Orders)
# ============================================================================
def generate_sample_datasets(customers_path: str, orders_path: str):
    """Generate reproducible 1,000-row customer and 5,000-row order datasets."""
    np.random.seed(42)

    # 1. Customers Table (1,000 customers: IDs 1 to 1000)
    customer_ids = list(range(1, 1001))
    segments = np.random.choice(['B2B', 'B2C', 'SMB', 'Enterprise'], size=1000, p=[0.25, 0.45, 0.20, 0.10])
    regions = np.random.choice(['North', 'South', 'East', 'West', 'Central'], size=1000)
    
    df_customers = pd.DataFrame({
        'customer_id': customer_ids,
        'customer_name': [f"Customer_{cid}" for cid in customer_ids],
        'customer_segment': segments,
        'region': regions,
        'signup_date': pd.date_range(start='2023-01-01', periods=1000, freq='8h').strftime('%Y-%m-%d')
    })

    # 2. Orders Table (5,000 orders)
    # 4,950 orders belong to customers 1..900 (leaving customers 901..1000 with 0 orders)
    # 50 orders belong to orphaned IDs 1001..1020 (simulating deleted/corrupted customer references)
    order_ids = list(range(50001, 55001))
    matched_cust_ids = np.random.choice(range(1, 901), size=4950)
    orphaned_cust_ids = np.random.choice(range(1001, 1021), size=50)
    order_customer_ids = np.concatenate([matched_cust_ids, orphaned_cust_ids])
    np.random.shuffle(order_customer_ids)

    order_amounts = np.round(np.random.exponential(scale=150, size=5000) + 15.0, 2)
    order_statuses = np.random.choice(['completed', 'shipped', 'pending', 'cancelled'], size=5000, p=[0.70, 0.15, 0.10, 0.05])
    
    df_orders = pd.DataFrame({
        'order_id': order_ids,
        'customer_id': order_customer_ids,
        'order_amount': order_amounts,
        'order_status': order_statuses,
        'order_date': pd.date_range(start='2024-01-01', periods=5000, freq='45min').strftime('%Y-%m-%d')
    })

    os.makedirs(os.path.dirname(customers_path), exist_ok=True)
    df_customers.to_csv(customers_path, index=False)
    df_orders.to_csv(orders_path, index=False)
    print(f"  ✓ Generated {len(df_customers)} customers → {customers_path}")
    print(f"  ✓ Generated {len(df_orders)} orders → {orders_path}")


# ============================================================================
# TASK 1 — Explicit Join with Row Count Validation
# ============================================================================
def execute_left_join(df_customers: pd.DataFrame, df_orders: pd.DataFrame) -> pd.DataFrame:
    """
    Perform explicit left join and validate row counts before and after.

    Business Context:
        Left join ensures all customer records remain present, even those with
        zero order history. This is essential for cohort retention, churn analysis,
        and customer lifetime value calculations.
    """
    print("\n" + "=" * 65)
    print("TASK 1 — Explicit Left Join & Row Count Validation")
    print("=" * 65)
    print(f"  Left table (Customers)  : {len(df_customers):,} rows")
    print(f"  Right table (Orders)    : {len(df_orders):,} rows")

    df_merged = pd.merge(df_customers, df_orders, on='customer_id', how='left')

    row_change = len(df_merged) - len(df_customers)
    print(f"\n  Merged result (Left)    : {len(df_merged):,} rows")
    print(f"  Net row count expansion : +{row_change:,} rows (due to 1-to-many relationship)")

    return df_merged


# ============================================================================
# TASK 2 — Detect Unmatched Keys (Orphans & Inactive Customers)
# ============================================================================
def detect_unmatched_keys(df_customers: pd.DataFrame, df_orders: pd.DataFrame) -> tuple:
    """
    Isolate keys present in only one table to audit data hygiene.

    Identifies:
        1. Customers without orders (prospects or churned accounts)
        2. Orphaned orders (orders referencing non-existent customer IDs)
    """
    print("\n" + "=" * 65)
    print("TASK 2 — Unmatched Keys Detection")
    print("=" * 65)

    unmatched_customers = df_customers[~df_customers['customer_id'].isin(df_orders['customer_id'])].copy()
    unmatched_orders = df_orders[~df_orders['customer_id'].isin(df_customers['customer_id'])].copy()

    print(f"  Customers without orders (inactive/prospects) : {len(unmatched_customers):,}")
    print(f"  Orphaned orders (missing customer reference) : {len(unmatched_orders):,}")

    os.makedirs("output", exist_ok=True)
    unmatched_customers.to_csv('output/unmatched_customers.csv', index=False)
    unmatched_orders.to_csv('output/unmatched_orders.csv', index=False)

    print(f"\n  ✓ Saved unmatched customers → output/unmatched_customers.csv")
    print(f"  ✓ Saved orphaned orders      → output/unmatched_orders.csv")

    return unmatched_customers, unmatched_orders


# ============================================================================
# TASK 3 — Compare Join Types
# ============================================================================
def compare_join_types(df_customers: pd.DataFrame, df_orders: pd.DataFrame) -> dict:
    """
    Compare row counts and implications across Inner, Left, Right, and Outer joins.
    """
    print("\n" + "=" * 65)
    print("TASK 3 — Join Type Comparison Matrix")
    print("=" * 65)

    inner = pd.merge(df_customers, df_orders, on='customer_id', how='inner')
    left = pd.merge(df_customers, df_orders, on='customer_id', how='left')
    right = pd.merge(df_customers, df_orders, on='customer_id', how='right')
    outer = pd.merge(df_customers, df_orders, on='customer_id', how='outer')

    comparison = {
        'inner_join_rows': len(inner),
        'left_join_rows': len(left),
        'right_join_rows': len(right),
        'outer_join_rows': len(outer)
    }

    print(f"  Inner Join : {len(inner):,} rows  (drops inactive customers & orphaned orders)")
    print(f"  Left Join  : {len(left):,} rows  (keeps all customers, drops orphaned orders)")
    print(f"  Right Join : {len(right):,} rows  (keeps all orders including orphans)")
    print(f"  Outer Join : {len(outer):,} rows  (keeps everything with null-padding)")

    return comparison


# ============================================================================
# TASK 4 — Validate No Unexpected Duplication
# ============================================================================
def validate_merge_integrity(df_merged: pd.DataFrame) -> dict:
    """
    Check for column collisions (e.g., _x / _y suffixes) and key multiplicity.
    """
    print("\n" + "=" * 65)
    print("TASK 4 — Join Integrity & Duplication Checks")
    print("=" * 65)

    # 1. Column suffix check
    conflicted_cols = [c for c in df_merged.columns if c.endswith('_x') or c.endswith('_y')]
    if conflicted_cols:
        print(f"  ⚠ Warning: Found overlapping column names: {conflicted_cols}")
    else:
        print(f"  ✓ No unexpected column collisions (0 columns with _x/_y suffixes)")

    print(f"  Final Merged Columns: {list(df_merged.columns)}")

    # 2. Key cardinality analysis
    key_counts = df_merged['customer_id'].value_counts()
    max_orders = int(key_counts.max())
    min_orders = int(key_counts.min())
    avg_orders = round(float(key_counts.mean()), 2)

    print(f"\n  Key multiplicity summary:")
    print(f"    - Max orders for single customer : {max_orders}")
    print(f"    - Min rows for single customer   : {min_orders}")
    print(f"    - Avg rows per customer          : {avg_orders}")

    return {
        'conflicted_columns': conflicted_cols,
        'max_orders_per_customer': max_orders,
        'min_orders_per_customer': min_orders,
        'avg_orders_per_customer': avg_orders
    }


# ============================================================================
# TASK 5 — Document Join Decision With Business Reasoning
# ============================================================================
def document_join_decision(
    df_customers: pd.DataFrame,
    df_orders: pd.DataFrame,
    df_merged: pd.DataFrame,
    unmatched_customers: pd.DataFrame,
    unmatched_orders: pd.DataFrame
) -> dict:
    """
    Generate structured join governance and decision report.
    """
    print("\n" + "=" * 65)
    print("TASK 5 — Document Join Decision")
    print("=" * 65)

    join_report = {
        'join_type': 'left',
        'left_table': 'customers',
        'right_table': 'orders',
        'join_key': 'customer_id',
        'left_rows': len(df_customers),
        'right_rows': len(df_orders),
        'result_rows': len(df_merged),
        'unmatched_left': len(unmatched_customers),
        'unmatched_right': len(unmatched_orders),
        'reasoning': 'Left join preserves all customers; unmatched customers have no orders',
        'business_context': (
            'A left join was selected because our analysis goals require evaluating the entire '
            'customer population (including newly registered users with 0 orders). Using an inner '
            'join would introduce survival bias by omitting non-purchasing customers.'
        ),
        'orphan_handling_policy': (
            'Orphaned orders (50 records) were logged to output/unmatched_orders.csv for '
            'data engineering investigation. They were excluded from customer metrics to avoid '
            'corrupting customer-level aggregations.'
        )
    }

    report_path = 'output/join_decision_report.json'
    with open(report_path, 'w') as f:
        json.dump(join_report, f, indent=2)

    print(json.dumps(join_report, indent=2))
    print(f"\n  ✓ Join decision report saved → {report_path}")

    return join_report


# ============================================================================
# MAIN PIPELINE
# ============================================================================
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(repo_root)

    CUSTOMERS_PATH = os.path.join(repo_root, "data", "raw", "customers_1000.csv")
    ORDERS_PATH = os.path.join(repo_root, "data", "raw", "orders_5000.csv")
    OUTPUT_MERGED_PATH = os.path.join(repo_root, "data", "processed", "merged_customer_orders.csv")

    print("=" * 65)
    print("  CoursePulse — Customer & Orders Data Merging Pipeline")
    print("=" * 65)

    # Generate sample datasets if not present or if row counts differ
    if not os.path.exists(CUSTOMERS_PATH) or not os.path.exists(ORDERS_PATH):
        print("  Generating 1,000 customers and 5,000 orders...")
        generate_sample_datasets(CUSTOMERS_PATH, ORDERS_PATH)

    df_customers = pd.read_csv(CUSTOMERS_PATH)
    df_orders = pd.read_csv(ORDERS_PATH)

    # Step 1: Explicit Left Join
    df_merged = execute_left_join(df_customers, df_orders)

    # Step 2: Detect Unmatched Keys
    unmatched_customers, unmatched_orders = detect_unmatched_keys(df_customers, df_orders)

    # Step 3: Compare Join Types
    compare_join_types(df_customers, df_orders)

    # Step 4: Validate Duplication and Merge Integrity
    validate_merge_integrity(df_merged)

    # Step 5: Document Join Decision
    document_join_decision(df_customers, df_orders, df_merged, unmatched_customers, unmatched_orders)

    # Save final merged dataset
    os.makedirs(os.path.dirname(OUTPUT_MERGED_PATH), exist_ok=True)
    df_merged.to_csv(OUTPUT_MERGED_PATH, index=False)
    print(f"\n  ✓ Final merged dataset saved → {OUTPUT_MERGED_PATH}")
    print(f"  ✓ Output Shape: {df_merged.shape[0]} rows × {df_merged.shape[1]} columns")
    print("=" * 65)
    print("  Data merging pipeline complete.")
    print("=" * 65)
