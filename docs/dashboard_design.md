# Dashboard Design Documentation

**Author:** Sreedhil Pavishanker B (Data Analyst — Member 2)  
**Branch:** `feature/dashboard-design-layout`  
**File:** `dashboard.py` | **Pipeline:** `analysis/dashboard_analysis.py`  
**Data Sources:** `data/raw/customers_1000.csv`, `data/raw/orders_5000.csv`

---

## Information Hierarchy Applied

The dashboard follows a strict **four-level progressive-disclosure** hierarchy so each stakeholder sees exactly the depth they need without being overwhelmed.

### Level 1 — Status (Top Row): KPI Cards

Five status cards occupy the full width of the top row. Each card shows:
- Metric name, current computed value, period-over-period Δ%, trend arrow (↑/↓).

| # | KPI | Business Question Answered |
|---|-----|---------------------------|
| 1 | **Revenue ($M)** | "Is total revenue growing half-on-half?" — primary financial health indicator. |
| 2 | **Active Customers** | "How many unique buyers actually transacted?" — measures real market traction, not just sign-ups. |
| 3 | **Avg Order Value (AOV)** | "Are customers spending more per transaction?" — signals upsell effectiveness and pricing power. |
| 4 | **Churn Rate (%)** | "What share of H1 buyers did not return in H2?" — retention proxy; rising churn = growing revenue leak. |
| 5 | **Conversion Rate (%)** | "What proportion of placed orders were successfully completed?" — operational fulfilment efficiency. |

> **Why these five?** Together they answer the CEO's single-page question: _Revenue_ (top-line), _Active Customers_ (volume), _AOV_ (depth), _Churn_ (sustainability), _Conversion_ (execution). No single metric tells the full story alone.

---

### Level 2 — Trends (Middle Section): Trend Charts

Three charts placed below the KPI row reveal directional movement over time.

#### Chart 1 — Monthly Revenue Trend (Line)
- Shows 12-month revenue ($M) as a line-with-markers with fill.
- A dashed green **target line** (+5% above average) provides context so viewers can see whether performance is above or below goal.
- Peak month is annotated to surface the high-water mark.
- **Pattern it reveals:** Seasonal spikes, sustained growth, or mid-year dips.

#### Chart 2 — Active vs Churned Customers (Dual Line)
- Blue solid line = active (unique) buyers each month.
- Red dotted line = customers present in the previous month but absent this month (churn proxy).
- **Relationship exposed:** When the two lines converge, retention is deteriorating. A widening gap confirms loyalty growth.

#### Chart 3 — Order Status Breakdown by Month (Stacked Bar)
- Four statuses stacked: `completed` (green), `shipped` (blue), `pending` (orange), `cancelled` (red).
- **Pattern it reveals:** Rising `cancelled` share = product or logistics issue. Rising `pending` = processing backlog.
- This is the third trend chart (chosen domain: operational health).

---

### Level 3 — Segments (Comparison Charts)

Two comparison charts that break revenue down by categorical dimension.

#### Chart A — Revenue by Customer Segment (Horizontal Bar)
- Segments: Enterprise, Mid-Market, SMB, Starter (mapped from raw B2B/B2C/SMB/Enterprise).
- Horizontal bars with dollar labels outside enable instant value reading.
- Auto-generated insights call out the highest and lowest segment.
- **Business question:** "Which customer tier drives the most revenue?" — lets the VP Sales allocate quota and the CEO identify concentration risk.

#### Chart B — Revenue by Region (Donut/Pie)
- Five regions: East, West, North, South, Central.
- Donut style distinguishes from the bar chart and lets the viewer compare proportional share.
- **Business question:** "Is revenue geographically diversified?" — Sales Director can identify underperforming regions.

---

### Level 4 — Detail (Progressive Disclosure)

A **sidebar filter panel** + **interactive data table** + **CSV export** give analysts and power-users drill-down capability without cluttering the summary view.

| Component | Implementation |
|-----------|---------------|
| Segment filter | `st.sidebar.selectbox` – filters all downstream data |
| Region filter | `st.sidebar.selectbox` |
| Order Status filter | `st.sidebar.selectbox` |
| Churn Risk filter | `st.sidebar.selectbox` (High / Low computed from H1→H2 cohort drop-off) |
| Date range | `st.sidebar.date_input` with full year span |
| Summary strip | 4 `st.metric` tiles: filtered record count, unique customers, total revenue, AOV |
| Data table | `st.dataframe` – sortable, scrollable, 500-row preview |
| Export | `st.download_button` – exports the full filtered set as CSV |

