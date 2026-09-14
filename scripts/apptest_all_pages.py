"""AppTest harness: runs every page of app.py and fails on any exception."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest

PAGES = [
    "Overview",
    "Funnel Analysis",
    "Course Performance",
    "Category Performance",
    "User Behaviour",
    "Trends and Monitoring",
    "Root Causes and Insights",
    "Interactive Plotly",
    "KPI Dashboard",
    "Export Reports",
    "Upload Preview",
    "Interactive Filters",
    "Session Workflow",
    "Real-Time Dashboard",
    "Insight Sharing",
]

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")

at = AppTest.from_file(APP_PATH, default_timeout=180)
at.run()
assert not at.exception, f"Default page crashed: {at.exception}"
print("default page (Overview) OK")

for page in PAGES[1:]:
    at = AppTest.from_file(APP_PATH, default_timeout=180)
    at.run()
    at.sidebar.radio[0].set_value(page)
    at.run()
    assert not at.exception, f"Page '{page}' crashed: {at.exception}"
    print(f"page '{page}' OK")

print("\nALL 15 PAGES PASSED AppTest")