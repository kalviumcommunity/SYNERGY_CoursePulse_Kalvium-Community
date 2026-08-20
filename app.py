import streamlit as st
import pandas as pd

st.set_page_config(page_title="Analytics Dashboard", layout="wide")

event_totals = pd.DataFrame(
    {
        "event": ["users", "searches", "previews", "enrollments"],
        "count": [2500, 12000, 4200, 860],
    }
)

total_users = int(event_totals.loc[event_totals["event"] == "users", "count"].iloc[0])
total_searches = int(
    event_totals.loc[event_totals["event"] == "searches", "count"].iloc[0]
)
total_previews = int(
    event_totals.loc[event_totals["event"] == "previews", "count"].iloc[0]
)
total_enrollments = int(
    event_totals.loc[event_totals["event"] == "enrollments", "count"].iloc[0]
)

search_to_preview = (total_previews / total_searches) * 100 if total_searches else 0
preview_to_enrollment = (
    (total_enrollments / total_previews) * 100 if total_previews else 0
)
search_to_enrollment = (
    (total_enrollments / total_searches) * 100 if total_searches else 0
)

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Funnel Analysis",
        "Course Performance",
        "Category Performance",
        "User Behaviour",
        "Trends and Monitoring",
        "Root Causes and Insights",
    ],
)

if page == "Overview":
    st.title("Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Users", f"{total_users:,}")
    with col2:
        st.metric("Total Searches", f"{total_searches:,}")
    with col3:
        st.metric("Total Previews", f"{total_previews:,}")
    with col4:
        st.metric("Total Enrollments", f"{total_enrollments:,}")

    st.header("Core Conversion KPIs")
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.subheader("Search -> Preview")
        st.metric("Conversion", f"{search_to_preview:.1f}%")
    with kpi2:
        st.subheader("Preview -> Enrollment")
        st.metric("Conversion", f"{preview_to_enrollment:.1f}%")
    with kpi3:
        st.subheader("Search -> Enrollment")
        st.metric("Conversion", f"{search_to_enrollment:.1f}%")

    st.divider()

    st.header("Overall Funnel")
    funnel_left, funnel_right = st.columns([2, 1])
    with funnel_left:
        st.subheader("Stage Progression")
        st.write(
            f"Searches ({total_searches:,}) -> Previews ({total_previews:,}) -> "
            f"Enrollments ({total_enrollments:,})"
        )
    with funnel_right:
        with st.expander("Funnel Notes"):
            st.write("Funnel chart placeholder and stage definitions will appear here.")

    st.divider()

    st.header("Key Insight Summary")
    insight_col, detail_col = st.columns([2, 1])
    with insight_col:
        st.subheader("Primary Observation")
        st.write(
            "High search volume is not converting proportionally into enrollments, "
            "indicating friction between preview and commitment."
        )
    with detail_col:
        with st.expander("How to Read This"):
            st.write(
                "This area will surface auto-generated narrative insights once model "
                "logic and threshold rules are connected."
            )

elif page == "Funnel Analysis":
    st.title("Funnel Analysis")

    st.header("Search -> Preview -> Enrollment Funnel")
    funnel_a, funnel_b = st.columns([2, 1])
    with funnel_a:
        st.subheader("Funnel Visualization")
        st.write("Funnel chart placeholder")
    with funnel_b:
        with st.expander("Funnel Definition"):
            st.write("Definitions for each funnel stage will appear here.")

    st.divider()

    st.header("Stage Conversion Rates")
    rate1, rate2, rate3 = st.columns(3)
    with rate1:
        st.subheader("Search -> Preview")
        st.metric("Rate", f"{search_to_preview:.1f}%")
    with rate2:
        st.subheader("Preview -> Enrollment")
        st.metric("Rate", f"{preview_to_enrollment:.1f}%")
    with rate3:
        st.subheader("Search -> Enrollment")
        st.metric("Rate", f"{search_to_enrollment:.1f}%")

    st.divider()

    st.header("Drop-off Analysis")
    drop_left, drop_right = st.columns(2)
    with drop_left:
        st.subheader("Drop-off Counts")
        st.write("Count placeholders by stage")
    with drop_right:
        st.subheader("Drop-off Percentages")
        st.write("Percentage placeholders by stage")

