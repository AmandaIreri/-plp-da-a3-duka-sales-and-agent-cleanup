# plp-da-a3-duka-sales-and-agent-cleanup

PLP Data Analysis, Week 3 assignment: *Data Analysis and Wrangling with Pandas*. One repository, two client engagements.

| Engagement | Client question | Deliverables |
|---|---|---|
| **1 · Duka Electronics** | Explore H1 2026 sales and answer the Head of Sales' questions: "answers, not just tables" | `duka_sales_exploration.ipynb`, `excel/duka_branch_summary.xlsx`, `outputs/premium_online_coast_capital.csv` |
| **2 · Mobile-money agent network** | Which agents and counties handle the most deposits and withdrawals, from an unreliable legacy extract? | `cleaning_pipeline.py`, `agent_cleanup.ipynb`, `outputs/agent_transactions_clean.csv` |

## Engagement 1: Duka Electronics (1,000 orders, seed 2026)

The notebook loads the data with `parse_dates`, documents a first-five-minutes inspection, derives `revenue`, `month`, `weekday`, `is_weekend` and `price_band`, and then answers each task in Markdown beneath its code: branch ranking by revenue vs orders, top products by revenue vs units, weekend vs weekday, best vs worst month, and the Premium online orders from Nairobi and Mombasa (exported with `index=False`). The Excel workbook reproduces the branch revenue ranking with `SUMIFS`, adds a region column with `XLOOKUP` and a PivotTable of revenue by branch and channel; the notebook reads the workbook and asserts that its totals equal pandas to the shilling.

### Executive Summary (Duka Electronics, Jan–Jun 2026)

- **Revenue is concentrated in Nairobi:** Duka booked KES 71.8M from 1,000 orders in January–June 2026, and Nairobi alone delivered KES 26.1M (36.4%), almost double second-placed Mombasa's KES 14.0M (19.5%).
- **A few high-priced products carry the business:** Premium products (laptops and tablets) are only 43.5% of orders but 84.8% of revenue, and laptops alone earn KES 41.5M (57.9%) even though tablets sell more units (691 vs 639).
- **Weekends behave like weekdays:** the 277 weekend orders (27.7% of the total) are worth KES 19.9M, and the average weekend order (KES 71,972) is within 0.3% of a weekday order (KES 71,724).
- **Sales have slid since April:** KES 13.52M in April was the best month and KES 10.90M in June the worst, so April was 24.0% higher than June (equivalently, June is 19.3% below the peak) after two consecutive monthly declines.
- **A clear target segment exists:** 83 Premium online orders from Nairobi and Mombasa generated KES 10.2M, or 14.2% of all H1 revenue, from just 8.3% of orders.

## Engagement 2: Mobile-money agent network (seed 44)

`clean_agent_data(txns, agents)` in `cleaning_pipeline.py` applies every cleaning rule in code and returns `(clean_df, log)`. `agent_cleanup.ipynb` imports and calls it, shows the data-quality audit table (issue, dimension, column, rows affected), the post-merge validation, the county summary and weekly pivot, and ends with a one-page Data Quality Report organised by the six dimensions plus a privacy paragraph (Kenya Data Protection Act 2019).

**Agent data before and after cleaning**

| | Rows |
|---|---|
| Raw `agent_transactions.csv` | **612** |
| Duplicate transactions removed (same `txn_id`) | 12 |
| Clean `agent_transactions_clean.csv` | **600** |

Key decisions (full reasoning is in the notebook):
- **Duplicates** are found by `txn_id`, not by whole row: one copy had its `agent_id` overwritten with `AG099`, so `drop_duplicates()` alone would miss it. The copy with a registered agent is kept.
- **Missing/invalid amounts** (blank and the text `"N/A"`): 20 transactions after de-duplication. Flagged first (`amount_imputed`), then filled with the same-type median of genuine non-outlier amounts. Rows are not dropped.
- **Outliers**: the IQR rule flags 40 amounts, all kept and flagged (`is_outlier`). Five are an identical KES 250,000 (46.5% of total value). They are quarantined from averages and reported with and without them, pending verification at source.
- **Unknown agents** (`AG099`): 7 transactions after de-duplication. A validated many-to-one left join keeps them with `county = "Unknown"` and `unknown_agent = True`.

## How to run

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python generate_data.py            # writes duka_sales.csv, agents.csv, agent_transactions.csv
jupyter notebook                   # open each notebook, then Kernel > Restart & Run All
```

Or run both from the command line: `jupyter nbconvert --to notebook --execute --inplace duka_sales_exploration.ipynb agent_cleanup.ipynb`.

The raw CSVs are **not committed** (see `.gitignore`); both notebooks call `generate_data.py` themselves if the CSVs are missing. Run the notebooks from the repository root so relative paths (`outputs/`, `excel/`) resolve. Developed with Python 3.12 and pandas 3.0.

## Repository layout

```
README.md
generate_data.py                  both dataset generators (Duka seed 2026; agents seed 44), unchanged
duka_sales_exploration.ipynb      Engagement 1 notebook (Executive Summary directly after the title)
agent_cleanup.ipynb               Engagement 2 notebook (Data Quality Report at the end)
cleaning_pipeline.py              clean_agent_data(txns, agents) -> (clean_df, log)
excel/duka_branch_summary.xlsx    SUMIFS table, XLOOKUP region column, PivotTable by branch x channel
outputs/premium_online_coast_capital.csv
outputs/agent_transactions_clean.csv
requirements.txt
```

## Notes and assumptions

- Duka's data has no region field. The branch → region mapping in the workbook (`regions` sheet) is an assumption to be confirmed by Sales.
- `XLOOKUP` needs Excel 2021 / Microsoft 365 or Google Sheets. The PivotTable refreshes when the workbook is opened.
- The Duka data runs from 1 January to 29 June 2026 (30 June is never generated), so June has 29 days of data; Task 6 checks revenue per day to confirm the conclusion is unaffected.
