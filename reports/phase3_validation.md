# FoodLens Phase 3B: cleaning and transformation validation

**Validation date:** 2026-10-09. **Status:** implemented and executed offline.

Phase 3B follows the simplified five-table request. It supersedes the proposed
six-table structure and blanket numeric quarantine scenario in the Phase 3A plan.
There is one primary brand per product and one wide nutrition row per product.
No database, SQL, dashboard, new API request or Phase 4 analysis was implemented.

## Files and reproduction

Created:

- `src/clean_transform.py`
- `tests/test_clean_transform.py`
- `data/cleaned/brands.csv`
- `data/cleaned/products.csv`
- `data/cleaned/categories.csv`
- `data/cleaned/product_categories.csv`
- `data/cleaned/nutrition.csv`
- `reports/phase3_validation.md`

Modified `README.md` with commands, reload instructions and measurement-basis
clarifications. The existing downloader, dependencies, extraction tests, Phase 1/2
reports, Phase 3A plan, repository agent instructions and notebook were not edited.

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m src.clean_transform
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The existing environment was used directly: Python 3.12.4, Pandas 3.0.6 and NumPy
2.5.3. No `PYTHONPATH` workaround, new dependency, configuration framework or
network access is needed. The module resolves input/output paths relative to its
repository location; the documented module command assumes the repository root.

Input: `data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv`.
SHA-256: `c7831ff6c476c8511365a543411d19ba090c65d89f51db537715f1b905d8776c`.

Each execution verifies the input checksum and schema against combined metadata,
complete category checkpoints, all saved response checksums, retained barcode
pointers, nutrient matches and full extraction memberships. The helper functions
reused from the downloader only read JSON, check values/hashes and write atomic
output files; the downloader's extraction or rebuilding workflows are not called.

## Actual output counts and relationships

The source baseline remains 2,000 original records across 20 saved pages, 1,987
unique products and 24 original analytical fields. Generated outputs were reloaded
and checked, rather than relying only on their pre-export DataFrames.

| Table | Rows | Key | Relationship |
| --- | ---: | --- | --- |
| brands | 525 | `brand_id` | One brand label to zero or more products |
| products | 1,987 | `barcode` | Nullable primary-brand FK; exactly one nutrition row |
| categories | 4 | `category_id` | Extraction categories only |
| product_categories | 2,000 | (`barcode`, `category_id`) | Product/category many-to-many bridge |
| nutrition | 1,987 | `barcode` | PK and FK to products |

All primary keys are unique and non-null. Every foreign key resolves. The product
and nutrition barcode sets equal the original combined CSV exactly. All 83
leading-zero barcodes survive CSV export/reload with explicit string dtypes.

Each extraction category retains 500 memberships. All 13 overlapping products
retain both categories; the bridge has no duplicate pairs. Overall summaries must
use unique products; category summaries may include a shared product in two groups.
`primary_category_id` preserves first-extraction provenance and is not an exclusive
classification. No taxonomy labels are inferred from the ambiguous flattened
source taxonomy field. Original taxonomy data remain in the preserved inputs.

## Cleaning decisions actually implemented

### Identity, text, primary brands and classifications

- Barcodes are preserved verbatim. Missing, malformed or duplicate combined
  identifiers stop the transformation; no padding, numeric conversion or silent
  deduplication occurs.
- Product names and primary-brand tokens receive Unicode NFC normalization,
  leading/trailing whitespace removal and repeated-whitespace collapse. Case,
  accents and punctuation remain. Ten product names changed representation.
- The first nonempty comma-separated source brand is selected consistently.
  There are 379 multi-brand source strings, 1,955 products with a primary brand,
  32 without one, and 525 distinct selected labels. Full original brand strings
  and product names remain in the products table. There are no fuzzy/case merges
  or corporate-ownership inferences. `brand:<normalized label>` is a stable text ID.
- Missing grade/NOVA values remain null. Nutri-Score source states are retained:
  1,871 reported, 57 unknown and 59 not applicable. NOVA is nullable `Int64` with
  valid values 1-4. No classifications are calculated or guessed.
- Known extraction timestamps are parsed as UTC; all 100 unknown legacy times
  remain missing. Import time is not substituted for original extraction time.

### Nutrients, flags and eligibility

Nine nutrients are represented, with kcal/kJ for energy and grams for the other
seven. All rule comparisons are evaluated on the original finite observations
before any value is nulled. Thresholds are project review criteria, not regulatory
limits or proof of a correct replacement value.

Each nutrient has four columns:

1. `reported_<nutrient>_per_100`: the exact original CSV cell as nullable string.
2. `<nutrient>_per_100`: nullable `Float64`; clearly implausible individual values
   are null here, while unresolved cross-field observations remain numeric.
