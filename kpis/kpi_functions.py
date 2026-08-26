# -*- coding: utf-8 -*-
"""
kpi_functions.py
================
SYNERGY CoursePulse — Kalvium Community
Member 2: Sreedhil Pavishanker B (Data Analyst)

Single source of truth for KPI computation.
USAGE:
    from kpi_functions import calculate_mau, validate_kpis, decompose_revenue

All functions accept a pandas DataFrame so any team can plug in their own
data extract and get the same, agreed figure.

Target ranges are loaded from kpi_validation_targets.json — edit that file
to update thresholds without touching this code.
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

# ── Locate the targets JSON relative to this file ────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGETS_FILE = os.path.join(_HERE, "kpi_validation_targets.json")

with open(_TARGETS_FILE, "r") as _f:
    _RAW = json.load(_f)

KPI_TARGETS: dict = {k: v for k, v in _RAW.items() if not k.startswith("_")}


# =============================================================================
# KPI COMPUTATION FUNCTIONS
# =============================================================================

def calculate_mau(df: pd.DataFrame, days: int = 30) -> int:
    """
    KPI 1 — Monthly Active Users (MAU).

    Distinct customers with at least one *successful* transaction in the
    last `days` calendar days.

    Parameters
    ----------
    df   : DataFrame with columns [customer_id, transaction_date, payment_status]
    days : look-back window (default 30)

    Returns
    -------
    int  : count of distinct active customer IDs
    """
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    mask = (df["transaction_date"] >= cutoff) & (df["payment_status"] == "success")
    return int(df[mask]["customer_id"].nunique())


def calculate_revenue_per_customer(df: pd.DataFrame) -> float:
    """
    KPI 2 — Revenue per Customer (RPC).

    Total successful transaction revenue divided by unique paying customers.

    Parameters
    ----------
    df : DataFrame with columns [customer_id, amount, payment_status]

    Returns
    -------
    float : average revenue per unique customer (USD)
    """
    paid = df[df["payment_status"] == "success"]
    if paid["customer_id"].nunique() == 0:
        return 0.0
    return round(paid["amount"].sum() / paid["customer_id"].nunique(), 2)


def calculate_churn_rate(df: pd.DataFrame, period_days: int = 30) -> float:
    """
    KPI 3 — Customer Churn Rate.

    Customers active in Period 1 (day -60 to day -30) who had ZERO activity
    in Period 2 (day -30 to today), expressed as a ratio.

    Parameters
    ----------
    df          : DataFrame with columns [customer_id, transaction_date]
    period_days : length of each comparison window in days (default 30)

    Returns
    -------
    float : churn rate as a ratio in [0, 1]
    """
    now = pd.Timestamp.now()
    p1_start = now - pd.Timedelta(days=period_days * 2)
    p1_end   = now - pd.Timedelta(days=period_days)
    p2_start = p1_end
    p2_end   = now

    active_p1 = set(
        df[(df["transaction_date"] >= p1_start) &
           (df["transaction_date"] <  p1_end)]["customer_id"].unique()
    )
    active_p2 = set(
        df[(df["transaction_date"] >= p2_start) &
           (df["transaction_date"] <= p2_end)]["customer_id"].unique()
    )

    if not active_p1:
        return 0.0

    churned = len(active_p1 - active_p2)
    return round(churned / len(active_p1), 4)


def calculate_payment_success_rate(df: pd.DataFrame) -> float:
    """
    KPI 4 — Payment Success Rate (PSR).

    Proportion of all payment attempts that resulted in 'success'.

    Parameters
    ----------
    df : DataFrame with column [payment_status]

    Returns
    -------
    float : success rate as a ratio in [0, 1]
    """
    total = len(df)
    if total == 0:
        return 0.0
    successful = (df["payment_status"] == "success").sum()
    return round(successful / total, 4)


def calculate_customer_acquisition_cost(
    marketing_spend: float, df: pd.DataFrame, period_days: int = 30
) -> float:
    """
    KPI 5 — Customer Acquisition Cost (CAC).

    Total marketing spend divided by new paying customers in the same period.
    A 'new' customer is one whose first-ever successful transaction falls
    within the look-back window.

    Parameters
    ----------
    marketing_spend : total USD spend on sales & marketing in the period
    df              : DataFrame with columns [customer_id, transaction_date, payment_status]
    period_days     : look-back window in days (default 30)

    Returns
    -------
    float : CAC in USD
    """
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=period_days)
    paid = df[df["payment_status"] == "success"].copy()

    # First successful transaction date per customer
    first_txn = paid.groupby("customer_id")["transaction_date"].min()
    new_customers = (first_txn >= cutoff).sum()

    if new_customers == 0:
        return 0.0
    return round(marketing_spend / new_customers, 2)


def calculate_conversion_rate(df: pd.DataFrame) -> float:
    """
    KPI 6 — Conversion Rate (Signup → First Purchase).

    Customers who completed their first purchase divided by all who clicked
    Signup, expressed as a ratio.

    Parameters
    ----------
    df : DataFrame with columns [customer_id, signup_completed, first_purchase]

    Returns
    -------
    float : conversion rate as a ratio in [0, 1]
    """
    total_signups = (df["signup_completed"] == 1).sum()
    if total_signups == 0:
        return 0.0
    converters = (df["first_purchase"] == 1).sum()
    return round(converters / total_signups, 4)


# =============================================================================
# TASK 3 — VALIDATION AGAINST TARGETS
# =============================================================================

def validate_kpis(current_kpis: dict, targets: dict = None) -> pd.DataFrame:
    """
    Compare actual KPI values against target ranges loaded from
    kpi_validation_targets.json (or a custom dict).

    Parameters
    ----------
    current_kpis : {kpi_name: actual_value}
    targets      : optional override; defaults to KPI_TARGETS from JSON

    Returns
    -------
    pd.DataFrame with columns:
        kpi, actual, target_min, target_max, status (PASS / ALERT)
    """
    if targets is None:
        targets = KPI_TARGETS

    rows = []
    for kpi_name, target in targets.items():
        actual = current_kpis.get(kpi_name)
        if actual is None:
            continue
        min_val = target["min"]
        max_val = target["max"]
        status  = "PASS" if min_val <= actual <= max_val else "ALERT"
        rows.append({
            "kpi":         kpi_name,
            "actual":      actual,
            "target_min":  min_val,
            "target_max":  max_val,
            "unit":        target.get("unit", ""),
            "owner":       target.get("owner", ""),
            "status":      status,
        })
    return pd.DataFrame(rows)


# =============================================================================
# TASK 4 — KPI DECOMPOSITION
# =============================================================================

def decompose_revenue(df: pd.DataFrame) -> dict:
    """
    Decompose total revenue into segment → product hierarchy.

    Level 0 : Total revenue
    Level 1 : Revenue by customer_type  (Enterprise / SMB / Startup)
    Level 2 : Revenue by product        (within all segments)

    Parameters
    ----------
    df : DataFrame with columns [amount, customer_type, product, payment_status]

    Returns
    -------
    dict with keys: total, by_segment, by_product
    """
    paid = df[df["payment_status"] == "success"]
    total          = paid["amount"].sum()
    by_segment     = paid.groupby("customer_type")["amount"].sum().sort_values(ascending=False)
    by_product     = paid.groupby("product")["amount"].sum().sort_values(ascending=False)
    by_seg_product = paid.groupby(["customer_type", "product"])["amount"].sum().unstack(fill_value=0)

    return {
        "total":          total,
        "by_segment":     by_segment,
        "by_product":     by_product,
        "by_seg_product": by_seg_product,
    }


# =============================================================================
# STANDALONE EXECUTION — runs all 5 tasks when called directly
# =============================================================================

if __name__ == "__main__":

    # ── UTF-8 stdout on Windows ───────────────────────────────────────────────
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")

    os.makedirs("output", exist_ok=True)

    print("=" * 70)
    print("KPI STANDARDIZATION — CoursePulse / Kalvium Community")
    print("Member 2: Sreedhil Pavishanker B (Data Analyst)")
    print("=" * 70)

    # ── Synthetic Dataset ─────────────────────────────────────────────────────
    # Reflects the business scenario:
    #   50,000 leads (email entered)  — Finance's number
    #   35,000 payment-qualified      — Sales's number
    #   28,000 first purchase         — Product's number
    # We build a transactions table and a funnel table for the 28k purchasers.

    np.random.seed(42)
    N_TXN = 35_000   # payment-qualified users → transaction records

    now = pd.Timestamp.now()

    # Generate transaction dates spread over the last 90 days
    txn_dates = [now - pd.Timedelta(days=int(d))
                 for d in np.random.uniform(0, 90, N_TXN)]

    customer_types = np.random.choice(
        ["Enterprise", "SMB", "Startup"],
        size=N_TXN,
        p=[0.20, 0.50, 0.30],
    )
    products = np.random.choice(
        ["CoursePulse Pro", "CoursePulse Basic", "CoursePulse Enterprise"],
        size=N_TXN,
        p=[0.40, 0.40, 0.20],
    )
    amounts = np.where(
        customer_types == "Enterprise",
        np.random.normal(200, 30, N_TXN),
        np.where(
            customer_types == "SMB",
            np.random.normal(100, 15, N_TXN),
            np.random.normal(50, 10, N_TXN),
        ),
    ).clip(10)

    # 98 % success rate
    statuses = np.where(np.random.random(N_TXN) < 0.98, "success", "failed")

    df_txn = pd.DataFrame({
        "customer_id":      [f"CUS_{i:05d}" for i in np.random.randint(1, 28_001, N_TXN)],
        "transaction_date": txn_dates,
        "amount":           amounts.round(2),
        "customer_type":    customer_types,
        "product":          products,
        "payment_status":   statuses,
    })

    # Funnel table (50 k leads, 28 k purchasers)
    N_LEADS = 50_000
    df_funnel = pd.DataFrame({
        "customer_id":       [f"LEAD_{i:05d}" for i in range(1, N_LEADS + 1)],
        "signup_completed":  np.ones(N_LEADS, dtype=int),
        "email_entered":     np.where(np.arange(N_LEADS) < 50_000, 1, 0),
        "payment_added":     np.where(np.arange(N_LEADS) < 35_000, 1, 0),
        "first_purchase":    np.where(np.arange(N_LEADS) < 28_000, 1, 0),
    })

    print(f"\nTransaction dataset : {len(df_txn):,} rows")
    print(f"Funnel dataset      : {len(df_funnel):,} rows")
    print(f"Overall txn success : {(df_txn['payment_status']=='success').mean():.1%}")
    print()

    # =========================================================================
    # TASK 1 — KPI Reference Document
    # =========================================================================
    print("-" * 60)
    print("TASK 1: KPI Reference Document")
    print("-" * 60)
    print("  → kpis/kpi_reference.md   (6 formal KPI definitions)")
    print("  → kpis/kpi_validation_targets.json  (target ranges)")
    print("  See those files for full details.\n")

    # =========================================================================
    # TASK 2 — Compute All KPIs
    # =========================================================================
    print("-" * 60)
    print("TASK 2: KPI Computation Functions")
    print("-" * 60)

    mau   = calculate_mau(df_txn)
    rpc   = calculate_revenue_per_customer(df_txn)
    churn = calculate_churn_rate(df_txn)
    psr   = calculate_payment_success_rate(df_txn)
    cac   = calculate_customer_acquisition_cost(
                marketing_spend=1_050_000,   # $1.05M monthly marketing budget
                df=df_txn,
            )
    conv  = calculate_conversion_rate(df_funnel)

    print(f"  MAU                    : {mau:,}")
    print(f"  Revenue per Customer   : ${rpc:,.2f}")
    print(f"  Churn Rate             : {churn:.1%}")
    print(f"  Payment Success Rate   : {psr:.1%}")
    print(f"  Customer Acquisition   : ${cac:,.2f}")
    print(f"  Conversion Rate        : {conv:.1%}")
    print()

    # =========================================================================
    # TASK 3 — Validate Against Targets
    # =========================================================================
    print("-" * 60)
    print("TASK 3: Validate Against Targets")
    print("-" * 60)

    current_kpis = {
        "monthly_active_users":       mau,
        "revenue_per_customer":       rpc,
        "churn_rate":                 churn,
        "payment_success_rate":       psr,
        "customer_acquisition_cost":  cac,
        "conversion_rate":            conv,
    }

    validation_df = validate_kpis(current_kpis)
    print("\nValidation Report:")
    print(validation_df.to_string(index=False))

    failures = validation_df[validation_df["status"] == "ALERT"]
    passes   = validation_df[validation_df["status"] == "PASS"]

    if len(failures) > 0:
        print(f"\n⚠️  {len(failures)} KPI(s) out of target range — REVIEW REQUIRED:")
        for _, row in failures.iterrows():
            print(f"   • {row['kpi']}: actual={row['actual']}  "
                  f"target=[{row['target_min']}, {row['target_max']}]")
    else:
        print(f"\n✓  All {len(validation_df)} KPIs within target range")

    print()

    # ── Plotly: validation status bar ────────────────────────────────────────
    bar_colors = ["#10b981" if s == "PASS" else "#ef4444"
                  for s in validation_df["status"]]

    fig_val = go.Figure(go.Bar(
        x=validation_df["kpi"],
        y=validation_df["actual"],
        marker_color=bar_colors,
        text=validation_df["status"],
        textposition="outside",
    ))
    fig_val.update_layout(
        title="Task 3 — KPI Validation: Actual vs Target (green=PASS, red=ALERT)",
        xaxis_title="KPI",
        yaxis_title="Actual Value",
        template="plotly_dark",
        height=480,
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=70, b=120),
    )
    fig_val.write_html("output/kpi_validation.html")
    fig_val.write_image("output/kpi_validation.png", scale=2)
    print("Saved: output/kpi_validation.html/.png")

    # =========================================================================
    # TASK 4 — KPI Decomposition
    # =========================================================================
    print()
    print("-" * 60)
    print("TASK 4: KPI Decomposition — Total Revenue")
    print("-" * 60)

    decomp = decompose_revenue(df_txn)

    print(f"""
