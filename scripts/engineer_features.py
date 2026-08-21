"""
scripts/engineer_features.py
=============================
Business Feature Engineering Pipeline for CoursePulse / Kalvium Community.

Purpose:
    Transform raw transaction and customer summary data into high-value business features:
    - Task 1: Ratio features (transactions_per_month, avg_spend_per_transaction, lifetime_value_per_month)
    - Task 2: Binning with cut (engagement_tier: low, medium, high)
    - Task 3: Quantile binning with qcut (spend_quartile: Q1, Q2, Q3, Q4)
    - Task 4: Composite scoring (RFM health score combining Recency, Frequency, Monetary quartiles/quintiles)
    - Task 5: Feature validation & distribution verification

Usage:
    python scripts/engineer_features.py

Outputs:
    • output/feature_engineering_report.json — summary metrics and distribution stats
    • data/processed/customer_features.csv   — final dataset with engineered features
"""

import os
import sys
import json
import numpy as np
import pandas as pd


# ============================================================================
# DATA GENERATOR (If input raw dataset doesn't exist)
# ============================================================================
def generate_sample_data(filepath: str) -> pd.DataFrame:
    """Generate realistic customer transaction summary data."""
    np.random.seed(42)
    n_customers = 500

    customer_ids = list(range(1, n_customers + 1))
    days_as_customer = np.random.randint(30, 730, size=n_customers) # 1 month to 2 years
    
    # Days since last purchase must be <= days as customer
    days_since_last = [np.random.randint(1, max(2, int(d * 0.8))) for d in days_as_customer]
    
    # Transactions scale with tenure plus noise
    total_tx = np.maximum(1, np.random.poisson(lam=12, size=n_customers))
    
    # Spend scales with transactions
    avg_ticket = np.random.uniform(25.0, 180.0, size=n_customers)
    total_spent = np.round(total_tx * avg_ticket, 2)

    df = pd.DataFrame({
        'customer_id': customer_ids,
        'customer_name': [f"Customer_{cid}" for cid in customer_ids],
        'total_transactions': total_tx,
        'purchase_count': total_tx, # alias for frequency
        'total_spent': total_spent,
        'days_as_customer': days_as_customer,
        'days_since_last_purchase': days_since_last
    })

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created synthetic customer transactions data → {filepath}")
    return df


# ============================================================================
# TASK 1 — Compute Ratio Features
# ============================================================================
def compute_ratio_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate rate, average, and velocity ratio metrics.

    Features:
        - transactions_per_month    : total_transactions / (days_as_customer / 30)
        - avg_spend_per_transaction : total_spent / total_transactions
        - lifetime_value_per_month  : total_spent / (days_as_customer / 30)
    """
    print("\n" + "=" * 65)
    print("TASK 1 — Compute Ratio Features")
    print("=" * 65)

    df = df.copy()

    # Tenure in months (avoid division by zero)
    months_as_customer = np.maximum(df['days_as_customer'] / 30.0, 0.1)
    
    df['transactions_per_month'] = np.round(df['total_transactions'] / months_as_customer, 2)
    df['avg_spend_per_transaction'] = np.round(df['total_spent'] / df['total_transactions'], 2)
    df['lifetime_value_per_month'] = np.round(df['total_spent'] / months_as_customer, 2)

    print("\n  Statistical Summary of Ratio Features:")
    print(df[['transactions_per_month', 'avg_spend_per_transaction', 'lifetime_value_per_month']].describe().round(2))

    return df


# ============================================================================
# TASK 2 — Binning with Custom/Equal-Width Bins (pd.cut)
# ============================================================================
def bin_engagement_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Categorize customers into engagement tiers based on monthly transaction velocity.

    Bins:
        - low    : 0 to 2 transactions/month
        - medium : 2 to 10 transactions/month
        - high   : >10 transactions/month
    """
    print("\n" + "=" * 65)
    print("TASK 2 — Engagement Tier Binning (pd.cut)")
    print("=" * 65)

    df = df.copy()

    df['engagement_tier'] = pd.cut(
        df['transactions_per_month'],
        bins=[0, 2, 10, float('inf')],
        labels=['low', 'medium', 'high'],
        include_lowest=True
    )

    print("\n  Engagement Tier Distribution:")
    print(df['engagement_tier'].value_counts(dropna=False))

    return df


