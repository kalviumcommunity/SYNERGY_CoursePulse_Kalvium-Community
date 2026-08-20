"""
Data Ingestion Pipeline for CoursePulse / Kalvium Community Platform.
Member 1: Data Engineer

Responsibilities:
- Ingest diverse data formats (CSV, JSON, nested JSON) with explicit parameters.
- Provide robust encoding and delimiter fallback strategies.
- Flatten nested structures into tabular format.
- Document ingestion audit trail (shape, dtypes, nulls, preview).
- Validate required schema columns for downstream analysis and Streamlit dashboards.
"""

import json
import os
import pandas as pd

# Expected dashboard columns for CoursePulse analytics
REQUIRED_DASHBOARD_COLUMNS = [
    "event_id",
    "user_id",
    "event_timestamp",
    "event_type",
    "course_id",
    "course_name",
    "category",
    "search_query",
]


def ingest_csv(filepath, delimiter=',', encoding='utf-8', dtype_dict=None):
    """
    Load CSV file with explicit parameters documented.
    
    Args:
        filepath: Path to CSV file
        delimiter: Field delimiter (comma by default, but could be semicolon or tab)
        encoding: File encoding (UTF-8 standard, but may be latin-1 or cp1252)
        dtype_dict: Dictionary mapping column names to data types
    
    Returns:
        Pandas DataFrame with shape and column names confirmed
    """
    try:
        df = pd.read_csv(
            filepath,
            delimiter=delimiter,
            encoding=encoding,
            dtype=dtype_dict
        )
        print(f"✓ CSV loaded: {filepath}")
        print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"  Columns: {list(df.columns)}")
        return df
    except FileNotFoundError:
        print(f"Error: File not found - {filepath}")
        raise
    except UnicodeDecodeError:
        print(f"Encoding error: Could not decode with {encoding}")
        print("Try: latin-1, iso-8859-1, or cp1252")
        raise


def ingest_json(filepath, is_nested=False):
    """
    Load JSON file, handling nested structures by flattening them.
    
    Args:
        filepath: Path to JSON file
        is_nested: If True, flatten nested JSON structures into columns
    
    Returns:
        Pandas DataFrame with nested structures expanded
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if is_nested:
            # Flatten nested JSON: {'customer': {'name': 'Alice'}} → 'customer.name': 'Alice'
            df = pd.json_normalize(data)
            print("✓ Nested JSON flattened to tabular format")
        else:
            df = pd.DataFrame(data)
        
        print(f"✓ JSON loaded: {filepath}")
        print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        return df
    except FileNotFoundError:
        print(f"Error: File not found - {filepath}")
        raise
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {filepath}: {e}")
        raise


def ingest_csv_with_fallback(filepath, delimiters=None, fallback_encodings=None):
    """
    Load CSV with fallback encodings if initial attempt fails.
    
    Tries multiple encodings and delimiters in sequence.
    
    Args:
        filepath: Path to CSV file
        delimiters: List of delimiters to try (default: [',', ';', '\t', '|'])
        fallback_encodings: List of encodings to try (default: ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252'])
        
    Returns:
        Pandas DataFrame loaded successfully
    """
    if delimiters is None:
        delimiters = [',', ';', '\t', '|']
    if fallback_encodings is None:
        fallback_encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    
    for delimiter in delimiters:
        for encoding in fallback_encodings:
            try:
                df = pd.read_csv(filepath, delimiter=delimiter, encoding=encoding)
                # If trying multiple delimiters and result is 1 column, prefer trying remaining delimiters
                if len(delimiters) > 1 and len(df.columns) == 1 and delimiter != delimiters[-1]:
                    continue
                print(f"✓ Successfully loaded with delimiter='{delimiter}', encoding='{encoding}'")
                return df
            except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
                continue
    
    raise ValueError(f"Could not load {filepath} with any encoding/delimiter combination")


def document_ingestion(df, source_file):
    """
    Print detailed ingestion report for audit trail.
    
    Args:
        df: Pandas DataFrame to document
        source_file: Name/path of the source file
        
    Returns:
        The input DataFrame
    """
    print(f"\n{'='*60}")
    print(f"INGESTION REPORT: {source_file}")
    print(f"{'='*60}")
    print(f"Rows: {df.shape[0]}")
    print(f"Columns: {df.shape[1]}")
    print(f"\nColumn Names & Data Types:")
    print(df.dtypes)
    print(f"\nNull Values Per Column:")
    print(df.isnull().sum())
    print(f"\nFirst 3 Rows:")
    print(df.head(3).to_string())
    print(f"{'='*60}\n")
    return df


def validate_dashboard_columns(df, required_columns=None, dataset_name="Dataset"):
    """
    Validate that required dashboard columns exist in the ingested dataframe.
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        dataset_name: Name of dataset for error/success reporting
    """
    if required_columns is None:
        required_columns = REQUIRED_DASHBOARD_COLUMNS
        
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Validation failed for {dataset_name}. Missing required columns: {missing}")
    print(f"✓ Schema validation passed for {dataset_name}: all required columns present ({', '.join(required_columns)})")


if __name__ == "__main__":
    print("Starting multi-format ingestion...\n")
    os.makedirs("data/processed", exist_ok=True)
    
    # 1. Load CSV with explicit parameters
    csv_df = ingest_csv(
        "data/raw/customers.csv",
        delimiter=',',
        encoding='utf-8'
    )
    document_ingestion(csv_df, "customers.csv")
    
    # 2. Load JSON with flattening
    json_df = ingest_json(
        "data/raw/transactions.json",
        is_nested=True
    )
    document_ingestion(json_df, "transactions.json")
    
    # 3. Load CoursePulse Events CSV & validate dashboard columns
    events_df = ingest_csv(
        "data/raw/course_pulse_events.csv",
        delimiter=',',
        encoding='utf-8'
    )
    validate_dashboard_columns(events_df, REQUIRED_DASHBOARD_COLUMNS, "course_pulse_events.csv")
    document_ingestion(events_df, "course_pulse_events.csv")
    
    # 4. Load Nested CoursePulse Events JSON
    nested_events_df = ingest_json(
        "data/raw/course_pulse_events_nested.json",
        is_nested=True
    )
    document_ingestion(nested_events_df, "course_pulse_events_nested.json")
    
    # Save ingested data to processed/
    csv_df.to_csv("data/processed/customers_ingested.csv", index=False)
    json_df.to_csv("data/processed/transactions_ingested.csv", index=False)
    events_df.to_csv("data/processed/events_ingested.csv", index=False)
    
    print("\n✓ All data ingested and saved to data/processed/")
