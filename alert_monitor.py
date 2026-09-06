"""Configurable threshold evaluation and Streamlit alert rendering."""

from __future__ import annotations

from typing import Mapping

import streamlit as st


def check_alerts(metrics: Mapping[str, float], thresholds: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    """Return complete alert records for breached configured thresholds."""
    triggered = []
    for key, config in thresholds.items():
        if key not in metrics:
            continue
        value = metrics[key]
        threshold = float(config["threshold"])
        direction = config["direction"]
        breached = (direction == "above" and value > threshold) or (direction == "below" and value < threshold)
        if breached:
            triggered.append({
                "key": key,
                "metric": config["metric"],
                "value": value,
                "threshold": threshold,
                "severity": config["severity"],
                "message": config["message"],
            })
    return triggered


def render_alerts(metrics: Mapping[str, float], thresholds: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    """Render critical and warning alerts, returning records for tests/callers."""
    alerts = check_alerts(metrics, thresholds)
    for alert in alerts:
        text = (
            f"{alert['metric']}: {float(alert['value']):.1f} "
            f"(threshold: {float(alert['threshold']):.1f}). {alert['message']}"
        )
        if alert["severity"] == "critical":
            st.error(f"ALERT: {text}")
        else:
            st.warning(f"WARNING: {text}")
    if not alerts:
        st.success("No threshold alerts triggered for the current filters.")
    return alerts