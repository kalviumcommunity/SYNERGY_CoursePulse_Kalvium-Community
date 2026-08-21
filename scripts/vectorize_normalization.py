"""
scripts/vectorize_normalization.py
===================================
NumPy Vectorization Pipeline for CoursePulse / Kalvium Community.

Purpose:
    Replace Python-loop normalisation (≈45s on 100k rows) with vectorised NumPy
    operations (≈15ms) so the same transforms stay production-viable on
    million-row customer-revenue datasets.

Tasks:
    Task 1: Min-max normalisation via NumPy (no Python loops)
    Task 2: Z-score normalisation via NumPy
    Task 3: Bulk descending revenue ranking via np.argsort
    Task 4: Timed loop vs NumPy comparison
    Task 5: Write NumPy results back onto the DataFrame and verify types/shapes

Usage:
    python scripts/vectorize_normalization.py

Outputs:
    • Console report with timings, speedup, dtypes, and shape
    • output/vectorization_performance.json       — structured timing report
    • data/processed/revenue_vectorized_sample.csv — ranked sample of results
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd


N_ROWS = 1_000_000
SAMPLE_ROWS = 5_000
RANDOM_SEED = 42


# ============================================================================
# DATA GENERATION
# ============================================================================
def generate_revenue_dataset(n_rows: int = N_ROWS, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    Build a reproducible million-row customer revenue table in memory.

    Revenue is a right-skewed lognormal mix so min-max, z-score, and ranking
    all have meaningful spread — matching real CoursePulse billing data.

    Input:
        n_rows (int): Number of customers to simulate. Default = 1_000_000.
        seed   (int): RNG seed for reproducibility.

    Output:
        pd.DataFrame with columns: customer_id, name, revenue, age, transactions
    """
    rng = np.random.default_rng(seed)

    # Lognormal revenue in USD, clipped to a realistic billing range
    revenue = np.round(rng.lognormal(mean=5.8, sigma=0.55, size=n_rows), 2)
    revenue = np.clip(revenue, 25.0, 25_000.0)

    df = pd.DataFrame({
        "customer_id": np.arange(1, n_rows + 1, dtype=np.int64),
        "name": np.array([f"Customer_{i}" for i in range(1, n_rows + 1)]),
        "revenue": revenue,
        "age": rng.integers(18, 75, size=n_rows, dtype=np.int16),
        "transactions": rng.integers(1, 40, size=n_rows, dtype=np.int16),
    })

    print(f"  ✓ Generated {len(df):,} customer rows in memory")
    return df


# ============================================================================
# TASK 1 — Min-Max Normalisation (NumPy, no loops)
# ============================================================================
def minmax_normalize(df: pd.DataFrame, column: str = "revenue") -> np.ndarray:
    """
    Scale `column` to [0, 1] with a single vectorised NumPy expression.

    Slow loop (DO NOT use in production — O(n) Python iterations, and
    min/max are recomputed on every pass):

        normalized_loop = []
        for val in df['revenue']:
            normalized_loop.append(
                (val - df['revenue'].min()) / (df['revenue'].max() - df['revenue'].min())
            )

    Fast NumPy: min and max are computed once; arithmetic runs in C.

    Input:
        df     (pd.DataFrame): Source frame.
        column (str):          Numeric column to normalise.

    Output:
        np.ndarray of float64 values in [0, 1], same length as df.
    """
    print("\n" + "=" * 65)
    print("TASK 1 — Min-Max Normalisation (NumPy Vectorization)")
    print("=" * 65)

    revenue_array = df[column].to_numpy(dtype=np.float64, copy=False)
    col_min = revenue_array.min()
    col_max = revenue_array.max()
    span = col_max - col_min

    if span == 0:
        raise ValueError(
            f"[TASK 1] Cannot min-max normalise '{column}': min == max ({col_min})."
        )

    normalized_np = (revenue_array - col_min) / span

    print(f"  Column     : {column}")
    print(f"  Rows       : {len(revenue_array):,}")
    print(f"  Min        : {col_min:.4f}")
    print(f"  Max        : {col_max:.4f}")
    print(f"  Norm min   : {normalized_np.min():.6f}")
    print(f"  Norm max   : {normalized_np.max():.6f}")
    print(f"  Norm mean  : {normalized_np.mean():.6f}")
    print("  ✓ Loop replaced with vectorised (x - min) / (max - min)")

    return normalized_np


