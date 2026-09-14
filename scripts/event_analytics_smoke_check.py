"""Standalone smoke test for event_analytics computations (no Streamlit runtime needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

pd.set_option("display.width", 160)

import event_analytics as ea

events = ea.load_events()
print("events loaded:", len(events), "rows,", events["user_id"].nunique(), "users")

funnel = ea.funnel_metrics(events)
print("\nFUNNEL totals:", funnel["totals"])
print("FUNNEL users: ", funnel["users"])
print("FUNNEL rates: ", {k: round(v, 1) for k, v in funnel["rates"].items()})
print("FUNNEL dropoffs:", funnel["dropoffs"])
print("direct previews:", funnel["direct_previews"])

courses = ea.course_metrics(events)
print("\nCOURSE METRICS:")
print(courses.to_string(index=False))

flagged, criteria = ea.at_risk_courses(courses)
print("\nAT-RISK criteria:", criteria)
print("flagged rows:", len(flagged))

cats = ea.category_metrics(events)
print("\nCATEGORY METRICS:")
print(cats.to_string(index=False))

users = ea.user_segments(events)
summary = ea.segment_summary(users)
print("\nUSER SEGMENTS:")
print(summary.to_string(index=False))

hourly = ea.hourly_activity(events)
print("\nHOURLY rows:", len(hourly), "| top hour:", hourly.loc[hourly["events"].idxmax(), "hour"])

searches = ea.top_searches(events)
print("\nTOP SEARCHES:")
print(searches.head(5).to_string(index=False))

trends = ea.daily_event_trends(events)
print("\nDAILY TRENDS:")
print(trends.to_string(index=False))

rev = ea.revenue_trends()
print("\nREVENUE TRENDS:", len(rev), "days | total revenue: $%.2f" % rev["revenue"].sum(),
      "| range:", rev["date"].min(), "->", rev["date"].max())

monthly = ea.monthly_revenue()
print("\nMONTHLY (last 4):")
print(monthly.tail(4).to_string(index=False))

anomalies = ea.revenue_anomalies()
print("\nANOMALIES (>2 sigma):", len(anomalies), "days")
if not anomalies.empty:
    print(anomalies.head(3).to_string(index=False))

churn = ea.segment_churn()
print("\nSEGMENT CHURN:")
print(churn.to_string(index=False))

alerts = ea.alert_status()
print("\nALERT STATUS:")
print(alerts.to_string(index=False))

patterns = ea.observed_patterns(funnel, courses, cats, churn)
print("\nPATTERNS:")
for p in patterns:
    print("-", p[:150])

print("\nACTIONS preview:")
print(ea.recommended_actions(funnel, courses, churn, alerts)[:500])
print("\nINSIGHT preview:")
print(ea.overview_insight(funnel, courses, cats)[:500])

print("\nfunnel figure:", ea.funnel_figure(funnel["totals"]) is not None)
print("anomaly figure:", ea.revenue_anomaly_figure() is not None)
print("\nALL MODULE CHECKS PASSED")