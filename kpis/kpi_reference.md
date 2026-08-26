# KPI Reference Document
**Project:** SYNERGY CoursePulse — Kalvium Community  
**Author:** Sreedhil Pavishanker B (Data Analyst — Member 2)  
**Last Updated:** 2026-08-26  
**Purpose:** Establish a single source of truth for all KPI definitions so that Finance, Sales, and Product report consistently identical numbers.

---

## Why This Document Exists

Three teams reported three different customer counts at the board meeting:
- **Finance:** 50,000 (anyone who ever entered an email)
- **Sales:** 35,000 (completed payment)
- **Product:** 28,000 (made a purchase)

None of these definitions is wrong — they are just measuring different things without a shared agreement. This document fixes that by formally defining every KPI used across teams.

---

## KPI 1: Monthly Active Users (MAU)

| Field | Value |
|-------|-------|
| **Name** | Monthly Active Users (MAU) |
| **Definition** | Distinct customers with at least one successful transaction in the last 30 calendar days. |
| **Formula** | `COUNT(DISTINCT customer_id) WHERE transaction_date >= TODAY() - 30 AND payment_status = 'success'` |
| **Data Source** | `transactions` table — columns: `customer_id`, `transaction_date`, `payment_status` |
| **Target Range** | 5,000 – 6,000 |
| **Owner** | Product Manager |
| **Update Frequency** | Daily |
| **Notes** | Primary engagement indicator. Expect seasonal dips in Q4. Does **not** count users who only entered email (Finance definition) or who only added payment (Sales definition). |

---

## KPI 2: Revenue per Customer (RPC)

| Field | Value |
|-------|-------|
| **Name** | Revenue per Customer (RPC) |
| **Definition** | Total transaction revenue divided by the count of unique paying customers in the measurement period. |
| **Formula** | `SUM(amount) / COUNT(DISTINCT customer_id) WHERE payment_status = 'success'` |
| **Data Source** | `transactions` table — columns: `customer_id`, `amount`, `payment_status` |
| **Target Range** | $90 – $110 |
| **Owner** | Finance |
| **Update Frequency** | Monthly |
| **Notes** | Use only successful transactions. Refunds must be subtracted from `amount` before computation. Break down by segment (Enterprise / SMB / Startup) to spot mix-shift effects. |

---

## KPI 3: Customer Churn Rate

| Field | Value |
|-------|-------|
| **Name** | Customer Churn Rate |
| **Definition** | Percentage of customers who were active in the prior 30-day window but had zero activity in the current 30-day window. |
| **Formula** | `(Customers active in Period 1 NOT active in Period 2) / Customers active in Period 1` |
| **Data Source** | `transactions` table — columns: `customer_id`, `transaction_date` |
| **Target Range** | 0% – 5% |
| **Owner** | Customer Success |
| **Update Frequency** | Monthly |
| **Notes** | A rate above 5% triggers a retention review. Period 1 = day −60 to day −30; Period 2 = day −30 to today. Do **not** include trial-only users in the base. |

---

## KPI 4: Payment Success Rate (PSR)

| Field | Value |
|-------|-------|
| **Name** | Payment Success Rate (PSR) |
| **Definition** | Proportion of payment attempts that result in a successful charge, excluding retries. |
| **Formula** | `COUNT(payment_status = 'success') / COUNT(ALL payment_attempts)` |
| **Data Source** | `transactions` table — columns: `payment_status` |
| **Target Range** | 95% – 100% |
| **Owner** | Engineering / Payments |
| **Update Frequency** | Daily |
| **Notes** | Below 95% indicates a gateway issue or fraud spike. Each 1% drop in PSR corresponds approximately to $X,XXX lost revenue (calibrate monthly). |

---

## KPI 5: Customer Acquisition Cost (CAC)

| Field | Value |
|-------|-------|
| **Name** | Customer Acquisition Cost (CAC) |
| **Definition** | Total sales and marketing spend divided by the number of new paying customers acquired in the same period. |
| **Formula** | `Total Marketing Spend ($) / New Paying Customers (COUNT DISTINCT customer_id, first transaction in period)` |
| **Data Source** | `marketing_spend` table + `transactions` table |
| **Target Range** | $0 – $50 |
| **Owner** | Marketing |
| **Update Frequency** | Monthly |
| **Notes** | New customer = first-ever successful transaction in the period. Must be benchmarked against LTV; healthy ratio is LTV:CAC ≥ 3:1. |

---

## KPI 6: Conversion Rate (Signup → First Purchase)

| Field | Value |
|-------|-------|
| **Name** | Conversion Rate |
| **Definition** | Percentage of users who clicked Signup and subsequently completed their first purchase within 30 days. |
| **Formula** | `COUNT(DISTINCT customer_id WHERE first_purchase = 1) / COUNT(DISTINCT customer_id WHERE signup_completed = 1)` |
| **Data Source** | `signup_funnel` table — columns: `customer_id`, `signup_completed`, `first_purchase` |
| **Target Range** | 18% – 25% |
| **Owner** | Product Manager |
| **Update Frequency** | Weekly |
| **Notes** | Current baseline is 20%. Dropping below 18% triggers funnel investigation (see `analysis/funnel_analysis.py`). |

---

## Glossary — Resolving the Board Meeting Discrepancy

| Team | Their Count | Their Definition | Correct KPI Name |
|------|-------------|------------------|-----------------|
| Finance | 50,000 | Anyone who ever entered an email | **Lead Volume** (not a customer KPI) |
| Sales | 35,000 | Completed payment | **Payment-Qualified Leads** |
| Product | 28,000 | Made a purchase | **MAU / Converted Customers** ✅ |

> **Resolution:** The board should align on **MAU** (KPI 1 above) as the single customer count metric. All three teams must use the shared `calculate_mau()` function from `kpi_functions.py`.

---

## Version History

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-08-26 | Sreedhil Pavishanker B | Initial document — 6 KPIs defined |