# ============================================================================
# TASK 2 — Z-Score Normalisation
# ============================================================================
def zscore_normalize(df: pd.DataFrame, column: str = "revenue") -> np.ndarray:
    """
    Standardise `column` to mean 0 / std 1 using NumPy (population std, ddof=0).

        z = (x - mean) / std

    Input:
        df     (pd.DataFrame): Source frame.
        column (str):          Numeric column to standardise.

    Output:
        np.ndarray of z-scores, same length as df.
    """
    print("\n" + "=" * 65)
    print("TASK 2 — Z-Score Normalisation")
    print("=" * 65)

    revenue_array = df[column].to_numpy(dtype=np.float64, copy=False)
    mean = revenue_array.mean()
    std = revenue_array.std()

    if std == 0:
        raise ValueError(
            f"[TASK 2] Cannot compute z-scores for '{column}': std == 0."
        )

    z_scores = (revenue_array - mean) / std

    print(f"  Column     : {column}")
    print(f"  Mean       : {mean:.4f}")
    print(f"  Std (ddof=0): {std:.4f}")
    print(f"  Z min      : {z_scores.min():.4f}")
    print(f"  Z max      : {z_scores.max():.4f}")
    print(f"  Z mean     : {z_scores.mean():.6e}  (≈ 0)")
    print(f"  Z std      : {z_scores.std():.6f}  (≈ 1)")
    print("  ✓ Vectorised z-score: (x - mean) / std")

    return z_scores


# ============================================================================
# TASK 3 — Bulk Ranking / Scoring
# ============================================================================
def rank_by_revenue(df: pd.DataFrame, column: str = "revenue") -> np.ndarray:
    """
    Rank every customer by revenue descending (rank 1 = highest revenue).

    np.argsort(-array) yields the permutation that sorts descending.
    Writing 1..n into those positions produces a dense rank column aligned
    to the original row order.

    Input:
        df     (pd.DataFrame): Source frame.
        column (str):          Numeric column to rank.

    Output:
        np.ndarray of int ranks (1 = highest), same length as df.
    """
    print("\n" + "=" * 65)
    print("TASK 3 — Bulk Ranking / Scoring")
    print("=" * 65)

    revenue_array = df[column].to_numpy(dtype=np.float64, copy=False)

    # Negative values → descending order; argsort returns source indices
    rankings = np.argsort(-revenue_array)
    revenue_rank = np.empty_like(rankings)
    revenue_rank[rankings] = np.arange(1, len(rankings) + 1)

    top_idx = rankings[0]
    bot_idx = rankings[-1]

    print(f"  Ranked     : {len(revenue_rank):,} customers")
    print(f"  Rank 1     : customer_id={df.iloc[top_idx]['customer_id']}  "
          f"revenue={revenue_array[top_idx]:,.2f}")
    print(f"  Rank {len(revenue_rank):,} : customer_id={df.iloc[bot_idx]['customer_id']}  "
          f"revenue={revenue_array[bot_idx]:,.2f}")
    print("  ✓ Vectorised descending rank via np.argsort")

    return revenue_rank


# ============================================================================
# TASK 4 — Timed Loop vs NumPy Comparison
# ============================================================================
def time_loop_vs_numpy(df: pd.DataFrame, column: str = "revenue") -> dict:
    """
    Time an identical 10% uplift in Python vs a single NumPy multiply.

    This is the production proof: same arithmetic, orders-of-magnitude
    difference once the interpreter is removed from the inner loop.

    Input:
        df     (pd.DataFrame): Source frame (million-row scale).
        column (str):          Numeric column to scale.

    Output:
        dict with loop_time_s, numpy_time_s, speedup.
    """
    print("\n" + "=" * 65)
    print("TASK 4 — Time Performance Comparison")
    print("=" * 65)

    series = df[column]
    values = series.to_numpy(dtype=np.float64, copy=False)

    # ── Loop version ────────────────────────────────────────────────────────
    start = time.perf_counter()
    result_loop = []
    for val in series:
        result_loop.append(val * 1.1)
    loop_time = time.perf_counter() - start

    # ── NumPy version ───────────────────────────────────────────────────────
    start = time.perf_counter()
    result_np = values * 1.1
    np_time = time.perf_counter() - start

    speedup = loop_time / np_time if np_time > 0 else float("inf")

    # Guard: both paths must produce the same numbers
    if not np.allclose(np.asarray(result_loop, dtype=np.float64), result_np):
        raise AssertionError("[TASK 4] Loop and NumPy results diverge.")

    print(f"  Rows       : {len(values):,}")
    print(f"  Loop       : {loop_time:.4f}s")
    print(f"  NumPy      : {np_time:.4f}s")
    print(f"  Speedup    : {speedup:.0f}x")

    return {
        "n_rows": int(len(values)),
        "operation": "revenue * 1.1",
        "loop_time_s": round(loop_time, 6),
        "numpy_time_s": round(np_time, 6),
        "speedup": round(speedup, 1),
        "results_match": True,
    }


