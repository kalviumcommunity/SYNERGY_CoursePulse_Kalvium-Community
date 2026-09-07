"""
dashboard.py
============
Business Performance Dashboard — Data Analyst (Sreedhil Pavishanker B)

Four-level information hierarchy:
  Level 1 – KPI Status Cards        (top row)
  Level 2 – Trend Charts            (middle section)
  Level 3 – Segment Comparisons     (below trends)
  Level 4 – Progressive Drill-down  (sidebar filters + detail table)

Run:
    streamlit run dashboard.py
"""

import json
import os
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CoursePulse · Business Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

      html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

      /* Dark gradient background */
      .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
      }

      /* Sidebar */
      section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
        border-right: 1px solid #30363d;
      }

      /* KPI Card Styling */
      .kpi-card {
        background: linear-gradient(145deg, #1c2128 0%, #21262d 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 22px 18px;
        text-align: center;
        transition: all 0.25s ease;
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
      }
      .kpi-card:hover {
        border-color: #4F8EF7;
        box-shadow: 0 8px 32px rgba(79,142,247,0.2);
        transform: translateY(-2px);
      }
      .kpi-label {
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8b949e;
        margin-bottom: 8px;
      }
      .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #e6edf3;
        line-height: 1.1;
        margin-bottom: 6px;
      }
      .kpi-delta-up   { color: #3fb950; font-size: 0.85rem; font-weight: 600; }
      .kpi-delta-down { color: #f85149; font-size: 0.85rem; font-weight: 600; }
      .kpi-delta-flat { color: #8b949e; font-size: 0.85rem; font-weight: 600; }
      .kpi-arrow-up   { color: #3fb950; }
      .kpi-arrow-down { color: #f85149; }

      /* Section headers */
      .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e6edf3;
        padding: 6px 0;
        border-bottom: 2px solid #4F8EF7;
        margin-bottom: 16px;
        letter-spacing: 0.03em;
      }
      .level-badge {
        display: inline-block;
        background: #4F8EF722;
        color: #4F8EF7;
        border: 1px solid #4F8EF755;
        border-radius: 20px;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2px 10px;
        margin-right: 8px;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        vertical-align: middle;
      }

      /* Insight boxes */
      .insight-box {
        background: #1c2128;
        border-left: 4px solid #4F8EF7;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 0.85rem;
        color: #c9d1d9;
        line-height: 1.6;
      }
      .insight-box.warning { border-left-color: #E15759; }
      .insight-box.success { border-left-color: #3fb950; }

      /* Data table */
      .stDataFrame { border-radius: 10px; overflow: hidden; }

      /* Divider */
      hr { border-color: #30363d !important; }

      /* Metric override */
      [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Data Loading ──────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DASH_DIR   = os.path.join(BASE_DIR, "output", "dashboard")
DATA_DIR   = os.path.join(BASE_DIR, "data", "raw")

PLOTLY_THEME = dict(
    template="plotly_dark",
    paper_bgcolor="#0d1117",
    plot_bgcolor="#161b22",
    font=dict(family="Inter", size=13, color="#c9d1d9"),
)

PALETTE = {
    "primary":   "#4F8EF7",
    "secondary": "#F28E2B",
    "success":   "#3fb950",
    "danger":    "#E15759",
    "purple":    "#A371F7",
    "teal":      "#26C6DA",
}

@st.cache_data
def load_kpis():
    path = os.path.join(DASH_DIR, "kpi_summary.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

@st.cache_data
def load_csv(name):
    path = os.path.join(DASH_DIR, name)
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

@st.cache_data
def load_detail():
    df = load_csv("detail_records.csv")
    if not df.empty:
        df["order_date"] = pd.to_datetime(df["order_date"])
    return df

kpis       = load_kpis()
rev_trend  = load_csv("revenue_trend.csv")
cust_trend = load_csv("customer_trend.csv")
status_df  = load_csv("order_status_trend.csv")
seg_df     = load_csv("revenue_by_segment.csv")
region_df  = load_csv("region_revenue.csv")
detail_df  = load_detail()

# ── Sidebar – Level 4 Filters ─────────────────────────────────────────────────
st.sidebar.markdown(
    "<h2 style='color:#e6edf3;font-size:1.1rem;'>🔍 Dashboard Filters</h2>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

segments_all = ["All"] + (
    sorted(detail_df["segment"].dropna().unique().tolist()) if not detail_df.empty else []
)
regions_all = ["All"] + (
    sorted(detail_df["region"].dropna().unique().tolist()) if not detail_df.empty else []
)
statuses_all = ["All"] + (
    sorted(detail_df["order_status"].dropna().unique().tolist()) if not detail_df.empty else []
)
risks_all = ["All", "High", "Low"]

sel_segment = st.sidebar.selectbox("Customer Segment", segments_all, key="seg_filter")
sel_region  = st.sidebar.selectbox("Region",           regions_all,  key="reg_filter")
sel_status  = st.sidebar.selectbox("Order Status",     statuses_all, key="sta_filter")
sel_risk    = st.sidebar.selectbox("Churn Risk",       risks_all,    key="risk_filter")

min_date = detail_df["order_date"].min().date() if not detail_df.empty else date(2024, 1, 1)
max_date = detail_df["order_date"].max().date() if not detail_df.empty else date(2024, 12, 31)
date_range = st.sidebar.date_input(
    "Date Range", value=(min_date, max_date),
    min_value=min_date, max_value=max_date, key="date_filter"
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='font-size:0.75rem;color:#8b949e;line-height:1.7;'>
    <b style='color:#c9d1d9;'>Data Analyst</b><br>
    Sreedhil Pavishanker B<br><br>
    <b style='color:#c9d1d9;'>Data Sources</b><br>
    • customers_1000.csv<br>
    • orders_5000.csv<br>
    • dashboard_analysis.py
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Dashboard Title ───────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:6px;">
      <h1 style="font-size:1.9rem;font-weight:700;color:#e6edf3;
                 background:linear-gradient(90deg,#4F8EF7,#A371F7);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 margin-bottom:2px;">
        📊 Business Performance Dashboard
      </h1>
      <p style="color:#8b949e;font-size:0.9rem;margin:0;">
        CoursePulse · Revenue Intelligence · 2024 Full Year
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

status_color = "#3fb950"
total_rev = kpis.get("revenue", {}).get("raw", 0)
status_msg = "✅ On Track" if total_rev > 0.5 else "⚠️ Below Target"
st.markdown(
    f"<span style='background:#1c2128;border:1px solid #30363d;"
    f"border-radius:20px;padding:4px 14px;font-size:0.8rem;"
    f"color:{status_color};font-weight:600;'>{status_msg}</span>",
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — KPI STATUS CARDS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<p class="section-header"><span class="level-badge">Level 1</span>KPI Status — At a Glance</p>',
    unsafe_allow_html=True,
)

KPI_ORDER = ["revenue", "active_customers", "avg_order_value", "churn_rate", "conversion_rate"]
KPI_ICONS = ["💰", "👥", "🛒", "📉", "⚡"]

cols = st.columns(5)
for col, key, icon in zip(cols, KPI_ORDER, KPI_ICONS):
    if key not in kpis:
        continue
    data   = kpis[key]
    trend  = data.get("trend", "flat")
    arrow  = "↑" if trend == "up" else ("↓" if trend == "down" else "→")
    delta  = data.get("delta_str", "N/A")

    # Churn Rate: delta_color is inverted (lower = better)
    if key == "churn_rate":
        delta_cls = "kpi-delta-down" if trend == "down" else "kpi-delta-up"
    else:
        delta_cls = "kpi-delta-up" if trend == "up" else "kpi-delta-down"

    arrow_cls = "kpi-arrow-up" if trend == "up" else "kpi-arrow-down"

    col.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">{icon}&nbsp;{data['label']}</div>
          <div class="kpi-value">{data['value']}</div>
          <div class="{delta_cls}">
            <span class="{arrow_cls}">{arrow}</span> {delta} vs prev period
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# KPI Justification Expander
with st.expander("💡 Why these five metrics? (Justification)", expanded=False):
    for key in KPI_ORDER:
        if key in kpis:
            st.markdown(
                f"<div class='insight-box'><b>{kpis[key]['label']}</b> — "
                f"{kpis[key]['justification']}</div>",
                unsafe_allow_html=True,
            )

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — TREND CHARTS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<p class="section-header"><span class="level-badge">Level 2</span>Trend Analysis — How Are We Moving?</p>',
    unsafe_allow_html=True,
)

# ── Chart 1: Revenue Trend ────────────────────────────────────────────────────
t1_col, t2_col = st.columns(2)

with t1_col:
    st.markdown("**📈 Monthly Revenue Trend (2024)**")
    if not rev_trend.empty:
        target_rev = rev_trend["revenue_m"].mean() * 1.05

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=rev_trend["month"],
            y=rev_trend["revenue_m"],
            mode="lines+markers",
            name="Revenue ($M)",
            line=dict(color=PALETTE["primary"], width=3),
            marker=dict(size=8, symbol="circle",
                        line=dict(width=2, color="#0d1117")),
            fill="tozeroy",
            fillcolor="rgba(79,142,247,0.08)",
            hovertemplate="<b>%{x}</b><br>Revenue: $%{y:.3f}M<extra></extra>",
        ))
        fig1.add_hline(
            y=target_rev, line_dash="dash", line_color=PALETTE["success"],
            annotation_text=f"Target +5%: ${target_rev:.2f}M",
            annotation_position="top right",
            annotation_font_color=PALETTE["success"]
        )
        # Annotate peak month
        peak_idx = rev_trend["revenue_m"].idxmax()
        fig1.add_annotation(
            x=rev_trend.loc[peak_idx, "month"],
            y=rev_trend.loc[peak_idx, "revenue_m"],
            text=f"Peak: ${rev_trend.loc[peak_idx, 'revenue_m']:.2f}M",
            showarrow=True, arrowhead=2,
            font=dict(color=PALETTE["secondary"]),
            arrowcolor=PALETTE["secondary"],
            ax=0, ay=-40,
        )
        fig1.update_layout(
            **PLOTLY_THEME,
            xaxis_title="Month",
            yaxis_title="Revenue ($M)",
            height=350,
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#21262d"),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown(
            "<div class='insight-box'>The revenue line shows month-over-month growth "
            "trajectory. The dashed green line marks the +5% above-average target. "
            "Months above this line indicate outperformance.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Revenue trend data not found. Run dashboard_analysis.py first.")

# ── Chart 2: Customer Trend ───────────────────────────────────────────────────
with t2_col:
    st.markdown("**👥 Active vs Churned Customers**")
    if not cust_trend.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=cust_trend["year_month"],
            y=cust_trend["active_customers"],
            mode="lines+markers",
            name="Active Customers",
            line=dict(color=PALETTE["primary"], width=2.5),
            marker=dict(size=7),
            hovertemplate="<b>%{x}</b><br>Active: %{y:,}<extra></extra>",
        ))
        fig2.add_trace(go.Scatter(
            x=cust_trend["year_month"],
            y=cust_trend["churned_customers"],
            mode="lines+markers",
            name="Churned Customers",
            line=dict(color=PALETTE["danger"], width=2.5, dash="dot"),
            marker=dict(size=7, symbol="diamond"),
            hovertemplate="<b>%{x}</b><br>Churned: %{y:,}<extra></extra>",
        ))
        fig2.add_annotation(
            x=cust_trend["year_month"].iloc[-1],
            y=cust_trend["active_customers"].iloc[-1],
            text="Latest",
            showarrow=True, arrowhead=2,
            font=dict(color=PALETTE["teal"]),
            arrowcolor=PALETTE["teal"],
            ax=-40, ay=-30,
        )
        fig2.update_layout(
            **PLOTLY_THEME,
            xaxis_title="Month",
            yaxis_title="Customers",
            height=350,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="right", x=1),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#21262d"),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown(
            "<div class='insight-box'>When the churn line rises toward the active line, "
            "retention is weakening. A healthy dashboard shows a widening gap between "
            "the two series.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Customer trend data not found.")

# ── Chart 3: Order Status Breakdown ──────────────────────────────────────────
st.markdown("<br>**⚡ Order Status Breakdown by Month**")
if not status_df.empty:
    status_colors = {
        "completed": PALETTE["success"],
        "shipped":   PALETTE["primary"],
        "pending":   PALETTE["secondary"],
        "cancelled": PALETTE["danger"],
    }

    pivot = status_df.pivot_table(
        index="year_month", columns="order_status", values="count", aggfunc="sum"
    ).fillna(0).reset_index()

    fig3 = go.Figure()
    for col_name in [c for c in pivot.columns if c != "year_month"]:
        fig3.add_trace(go.Bar(
            name=col_name.capitalize(),
            x=pivot["year_month"],
            y=pivot[col_name],
            marker_color=status_colors.get(col_name, "#8b949e"),
            hovertemplate=f"<b>%{{x}}</b><br>{col_name.capitalize()}: %{{y:,}}<extra></extra>",
        ))

    fig3.update_layout(
        **PLOTLY_THEME,
        barmode="stack",
        xaxis_title="Month",
        yaxis_title="Order Count",
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#21262d"),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown(
        "<div class='insight-box'>This stacked bar reveals the operational health of "
        "order fulfilment. Growing 'completed' portions are positive; rising 'cancelled' "
        "portions signal a fulfilment or product-market issue.</div>",
        unsafe_allow_html=True,
    )
else:
    st.warning("Order status trend data not found.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — SEGMENT COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<p class="section-header"><span class="level-badge">Level 3</span>Segment Analysis — Who Is Driving Growth?</p>',
    unsafe_allow_html=True,
)

s1_col, s2_col = st.columns(2)

# ── Chart A: Revenue by Customer Segment ─────────────────────────────────────
with s1_col:
    st.markdown("**💼 Revenue by Customer Segment**")
    if not seg_df.empty:
        seg_plot = seg_df.sort_values("revenue_m", ascending=True)
        seg_colors = [PALETTE["primary"], PALETTE["secondary"],
                      PALETTE["success"], PALETTE["danger"],
                      PALETTE["purple"], PALETTE["teal"]]

        fig4 = go.Figure(go.Bar(
            x=seg_plot["revenue_m"],
            y=seg_plot["segment"],
            orientation="h",
            marker_color=seg_colors[:len(seg_plot)],
            text=[f"${v:.2f}M" for v in seg_plot["revenue_m"]],
            textposition="outside",
            textfont=dict(color="#e6edf3"),
            hovertemplate="<b>%{y}</b><br>Revenue: $%{x:.3f}M<extra></extra>",
        ))
        total_seg = seg_df["revenue_m"].sum()
        for _, row in seg_plot.iterrows():
            share = row["revenue_m"] / total_seg * 100 if total_seg else 0

        fig4.update_layout(
            **PLOTLY_THEME,
            xaxis_title="Revenue ($M)",
            yaxis_title="",
            height=320,
            showlegend=False,
            xaxis=dict(gridcolor="#21262d"),
            yaxis=dict(showgrid=False),
            margin=dict(l=10, r=60, t=10, b=10),
        )
        st.plotly_chart(fig4, use_container_width=True)

        # Highlight top & bottom
        top_seg  = seg_df.loc[seg_df["revenue_m"].idxmax(), "segment"]
        bot_seg  = seg_df.loc[seg_df["revenue_m"].idxmin(), "segment"]
        st.markdown(
            f"<div class='insight-box success'>🏆 <b>{top_seg}</b> leads revenue — "
            f"premium offerings should be optimised for this segment.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='insight-box warning'>⚠️ <b>{bot_seg}</b> contributes least — "
            f"evaluate acquisition strategy or pricing for this segment.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Segment data not found.")

# ── Chart B: Revenue by Region ────────────────────────────────────────────────
with s2_col:
    st.markdown("**🗺️ Revenue by Region**")
    if not region_df.empty:
        fig5 = px.pie(
            region_df,
            values="revenue_m",
            names="region",
            hole=0.5,
            color_discrete_sequence=[PALETTE["primary"], PALETTE["secondary"],
                                     PALETTE["success"], PALETTE["danger"],
                                     PALETTE["purple"]],
        )
        fig5.update_traces(
            textposition="outside",
            texttemplate="<b>%{label}</b><br>$%{value:.2f}M (%{percent:.1%})",
            hovertemplate="<b>%{label}</b><br>Revenue: $%{value:.3f}M<extra></extra>",
        )
        fig5.update_layout(
            **PLOTLY_THEME,
            showlegend=True,
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25,
                        xanchor="center", x=0.5),
        )
        st.plotly_chart(fig5, use_container_width=True)

        top_region = region_df.loc[region_df["revenue_m"].idxmax(), "region"]
        st.markdown(
            f"<div class='insight-box'><b>{top_region}</b> is the highest-revenue "
            f"region. Sales director should prioritise resource allocation here.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Region data not found.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 4 — PROGRESSIVE DISCLOSURE / DETAIL EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    '<p class="section-header"><span class="level-badge">Level 4</span>Detail Explorer — Drill Down & Export</p>',
    unsafe_allow_html=True,
)

if not detail_df.empty:
    # Apply sidebar filters
    filtered = detail_df.copy()

    if len(date_range) == 2:
        start_d, end_d = date_range
        filtered = filtered[
            (filtered["order_date"].dt.date >= start_d) &
            (filtered["order_date"].dt.date <= end_d)
        ]

    if sel_segment != "All":
        filtered = filtered[filtered["segment"] == sel_segment]
    if sel_region != "All":
        filtered = filtered[filtered["region"] == sel_region]
    if sel_status != "All":
        filtered = filtered[filtered["order_status"] == sel_status]
    if sel_risk != "All":
        filtered = filtered[filtered["churn_risk"] == sel_risk]

    # Summary strip
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Filtered Records",      f"{len(filtered):,}")
    m2.metric("Unique Customers",      f"{filtered['customer_id'].nunique():,}")
    m3.metric("Total Revenue",         f"${filtered['order_amount'].sum()/1e6:.3f}M")
    m4.metric("Avg Order Value",       f"${filtered['order_amount'].mean():.0f}" if len(filtered) else "$0")

    st.markdown("<br>", unsafe_allow_html=True)

    # Display table
    display_cols = ["order_id", "customer_id", "segment", "region",
                    "order_amount", "order_status", "order_date", "churn_risk"]
    existing = [c for c in display_cols if c in filtered.columns]

    st.dataframe(
        filtered[existing].sort_values("order_date", ascending=False).head(500),
        use_container_width=True,
        height=320,
    )

    # Export
    csv_data = filtered[existing].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️  Download Filtered Data (CSV)",
        data=csv_data,
        file_name="filtered_dashboard_data.csv",
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )
else:
    st.warning(
        "Detail records not found. Please run `python analysis/dashboard_analysis.py` first."
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    """
    <div style="text-align:center;color:#484f58;font-size:0.75rem;border-top:
                1px solid #21262d;padding-top:12px;">
      CoursePulse Business Intelligence Dashboard &nbsp;·&nbsp;
      Data Analyst: Sreedhil Pavishanker B &nbsp;·&nbsp;
      Branch: feature/dashboard-design-layout
    </div>
    """,
    unsafe_allow_html=True,
)
