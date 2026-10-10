# FoodLens Phase 4: data analysis and insights validation

**Date:** 2026-10-09. **Status:** implemented and executed offline.

## Deliverables and reproduction

Created `notebooks/02_data_analysis.ipynb`, this report,
`scripts/execute_analysis.py`, and five PNG charts:

| Question | Figure in `reports/figures/` |
| --- | --- |
| Median sugars | [phase4_01_median_sugar.png](figures/phase4_01_median_sugar.png) |
| Median protein | [phase4_02_median_protein.png](figures/phase4_02_median_protein.png) |
| Top protein per 100 kcal | [phase4_03_top_protein_per_100kcal.png](figures/phase4_03_top_protein_per_100kcal.png) |
| Nutrition completeness | [phase4_04_nutrition_completeness.png](figures/phase4_04_nutrition_completeness.png) |
| Nutri-Score distribution | [phase4_05_nutriscore_distribution.png](figures/phase4_05_nutriscore_distribution.png) |

Updated `README.md` with execution instructions and analysis policies. Repository
agent instructions, Phase 2 EDA code/outputs, Phase 3 transformation code and
validation reports were inspected before implementation. The existing `.gitignore`
modification and untracked `.github/` directory were left untouched.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/execute_analysis.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The executor uses the current project interpreter in fresh kernels for both
supported working directories. It saves the executed notebook only after both
runs pass. Re-execution updates only Phase 4 notebook outputs and its five charts.
It does not call the extraction or transformation runners. No new dependencies
were added: the existing Pandas/NumPy, Matplotlib, nbformat, nbclient and ipykernel
environment was sufficient.

## Verified input and analysis policy

| Cleaned table | Actual rows |
| --- | ---: |
| products | 1,987 |
| brands | 525 |
| categories | 4 |
| product_categories | 2,000 |
| nutrition | 1,987 |

All five CSVs are loaded with explicit string identifiers before deliberate
numeric/Boolean conversion. All 83 leading-zero barcodes are preserved. Primary
keys, foreign keys and merge cardinalities are checked. The notebook displays
actual column names/dtypes, eligibility counts and the SHA-256 of each input CSV.

Products join to primary brands many-to-one and nutrition one-to-one, retaining
all 1,987 products. Category links join many-to-one to products and categories,
yielding exactly 2,000 unique barcode/category pairs. Each category has 500
memberships. All 13 shared products retain their two memberships. Overall
statistics and rankings use the unique-product view, never the expanded view.

Only the field(s) required by a question determine exclusions. No global
`has_numeric_flags` filter removes otherwise usable nutrients. A true eligibility
flag is checked against a present numeric value with no numeric reason flags.
Unresolved cross-field values remain stored but are not eligible. Statistical
outliers alone are not removed.

There are 1,254 unique products with confirmed 100 g basis, five with 100 ml basis,
and 728 with unknown basis. Questions 1 and 2 use only confirmed 100 g measurements.
Question 3 permits a known common mass or volume denominator because it cancels
in the ratio. Questions 4 and 5 concern coverage/classification, so they retain all
memberships regardless of measurement basis.

## Q1 and Q2: median sugars and protein by category

| Category | Median sugars, g/100 g | Sugar sample n | Median protein, g/100 g | Protein sample n | Total memberships |
| --- | ---: | ---: | ---: | ---: | ---: |
| Breakfast cereals | 17.00 | 292 | 9.40 | 292 | 500 |
| Yogurts | 8.10 | 307 | 3.50 | 313 | 500 |
| Biscuits | 26.00 | 324 | 6.80 | 325 | 500 |
| Cereal bars | 24.00 | 306 | 7.10 | 306 | 500 |

**Insight 1:** Biscuits have the highest median sugar content, **26.00 g/100 g**
among 324 eligible mass-basis memberships, followed by cereal bars at 24.00.
Breakfast cereals and yogurts have medians of 17.00 and 8.10 respectively. These
are different available-case subsets; missingness and basis exclusions may affect
the ordering. They are not per-serving or whole-market estimates.

**Insight 2:** Breakfast cereals have the highest median protein concentration,
**9.40 g/100 g** among 292 eligible memberships. Cereal bars, biscuits and yogurts
have medians of 7.10, 6.80 and 3.50. This describes protein concentration in the
selected records, not overall nutritional quality or a population difference.