# ============================================================================
# TASK 5 — Integrate NumPy Results Back onto the DataFrame
# ============================================================================
def integrate_results(
    df: pd.DataFrame,
    normalized_np: np.ndarray,
    z_scores: np.ndarray,
    revenue_rank: np.ndarray,
) -> pd.DataFrame:
    """
    Attach every NumPy result as a new column and verify shape / dtypes.

    Rank uses the dense 1..n scores from Task 3 (not the raw argsort
    permutation), so `revenue_rank` is a customer-facing rank, not an index.

    Input:
        df            (pd.DataFrame): Working frame.
        normalized_np (np.ndarray):   Task 1 min-max values.
        z_scores      (np.ndarray):   Task 2 z-scores.
        revenue_rank  (np.ndarray):   Task 3 dense ranks.

    Output:
        pd.DataFrame with three new columns added.
    """
    print("\n" + "=" * 65)
    print("TASK 5 — Integrate Back to DataFrame")
    print("=" * 65)

    n = len(df)
    for name, arr in (
        ("normalized_np", normalized_np),
        ("z_scores", z_scores),
        ("revenue_rank", revenue_rank),
    ):
        if arr.shape != (n,):
            raise ValueError(
                f"[TASK 5] {name} shape {arr.shape} does not match DataFrame length {n}."
            )

    df["revenue_normalized"] = normalized_np
    df["revenue_zscore"] = z_scores
    df["revenue_rank"] = revenue_rank

    print(f"Shape: {df.shape}")
    print(f"Dtypes:\n{df.dtypes}")
    print(f"\n  New columns : revenue_normalized, revenue_zscore, revenue_rank")
    print(f"  Nulls       : {int(df[['revenue_normalized', 'revenue_zscore', 'revenue_rank']].isna().sum().sum())}")

    return df


def export_outputs(
    df: pd.DataFrame,
    timing: dict,
    sample_path: str,
    report_path: str,
    sample_rows: int = SAMPLE_ROWS,
) -> dict:
    """Persist a ranked sample CSV and a machine-readable timing report."""
    os.makedirs(os.path.dirname(sample_path), exist_ok=True)
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    sample = (
        df.sort_values("revenue_rank")
        .head(sample_rows)
        .reset_index(drop=True)
    )
    sample.to_csv(sample_path, index=False)

    report = {
        "n_rows_processed": int(len(df)),
        "columns_added": ["revenue_normalized", "revenue_zscore", "revenue_rank"],
        "shape": list(df.shape),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "revenue_normalized": {
            "min": float(df["revenue_normalized"].min()),
            "max": float(df["revenue_normalized"].max()),
            "mean": float(df["revenue_normalized"].mean()),
        },
        "revenue_zscore": {
            "min": float(df["revenue_zscore"].min()),
            "max": float(df["revenue_zscore"].max()),
            "mean": float(df["revenue_zscore"].mean()),
            "std": float(df["revenue_zscore"].std(ddof=0)),
        },
        "performance": timing,
        "sample_path": os.path.relpath(sample_path, os.getcwd()),
        "sample_rows": int(len(sample)),
    }

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"\n  ✓ Ranked sample saved      → {sample_path}  ({len(sample):,} rows)")
    print(f"  ✓ Performance report saved → {report_path}")

    return report


# ============================================================================
# MAIN PIPELINE
# ============================================================================
if __name__ == "__main__":
    """
    End-to-end vectorised normalisation pipeline.

    Run with:
        python scripts/vectorize_normalization.py
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(repo_root)

    SAMPLE_PATH = os.path.join(repo_root, "data", "processed", "revenue_vectorized_sample.csv")
    REPORT_PATH = os.path.join(repo_root, "output", "vectorization_performance.json")

    print("=" * 65)
    print("  CoursePulse — NumPy Vectorization Pipeline")
    print("=" * 65)
    print(f"  Rows   : {N_ROWS:,}")
    print(f"  Sample : {SAMPLE_PATH}")
    print(f"  Report : {REPORT_PATH}")
    print("=" * 65)

    df = generate_revenue_dataset(n_rows=N_ROWS, seed=RANDOM_SEED)
    print(f"\n  Loaded {len(df):,} rows × {len(df.columns)} columns")

    # Task 1: min-max
    normalized_np = minmax_normalize(df, column="revenue")

    # Task 2: z-score
    z_scores = zscore_normalize(df, column="revenue")

    # Task 3: bulk rank
    revenue_rank = rank_by_revenue(df, column="revenue")

    # Task 4: timed comparison
    timing = time_loop_vs_numpy(df, column="revenue")

    # Task 5: write arrays back onto the frame
    df = integrate_results(df, normalized_np, z_scores, revenue_rank)

    export_outputs(df, timing, SAMPLE_PATH, REPORT_PATH)

    print("\n" + "=" * 65)
    print("  Vectorization pipeline complete.")
    print("=" * 65)
    sys.exit(0)