Filters **dynamically update** every element in Level 4 in real-time on each widget interaction.

---

## Design Principles Applied

### 1. Progressive Disclosure
Summary is always visible at page load (KPIs → Trends → Segments). Detail only
appears when the analyst actively manipulates the sidebar filters. This matches
how each stakeholder uses the dashboard:
- **CEO** reads Level 1 only (30 sec check).
- **VP Marketing / VP Sales** scan Levels 1–3 (5 min review).
- **Data Analyst** uses Level 4 to pull filtered exports.

### 2. Spatial Organisation
The most critical metrics (Revenue, Active Customers) are positioned **top-left**
because Western reading patterns scan left-to-right, top-to-bottom. AOV, Churn,
Conversion follow in descending urgency.

### 3. Consistent Colour Metaphor
`Green = good`, `Red = bad` is applied uniformly across all four levels:
- Positive KPI deltas → green text + ↑ arrow.
- Churn Rate delta is **inverted** (a decrease in churn is shown in green).
- Chart series use consistent palette across Levels 2 and 3.

### 4. Context Over Numbers
Every metric includes a comparison baseline:
- KPI cards show period-over-period % change.
- Revenue trend has the **target line** (+5% above average) for goal context.
- Segment chart auto-annotates the top and bottom performers.

### 5. Dark Theme & Glassmorphism
A dark gradient background (`#0d1117` → `#161b22`) reduces eye strain for
extended dashboard sessions. KPI cards use a subtle hover lift effect to provide
interactive affordance without being distracting.

---

## Colour Palette

| Role | Hex | Usage |
|------|-----|-------|
| Primary | `#4F8EF7` | Main metric lines, active-state borders |
| Secondary | `#F28E2B` | Comparison elements, pending orders |
| Success | `#3fb950` | Positive deltas, target lines, completed status |
| Danger | `#E15759` | Negative deltas, churned customers, cancelled orders |
| Purple | `#A371F7` | Accent for segment 4 |
| Teal | `#26C6DA` | Annotations and latest-period markers |
| Background | `#0d1117` | Plotly chart backgrounds |
| Card surface | `#1c2128` | KPI card and insight-box backgrounds |

---

## Target Audience

| Persona | Usage Frequency | Dashboard Depth Used |
|---------|----------------|----------------------|
| **CEO** | Weekly — 30-second glance | Level 1 (KPI row) + status badge |
| **VP Marketing** | Daily — looks for campaign effect | Levels 1–2 (KPIs + Revenue Trend) |
| **VP Sales / Sales Director** | Daily — checks region & segment | Levels 1–3 (KPIs + Segment charts) |
| **Data Analyst** | Ad-hoc — deep investigation | Levels 1–4 (all + Export) |

---

## Data Sources & Computation

| Output | Source | Logic |
|--------|--------|-------|
| `kpi_summary.json` | `orders_5000.csv` + `customers_1000.csv` | H2 2024 vs H1 2024 period comparison |
| `revenue_trend.csv` | Completed + shipped orders grouped by month | `order_amount.sum() / 1_000_000` per `year_month` |
| `customer_trend.csv` | Unique `customer_id` per month; churn = H₍n-1₎ buyers absent in Hₙ | Month-level cohort tracking |
| `order_status_trend.csv` | All orders grouped by `order_status` × `year_month` | Stacked count |
| `revenue_by_segment.csv` | Customers mapped: Enterprise/SMB/B2B→Mid-Market/B2C→Starter | Revenue summed per segment key |
| `region_revenue.csv` | Customer `region` joined to orders | Revenue summed per region |
| `detail_records.csv` | Full join of orders + customers + churn-risk flag | Exported as Level-4 explorer dataset |

**Pipeline to regenerate all outputs:**
```bash
python analysis/dashboard_analysis.py
```

**To launch dashboard:**
```bash
streamlit run dashboard.py
```

---

## Validation Checklist

- [x] **Task 1** — Five KPI cards display correctly with value, Δ%, trend arrow, justification.
- [x] **Task 2** — Three trend charts: Revenue (line + target), Customer Dual-line, Order Status stacked bar.
- [x] **Task 3** — Two segment charts: Revenue by Segment (bar), Revenue by Region (donut).
- [x] **Task 4** — Sidebar filters (segment, region, status, churn risk, date) dynamically update the data table; export button works.
- [x] **Task 5** — This document covers hierarchy, principles, colours, audience, and data sources.
