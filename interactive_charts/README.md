# Interactive Plotly Charts

This assignment uses the real CoursePulse `orders_5000.csv` and customer
dimension. The lesson examples mention product, profit, and marketing fields;
those columns are not present here, so the equivalent customer-segment and
customer-revenue questions are used and labelled explicitly.

## Charts

- `chart1_revenue_trend.html`: daily revenue with custom hover values for revenue, order count, and average order value; date range buttons and a range slider.
- `chart2_segment_performance.html`: revenue by customer segment with three-field hover details.
- `chart3_metric_selector.html`: dropdown switches between revenue, order count, and average order value without reloading data.
- `chart4_interactive_explorer.html`: customer-level scatter plot with hover, select, zoom, pan, and double-click reset.

## Streamlit

The `Interactive Plotly` page in `app.py` embeds the trend, dropdown, and
customer explorer with `st.plotly_chart`. Its sidebar date inputs filter the
same loaded data before rendering.

Run the standalone exports:

```bash
.venv/bin/python -m interactive_charts.plotly_dashboard
```

Run the tests:

```bash
.venv/bin/python -m unittest scripts/test_plotly_dashboard.py
```

## Date-range slider answer

Plotly provides both quick `rangeselector` buttons and a draggable `rangeslider`.
The buttons are best for common windows such as one month, one quarter, or YTD;
the slider is better for an exploratory custom period. The revenue trend uses
both:

```python
figure.update_xaxes(
    rangeselector={"buttons": [
        {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
        {"step": "all", "label": "All"},
    ]},
    rangeslider={"visible": True},
)
```