3. `<nutrient>_flags`: semicolon-separated reason codes, null if no numeric issue.
4. `<nutrient>_eligible`: true only when the numeric value is present and has no
   numeric reason flag. It does not by itself establish a gram denominator.

For example, the nutrient name `protein_g` gives `protein_g_per_100` and
`reported_protein_g_per_100`. Numeric flags remain separate from source missingness:
a missing source cell has a missing reported value and no numeric error flag.
A nulled implausible measurement has a preserved reported value and a reason flag.

| Rule code | Predicate | Products affected | Action |
| --- | --- | ---: | --- |
| NUM_PARSE | Present but unparseable numeric input, including Boolean input | 0 | Null numeric value; preserve reported input |
| NUM_NONFINITE | Infinity or other parsed non-finite value | 0 | Null numeric value |
| NUM_NEGATIVE | Numeric value <0 | 0 | Null numeric value |
| GRAM_GT100 | Gram nutrient >100 on explicit mass or unknown basis | 2 | Null that individual measurement; unknown basis remains an uncertainty |
| VOLUME_GRAM_GT100 | Gram numerator >100 with explicit 100 ml denominator | 0 | Review flag only; no mass-limit deletion |
| ENERGY_EXTREME | kcal >1,000 or kJ >4,184 per reported 100 units | 3 | Null only the individually excessive measurement |
| SUGAR_GT_CARB | Sugar >carbohydrates +0.5 g | 5 | Flag both; keep numeric values unless independently invalid |
| SATFAT_GT_FAT | Saturated fat >fat +0.5 g | 2 | Flag both; keep numeric values unless independently invalid |
| MACRO_SUM_GT105 | Protein +carbohydrates +fat >105, all present, not explicit volume basis | 4 | Flag all three; keep otherwise valid individual values |
| ENERGY_DISAGREEMENT | abs(kcal -kJ/4.184) >max(20 kcal, 10% of kcal) | 83 | Flag both; do not choose which energy is correct |

There are **91 unique numerically flagged products**. Rule counts overlap.
Component, subtotal and energy review flags make all implicated operands
ineligible symmetrically, without overwriting their reported or otherwise valid
numeric values. Unrelated nutrients in the same product remain available.

Only **five individual numeric values in five products** become additional nulls:

| Barcode | Saved value | Numeric field made null |
| --- | ---: | --- |
| `8901063139329` | 295 | Salt, g per reported 100 units |
| `0602652419263` | 120 | Carbohydrates, g per reported 100 units |
| `8410376033267` | 3,305.1094890511 | Energy, kcal per reported 100 units |
| `5000168036755` | 2,092.8571428571 | Energy, kcal per reported 100 units |
| `3175681135024` | 1,364.2857142857 | Energy, kcal per reported 100 units |

The carbohydrate record explicitly declares 100 g. The salt record lacks a
declared denominator; its 295 value is conservatively excluded under the
documented plausibility screen, not corrected to an assumed decimal or unit.
Extreme energy exclusions also retain basis uncertainty. Their paired kJ values
remain numeric with review flags. Exact source strings, not the rounded display
values in this table, are retained in `nutrition.csv`.

Across all fields, **193 distinct observed measurements** carry numeric flags:
five are nulled individually and 188 remain numeric but are ineligible for strict
analysis. No product is removed. Statistical IQR flags alone have no cleaning
effect; the EDA notebook retains its statistical investigation and outputs.

### Measurement basis and strict comparisons

The retained source record's `nutrition_data_per` supplies the basis. The original
declaration is also retained. Missing or unrecognized declarations map to
`unknown`, never automatically to mass.

| Basis | Unique products | Treatment |
| --- | ---: | --- |
| 100g | 1,254 | Eligible fields may enter strict per-100-g comparisons |
| 100ml | 5 | Preserve volume measurements; exclude from per-100-g comparisons |
| unknown | 728 | Preserve observations; require a labelled assumption for sensitivity analysis |

No density, serving-size or preparation-state conversion is inferred. The saved
`_100g` nutrient keys alone do not resolve the denominator. The explicit volume
records have 45 observations, all retained. Basis is distinct from numeric flags.

For strict energy comparisons, filter `measurement_basis == '100g'` **and**
`energy_kcal_eligible == True`. Apply the equivalent flag for any other nutrient.
For joint comparisons, require every involved nutrient to be eligible. These
flags mean the measurement passed the implemented screens, not label verification.

## Missingness before and after

Counts use all 1,987 products. Original reported columns keep exactly the input
missingness; the numeric column gains only individual-invalidity nulls.

