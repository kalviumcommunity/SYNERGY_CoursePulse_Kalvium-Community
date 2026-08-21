# Data Workflow Script — Documentation

## Overview

`scripts/data_workflow.py` is a production-ready, command-line-executable Python
pipeline that replaces notebook-based exploration with a modular, reusable script.
It follows a strict **Ingest → Process → Output** architecture so each concern is
isolated, testable, and maintainable independently.

---

## How to Execute the Script

### Prerequisites

Activate the project virtual environment first:

```bash
source .venv/bin/activate        # macOS / Linux
# or
.venv\Scripts\activate           # Windows
```

### Run the pipeline

```bash
# From the repository root (recommended)
python scripts/data_workflow.py

# From inside the scripts/ directory
cd scripts
python data_workflow.py
```

The script auto-resolves paths relative to the repo root regardless of which
directory you invoke it from.

### Capture output to file

```bash
python scripts/data_workflow.py > output/sample_run.txt
```

---

## What Each Function Does

### `ingest_data(filepath)`

| Item | Detail |
|------|--------|
| **Purpose** | Load a raw CSV file from disk into a Pandas DataFrame |
| **Input** | `filepath` — path to a UTF-8 encoded, comma-delimited CSV |
| **Output** | Raw `pd.DataFrame` — no transformations applied |
| **Guards** | Raises `FileNotFoundError` if file missing; `RuntimeError` if file is empty |

```python
raw_df = ingest_data("data/raw/course_pulse_events.csv")
```

---

### `process_data(df)`

| Step | Operation | Why |
|------|-----------|-----|
| 1 | `drop_duplicates()` | Remove rows logged more than once |
| 2 | `dropna(subset=['event_id'])` | Discard corrupt records with no primary key |
| 3 | Fill string nulls → `'N/A'` | Prevents groupby/pivot failures on NaN strings |
| 4 | Parse `event_timestamp` → `datetime64` | Enables all temporal operations |
| 5 | Extract `hour_of_day`, `day_of_week` | Ready-to-use temporal features |
| 6 | Add `is_enrollment` (0/1 flag) | High-value signal for churn modelling |
| 7 | `reset_index(drop=True)` | Ensures clean 0-based index after row drops |

```python
processed_df = process_data(raw_df)
```

---

### `output_results(df, output_path)`

| Item | Detail |
|------|--------|
| **Purpose** | Write processed DataFrame to CSV and print execution summary |
| **Input** | `df` — processed DataFrame; `output_path` — destination path |
| **Output** | CSV file on disk (no pandas index column); summary to stdout |
| **Side effects** | Creates parent directory automatically if it does not exist |

```python
output_results(processed_df, "output/processed.csv")
```

---

## How to Modify It for New Datasets

### 1 — Point to a different input file

Change `INPUT_PATH` in the `__main__` block, or call `ingest_data()` with any
CSV path:

```python
INPUT_PATH = os.path.join(repo_root, "data", "raw", "your_new_file.csv")
```

### 2 — Add a new processing step

Append a numbered step inside `process_data()` following the existing pattern:

```python
# ── Step 8: Your new transformation ──────────────────────────────────────────
# Explain why this step is needed.
df["new_column"] = df["existing_column"].str.upper()
print("[PROCESS] Step 8 — Added 'new_column'.")
```

### 3 — Change the output format

Replace `df.to_csv(...)` in `output_results()` with any Pandas writer:

```python
df.to_parquet(output_path, index=False)   # Parquet
df.to_json(output_path, orient="records") # JSON
```

### 4 — Accept command-line arguments

Replace the hardcoded paths with `argparse` for flexible CLI usage:

```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--input",  default="data/raw/course_pulse_events.csv")
parser.add_argument("--output", default="output/processed.csv")
args = parser.parse_args()
raw_df = ingest_data(args.input)
```

---

## File Outputs

| File | Description |
|------|-------------|
| `output/processed.csv` | Cleaned, enriched dataset ready for analysis |
| `output/sample_run.txt` | Captured stdout from a successful pipeline run |

---

## Pipeline Architecture

```
data/raw/course_pulse_events.csv
          │
          ▼
   ingest_data()          ← loads raw CSV, validates file exists & non-empty
          │
          ▼
   process_data()         ← dedup → drop nulls → parse datetime → feature extract
          │
          ▼
  output_results()        ← writes CSV, prints execution summary
          │
          ▼
   output/processed.csv
   output/sample_run.txt
```
