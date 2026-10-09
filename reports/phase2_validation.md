# FoodLens Phase 2 EDA validation

**Validation date:** 2026-10-09
**Result:** implemented and executed; exploratory analysis only.

Repository instructions in `.github/agents/AGENTS.md` were read before implementation.
No live Open Food Facts requests, cleaning, imputation, permanent deduplication,
outlier removal, database work, commits or pushes were performed.

## Deliverables

- `notebooks/01_eda.ipynb`: 32 cells, including 19 executable code cells and seven
  figures with calculated interpretations; executed outputs are embedded.
- `scripts/execute_eda.py`: executes the notebook in fresh project-venv kernels
  from both supported working directories and checks data preservation.
- `requirements-eda.txt`: optional pinned Matplotlib, nbformat, nbclient and
  ipykernel dependencies, including the existing Phase 1 requirements.
- `README.md`: Phase 2 setup, execution, scope and comparison policy.
- This report: observed findings and verification evidence.

The original `requirements.txt`, downloader, tests, Phase 1 report, and agent
instructions were not edited. The existing untracked `.github/` directory was
left untouched. Git's ownership check required a command-local
`-c safe.directory=...` setting; no global Git configuration was changed.

## Execution and verification

Run from the repository root with the project interpreter:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-eda.txt
.\.venv\Scripts\python.exe scripts/execute_eda.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The actual notebook executions used Python 3.12.4, pandas 3.0.6, NumPy 2.5.3,
Matplotlib 3.11.2 and nbclient 0.11.0. The runner used the exact `.venv`
interpreter, cleared `PYTHONPATH` from the child environment and required no
globally installed kernel.

| Check | Actual result |
| --- | --- |
| Fresh kernel, repository root working directory | 19 code cells executed; zero errors; seven PNG figures |
| Fresh kernel, `notebooks/` working directory | 19 code cells executed; zero errors; seven PNG figures |
| Notebook format/schema validation | Passed |
| Notebook's baseline, source checksums and membership assertions | Passed |
| Notebook's original DataFrame and CSV preservation assertions | Passed |
| Visual inspection of every figure, including revised energy axes | Passed; titles, axes, units and legends rendered |
| Existing extraction suite | **36 tests in 1.175 seconds — OK** |
| Dependency consistency | `No broken requirements found.` |
| `git diff --check` | Passed |

The Windows kernel emitted startup permission/transport warnings, but no notebook
cell errors. These warnings do not change the successful execution results.
The runner was repeated after notebook presentation edits; the delivered notebook
is the final successfully executed version.

### Preservation evidence

Before implementation, all **49 existing files under `data/`** were inventoried.
After execution and tests, their relative paths, SHA-256 hashes, byte sizes and
modification timestamps matched exactly. This includes existing raw data, source
page responses, manifests, checkpoints, backups and processed files. The notebook
also verifies its input CSV hash and in-memory DataFrame at the end of execution.

Input CSV:
`data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv`

Verified SHA-256:
`c7831ff6c476c8511365a543411d19ba090c65d89f51db537715f1b905d8776c`

## Verified dataset baseline

| Measure | Observed |
| --- | ---: |
| Original source records across saved pages | 2,000 |
| Saved page responses | 20 |
| Unique combined products / CSV rows | 1,987 |
| Analytical columns | 24 |
| Extraction categories | 4 |
| Products with two category memberships | 13 |
| Missing or duplicate combined barcodes | 0 |
| Membership discrepancies against source pages | 0 |

Each extraction contains 500 source records and 500 unique barcodes. Counts by
retained primary category are breakfast cereals 500, yogurts 498, biscuits 498,
and cereal bars 491. Counts using every preserved membership are 500 each.

The 13 overlap pairs are breakfast cereals/cereal bars 7, breakfast cereals/biscuits
2, breakfast cereals/yogurts 2, and biscuits/cereal bars 2. Category comparisons
use all memberships; overall summaries and the energy consistency scatter use
unique products. The latter is colored by retained primary category. Overlapping
groups are not independent, and their counts must not be added as unique products.

## Missing-value findings

Percentages use all 1,987 unique products. The notebook includes all 24 columns;
the 14 columns with missing values are listed here. The other ten have none.

| Column | Missing | Missing % |
| --- | ---: | ---: |
| fiber_g_100g | 351 | 17.66 |
| nova_group | 130 | 6.54 |
| nutriscore_grade | 116 | 5.84 |
| extracted_at_utc | 100 | 5.03 |
| salt_g_100g | 66 | 3.32 |
| energy_kj_100g | 55 | 2.77 |
| saturated_fat_g_100g | 54 | 2.72 |
| sugars_g_100g | 50 | 2.52 |
| carbohydrates_g_100g | 44 | 2.21 |
| protein_g_100g | 43 | 2.16 |
| fat_g_100g | 41 | 2.06 |
| product_name | 40 | 2.01 |
| energy_kcal_100g | 39 | 1.96 |
| brands | 32 | 1.61 |

