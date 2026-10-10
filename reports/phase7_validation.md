# FoodLens Phase 7: SQL Reporting and Insights Validation

**Date:** 2026-10-10. **Status:** Phase 7 completed successfully.

Eight meaningful SQL reports were successfully executed against the live Neon PostgreSQL database. All operations were read-only and no data was modified during this phase.

## Phase 6 Documentation Review

The Phase 6 documentation review was completed successfully. Both `README.md` and `reports/phase6_validation.md` were inspected. They correctly reflected the live Neon results reported by the project owner (a total of 6,503 rows successfully loaded and verified across the five tables). No fixes were necessary to the Phase 6 code or its documentation.

## Files Created and Modified

**Created:**
- `sql/reports.sql`: Contains the eight read-only SELECT queries with comments explaining their logic and the SQL concepts demonstrated.
- `scripts/run_sql_reports.py`: A Python runner script that securely connects to the Neon database (using the existing local `.env`), executes the queries in a single repeatable-read read-only transaction, exports the results to CSV files, and verifies table row counts before and after.
- `reports/phase7_validation.md`: This validation report.
- `reports/sql_results/` directory containing eight CSV output files:
  - `q1_products_per_category.csv`
  - `q2_median_sugar_by_category.csv`
  - `q3_median_protein_by_category.csv`
  - `q4_top_protein_per_100kcal.csv`
  - `q5_nutriscore_by_category.csv`
  - `q6_nova_by_category.csv`
  - `q7_brands_most_products.csv`
  - `q8_missing_flagged_by_category.csv`

**Modified:**
- `README.md`: Updated to include instructions for executing Phase 7 SQL reports and to mark Phase 7 as implemented.

## SQL Concepts Demonstrated

The eight queries demonstrate the following required SQL techniques:
- **INNER JOIN / LEFT JOIN**: Used extensively to link products to their primary brands, extraction categories, bridge memberships, and nutritional measurements.
- **WHERE**: Used to filter for specific measurement bases (e.g., `'100g'`) and numeric eligibility flags (`TRUE`).
- **GROUP BY**: Used to aggregate data at the category and brand levels.
- **ORDER BY**: Used to sort results meaningfully (e.g., descending medians or product counts).
- **COUNT / AVG**: Used to calculate sample sizes, total memberships, average completion percentages, and missing value rates.
- **HAVING**: Used in Q7 to limit the brand ranking to those with more than 5 products.
- **CASE WHEN**: Used in Q5, Q6, and Q8 for conditional counting (e.g., tallying specific Nutri-Score grades or checking for missing fields).
- **PERCENTILE_CONT**: Used in Q2 and Q3 to accurately calculate the median sugar and protein content across product categories in PostgreSQL.
- **NULLIF**: Used to safely calculate percentages and ratios by preventing division by zero.

## The Eight SQL Reports and Findings

All queries respect Phase 3 cleaning and measurement-eligibility policies. Unreliable or ineligible measurements were safely bypassed, maintaining analytical integrity. Denominators count overlapping category memberships correctly, and unique product statistics prevent barcode double-counting.

### Q1: Products per category
*Goal: How many products belong to each food category?*
- **Biscuits**: 500 total memberships (25.0%), 500 unique products.
- **Breakfast cereals**: 500 total memberships (25.0%), 500 unique products.
- **Cereal bars**: 500 total memberships (25.0%), 500 unique products.
- **Yogurts**: 500 total memberships (25.0%), 500 unique products.
*(Note: There are 2,000 total memberships in the bridge table across 1,987 unique products. 13 dual-category products are correctly counted in both of their respective categories).*

### Q2: Median sugar content by category
*Goal: Which categories have the highest median sugar content per 100 g?*
- **Biscuits**: 26.00 g (324 eligible products)
- **Cereal bars**: 24.00 g (306 eligible products)
- **Breakfast cereals**: 17.00 g (292 eligible products)
- **Yogurts**: 8.10 g (307 eligible products)
*(Note: This perfectly matches the Phase 4 Pandas EDA notebook findings).*

### Q3: Median protein content by category
*Goal: Which categories have the highest median protein content per 100 g?*
- **Breakfast cereals**: 9.40 g (292 eligible products)
- **Cereal bars**: 7.10 g (306 eligible products)
- **Biscuits**: 6.80 g (325 eligible products)
- **Yogurts**: 3.50 g (313 eligible products)
*(Note: This perfectly matches the Phase 4 Pandas EDA notebook findings).*