elif page == "Course Performance":
    st.title("Course Performance")

    st.header("Top and Bottom Courses")
    top_col, bottom_col = st.columns(2)
    with top_col:
        st.subheader("Top Courses by Views / Enrollments / Conversion")
        st.write("Top performers table placeholder")
    with bottom_col:
        st.subheader("Bottom Courses by Views / Enrollments / Conversion")
        st.write("Bottom performers table placeholder")

    st.divider()

    st.header("High-view, Low-conversion Courses")
    hv_left, hv_right = st.columns([2, 1])
    with hv_left:
        st.subheader("At-risk Course Identification")
        st.write("Detection logic output placeholder")
    with hv_right:
        with st.expander("Detection Criteria"):
            st.write("Thresholds for high views and low conversion will be listed here.")

    st.divider()

    st.header("Performance Comparison")
    cmp_left, cmp_right = st.columns(2)
    with cmp_left:
        st.subheader("Underperformers")
        st.write("Comparison cohort placeholder")
    with cmp_right:
        st.subheader("Better-performing Courses")
        st.write("Benchmark cohort placeholder")

elif page == "Category Performance":
    st.title("Category Performance")

    st.header("Category Metrics")
    cat_left, cat_right = st.columns(2)
    with cat_left:
        st.subheader("Views, Enrollments, and Conversion by Category")
        st.write("Category table/chart placeholder")
    with cat_right:
        with st.expander("Metric Definitions"):
            st.write("Category-level formulas and aggregation rules placeholder")

    st.divider()

    st.header("Category Comparison and Filtering")
    filter_left, filter_right = st.columns([2, 1])
    with filter_left:
        st.subheader("Comparison View")
        st.write("Side-by-side category comparison placeholder")
    with filter_right:
        st.subheader("Filters")
        st.write("Category filters placeholder")

elif page == "User Behaviour":
    st.title("User Behaviour")

    st.header("User Segments")
    seg_left, seg_right = st.columns([2, 1])
    with seg_left:
        st.subheader("Segments by Supported Behaviour")
        st.write("Segment definition and counts placeholder")
    with seg_right:
        with st.expander("Segmentation Logic"):
            st.write("Rules for behavior-based segments will be documented here.")

    st.divider()

    st.header("Activity vs Enrollment")
    act_left, act_right = st.columns(2)
    with act_left:
        st.subheader("Search and Preview Activity")
        st.write("User activity distribution placeholder")
    with act_right:
        st.subheader("Enrollment Comparison")
        st.write("Segment-wise enrollment comparison placeholder")

elif page == "Trends and Monitoring":
    st.title("Trends and Monitoring")

    st.header("Conversion Trends Over Time")
    conv_left, conv_right = st.columns([2, 1])
    with conv_left:
        st.subheader("Trend View")
        st.write("Chart placeholder")
    with conv_right:
        with st.expander("Trend Notes"):
            st.write("Rolling windows and smoothing approach placeholder")

    st.divider()

    st.header("Search, Preview, and Enrollment Trends")
    trend_left, trend_right = st.columns(2)
    with trend_left:
        st.subheader("Volume Trends")
        st.write("Chart placeholder")
    with trend_right:
        st.subheader("Rate Trends")
        st.write("Chart placeholder")

    st.divider()

    st.header("Threshold and Anomaly Indicators")
    anomaly_left, anomaly_right = st.columns([2, 1])
    with anomaly_left:
        st.subheader("Alert Stream")
        st.write("Threshold breach and anomaly list placeholder")
    with anomaly_right:
        with st.expander("Alert Rules"):
            st.write("Business thresholds and anomaly sensitivity settings placeholder")

elif page == "Root Causes and Insights":
    st.title("Root Causes and Insights")

    st.header("Evidence-based Patterns")
    pat_left, pat_right = st.columns([2, 1])
    with pat_left:
        st.subheader("Observed Patterns")
        st.write("Pattern detection output placeholder")
    with pat_right:
        with st.expander("Evidence Sources"):
            st.write("Data slices and confidence notes placeholder")

    st.divider()

    st.header("Underperformers vs Better Performers")
    perf_left, perf_right = st.columns(2)
    with perf_left:
        st.subheader("Underperforming Courses")
        st.write("Feature profile placeholder")
    with perf_right:
        st.subheader("Better-performing Courses")
        st.write("Reference profile placeholder")

    st.divider()

    st.header("Business Interpretation and Recommended Actions")
    action_left, action_right = st.columns([2, 1])
    with action_left:
        st.subheader("Interpretation")
        st.write("Narrative interpretation placeholder")
    with action_right:
        with st.expander("Recommended Actions"):
            st.write("Prioritized actions, owners, and expected impact placeholder")