Sugar uses **1,224 unique products /1,229 memberships**. Protein uses **1,231
unique products /1,236 memberships**. The differences reflect five retained
shared products in each eligible subset, not accidental duplication.

The notebook reconciles exclusions to each category's full denominator:

| Category | Nonmass/unknown basis | Mass-basis missing or flagged sugar | Mass-basis missing or flagged protein |
| --- | ---: | ---: | ---: |
| Breakfast cereals | 206 | 2 | 2 |
| Yogurts | 176 | 17 | 11 |
| Biscuits | 168 | 8 | 7 |
| Cereal bars | 191 | 3 | 3 |

For each nutrient, eligible n +nonmass/unknown +mass missing/flagged =500.
These exclusion groups are disjoint. The five volume-basis memberships are all
within the yogurt nonmass count.

## Q3: highest valid protein-per-100-kcal ratios

The formula is `100 * protein_g_per_100 / energy_kcal_per_100`, with units of
g protein per 100 kcal. Both operands must be eligible; kcal must be positive;
measurement basis must be explicitly 100 g or 100 ml. Missing, ineligible or
zero-denominator calculations remain null. No inferred basis or health score is
introduced. The notebook recalculates the formula independently, verifies values
and null positions against the saved Phase 3 metric, then uses that saved metric.

There are **1,204 eligible unique products**: 1,199 on mass basis and five on volume
basis. The other 783 products do not enter this ranking. All ten charted products
appear once by barcode. Ordering uses unrounded ratios descending and barcode
ascending for exact ties.

| Rank | Barcode | Product | Primary brand | Protein, g/100 kcal |
| --- | --- | --- | --- | ---: |
| 1 | `5400101078673` | Carrefour Sensation Skyr Nature 0% M.G. | Carrefour | 19.37 |
| 2 | `0034361482953` | HiPro | Danone | 17.92 |
| 3 | `4056489491217` | Skyr | Milbona | 17.74 |
| 4 | `3033491588136` | Yaourt protéiné Hipro Vanille 0%mg - 2x160g | Danone | 17.69 |
| 5 | `3033491482892` | Hipro fruit citron | Danone | 17.51 |
| 6 | `3273221114864` | Skyr bio | Vrai | 17.22 |
| 7 | `3560071495619` | High protein vanille | Carrefour | 17.04 |
| 8 | `3033491690334` | HiPRO Saveur Coco | Danone | 16.79 |
| 9 | `3560071495640` | High protein Myrtille | Carrefour | 16.73 |
| 10 | `3523230063715` | Skyr au lait de chèvre | Soignon | 16.55 |

**Insight 3:** Carrefour Sensation Skyr Nature 0% M.G. ranks highest among the
1,204 eligible products at **19.37 g protein/100 kcal**, calculated from 10.00 g
protein and 51.62524 kcal per 100 g. HiPro and Milbona Skyr follow at 17.92 and
17.74. Validity here means passing the implemented screens, not independent label
verification. Reported energy affects the ratio; this is not a health recommendation
or a ranking of protein per serving. The notebook table retains each product's
actual mass/volume basis and all extraction memberships.

## Q4: nutritional data completeness

Completeness is reported coverage across eight fields: kcal, protein,
carbohydrates, sugars, fat, saturated fat, fiber and salt. kJ is excluded to avoid
counting energy twice. Each product's score is `100 * reported_fields /8`.
All 500 memberships contribute per category, or 4,000 possible field slots.

| Category | Mean reported completeness, % | Median, % | All eight fields reported | Mean numeric eligibility coverage, % |
| --- | ---: | ---: | ---: | ---: |
| Breakfast cereals | 98.675 | 100.0 | 489/500 | 98.350 |
| Cereal bars | 98.525 | 100.0 | 478/500 | 97.475 |
| Biscuits | 96.625 | 100.0 | 442/500 | 96.075 |
| Yogurts | 88.950 | 87.5 | 225/500 | 88.125 |

**Insight 4:** Breakfast cereals have the highest mean reported completeness,
**98.675%**, narrowly ahead of cereal bars at 98.525%. Yogurts are lowest at 88.950%,
a **9.725 percentage-point** gap from breakfast cereals. Means are useful here
because three category medians tie at 100%. Across 1,987 unique products, overall
reported completeness is **95.6719%**, without counting shared products twice.

