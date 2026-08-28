# Database Source of Truth (SQLite & PostgreSQL)

## Overview
Previously, cleaned datasets lived scattered across Jupyter notebooks, temporary local directories, and emailed CSV files. This lack of a centralized truth caused version divergence across analyses.

This module introduces a centralized relational database architecture using **SQLAlchemy** and **SQLite** (with seamless **PostgreSQL** production compatibility) to serve as the immutable single source of truth for all CoursePulse analytics pipelines.

---

## Task 1: Setup Database Connection

### Architecture
We use SQLAlchemy's `create_engine` abstraction:
- **Development & Local Analytics**: SQLite (zero configuration, self-contained file `analytics.db`)
- **Production Server**: PostgreSQL (multi-tenant, networked database with connection pooling)

### Connection Strings (Without Hardcoded Credentials)
Connection strings should always read from environment variables to prevent accidental credential leakage:

```python
import os
from sqlalchemy import create_engine

# 1. SQLite (File-based, zero setup)
engine = create_engine('sqlite:///analytics.db')

# 2. PostgreSQL (Server-based for production)
# Connection parameters are retrieved securely from environment variables:
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASS", "")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "analytics")

pg_engine = create_engine(f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")

# Test connection
with engine.connect() as conn:
    print("✓ Database connection successful")
```

---

## Task 2: Load Cleaned DataFrame as Table

To populate the central database, cleaned DataFrames are written directly into relational tables with strict replace semantics on initial load:

```python
import pandas as pd
from sqlalchemy import inspect

# Load cleaned data to database
df_clean.to_sql('customers_cleaned', engine, if_exists='replace', index=False)

# Verify table created
inspector = inspect(engine)
print(inspector.get_table_names())

# Check row count
count = pd.read_sql("SELECT COUNT(*) as row_count FROM customers_cleaned", engine)
print(f"Rows loaded: {count.iloc[0]['row_count']}")
```

---

## Task 3: Validate Schema

Database schema inspection verifies column definitions, data types, and nullability constraints:

```python
from sqlalchemy import inspect

# Inspect table schema
inspector = inspect(engine)
columns = inspector.get_columns('customers_cleaned')

print("TABLE SCHEMA:")
for col in columns:
    print(f"  {col['name']:20} {str(col['type']):15} {'NOT NULL' if col['nullable']==False else ''}")

# Verify column types
print("\nDATATYPE VALIDATION:")
expected_types = {
    'customer_id': 'INTEGER',
    'email': 'VARCHAR',
    'signup_date': 'DATE'
}

for col_name, expected_type in expected_types.items():
    actual = [c['type'] for c in columns if c['name'] == col_name][0]
    status = '✓' if expected_type in str(actual).upper() else '✗'
    print(f"{status} {col_name}: {actual}")
```

---

## Task 4: Query and Return Results

All downstream scripts and analysts query directly from the database into Pandas DataFrames:

```python
import pandas as pd

# 1. Simple filter query
query = "SELECT * FROM customers_cleaned WHERE customer_type = 'Enterprise'"
results = pd.read_sql(query, engine)
print(f"Retrieved {len(results)} rows")
print(results.head())

# 2. Aggregation query
query_agg = """
SELECT 
    customer_type,
    COUNT(*) as count,
    AVG(lifetime_value) as avg_ltv
FROM customers_cleaned
GROUP BY customer_type
ORDER BY avg_ltv DESC
"""
summary = pd.read_sql(query_agg, engine)
print("\nSummary by segment:")
print(summary)
```

---

## Task 5: Make Loading Repeatable

The repeatable loader function standardizes ingesting new cleaned tables into the source-of-truth database:

```python
from sqlalchemy import create_engine
import pandas as pd

def load_cleaned_data_to_database(df, table_name, database_path='analytics.db'):
    """Load cleaned DataFrame to database - repeatable function."""
    engine = create_engine(f'sqlite:///{database_path}')
    
    # Load
    df.to_sql(table_name, engine, if_exists='replace', index=False)
    
    # Validate
    count = pd.read_sql(f"SELECT COUNT(*) as ct FROM {table_name}", engine)
    rows_loaded = count.iloc[0]['ct']
    
    print(f"✓ Loaded {rows_loaded} rows to {table_name}")
    return engine

# Usage
engine = load_cleaned_data_to_database(df_clean, 'customers_cleaned')

# Now anyone can query
results = pd.read_sql("SELECT * FROM customers_cleaned LIMIT 10", engine)
```

---

## Running the Pipeline

```bash
# Execute the full pipeline
python scripts/sqlite_database_setup.py

# Run unit and integration tests
python -m unittest scripts/test_sqlite_database.py
```
