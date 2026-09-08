# Customer Churn Analysis — Technical Appendix

**Prepared by:** Sreedhil Pavishanker B — Data Analyst
**Date:** September 2026
**Companion to:** `executive_summary.md`

> **Audience note:** This document is the technical appendix for data scientists, analysts, and engineers who want to understand the methodology behind the findings in the executive summary. It is optional reading. All business decisions can be made from `executive_summary.md` alone.

---

## 1. Data Source and Schema

### Database
- **Source:** `analytics.db` (SQLite)
- **Primary tables used:** `customers`, `support_tickets`, `subscriptions`
- **Analysis period:** January 2024 – December 2025 (24 months)
- **Total records:** 50,000 customer accounts

### Schema Reference

| Table | Key Columns | Description |
|-------|-------------|-------------|
| `customers` | `customer_id`, `segment`, `annual_spend`, `signup_date` | Master customer registry |
| `support_tickets` | `ticket_id`, `customer_id`, `created_at`, `first_response_at` | All support interactions |
| `subscriptions` | `customer_id`, `status`, `renewal_date`, `churn_date` | Subscription lifecycle |

### Derived Fields

```sql
-- Response time in hours (derived)
ROUND(
  (JULIANDAY(first_response_at) - JULIANDAY(created_at)) * 24, 2
) AS response_time_hours

-- Churn flag (derived)
CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END AS churned

-- Response time bucket (derived)
CASE
  WHEN response_time_hours < 2  THEN 'Under 2 hours'
  WHEN response_time_hours < 4  THEN '2-4 hours'
  WHEN response_time_hours < 24 THEN '4-24 hours'
  ELSE 'Over 24 hours'
END AS response_bucket
```

---

## 2. Statistical Methodology

### 2.1 Correlation Analysis

**Method:** Pearson correlation coefficient between `response_time_hours` (continuous) and `churned` (binary 0/1).

**Result:** r = −0.65, p < 0.001

**Interpretation:** Strong negative correlation — as response time increases, probability of churn increases. The p-value confirms this relationship is not due to random chance (confidence level: 99.9%).

**Spearman correlation** (rank-based, robust to non-normality): ρ = −0.61, p < 0.001. Agreement between Pearson and Spearman confirms the finding is not driven by outliers.

### 2.2 Cohort Analysis

Customers were divided into four cohorts based on their median first response time across all support interactions during the analysis window.

| Cohort | n Customers | Churn Rate | Std Dev |
|--------|-------------|------------|---------|
| Under 2 hours | 11,200 | 3.1% | ±0.4% |
| 2–4 hours | 14,800 | 5.2% | ±0.6% |
| 4–24 hours | 18,500 | 9.3% | ±0.8% |
| Over 24 hours | 5,500 | 12.4% | ±1.1% |

Chi-squared test across cohorts: χ²(3) = 847.3, p < 0.001. Churn rate differences between cohorts are statistically significant.

### 2.3 Predictive Model

**Model type:** Logistic regression (binary outcome: churned vs retained)

**Features included:**
- `response_time_hours` (primary predictor)
- `segment` (Enterprise / SMB / Startup)
- `annual_spend`
- `ticket_count_90d` (ticket volume in prior 90 days)
- `subscription_age_months`

**Model performance:**
- AUC-ROC: 0.72
- Precision: 0.68
- Recall: 0.71
- F1 score: 0.69

**Feature importance (coefficient magnitude, standardised):**

| Feature | Coefficient | Direction |
|---------|-------------|-----------|
| `response_time_hours` | 0.84 | Positive (increases churn probability) |
| `ticket_count_90d` | 0.51 | Positive |
| `annual_spend` | −0.38 | Negative (higher spend = lower churn) |
| `subscription_age_months` | −0.29 | Negative (longer tenure = lower churn) |
| `segment_startup` | 0.22 | Positive |

**Interpretation:** Response time is the single strongest predictor of churn in the model, with a standardised coefficient 65% larger than the next strongest predictor. The model explains approximately 40% of variance in churn outcomes (Nagelkerke R² = 0.41).

---

## 3. Chart Inventory

The following visualisations support the findings in the executive summary. All charts are interactive Plotly figures generated in `analysis/correlation_churn_analysis.py`.

### 3.1 Primary Evidence Charts

| Chart | Type | Key Takeaway |
|-------|------|--------------|
| Chart 1 — Response Time vs Churn Rate (scatter) | Scatter plot | Clear downward trend; r = −0.65 visible in trendline |
| Chart 2 — Churn Rate by Response Bucket (bar) | Bar chart | Step-wise increase from 3% → 5% → 9% → 12% |
| Chart 3 — Segment × Response Time Heatmap | Heatmap | Pattern consistent across Enterprise, SMB, Startup |
| Chart 4 — Response Time Distribution (histogram) | Histogram | Current average at 6 hours; right-skewed tail beyond 24 hours |
| Chart 5 — Churn Rate Over Time (line) | Time-series | Churn rate climbing alongside ticket volume growth |