Reported completeness includes flagged values because they were reported. It
does not mean correctness or confirmed mass basis. The separate eligibility column
counts numerically eligible fields, also without a basis restriction. Neither
metric measures food health. Reporting practices and missingness may explain
category differences; this is not evidence of better nutrient composition.

## Q5: Nutri-Score distributions

Counts below use **all 500 memberships per category**. Unknown and not-applicable
states remain separate and in the denominator. Each count divided by five is its
percentage of the category. Full percentage tables are also displayed in the
notebook and its 100% stacked chart.

| Category | A | B | C | D | E | Unknown | Not applicable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Breakfast cereals | 155 | 55 | 188 | 77 | 19 | 6 | 0 |
| Yogurts | 107 | 91 | 206 | 24 | 31 | 33 | 8 |
| Biscuits | 6 | 26 | 79 | 107 | 268 | 12 | 2 |
| Cereal bars | 20 | 11 | 130 | 211 | 73 | 6 | 49 |

**Insight 5:** The modal grade is C for breakfast cereals (**37.6%**) and yogurts
(**41.2%**), E for biscuits (**53.6%**), and D for cereal bars (**42.2%**).
Combined D/E shares are 19.2%, 11.0%, 75.0% and 56.8% respectively, using all 500
memberships per category. Across unique products, **116 lack a grade**: 57 unknown
and 59 not applicable. These are source-provided classifications with incomplete
coverage, not grades recomputed from the cleaned nutrients. Not applicable is not
an unfavorable grade; the comparison does not establish causal category effects.

## Execution, tests and preservation

The final notebook contains **18 cells, including nine code cells**. Both full
executions used the project environment: Python 3.12.4, Pandas 3.0.6, NumPy 2.5.3
and Matplotlib 3.11.2. No `PYTHONPATH` workaround or global kernel installation was
used. The notebook was rerun after a chart readability adjustment.

| Check performed | Actual result |
| --- | --- |
| Fresh kernel with repository-root working directory | Nine code cells executed; zero errors; five embedded/exported charts |
| Fresh kernel with notebooks working directory | Nine code cells executed; zero errors; five embedded/exported charts |
| Notebook schema | Passed nbformat validation |
| Chart reproducibility | All five PNG hashes identical across the two working-directory runs |
| Chart readability | All five images visually inspected; titles, axes, units, values and labels readable |
| Insight consistency | Five insights generated from the same calculated tables used by charts |
| Category calculations | Independently selected barcode sets reproduce medians, sample sizes, coverage means and grade counts |
| Protein ratio | Saved and independently calculated values/null masks agree; no non-finite ratios |
| Existing automated suite | **54 tests passed in 5.085 seconds** |
| Dependency consistency | `No broken requirements found.` |
| `git diff --check` and explicit new-file whitespace checks | Passed; Git status/diff reviewed |

The executor emitted local IPython directory-permission and kernel-transport
warnings under the Windows environment. They did not prevent kernel execution;
no notebook cell errors occurred.

Preservation checks compare relative path sets, SHA-256 hashes, sizes and
modification times. All **54 existing data files**, including the five cleaned
CSVs, and `notebooks/01_eda.ipynb` remained unchanged. In-memory input DataFrames
also match their saved copies at notebook completion. No imputation, permanent
filtering, dataset regeneration or source writes occurred.

## Remaining analytical limitations and scope

- API sampling was nonrandom with fixed category targets. These findings do not
  represent all Open Food Facts products, market shares or consumer purchases.
- Strict basis/eligibility filtering selects subsets. Missingness may be systematic;
  nutrient-specific sample sizes differ, so categories cannot be compared as if
  every product had complete verified measurements.
- Shared memberships make category groups non-independent. Source values reflect
  the retained first observation, not multiple independent product measurements.
- Quality flags screen known issues but cannot verify all labels, preparation
  states or product-category assignments. Statistical extremes remain when eligible.
- Completeness is a reporting measure, not accuracy or food health. Nutri-Score is
  source-provided, incomplete and not recalculated. Primary brand labels are a
  simplified first-listed relationship rather than verified ownership.
- Protein-per-energy rankings depend on both source operands and exclude unknown
  bases. They do not evaluate serving sizes, dietary needs or overall food quality.

**Phase 4 ends here. No live API requests, commits, pushes, database/SQL work,
machine learning, dashboard or next-phase implementation was performed.**