All 100 missing extraction timestamps belong to legacy imports. Their import
times are not treated as original extraction times. Fiber coverage varies
substantially: only 227 of 500 yogurt memberships have fiber values, leaving
273 missing (54.6%). No missing value is replaced with zero.

## Suspicious values and statistical extremes

No negative, non-finite or non-numeric nutrient cells were found in the combined
CSV. The audit of nine nutrient fields across 2,000 saved source records also
found no negative, non-finite or invalid numeric/Boolean source cells. The notebook
documents that the exporter would map those cases to blanks, so they must be
distinguished from ordinary source omissions.

| Explicit review rule | Products flagged |
| --- | ---: |
| Any gram-denominated nutrient >100 g/100 g | 2 |
| Energy >1,000 kcal/100 g or >4,184 kJ/100 g | 3 |
| Sugars > carbohydrates +0.5 g/100 g | 5 |
| Saturated fat > total fat +0.5 g/100 g | 2 |
| Protein + carbohydrates + fat >105 g/100 g | 4 |
| Energy disagreement >max(20 kcal, 10% of reported kcal) after kJ/4.184 conversion | 83 |
| Unique products with any review flag | 91 |

Counts overlap and must not be summed. Energy discrepancies affect 83 of 1,931
products with both energy measures (4.30%). Maximum observed values include
**295 g salt/100 g**, **120 g carbohydrates/100 g**, and
**3,305.109 kcal/100 g**. The notebook traces the grossly implausible cases back
to the saved original nutrient values by extraction ID, page and record index.
It does not guess units, shift decimals, replace or delete observations.

Category-specific 1.5×IQR screening flags **500 unique products** in at least one
nutrient/category. Of these, **438 have no rule-based review flag**. Statistical
rarity alone does not prove invalidity; specialized formulations may legitimately
have unusual nutrient concentrations. Thresholds are disclosed analyst-selected
review criteria, not regulatory limits or automatic cleaning rules.

## Seven figures and interpretations

| Figure | Calculated interpretation |
| --- | --- |
| 1. Missingness by field | Fiber has the largest gap: 351 products, 17.66%; classification and legacy timestamp gaps are also explicit. |
| 2. Primary counts versus all memberships | Four sets of 500 memberships represent 1,987 products, demonstrating the overlap/retention policy rather than market prevalence. |
| 3. Top exact brand strings | MERCADONA is the most frequent exact string, 64 products (3.22%); exact strings are not normalized companies or market shares. |
| 4. Nutri-Score profiles by membership | D/E shares are 19.2% breakfast cereals, 11.0% yogurts, 75.0% biscuits and 56.8% cereal bars, retaining missing grades in denominators. |
| 5. NOVA profiles by membership | NOVA 4 covers 1,336 products: 67.24% of all products or 71.94% of classified products. Missing groups remain explicit. |
| 6. Six nutrient-distribution panels by membership | Yogurts have lower observed median energy and sugars. Available-case counts are shown; full extremes remain visible, with labelled symmetric-log axes for energy and salt. |
| 7. Energy-unit consistency | 83 paired records exceed the stated discrepancy tolerance; the scatter retains all paired values and highlights source-review candidates. |

Membership-based nutrient medians:

| Category | Energy (kcal/100 g) | Sugars (g/100 g) |
| --- | ---: | ---: |
| Breakfast cereals | 397.39 | 15.00 |
| Yogurts | 78.00 | 5.50 |
| Biscuits | 467.00 | 25.00 |
| Cereal bars | 416.67 | 23.73 |

These are available-case sample comparisons on the declared per-mass basis,
not per-serving comparisons or statements about all products in a category.

## Phase 3 considerations and remaining limitations

Phase 3 should define auditable decisions for implausible concentrations,
cross-field/energy inconsistencies, category-specific missingness, exact brand
and name variants, classification gaps and unknown legacy extraction times.
Barcodes and all memberships must remain traceable; names are not product keys.
IQR flags alone should not trigger deletion or winsorization. Source evidence is
needed before deciding corrections or quarantine rules. None was implemented.

Sampling was nonrandom, used API-default ordering and fixed category targets, and
cannot represent all Open Food Facts products or the food market. Nutrient
missingness may be systematic; available-case denominators differ. Source
classifications are incomplete and not independently recalculated. Shared
memberships and first-row retention limit independent category comparisons.

No serving-size, original nutrient-unit or prepared/unprepared fields exist in
the combined export, so serving-size analysis and definitive measurement-basis
validation are unsupported. Source snapshots may come from different extraction
times; legacy timestamps are unknown. The saved data support this reproducible
EDA, not population estimates, time trends or causal conclusions.

**Phase 2 stops here.**