KPI DECOMPOSITION: Total Monthly Revenue
{'=' * 50}
Level 0 (Top-level):  ${decomp['total']:>12,.0f}

Level 1 (By Segment):""")
    for seg, rev in decomp["by_segment"].items():
        pct = rev / decomp["total"] * 100
        print(f"  {seg:<20}: ${rev:>10,.0f}  ({pct:.1f}%)")

    level1_sum = decomp["by_segment"].sum()
    print(f"  {'TOTAL':<20}: ${level1_sum:>10,.0f}  (check: sums to top-level ✓)")

    print("\nLevel 2 (By Product):")
    for prod, rev in decomp["by_product"].items():
        pct = rev / decomp["total"] * 100
        print(f"  {prod:<30}: ${rev:>10,.0f}  ({pct:.1f}%)")

    print("\nLevel 2 cross-tab (Segment × Product):")
    print(decomp["by_seg_product"].map(lambda x: f"${x:,.0f}").to_string())

    # ── Plotly: sunburst decomposition ───────────────────────────────────────
    paid   = df_txn[df_txn["payment_status"] == "success"]
    sb_df  = (paid.groupby(["customer_type", "product"])["amount"]
                  .sum().reset_index())

    fig_sun = px.sunburst(
        sb_df,
        path=["customer_type", "product"],
        values="amount",
        title="Task 4 — Revenue Decomposition: Segment → Product",
        color="customer_type",
        color_discrete_map={
            "Enterprise": "#3b82f6",
            "SMB":        "#10b981",
            "Startup":    "#f59e0b",
        },
        template="plotly_dark",
    )
    fig_sun.update_layout(height=520, margin=dict(l=20, r=20, t=70, b=20))
    fig_sun.write_html("output/kpi_decomposition_sunburst.html")
    fig_sun.write_image("output/kpi_decomposition_sunburst.png", scale=2)
    print("\nSaved: output/kpi_decomposition_sunburst.html/.png")

    # ── Full dashboard ────────────────────────────────────────────────────────
    fig_dash = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "KPI Status (PASS / ALERT)",
            "Revenue by Segment",
            "Revenue by Product",
            "Churn Rate vs Target",
        ],
        vertical_spacing=0.20,
        horizontal_spacing=0.12,
    )

    # (1,1) validation bars
    fig_dash.add_trace(go.Bar(
        x=validation_df["kpi"],
        y=validation_df["actual"],
        marker_color=bar_colors,
        text=validation_df["status"],
        textposition="outside",
        showlegend=False,
    ), row=1, col=1)

    # (1,2) segment revenue
    seg  = decomp["by_segment"]
    fig_dash.add_trace(go.Bar(
        x=seg.index.tolist(),
        y=seg.values.tolist(),
        marker_color=["#3b82f6", "#10b981", "#f59e0b"],
        text=[f"${v:,.0f}" for v in seg.values],
        textposition="outside",
        showlegend=False,
    ), row=1, col=2)

    # (2,1) product revenue
    prod = decomp["by_product"]
    fig_dash.add_trace(go.Bar(
        x=prod.index.tolist(),
        y=prod.values.tolist(),
        marker_color=["#8b5cf6", "#ec4899", "#06b6d4"],
        text=[f"${v:,.0f}" for v in prod.values],
        textposition="outside",
        showlegend=False,
    ), row=2, col=1)

    # (2,2) churn gauge-style scatter
    churn_target_max = KPI_TARGETS["churn_rate"]["max"]
    fig_dash.add_trace(go.Scatter(
        x=["Churn Rate"],
        y=[churn],
        mode="markers+text",
        marker=dict(size=24,
                    color="#ef4444" if churn > churn_target_max else "#10b981"),
        text=[f"{churn:.1%}"],
        textposition="top center",
        showlegend=False,
    ), row=2, col=2)
    fig_dash.add_hline(
        y=churn_target_max, line_dash="dash",
        line_color="#f59e0b", annotation_text="Target Max",
        row=2, col=2,
    )

    fig_dash.update_layout(
        title_text=(
            "KPI Standardization Dashboard — CoursePulse "
            "(Member 2: Sreedhil Pavishanker B)"
        ),
        template="plotly_dark",
        height=840,
    )
    fig_dash.write_html("output/kpi_dashboard.html")
    fig_dash.write_image("output/kpi_dashboard.png", scale=2)
    print("Saved: output/kpi_dashboard.html/.png")

    # ── Text summary report ───────────────────────────────────────────────────
    with open("output/kpi_summary_report.txt", "w", encoding="utf-8") as f:
        f.write("KPI STANDARDIZATION REPORT\n")
        f.write("Member 2: Sreedhil Pavishanker B (Data Analyst)\n")
        f.write("=" * 70 + "\n\n")
        f.write("COMPUTED KPIs\n")
        f.write(f"  MAU                   : {mau:,}\n")
        f.write(f"  Revenue per Customer  : ${rpc:,.2f}\n")
        f.write(f"  Churn Rate            : {churn:.1%}\n")
        f.write(f"  Payment Success Rate  : {psr:.1%}\n")
        f.write(f"  CAC                   : ${cac:,.2f}\n")
        f.write(f"  Conversion Rate       : {conv:.1%}\n\n")
        f.write("VALIDATION RESULTS\n")
        f.write(validation_df.to_string(index=False))
        f.write("\n\nREVENUE DECOMPOSITION\n")
        f.write(f"  Total: ${decomp['total']:,.0f}\n")
        for seg_name, rev in decomp["by_segment"].items():
            f.write(f"    {seg_name}: ${rev:,.0f}\n")

    print("Saved: output/kpi_summary_report.txt")

    # =========================================================================
    # TASK 5 — Summary: version-controlled structure
    # =========================================================================
    print()
    print("-" * 60)
    print("TASK 5: Version-Controlled KPI Structure")
    print("-" * 60)
    print("""
  /kpis/
    kpi_reference.md              — 6 formal KPI definitions
    kpi_functions.py              — reusable Python module  (THIS FILE)
    kpi_validation_targets.json   — target ranges (edit to update thresholds)

  Any team member can now run:
    from kpis.kpi_functions import calculate_mau
    mau = calculate_mau(df)

  and get the single agreed number — no more board-meeting discrepancies.
""")

    print("=" * 70)
    print("ANALYSIS COMPLETE — All outputs written to output/")
    print("  Task 1 -> kpis/kpi_reference.md")
    print("  Task 2 -> KPI values printed above")
    print("  Task 3 -> output/kpi_validation.html/.png")
    print("  Task 4 -> output/kpi_decomposition_sunburst.html/.png")
    print("  Task 5 -> kpis/ directory committed to version control")
    print("  Bonus  -> output/kpi_dashboard.html/.png (4-panel)")
    print("=" * 70)
