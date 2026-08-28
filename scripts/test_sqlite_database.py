# -*- coding: utf-8 -*-
"""
scripts/test_sqlite_database.py
===============================
Unit and integration tests for the SQLite Database Setup pipeline.

Tests:
    - Test Task 1: Database Connection & Engine instantiation
    - Test Task 2: Table loading and row count matching
    - Test Task 3: Schema inspection and datatype validation
    - Test Task 4: Filter and Aggregation SQL queries via pandas
    - Test Task 5: Repeatable loading function
"""

import os
import unittest
import pandas as pd
from sqlalchemy import inspect

from scripts.sqlite_database_setup import (
    task1_setup_database_connection,
    task2_load_cleaned_dataframe,
    task3_validate_schema,
    task4_query_and_return_results,
    load_cleaned_data_to_database,
    prepare_cleaned_customer_data,
    get_connection_string
)


class TestSQLiteDatabasePipeline(unittest.TestCase):
    """Test suite for SQLite single source of truth database."""

    @classmethod
    def setUpClass(cls):
        cls.test_db_path = "test_analytics_suite.db"
        cls.df_clean = prepare_cleaned_customer_data()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

    def test_task1_connection(self):
        """Task 1: Connection string and engine verification."""
        conn_str = get_connection_string("sqlite", self.test_db_path)
        self.assertIn("sqlite:///", conn_str)

        pg_conn_str = get_connection_string("postgresql")
        self.assertTrue(pg_conn_str.startswith("postgresql://"))

        engine = task1_setup_database_connection(self.test_db_path)
        self.assertIsNotNone(engine)

    def test_task2_table_loading(self):
        """Task 2: Load DataFrame and verify row counts."""
        engine = task1_setup_database_connection(self.test_db_path)
        task2_load_cleaned_dataframe(self.df_clean, engine, "customers_cleaned")

        inspector = inspect(engine)
        self.assertIn("customers_cleaned", inspector.get_table_names())

        count_df = pd.read_sql("SELECT COUNT(*) as row_count FROM customers_cleaned", engine)
        self.assertEqual(count_df.iloc[0]["row_count"], len(self.df_clean))

    def test_task3_schema_validation(self):
        """Task 3: Validate column types and constraints."""
        engine = task1_setup_database_connection(self.test_db_path)
        task2_load_cleaned_dataframe(self.df_clean, engine, "customers_cleaned")
        cols = task3_validate_schema(engine, "customers_cleaned")

        col_names = [c["name"] for c in cols]
        self.assertIn("customer_id", col_names)
        self.assertIn("email", col_names)
        self.assertIn("signup_date", col_names)
        self.assertIn("customer_type", col_names)
        self.assertIn("lifetime_value", col_names)

    def test_task4_queries(self):
        """Task 4: Execute simple filter and aggregation queries."""
        engine = task1_setup_database_connection(self.test_db_path)
        task2_load_cleaned_dataframe(self.df_clean, engine, "customers_cleaned")
        results = task4_query_and_return_results(engine)

        self.assertIn("enterprise_customers", results)
        self.assertIn("segment_summary", results)
        self.assertGreater(len(results["enterprise_customers"]), 0)
        self.assertGreater(len(results["segment_summary"]), 0)

    def test_task5_repeatable_loading(self):
        """Task 5: Repeatable loading function validation."""
        engine = load_cleaned_data_to_database(self.df_clean, "customers_cleaned", self.test_db_path)
        sample = pd.read_sql("SELECT * FROM customers_cleaned LIMIT 10", engine)
        self.assertEqual(len(sample), 10)


if __name__ == "__main__":
    unittest.main()