| Nutrient | Missing in input/reported | Null in numeric output | Flagged observations | Numerically eligible | Eligible with explicit 100 g |
| --- | ---: | ---: | ---: | ---: | ---: |
| Energy kcal | 39 | 42 | 83 | 1,865 | 1,201 |
| Energy kJ | 55 | 55 | 83 | 1,849 | 1,189 |
| Protein | 43 | 43 | 4 | 1,940 | 1,231 |
| Carbohydrates | 44 | 45 | 9 | 1,934 | 1,229 |
| Sugars | 50 | 50 | 5 | 1,932 | 1,224 |
| Fat | 41 | 41 | 6 | 1,940 | 1,231 |
| Saturated fat | 54 | 54 | 2 | 1,931 | 1,222 |
| Fiber | 351 | 351 | 0 | 1,636 | 1,009 |
| Salt | 66 | 67 | 1 | 1,920 | 1,219 |
| **Total measurement cells** | **743** | **748** | **193** | **16,947** | **10,755** |

There are 17,883 possible product/nutrient cells. The 17,140 original observations
remain available as reported strings; 17,135 remain numeric, with 16,947 passing
the numeric eligibility rules. Missing values never become zero. Numeric null
counts and flagged counts must not be added without accounting for overlap.

| Product field | Missing before | Missing after |
| --- | ---: | ---: |
| Name | 40 | 40 |
| Brand / primary brand FK | 32 | 32 |
| Nutri-Score grade | 116 | 116 |
| NOVA group | 130 | 130 |
| Original extraction timestamp | 100 | 100 |

## Derived columns

| Column | Formula | Units and safeguards | Non-null rows |
| --- | --- | --- | ---: |
| protein_g_per_100kcal | 100 x protein / kcal | g per 100 kcal; both operands eligible, energy >0 and explicit shared basis 100 g or 100 ml | 1,204 |
| sugar_to_carbohydrate_ratio | sugars / carbohydrates | Dimensionless; both operands eligible, carbohydrates >0 and explicit shared basis | 1,223 |
| nutrition_completeness_pct | 100 x reported core-field count /8 | kcal plus protein, carbohydrates, sugars, fat, saturated fat, fiber and salt; excludes kJ to avoid duplicate energy coverage | 1,987 |

Unknown basis, missing operands, ineligible operands or zero denominators yield
null ratios, never infinity. The per-100 denominator cancels for ratios with an
explicit common basis, including 100 ml. No density conversion occurs. A valid
zero numerator stays zero. Ratios are not clipped or converted to a health score.

Completeness measures reported coverage, not correctness or analysis eligibility.
It ranges from 0 to 100 with a mean of 95.6719%. Numeric exclusions do not erase
the fact that a value was reported. This definition keeps missingness separate
from quality concerns.

## Data dictionary and traceability

All identifier/text columns use Pandas nullable `string`. CSV itself stores no
type metadata, so `reload_tables()` explicitly restores types. Empty cells mean
null; literal strings such as `NA` are preserved.

| Table | Columns and types | Nullable fields / constraints |
| --- | --- | --- |
| brands | brand_id, brand_name: string | Neither nullable; both unique; case-preserving labels |
| products | barcode, product_name, original_product_name, brand_id, original_brands, nutriscore_grade, nutriscore_status, primary_category_id, extraction_id, record_origin, source_relative_path, source_response_sha256: string; nova_group, source_page, source_record_index: Int64; extracted_at_utc: UTC datetime | Names, brands/FK, grade, NOVA and timestamp may be null; barcode PK; brand/category FKs |
| categories | category_id, category_name: string | Non-null, four unique extraction slugs and readable names |
| product_categories | barcode, category_id: string | Non-null composite PK and FKs |
| nutrition | barcode, measurement_basis, reported_measurement_basis: string; nine reported strings, nine Float64 numeric fields, nine string flags, nine boolean eligibility fields; three Float64 derived columns; has_numeric_flags: boolean | Barcode PK/FK; reported basis/measurements, numeric fields, flags and ratios may be null; completeness and Boolean fields non-null |

Nutrient names are `energy_kcal`, `energy_kj`, `protein_g`, `carbohydrates_g`,
`sugars_g`, `fat_g`, `saturated_fat_g`, `fiber_g`, `salt_g`. Their source CSV and
raw dictionary keys are mapped explicitly in `NUTRIENTS` in the module.

Every product retains its extraction ID, page, zero-based record index, relative
saved-response path and canonical response checksum. Joining nutrition to
products therefore identifies the exact retained raw observation. Original
duplicate category observations remain in preserved pages. Complete extraction
memberships are independently checked against all source occurrences.

## Executed tests and preservation evidence

