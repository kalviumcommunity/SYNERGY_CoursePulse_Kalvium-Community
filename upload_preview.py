"""CSV/JSON upload parsing and dynamic Streamlit preview components."""

from __future__ import annotations

import io
import json
from typing import BinaryIO

import pandas as pd
import streamlit as st


def load_uploaded_dataframe(filename: str, file_bytes: bytes) -> pd.DataFrame:
    """Parse CSV or JSON upload bytes into a non-empty DataFrame."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "csv":
        dataframe = pd.read_csv(io.BytesIO(file_bytes))
    elif suffix == "json":
        try:
            payload = json.loads(file_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("JSON could not be parsed. Check the file format.") from error
        if isinstance(payload, list):
            dataframe = pd.json_normalize(payload)
        elif isinstance(payload, dict) and any(isinstance(value, list) for value in payload.values()):
            dataframe = pd.DataFrame(payload)
        elif isinstance(payload, dict):
            dataframe = pd.json_normalize(payload)
        else:
            raise ValueError("JSON must contain an object or array of records.")
    else:
        raise ValueError("Unsupported file type. Please upload a CSV or JSON file.")
    if dataframe.empty:
        raise ValueError("The uploaded file is empty. Please choose a file with rows.")
    return dataframe


def column_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return type, non-null, null-count, and null-percent information."""
    row_count = len(dataframe)
    return pd.DataFrame(
        {
            "Column": dataframe.columns,
            "Type": dataframe.dtypes.astype(str).values,
            "Non-Null": dataframe.notna().sum().values,
            "Null Count": dataframe.isna().sum().values,
            "Null %": (dataframe.isna().sum() / row_count * 100).round(1).values,
        }
    )


def render_upload_page() -> None:
    """Render upload, validation, preview, profiling, and quick exploration UI."""
    st.title("Dataset Upload & Dynamic Preview")
    st.write("Upload a CSV or JSON file to inspect its quality and explore numeric columns immediately.")
    uploaded_file = st.file_uploader("Upload your dataset", type=["csv", "json"])
    if uploaded_file is None:
        st.info("Upload a CSV or JSON file to begin.")
        return

    try:
        dataframe = load_uploaded_dataframe(uploaded_file.name, uploaded_file.getvalue())
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError, pd.errors.ParserError) as error:
        st.error(f"Could not read this file: {error}")
        return
    except Exception:
        st.error("Could not read this file. Check the format and try again.")
        return

    st.success(f"Loaded: {uploaded_file.name} ({len(dataframe):,} rows, {len(dataframe.columns)} columns)")
    total_cells = dataframe.shape[0] * dataframe.shape[1]
    null_percentage = dataframe.isna().sum().sum() / total_cells * 100 if total_cells else 0
    metric_columns = st.columns(3)
    metric_columns[0].metric("Rows", f"{len(dataframe):,}")
    metric_columns[1].metric("Columns", f"{len(dataframe.columns):,}")
    metric_columns[2].metric("Null %", f"{null_percentage:.1f}%")

    st.subheader("First 10 Rows")
    st.dataframe(dataframe.head(10), use_container_width=True)
    st.subheader("Column Summary")
    st.dataframe(column_summary(dataframe), hide_index=True, use_container_width=True)
    st.subheader("Descriptive Statistics")
    numeric_data = dataframe.select_dtypes(include="number")
    if numeric_data.empty:
        st.info("No numeric columns were found for descriptive statistics.")
    else:
        st.dataframe(numeric_data.describe().T, use_container_width=True)
        st.subheader("Quick Exploration")
        selected_column = st.selectbox("Select a numeric column to visualise", numeric_data.columns.tolist())
        st.bar_chart(numeric_data[selected_column].value_counts().head(20))