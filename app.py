import streamlit as st
import pandas as pd
from export_functions import build_default_report, verify_exports
from upload_preview import render_upload_page
from filter_page import render_filter_page
from session_workflow import render_workflow_page
from realtime_dashboard import render_realtime_dashboard
from report_generator import generate_report
from email_sender import send_report
from alert_config import ALERT_THRESHOLDS
import event_analytics as ea
from interactive_charts.plotly_dashboard import (
    interactive_explorer,
    load_orders,
    metric_selector,
    revenue_trend,
)
from kpis.kpi_dashboard import render_dashboard

st.set_page_config(page_title="Analytics Dashboard", layout="wide")

# All Overview / Funnel / Course / Category / Behaviour / Trends / Root-Cause
# content is computed at runtime by event_analytics from the repository datasets.
events = ea.load_events()

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
        "Interactive Plotly",
        "KPI Dashboard",
        "Export Reports",
        "Upload Preview",
        "Interactive Filters",
        "Session Workflow",
        "Real-Time Dashboard",
        "Insight Sharing",
    ],
)

if page == "Overview":
    st.title("Overview")

    funnel = ea.funnel_metrics(events)
    totals = funnel["totals"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Users", f"{funnel['unique_users']:,}")
    with col2:
        st.metric("Total Searches", f"{totals['search']:,}")
    with col3:
        st.metric("Total Previews", f"{totals['preview']:,}")
    with col4:
        st.metric("Total Enrollments", f"{totals['enrollment']:,}")

    st.header("Core Conversion KPIs")
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.subheader("Search -> Preview")
        st.metric("Conversion", f"{funnel['rates']['search_to_preview']:.1f}%")
    with kpi2:
        st.subheader("Preview -> Enrollment")
        st.metric("Conversion", f"{funnel['rates']['preview_to_enrollment']:.1f}%")
    with kpi3:
        st.subheader("Search -> Enrollment")
        st.metric("Conversion", f"{funnel['rates']['search_to_enrollment']:.1f}%")

    st.divider()

    st.header("Overall Funnel")
    funnel_left, funnel_right = st.columns([2, 1])
    with funnel_left:
        st.plotly_chart(ea.funnel_figure(totals), use_container_width=True)
    with funnel_right:
        with st.expander("Funnel Notes"):
            st.markdown(
                "**Stage definitions**\n"
                "- **Search**: `event_type = search` — a user submits a query.\n"
                "- **Preview**: `event_type = preview` — a user opens a course page.\n"
                "- **Enrollment**: `event_type = enrollment` — a user enrolls in a course.\n\n"
                f"Counts are computed live from `{ea.EVENTS_PATH.name}`: "
                f"{totals['search']} searches, {totals['preview']} previews, "
                f"{totals['enrollment']} enrollments.\n\n"
                f"{funnel['direct_previews']} preview users never searched first, so "
                "previews can legitimately exceed searches."
            )

    st.divider()

    st.header("Key Insight Summary")
    insight_col, detail_col = st.columns([2, 1])
    with insight_col:
        st.subheader("Primary Observation")
        courses = ea.course_metrics(events)
        categories = ea.category_metrics(events)
        st.markdown(ea.overview_insight(funnel, courses, categories))
    with detail_col:
        with st.expander("How to Read This"):
            st.markdown(
                "- Conversion rates are event-count ratios computed with pandas from the raw event log.\n"
                "- The weakest stage is the transition with the lowest conversion percentage.\n"
                "- Direct previews are users who previewed a course without searching first.\n"
                "- Every figure on this page updates automatically when `data/raw/course_pulse_events.csv` changes."
            )

elif page == "Funnel Analysis":
    st.title("Funnel Analysis")

    funnel = ea.funnel_metrics(events)
    totals = funnel["totals"]

    st.header("Search -> Preview -> Enrollment Funnel")
    funnel_a, funnel_b = st.columns([2, 1])
    with funnel_a:
        st.plotly_chart(ea.funnel_figure(totals), use_container_width=True)
    with funnel_b:
        with st.expander("Funnel Definition"):
            st.markdown(
                "- **Search**: `event_type = search` — user submits a query.\n"
                "- **Preview**: `event_type = preview` — user opens a course page.\n"
                "- **Enrollment**: `event_type = enrollment` — user enrolls.\n\n"
                f"Observed counts: {totals['search']} searches, {totals['preview']} previews, "
                f"{totals['enrollment']} enrollments from {funnel['unique_users']} users.\n\n"
                "Stage users are distinct `user_id` values per stage; rates are stage-to-stage ratios."
            )

    st.divider()

    st.header("Stage Conversion Rates")
    rate1, rate2, rate3 = st.columns(3)
    with rate1:
        st.subheader("Search -> Preview")
        st.metric("Rate", f"{funnel['rates']['search_to_preview']:.1f}%")
    with rate2:
        st.subheader("Preview -> Enrollment")
        st.metric("Rate", f"{funnel['rates']['preview_to_enrollment']:.1f}%")
    with rate3:
        st.subheader("Search -> Enrollment")
        st.metric("Rate", f"{funnel['rates']['search_to_enrollment']:.1f}%")

    st.divider()

    st.header("Drop-off Analysis")
    drop_left, drop_right = st.columns(2)
    drop_rows = [
        {
            "transition": "Search -> Preview",
            "users_gained": funnel["dropoffs"]["search_to_preview"]["count"],
            "percent_of_prior_stage": funnel["dropoffs"]["search_to_preview"]["percent"],
        },
        {
            "transition": "Preview -> Enrollment",
            "users_gained": funnel["dropoffs"]["preview_to_enrollment"]["count"],
            "percent_of_prior_stage": funnel["dropoffs"]["preview_to_enrollment"]["percent"],
        },
    ]
    with drop_left:
        st.subheader("Drop-off Counts")
        st.dataframe(pd.DataFrame(drop_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Negative values mean the later stage is larger than the earlier stage "
            "(users arrived at the later stage without passing through the earlier one)."
        )
    with drop_right:
        st.subheader("Drop-off Percentages")
        drop1, drop2 = st.columns(2)
        with drop1:
            st.metric(
                "Search -> Preview",
                f"{funnel['dropoffs']['search_to_preview']['percent']:.1f}%",
                help="Share of the prior stage that did not reach the next stage.",
            )
        with drop2:
            st.metric(
                "Preview -> Enrollment",
                f"{funnel['dropoffs']['preview_to_enrollment']['percent']:.1f}%",
                help="Share of previews that did not convert to enrollments.",
            )
        st.caption(
            f"Preview -> Enrollment is the largest loss: "
            f"{funnel['dropoffs']['preview_to_enrollment']['count']} of {totals['preview']} previews stopped here."
        )

elif page == "Course Performance":
    st.title("Course Performance")

    courses = ea.course_metrics(events)
    flagged, criteria = ea.at_risk_courses(courses)

    st.header("Top and Bottom Courses")
    top_col, bottom_col = st.columns(2)
    with top_col:
        st.subheader("Top Courses by Views / Enrollments / Conversion")
        st.dataframe(
            courses.sort_values(["conversion", "previews"], ascending=[False, False]).head(3),
            use_container_width=True,
            hide_index=True,
        )
    with bottom_col:
        st.subheader("Bottom Courses by Views / Enrollments / Conversion")
        st.dataframe(
            courses.sort_values(["conversion", "previews"], ascending=[True, True]).head(3),
            use_container_width=True,
            hide_index=True,
        )
    st.bar_chart(courses.set_index("course_name")[["previews", "enrollments"]], use_container_width=True)

    st.divider()

    st.header("High-view, Low-conversion Courses")
    hv_left, hv_right = st.columns([2, 1])
    with hv_left:
        st.subheader("At-risk Course Identification")
        if flagged.empty:
            st.info(
                "No course currently breaches both thresholds. Watchlist — highest traffic, lowest conversion:"
            )
            watchlist = courses.sort_values(
                ["previews", "conversion"], ascending=[False, True]
            ).head(3)
            st.dataframe(watchlist, use_container_width=True, hide_index=True)
        else:
            st.dataframe(flagged, use_container_width=True, hide_index=True)
    with hv_right:
        with st.expander("Detection Criteria"):
            st.markdown(
                f"- **High views**: previews ≥ 75th percentile of all courses "
                f"({criteria['view_threshold']:.1f} previews).\n"
                f"- **Low conversion**: conversion < median course conversion "
                f"({criteria['conversion_median']:.1f}%).\n\n"
                "Both conditions must hold for a course to be flagged; both are "
                "computed with numpy from the per-course table."
            )

    st.divider()

    st.header("Performance Comparison")
    cmp_left, cmp_right = st.columns(2)
    with cmp_left:
        st.subheader("Underperformers")
        st.dataframe(
            courses.sort_values("conversion").head(3),
            use_container_width=True,
            hide_index=True,
        )
    with cmp_right:
        st.subheader("Better-performing Courses")
        st.dataframe(
            courses.sort_values("conversion", ascending=False).head(3),
            use_container_width=True,
            hide_index=True,
        )
    st.subheader("Median metric profile: bottom half vs top half (by conversion)")
    st.dataframe(ea.benchmark_profiles(courses), use_container_width=True, hide_index=True)

elif page == "Category Performance":
    st.title("Category Performance")

    categories = ea.category_metrics(events)

    st.header("Category Metrics")
    cat_left, cat_right = st.columns(2)
    with cat_left:
        st.subheader("Views, Enrollments, and Conversion by Category")
        st.dataframe(categories, use_container_width=True, hide_index=True)
        st.bar_chart(categories.set_index("category")[["views", "enrollments"]], use_container_width=True)
    with cat_right:
        with st.expander("Metric Definitions"):
            st.markdown(
                "- **Views**: count of `preview` events in the category "
                "(`event_type = preview`, grouped by `category`).\n"
                "- **Enrollments**: count of `enrollment` events in the category.\n"
                "- **Unique users**: distinct `user_id` values with any event in the category.\n"
                "- **Conversion**: enrollments / views × 100 (computed with numpy; "
                "blank when a category has no views)."
            )

    st.divider()

    st.header("Category Comparison and Filtering")
    filter_left, filter_right = st.columns([2, 1])
    with filter_left:
        st.subheader("Comparison View")
        st.bar_chart(
            categories.set_index("category")["conversion"], use_container_width=True
        )
        st.caption("Conversion (enrollments ÷ views) per category, sorted by traffic.")
    with filter_right:
        st.subheader("Filters")
        selected_categories = st.multiselect(
            "Select categories to compare",
            options=categories["category"].tolist(),
            default=categories["category"].tolist()[:2],
        )
        if selected_categories:
            selection = categories[categories["category"].isin(selected_categories)]
            st.dataframe(
                selection[["category", "views", "enrollments", "conversion"]],
                use_container_width=True,
                hide_index=True,
            )
            rest = categories[~categories["category"].isin(selected_categories)]
            if not rest.empty:
                st.caption(
                    f"Selected categories convert {selection['conversion'].mean():.1f}% on average "
                    f"vs {rest['conversion'].mean():.1f}% for the rest."
                )
        else:
            st.info("Select at least one category to build the comparison.")

elif page == "User Behaviour":
    st.title("User Behaviour")

    users = ea.user_segments(events)
    summary = ea.segment_summary(users)

    st.header("User Segments")
    seg_left, seg_right = st.columns([2, 1])
    with seg_left:
        st.subheader("Segments by Supported Behaviour")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.bar_chart(summary.set_index("segment")["users"], use_container_width=True)
    with seg_right:
        with st.expander("Segmentation Logic"):
            st.markdown(
                "Each `user_id` is labelled from the set of `event_type` values they generated:\n"
                "- **Committed (enrolled)**: has at least one enrollment event.\n"
                "- **Explorers (search + preview)**: searched and previewed, no enrollment.\n"
                "- **Direct previews (no search)**: previewed without ever searching.\n"
                "- **Searchers (search only)**: searched but never previewed."
            )

    st.divider()

    st.header("Activity vs Enrollment")
    act_left, act_right = st.columns(2)
    with act_left:
        st.subheader("Search and Preview Activity")
        st.bar_chart(users.set_index("user_id")["events"], use_container_width=True)
        hourly = ea.hourly_activity(events)
        st.line_chart(hourly.set_index("hour")[["events", "rolling_3h"]], use_container_width=True)
        st.caption("Events per user (bar) and events per hour with a 3-event rolling mean (line).")
    with act_right:
        st.subheader("Enrollment Comparison")
        enrolled_avg = users.loc[users["enrolled"], "events"].mean()
        not_enrolled_avg = users.loc[~users["enrolled"], "events"].mean()
        comp1, comp2 = st.columns(2)
        with comp1:
            st.metric("Avg events — enrolled users", f"{enrolled_avg:.1f}" if pd.notna(enrolled_avg) else "n/a")
        with comp2:
            st.metric("Avg events — not enrolled", f"{not_enrolled_avg:.1f}" if pd.notna(not_enrolled_avg) else "n/a")
        st.bar_chart(
            summary.set_index("segment")[["users", "enrolled_users"]],
            use_container_width=True,
        )
        st.dataframe(ea.top_searches(events), use_container_width=True, hide_index=True)
        st.caption("Top search queries by frequency.")

elif page == "Trends and Monitoring":
    st.title("Trends and Monitoring")

    trends = ea.daily_event_trends(events)
    hourly = ea.hourly_activity(events)

    st.header("Conversion Trends Over Time")
    conv_left, conv_right = st.columns([2, 1])
    with conv_left:
        st.subheader("Trend View")
        st.line_chart(hourly.set_index("hour")["rolling_3h"], use_container_width=True)
        st.caption("Hourly event volume smoothed with a 3-hour rolling mean (pandas rolling).")
    with conv_right:
        with st.expander("Trend Notes"):
            st.markdown(
                "- The smoothing window is a 3-period rolling mean (`min_periods=1`) so early hours still plot.\n"
                "- The event log currently covers "
                f"{trends['date'].min()} to {trends['date'].max()} "
                f"({len(trends)} day(s)); rate lines will separate as more days arrive.\n"
                "- Order revenue trends below cover the full validated order history."
            )

    st.divider()

    st.header("Search, Preview, and Enrollment Trends")
    trend_left, trend_right = st.columns(2)
    with trend_left:
        st.subheader("Volume Trends")
        st.bar_chart(
            trends.set_index("date")[["search", "preview", "enrollment"]],
            use_container_width=True,
        )
    with trend_right:
        st.subheader("Rate Trends")
        st.line_chart(
            trends.set_index("date")[["search_to_preview", "preview_to_enrollment"]],
            use_container_width=True,
        )
        st.caption("Daily conversion rates (percent) per transition.")

    st.divider()

    st.header("Threshold and Anomaly Indicators")
    anomaly_left, anomaly_right = st.columns([2, 1])
    with anomaly_left:
        st.subheader("Alert Stream")
        alerts = ea.alert_status()
        st.dataframe(alerts, use_container_width=True, hide_index=True)
        anomalies = ea.revenue_anomalies()
        st.subheader(f"Revenue Anomalies (>2σ from rolling trend) — {len(anomalies)} day(s)")
        if anomalies.empty:
            st.success("No revenue day deviates more than 2σ from its 30-day rolling mean.")
        else:
            st.dataframe(
                anomalies[["date", "revenue", "rolling_7d", "z_score"]],
                use_container_width=True,
                hide_index=True,
            )
        st.plotly_chart(ea.revenue_anomaly_figure(), use_container_width=True)
    with anomaly_right:
        with st.expander("Alert Rules"):
            st.markdown(
                "Thresholds come from `alert_config.py` (business-owned config):\n\n"
                + "\n".join(
                    f"- **{config['metric']}**: alert when {config['direction']} {config['threshold']} "
                    f"({config['severity']})"
                    for config in ALERT_THRESHOLDS.values()
                )
                + "\n\n- **Revenue anomalies**: daily revenue whose z-score against its "
                "30-day rolling mean exceeds ±2 (numpy)."
            )

elif page == "Root Causes and Insights":
    st.title("Root Causes and Insights")

    funnel = ea.funnel_metrics(events)
    courses = ea.course_metrics(events)
    categories = ea.category_metrics(events)
    churn = ea.segment_churn()
    alerts = ea.alert_status()

    st.header("Evidence-based Patterns")
    pat_left, pat_right = st.columns([2, 1])
    with pat_left:
        st.subheader("Observed Patterns")
        patterns = ea.observed_patterns(funnel, courses, categories, churn)
        st.markdown("\n\n".join(f"- {item}" for item in patterns))
        st.subheader("Churn by Customer Segment (activity-based proxy)")
        st.dataframe(churn, use_container_width=True, hide_index=True)
    with pat_right:
        with st.expander("Evidence Sources"):
            st.markdown(
                "- `data/raw/course_pulse_events.csv` — funnel, course, and category metrics.\n"
                "- `data/raw/orders_5000.csv` validated with the pipeline rules "
                "(completed/shipped/delivered, positive amounts) — churn and revenue evidence.\n"
                "- `data/raw/customers_1000.csv` — segment dimension.\n"
                "- Churn definition: a customer is *churned* when their latest order is more than "
                "90 days older than the newest order in the dataset (README's activity-churn proxy)."
            )

    st.divider()

    st.header("Underperformers vs Better Performers")
    perf_left, perf_right = st.columns(2)
    with perf_left:
        st.subheader("Underperforming Courses")
        st.dataframe(
            courses.sort_values("conversion").head(3),
            use_container_width=True,
            hide_index=True,
        )
    with perf_right:
        st.subheader("Better-performing Courses")
        st.dataframe(
            courses.sort_values("conversion", ascending=False).head(3),
            use_container_width=True,
            hide_index=True,
        )
    st.subheader("Feature profile: underperformers vs benchmark (medians)")
    st.dataframe(ea.benchmark_profiles(courses), use_container_width=True, hide_index=True)

    st.divider()

    st.header("Business Interpretation and Recommended Actions")
    action_left, action_right = st.columns([2, 1])
    with action_left:
        st.subheader("Interpretation")
        st.markdown(ea.overview_insight(funnel, courses, categories))
        weekday = ea.weekday_revenue()
        st.subheader("Weekday Revenue Pattern (orders)")
        st.bar_chart(weekday.set_index("weekday")["revenue"], use_container_width=True)
        st.caption(
            f"Weakest revenue day: {weekday.sort_values('revenue').iloc[0]['weekday']} "
            f"(${weekday['revenue'].min():,.2f}); strongest: "
            f"{weekday.sort_values('revenue').iloc[-1]['weekday']} (${weekday['revenue'].max():,.2f})."
        )
    with action_right:
        with st.expander("Recommended Actions"):
            st.markdown(ea.recommended_actions(funnel, courses, churn, alerts))

elif page == "Interactive Plotly":
    st.title("Interactive Plotly Explorer")
    st.write("Explore valid CoursePulse orders with hover details, metric controls, and native Plotly navigation.")
    interactive_orders = load_orders()
    min_date = interactive_orders["order_date"].min().date()
    max_date = interactive_orders["order_date"].max().date()
    start_date, end_date = st.sidebar.date_input("Order date range", (min_date, max_date), min_value=min_date, max_value=max_date)
    filtered_orders = interactive_orders[
        (interactive_orders["order_date"].dt.date >= start_date)
        & (interactive_orders["order_date"].dt.date <= end_date)
    ]
    st.caption(f"Showing {len(filtered_orders):,} valid orders from {start_date} to {end_date}.")
    st.plotly_chart(revenue_trend(filtered_orders), use_container_width=True)
    st.plotly_chart(metric_selector(filtered_orders), use_container_width=True)
    st.plotly_chart(interactive_explorer(filtered_orders), use_container_width=True)

elif page == "KPI Dashboard":
    render_dashboard()

elif page == "Export Reports":
    st.title("Insight Export & Report Generation")
    st.write("Generate timestamped CSV, PDF, HTML, and metadata files from the validated analysis data.")
    if st.button("Export Analysis"):
        report_dir = build_default_report()
        verify_exports(report_dir)
        st.success(f"Report generated: {report_dir.name}")
        for filename, mime in [
            ("cleaned_data.csv", "text/csv"),
            ("summary_report.pdf", "application/pdf"),
            ("interactive_report.html", "text/html"),
            ("README.md", "text/markdown"),
        ]:
            path = report_dir / filename
            st.download_button(
                f"Download {filename}", path.read_bytes(), file_name=filename, mime=mime,
                key=f"download_{filename}",
            )

elif page == "Upload Preview":
    render_upload_page()

elif page == "Interactive Filters":
    render_filter_page()

elif page == "Session Workflow":
    render_workflow_page()

elif page == "Real-Time Dashboard":
    render_realtime_dashboard()

elif page == "Insight Sharing":
    st.title("Insight Sharing & Email Reports")
    report_data = load_orders()
    report_text = generate_report(report_data, pd.Timestamp.now().date())
    st.subheader("Report Preview")
    st.text(report_text)
    recipient = st.text_input("Recipient Email")
    if st.button("Send Report"):
        if not recipient:
            st.error("Enter a recipient email.")
        elif send_report(report_text, recipient):
            st.success(f"Report sent to {recipient}")
        else:
            st.error("Report delivery failed or email credentials are not configured. Check the logs and dashboard directly.")