| Check actually executed | Result |
| --- | --- |
| Transformation using project interpreter | Passed; all five requested CSVs generated |
| CSV reload with explicit string/numeric/Boolean types | Passed; all frames compared with pre-export values |
| Primary keys, foreign keys and category reconciliation | Passed on generated/reloaded outputs |
| Exact reported observation comparison against original CSV | Passed for every nutrient cell |
| Non-null numeric observations equal their source values | Passed within floating-point tolerance 1e-12 |
| Missing source measurements remain missing; no new zeros | Passed |
| Leading-zero barcode preservation | All 83 retained |
| Repeated transformation | Passed; all five CSV bytes and modification times identical |
| Focused new transformation suite | 18 tests passed in 3.755 seconds on the initial focused run |
| Complete suite after the additional source-corruption check | **54 tests passed in 4.174 seconds**: 36 extraction +18 transformation |
| Dependency consistency | `No broken requirements found.` |
| `git diff --check` | Passed for tracked changes |
| Explicit no-index whitespace checks of new source/tests/report | Passed |

Transformation tests cover real-data reconciliation, text and primary-brand
selection, missing values/classes, barcode failures, negative/invalid/non-finite
numbers, individual exclusions, unresolved pairs, rule boundaries, measurement
bases, derivations, zero denominators, IQR-only retention, broken FKs/memberships,
CSV round trips, repeated execution, output conflicts, atomic write failure,
source preservation and corrupted CSV/page checksums. Tests block real Requests
HTTP calls. Deliberately altered test-record copies remain in memory or temporary
directories and never enter project data.

An additional no-index check of all new CSVs found two trailing-space warnings
inside quoted, multiline `original_product_name` values in `products.csv`
(barcodes `0018627102557` and `0018627114314`). These spaces are present in the
original names and intentionally retained for source fidelity; the cleaned names
have normalized whitespace. The other four CSVs have no whitespace warnings.
No data were altered merely to silence a text-oriented Git check. Git also
emitted its normal LF-to-CRLF working-copy notice for Markdown. Git status/diff
were reviewed; the pre-existing untracked `.github/` directory and Phase 3A plan
were left untouched. No files were staged, committed or pushed.

Before implementation, recorded relative paths, SHA-256 hashes, sizes and
modification times for **49 existing data files and the EDA notebook**. All 50
matched after transformation and tests; the protected data path set is unchanged.
Only the five requested CSVs were added under `data/cleaned/`. The notebook was
read, not executed or rewritten. No original dataset, backup, checkpoint or
extraction artifact was modified, deleted or replaced.

Publication first checks every target for conflicts. Identical outputs are reused;
differing files stop the run before any new file is written. New CSV writes use
the existing atomic temporary-file/flush/fsync/replace helper. Atomicity is per
file, not across all five. After interruption, rerun to complete missing files,
then use outputs only after successful validation. No additional audit database
or configuration layer was introduced.

Output SHA-256 hashes:

| File | SHA-256 |
| --- | --- |
| brands.csv | fdc10c0761c5ad7563784cb6fa6ce290c17c510f1da74adff88c23c9f0e5cbde |
| products.csv | 9bf2bb50247d0c376efea908a3ab5cc35a5a47dd9179e9bc092d3e943127c540 |
| categories.csv | e411db0b835028ad5a46b3e96f703239eee48a625b3937c5269402323eac7d04 |
| product_categories.csv | d10e12fb8dc6c9be4f10cc367623f14e7766cbcfdded3a2282da47e0a75e4dea |
| nutrition.csv | 2ce5887ab59f9f6a69a6310366092b8fd51c0a9fad68a1fd525471ca81f35ff3 |

## Remaining limitations

- Saved source consistency does not prove the package label is correct. Unknown
  measurement bases and unresolved paired values remain unresolved; no guessed
  corrections, nutrient enrichment or serving conversions were applied.
- Strict mass/eligibility filters reduce available counts and may select better
  documented products. Report per-analysis denominators. Missingness, especially
  fiber, may be systematic. The nonrandom API sample is not representative of
  all Open Food Facts products or the market.
- First-listed brand is a reproducible simplification, not verified ownership.
  It omits secondary brand relationships and treats commas as source separators.
  Case variants remain distinct labels.
- Numeric eligibility does not include manual product-scope adjudication. The
  source's soy-sauce/cereal-bar category conflict and contextually suspicious
  IQR-only values identified in Phase 3A remain available for documented review.
  No source extraction membership was removed.
- The historical EDA retains its original `_100g` assumptions. Phase 3B's raw
  basis findings qualify those comparisons; the notebook was preserved as requested.
- CSV users must restore identifier/Boolean/numeric types explicitly. Concurrent
  transformation writers are not supported; run one transformation at a time.

**Phase 3B stops here. No Phase 4 or database work was performed.**
