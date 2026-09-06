"""Build and query the CoursePulse SQL views and aggregation layer."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pandas as pd

try:
    from scripts.query_optimization import build_connection
except ModuleNotFoundError:
    from query_optimization import build_connection


BASE_DIR = Path(__file__).resolve().parents[1]
VIEWS_DIR = BASE_DIR / "database" / "views"
AGGREGATIONS_DIR = BASE_DIR / "database" / "aggregations"
OUTPUT_DIR = BASE_DIR / "output"

VIEW_FILES = ("vw_active_customers.sql", "vw_revenue_by_region.sql")


def execute_sql_file(connection: sqlite3.Connection, path: Path) -> None:
    """Execute a version-controlled SQL definition file."""
    connection.executescript(path.read_text(encoding="utf-8"))


def create_data_layer(connection: sqlite3.Connection) -> None:
    """Create both shared views and refresh the pre-aggregated table."""
    connection.executescript(
        """
        DROP VIEW IF EXISTS vw_active_customers;
        DROP VIEW IF EXISTS vw_revenue_by_region;
        DROP TABLE IF EXISTS agg_daily_revenue;
        """
    )
    for filename in VIEW_FILES:
        execute_sql_file(connection, VIEWS_DIR / filename)
    execute_sql_file(connection, AGGREGATIONS_DIR / "agg_daily_revenue.sql")
    connection.commit()


def query_dashboard_layer(connection: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    """Return the three datasets a dashboard can query without raw tables."""
    started = time.perf_counter()
    active_customers = pd.read_sql_query(
        """
        SELECT customer_id, customer_name, customer_segment,
               order_count_30d, revenue_30d, days_since_order
        FROM vw_active_customers
        WHERE days_since_order <= 30
        ORDER BY revenue_30d DESC, customer_id
        LIMIT 20
        """,
        connection,
    )
    revenue_by_region = pd.read_sql_query(
        """
        SELECT region, customer_segment, order_count, total_revenue,
               average_order_value
        FROM vw_revenue_by_region
        ORDER BY total_revenue DESC, region, customer_segment
        """,
        connection,
    )
    daily_revenue = pd.read_sql_query(
        """
        SELECT aggregation_date, total_revenue, order_count,
               average_order_value, updated_at
        FROM agg_daily_revenue
        ORDER BY aggregation_date DESC
        """,
        connection,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"Dashboard data layer query time: {elapsed_ms:.3f} ms")
    return {
        "active_customers": active_customers,
        "revenue_by_region": revenue_by_region,
        "daily_revenue": daily_revenue,
    }


def validate_data_layer(connection: sqlite3.Connection, results: dict[str, pd.DataFrame]) -> None:
    """Validate object names, required columns, freshness, and metric sanity."""
    objects = pd.read_sql_query(
        """
        SELECT name, type FROM sqlite_master
        WHERE name IN ('vw_active_customers', 'vw_revenue_by_region', 'agg_daily_revenue')
        ORDER BY name
        """,
        connection,
    )
    expected_objects = {
        ("vw_active_customers", "view"),
        ("vw_revenue_by_region", "view"),
        ("agg_daily_revenue", "table"),
    }
    assert set(map(tuple, objects.to_records(index=False))) == expected_objects
    assert {"customer_id", "revenue_30d", "days_since_order"}.issubset(results["active_customers"].columns)
    assert {"region", "total_revenue", "order_count"}.issubset(results["revenue_by_region"].columns)
    assert {"aggregation_date", "updated_at", "total_revenue"}.issubset(results["daily_revenue"].columns)
    assert not results["daily_revenue"].empty
    assert results["daily_revenue"]["updated_at"].notna().all()
    assert (results["daily_revenue"]["total_revenue"] >= 0).all()


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    connection = build_connection()
    try:
        create_data_layer(connection)
        results = query_dashboard_layer(connection)
        validate_data_layer(connection, results)
        results["active_customers"].to_csv(OUTPUT_DIR / "vw_active_customers_sample.csv", index=False)
        results["revenue_by_region"].to_csv(OUTPUT_DIR / "vw_revenue_by_region.csv", index=False)
        results["daily_revenue"].to_csv(OUTPUT_DIR / "agg_daily_revenue.csv", index=False)
        for name, dataframe in results.items():
            print(f"{name}: {len(dataframe):,} rows; columns={list(dataframe.columns)}")
        print("SQL views and aggregation table validated successfully.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()