### Q4: Top products by protein per 100 kcal
*Goal: Which products have the highest protein per 100 kcal, including brand information?*
1. **Carrefour Sensation Skyr Nature 0% M.G.** (Carrefour): 19.37 g/100 kcal
2. **HiPro** (Danone): 17.92 g/100 kcal
3. **Skyr** (Milbona): 17.74 g/100 kcal
...
*(Note: The ranking and values perfectly match Insight 3 from Phase 4. The top 10 products successfully linked to their primary brands via a `LEFT JOIN`).*

### Q5: Nutri-Score distribution by category
*Goal: How are Nutri-Score grades distributed across the categories?*
- **Biscuits**: Predominantly Grade E (268), followed by D (107).
- **Breakfast cereals**: Predominantly Grade C (188), followed by A (155).
- **Cereal bars**: Predominantly Grade D (211), followed by C (130).
- **Yogurts**: Predominantly Grade C (206), followed by A (107).
*(Note: This reproduces the categorical distribution insights from Phase 4).*

### Q6: NOVA processing classification by category
*Goal: How do NOVA processing classifications differ by category?*
- **Biscuits**: 85.3% NOVA 4 among classified (413/484).
- **Breakfast cereals**: 54.1% NOVA 4 among classified (262/484).
- **Cereal bars**: 91.0% NOVA 4 among classified (437/480).
- **Yogurts**: 55.6% NOVA 4 among classified (234/421).

### Q7: Brands with the most products
*Goal: Which brands have the most products (minimum > 5)?*
1. **Nestlé**: 70 products
2. **Gerblé**: 69 products
3. **Danone**: 65 products
4. **MERCADONA**: 64 products
5. **Bjorg**: 56 products

### Q8: Missing or flagged nutritional measurements by category
*Goal: Which categories have the most missing or flagged nutritional measurements?*
- **Yogurts**: Highest mean cleaned numeric null count (0.93/9 per product); 6.0% flagged (30/500).
- **Biscuits**: 0.31 numeric nulls on average; 3.6% flagged (18/500).
- **Cereal bars**: 0.14 numeric nulls on average; highest flagged share at 6.4% (32/500).
- **Breakfast cereals**: 0.12 numeric nulls on average; 2.2% flagged (11/500).

Numeric null counts include both source omissions and individually excluded values.
They cover nine fields, while reported completeness uses eight fields and retains
flagged reported observations.

### Final submission correction on 10 October 2026

The Q6, Q7 and Q8 prose above was corrected during final preparation because the
earlier narrative disagreed with the saved CSVs. `scripts/verify_saved_results.py`
independently recomputed all eight result sets from the cleaned data: all 54 rows
and 328 cells agreed. The CSVs, SQL and datasets were not modified. This offline
reconciliation is separate from the historical live execution described below;
no new API request or database connection was made for the correction.

Technique clarification: Q5 and Q6 actually use INNER JOINs. Q4 uses a LEFT JOIN
for brands and reads the previously guarded ratio; NULLIF is used directly in
percentage queries, not to recalculate the ratio in Q4.

## Live Neon Execution Status and Verification

**Execution Status**: Succeeded.
All eight queries were run successfully against the live Neon database using the `scripts/run_sql_reports.py` script. The transaction was explicitly locked to `READ ONLY` and `REPEATABLE READ`.

**Verification**:
- **Table Counts**: The runner script checked the counts before and after the queries. The row counts remained exactly 6,503 across the five tables (525 brands, 4 categories, 1,987 products, 2,000 memberships, 1,987 nutrition). **No data was modified.**
- **Tests Passed**: Running `python -m unittest discover -s tests -v` confirmed that all 89 offline tests continue to pass.
- **Dependencies**: `python -m pip check` passed.
- **Git Status**: `git diff --check` passed cleanly.
- **Phase 4 Consistency**: The PostgreSQL aggregation results for Q2, Q3, Q4, and Q5 completely matched the exploratory data analysis from Phase 4, validating that both the Python (Pandas) and SQL analysis methodologies were sound and properly respected the Phase 3 cleaning rules.

## Reproduction Commands

Run these commands from the repository root:

```powershell
# Run the 8 SQL reports (requires DATABASE_URL in .env)
.\.venv\Scripts\python.exe scripts/run_sql_reports.py

# Run all tests to ensure project integrity
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Remaining Limitations
- These SQL reports analyze a fixed subset of Open Food Facts API data and should not be used as broad market estimates.
- Measurement basis limitations (missing explicit denominators) continue to restrict the sample sizes for strict 100g comparative queries.

**Phase 7 is complete.**