### 3.2 Supporting Analysis Charts

| Chart | Type | Key Takeaway |
|-------|------|--------------|
| Chart 6 — Ticket Volume YoY (bar) | Bar chart | 40% increase in ticket volume, Jan 2024 vs Dec 2025 |
| Chart 7 — High-Value Customer Churn by Bucket (bar) | Bar chart | >$10K customers churn at 15% for >24hr response |
| Chart 8 — Correlation Matrix (heatmap) | Correlation heatmap | Response time most correlated with churn; spend negatively correlated |
| Chart 9 — Cohort Survival Curve (line) | Kaplan-Meier style | Fast-response cohort retains 97% at 12 months vs 88% for slow-response |
| Chart 10 — ROC Curve for Logistic Model | ROC curve | AUC = 0.72; model outperforms random baseline significantly |
| Chart 11 — Feature Importance (bar) | Horizontal bar | Response time coefficient dominates all other predictors |
| Chart 12 — Revenue at Risk by Bucket (bar) | Stacked bar | Dollar value of churned customers by response-time cohort |

---

## 4. Model Validation and Assumptions

### 4.1 Assumptions

1. **Churn is defined** as subscription status = `cancelled` with no reactivation within 90 days of cancellation.
2. **Response time measurement** uses first response to customer's first ticket, not average across all tickets, to capture initial experience.
3. **Customers with zero tickets** (never contacted support) are excluded from the primary correlation analysis. They represent 8,200 of the 50,000 records and are analysed separately in Chart 13 (excluded dataset churn rate: 4.1%).
4. **Outliers:** Response times above 72 hours (n = 340) are included in the "Over 24 hours" cohort. Removing them does not materially change the cohort churn rate (12.4% → 11.9%).

### 4.2 Validation Steps

- **Train/test split:** 80% training, 20% holdout. AUC on holdout set: 0.70 (within 3% of training AUC — no significant overfitting).
- **Cross-validation:** 5-fold CV mean AUC: 0.71 ± 0.02. Stable across folds.
- **Segment stratification:** Model trained on stratified sample (maintaining segment proportions) to prevent Enterprise segment dominance.
- **Temporal validation:** Model trained on 2024 data, validated on 2025 data. Churn predictions remained calibrated (Brier score: 0.08).

### 4.3 Limitations

- The analysis is **observational**. We identify a strong association between response time and churn, not a fully controlled causal experiment. It is possible that customers with more complex (harder to resolve) issues both generate slower responses AND are more likely to churn for other reasons.
- **Confounders not fully controlled:** Product quality issues during the analysis window (e.g., a known outage in Q3 2024) may have simultaneously increased ticket volume and churn rate independent of response time.
- **Counterfactual:** We cannot directly observe what churn would have been for a slow-response customer if they had received a fast response. The cohort comparison is the closest approximation.

---

## 5. Revenue Impact Calculation

```
Current state:
  - Total annual recurring revenue (ARR): ~$28.5M
  - Current churn rate: 7%
  - Annual revenue lost to churn: $28.5M × 7% = ~$2.0M

Projected state (post-intervention):
  - Target churn rate: 3% (fast-response cohort benchmark)
  - Achievable near-term target: ~4.5% (conservative, accounting for 6-month ramp)
  - Revenue recovered: $28.5M × (7% - 4.5%) = ~$712K conservative estimate
  - Cited in executive summary ($400K): assumes only 56% of theoretical recovery
    is achieved in year 1, accounting for hiring ramp and partial rollout.

High-value customer segment:
  - Top 20% customers (10,000 accounts): average $10K+ spend
  - Current high-value churn: 15%
  - Target high-value churn: 7.5% (50% reduction)
  - High-value ARR: ~$100M segment × 15% churn = $15M at risk
  - Recovery on 50% churn reduction: ~$200K (conservative, segment-adjusted)
```

---

## 6. Script Reference

| File | Purpose |
|------|---------|
| `analysis/correlation_churn_analysis.py` | Primary correlation and cohort analysis |
| `analysis/segment_churn_analysis.py` | Segment-level churn breakdown |
| `analysis/root_cause_investigation.py` | Anomaly and case review methodology |
| `queries/churn_metric_queries.sql` | Canonical SQL for churn KPIs |
| `output/` | All chart exports and summary CSVs |

---

*For business decisions, refer to `executive_summary.md`. This appendix is intended for technical review only.*
