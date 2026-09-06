"""Business-owned threshold configuration for the real-time dashboard."""


ALERT_THRESHOLDS = {
    "average_order": {
        "metric": "Average Order Value",
        "threshold": 30.0,
        "direction": "below",
        "severity": "warning",
        "message": "Average order value is below target. Check pricing and product mix.",
    },
    "quality": {
        "metric": "Data Quality",
        "threshold": 95.0,
        "direction": "below",
        "severity": "warning",
        "message": "Data quality is below the safe limit. Check the upload pipeline.",
    },
    "churn_rate": {
        "metric": "Churn Rate",
        "threshold": 7.0,
        "direction": "above",
        "severity": "critical",
        "message": "Churn exceeds the safe limit. Investigate customer retention immediately.",
    },
}