# ============================================================================
# TASK 3 — Binning with Quantiles (pd.qcut)
# ============================================================================
def bin_spend_quartiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Segment total spend into 4 balanced quartiles.

    Quartiles:
        - Q1: Bottom 25% spenders
        - Q2: 25% - 50%
        - Q3: 50% - 75%
        - Q4: Top 25% high-value spenders
    """
    print("\n" + "=" * 65)
    print("TASK 3 — Spend Quartiles Binning (pd.qcut)")
    print("=" * 65)

    df = df.copy()

    df['spend_quartile'] = pd.qcut(
        df['total_spent'],
        q=4,
        labels=['Q1', 'Q2', 'Q3', 'Q4']
    )

    print("\n  Spend Quartile Distribution:")
    print(df['spend_quartile'].value_counts().sort_index())

    return df


# ============================================================================
# TASK 4 — Composite RFM Health Score
# ============================================================================
def compute_rfm_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate composite RFM (Recency, Frequency, Monetary) Customer Health Score.

    Components:
        - Recency  : Lower days since last purchase = higher score (5 to 1)
        - Frequency: Higher purchase count = higher score (1 to 5)
        - Monetary : Higher total spend = higher score (1 to 5)
        - RFM Score: Sum of R + F + M (range 3 to 15)
    """
    print("\n" + "=" * 65)
    print("TASK 4 — Composite RFM Health Score")
    print("=" * 65)

    df = df.copy()

    # Recency: 5 is most recent (lowest days), 1 is least recent (highest days)
    df['recency_score'] = pd.qcut(
        df['days_since_last_purchase'].rank(method='first'),
        q=5,
        labels=[5, 4, 3, 2, 1]
    )

    # Frequency: 5 is highest transactions
    df['frequency_score'] = pd.qcut(
        df['purchase_count'].rank(method='first'),
        q=5,
        labels=[1, 2, 3, 4, 5]
    )

    # Monetary: 5 is highest spend
    df['monetary_score'] = pd.qcut(
        df['total_spent'].rank(method='first'),
        q=5,
        labels=[1, 2, 3, 4, 5]
    )

    df['rfm_score'] = (
        df['recency_score'].astype(int) +
        df['frequency_score'].astype(int) +
        df['monetary_score'].astype(int)
    )

    print(f"  RFM Score Range : {df['rfm_score'].min()} (min) to {df['rfm_score'].max()} (max)")
    print(f"  RFM Score Mean  : {df['rfm_score'].mean():.2f}")

    return df


# ============================================================================
# TASK 5 — Feature Validation & Export
# ============================================================================
def validate_and_export_features(df: pd.DataFrame, output_csv: str, output_report: str) -> dict:
    """
    Validate engineered features for missing values, out-of-bounds metrics,
    and generate structured validation summary.
    """
    print("\n" + "=" * 65)
    print("TASK 5 — Feature Validation & Export")
    print("=" * 65)

    feature_cols = ['transactions_per_month', 'avg_spend_per_transaction', 'lifetime_value_per_month',
                    'engagement_tier', 'spend_quartile', 'rfm_score']

    null_counts = df[feature_cols].isna().sum().to_dict()
    print("  Missing values in engineered features:")
    for col, cnt in null_counts.items():
        print(f"    - {col:<26}: {cnt} missing")

    # Generate JSON report
    report = {
        'total_customers_processed': len(df),
        'engineered_features': feature_cols,
        'rfm_score_stats': {
            'min': int(df['rfm_score'].min()),
            'max': int(df['rfm_score'].max()),
            'mean': round(float(df['rfm_score'].mean()), 2),
            'median': float(df['rfm_score'].median())
        },
        'engagement_tier_breakdown': df['engagement_tier'].value_counts().to_dict(),
        'spend_quartile_breakdown': df['spend_quartile'].value_counts().to_dict(),
        'missing_value_check': null_counts,
        'validation_status': 'PASS' if sum(null_counts.values()) == 0 else 'FAIL'
    }

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    os.makedirs(os.path.dirname(output_report), exist_ok=True)

    df.to_csv(output_csv, index=False)
    with open(output_report, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n  ✓ Engineered features saved → {output_csv}")
    print(f"  ✓ Feature report saved     → {output_report}")
    print(f"  ✓ Validation Status: {report['validation_status']}")

    return report


# ============================================================================
# MAIN PIPELINE
# ============================================================================
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(repo_root)

    INPUT_FILE = os.path.join(repo_root, "data", "raw", "customer_transactions_summary.csv")
    OUTPUT_CSV = os.path.join(repo_root, "data", "processed", "customer_features.csv")
    OUTPUT_REPORT = os.path.join(repo_root, "output", "feature_engineering_report.json")

    print("=" * 65)
    print("  CoursePulse — Feature Engineering Pipeline")
    print("=" * 65)

    if not os.path.exists(INPUT_FILE):
        df_raw = generate_sample_data(INPUT_FILE)
    else:
        df_raw = pd.read_csv(INPUT_FILE)

    print(f"  Loaded {len(df_raw)} customer records.")

    # Step 1: Ratio Features
    df = compute_ratio_features(df_raw)

    # Step 2: Binning with cut
    df = bin_engagement_tiers(df)

    # Step 3: Quantile binning with qcut
    df = bin_spend_quartiles(df)

    # Step 4: Composite RFM Health Score
    df = compute_rfm_score(df)

    # Step 5: Feature Validation & Export
    report = validate_and_export_features(df, OUTPUT_CSV, OUTPUT_REPORT)

    print("\n" + "=" * 65)
    print("  Feature engineering pipeline complete.")
    print("=" * 65)
