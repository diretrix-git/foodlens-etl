# FoodLens Phase 5: PostgreSQL design and ERD validation

**Date:** 2026-10-10. **Status:** schema and ERD implemented; offline validation passed.
**PostgreSQL DDL execution was not verified because a local installation/instance was not found.**

## Source of truth and scope

Inspected `.github/agents/AGENTS.md`, the complete README, `src/clean_transform.py`,
transformation tests, Phase 3 and Phase 4 validation reports, all source cells of
`notebooks/02_data_analysis.ipynb`, and the actual five CSV headers, values and nulls
before designing the schema. The implemented Phase 3B five-table model supersedes
the older six-table proposal. No source data were regenerated.

## Design and relationships

Five tables separate primary brand labels, product identity/provenance, extraction
categories, category memberships, and nutrition. Brand/category descriptions are
stored once, and the bridge avoids repeating product records for multiple categories.
Text IDs are reused exactly from the CSVs; no surrogate IDs or unnecessary entities
are introduced. Original text, source provenance, quality flags and derived metrics
remain as explicit audit/analysis fields to preserve the existing output contract.
This is a normalized entity model with intentionally retained derived and audit
fields, not a claim that every stored field is irreducible under strict normalization.

| Table | Actual rows | Columns | Primary key |
| --- | ---: | ---: | --- |
| brands | 525 | 2 | brand_id |
| products | 1,987 | 16 | barcode |
| categories | 4 | 2 | category_id |
| product_categories | 2,000 | 2 | (barcode, category_id) |
| nutrition | 1,987 | 43 | barcode |

- `products.brand_id -> brands.brand_id`: each product has zero or one primary
  brand; a brand may have zero or many products. Actual data: 1,955 branded products,
  32 without a brand. Brand names are unique exact normalized labels, not inferred
  corporate ownership. Original multi-brand strings remain in products.
- `products.primary_category_id -> categories.category_id`: required first-extraction
  provenance, not exclusive category assignment.
- Bridge FKs reference products and categories. Each bridge row has exactly one
  parent of each kind; a category can have zero or many links. Every product must
  have at least its primary membership at commit. All four categories have 500
  memberships; 13 products have two categories and 1,974 have one.
- `nutrition.barcode -> products.barcode` is also the nutrition PK, preventing
  duplicates/orphans. A reciprocal deferred `products.barcode -> nutrition.barcode`
  FK enforces exactly one nutrition row per product at commit, rather than merely
  at most one. Actual barcode sets are identical.
- A deferred composite FK from `products.(barcode, primary_category_id)` to
  `product_categories.(barcode, category_id)` ensures the primary category belongs
  to that product. All actual rows satisfy it.

There are five PK constraints, two name UNIQUE constraints, seven FKs and 25 CHECKs.
PK/UNIQUE indexes are automatic; three additional indexes support brand/category
FK lookups. Default FK actions are NO ACTION, with no cascading deletion. The two
product-side cyclic FKs are DEFERRABLE INITIALLY DEFERRED; the others are immediate.
Phase 6 must insert products before their child rows and complete nutrition and
memberships in the same transaction before committing. No loader is implemented.

## Types, nulls and CHECK policy

All barcodes are `text`, with the existing ASCII 8-14 digit rule on products.
FKs require matching text identifiers in child tables. All 83 leading-zero codes,
including `00038317`, remain exact strings. Names, IDs, source paths, hashes,
reported nutrient observations and semicolon-delimited review flags use `text`.
No fixed text-length limits, new normalization, padding or barcode arithmetic are used.

Numeric nutrient values and ratios use `double precision`, matching Phase 3 Float64
without decimal scale rounding. Numeric CHECKs require finite nonnegative values,
but impose no nutrient ceilings, sugar/carbohydrate inequality, saturated-fat/fat
inequality, macro-sum bound, energy conversion equality or ratio upper bound.
All 188 flagged-but-retained numeric observations pass. Reported text accepts the
original observations, including the five values whose cleaned numeric cells are null.
A regression fixture also accepts a flagged volume concentration above 100 and
sugars above carbohydrates. These fixtures exist only in memory.

Classification checks allow grades a-e, NOVA 1-4, and the transformer-supported
Nutri-Score statuses `reported`, `unknown`, `not_applicable`, `missing`, `invalid`.
Grade presence must agree with reported status. Actual statuses are 1,871 reported,
57 unknown and 59 not applicable. Measurement basis allows `100g`, `100ml`, `unknown`;
actual counts are 1,254, 5 and 728. Completeness is bounded 0-100. Source pages are
positive, record indexes nonnegative, and origins are `api` or `legacy_import`.

Names, primary brands, grades, NOVA, legacy timestamps, reported basis, nutrient
measurements, flags and derived ratios are nullable by meaning. A flag column can
be entirely null (fiber) without becoming required. Eligibility flags, basis,
completeness, provenance identifiers and relational keys are required. Timestamps
use `timestamptz` and preserve instants; the session timezone controls their display.
NOVA uses `smallint`; source page and record index use `integer`. CSV blank cells
map to SQL NULL; literal text such as NA is not automatically missing. No zero or
other default fills missing nutrition.

## Complete CSV-to-SQL mapping and observed nullability

Every CSV column maps to the same-named SQL column in the same order. The following
inventory was generated from the checked-in SQL and actual CSVs. NULL counts are
observed cells; nullable columns remain nullable even when currently complete.

### brands

| CSV / SQL column | PostgreSQL type | Nullable | Actual nulls |
| --- | --- | --- | ---: |
| `brand_id` | `text` | No | 0 |
| `brand_name` | `text` | No | 0 |

### categories

| CSV / SQL column | PostgreSQL type | Nullable | Actual nulls |
| --- | --- | --- | ---: |
| `category_id` | `text` | No | 0 |
| `category_name` | `text` | No | 0 |

### products

| CSV / SQL column | PostgreSQL type | Nullable | Actual nulls |
| --- | --- | --- | ---: |
| `barcode` | `text` | No | 0 |
| `product_name` | `text` | Yes | 40 |
| `original_product_name` | `text` | Yes | 40 |
| `brand_id` | `text` | Yes | 32 |
| `original_brands` | `text` | Yes | 32 |
| `nutriscore_grade` | `text` | Yes | 116 |
| `nutriscore_status` | `text` | No | 0 |
| `nova_group` | `smallint` | Yes | 130 |
| `primary_category_id` | `text` | No | 0 |
| `extraction_id` | `text` | No | 0 |
| `source_page` | `integer` | No | 0 |
| `source_record_index` | `integer` | No | 0 |
| `extracted_at_utc` | `timestamptz` | Yes | 100 |
| `record_origin` | `text` | No | 0 |
| `source_relative_path` | `text` | No | 0 |
| `source_response_sha256` | `text` | No | 0 |

### product_categories

| CSV / SQL column | PostgreSQL type | Nullable | Actual nulls |
| --- | --- | --- | ---: |
| `barcode` | `text` | No | 0 |
| `category_id` | `text` | No | 0 |

### nutrition

| CSV / SQL column | PostgreSQL type | Nullable | Actual nulls |
| --- | --- | --- | ---: |
| `barcode` | `text` | No | 0 |
| `measurement_basis` | `text` | No | 0 |
| `reported_measurement_basis` | `text` | Yes | 728 |
| `reported_energy_kcal_per_100` | `text` | Yes | 39 |
| `energy_kcal_per_100` | `double precision` | Yes | 42 |
| `energy_kcal_flags` | `text` | Yes | 1904 |
| `energy_kcal_eligible` | `boolean` | No | 0 |
| `reported_energy_kj_per_100` | `text` | Yes | 55 |
| `energy_kj_per_100` | `double precision` | Yes | 55 |
| `energy_kj_flags` | `text` | Yes | 1904 |
| `energy_kj_eligible` | `boolean` | No | 0 |
| `reported_protein_g_per_100` | `text` | Yes | 43 |
| `protein_g_per_100` | `double precision` | Yes | 43 |
| `protein_g_flags` | `text` | Yes | 1983 |
| `protein_g_eligible` | `boolean` | No | 0 |
| `reported_carbohydrates_g_per_100` | `text` | Yes | 44 |
| `carbohydrates_g_per_100` | `double precision` | Yes | 45 |
| `carbohydrates_g_flags` | `text` | Yes | 1978 |
| `carbohydrates_g_eligible` | `boolean` | No | 0 |
| `reported_sugars_g_per_100` | `text` | Yes | 50 |
| `sugars_g_per_100` | `double precision` | Yes | 50 |
| `sugars_g_flags` | `text` | Yes | 1982 |
| `sugars_g_eligible` | `boolean` | No | 0 |
| `reported_fat_g_per_100` | `text` | Yes | 41 |
| `fat_g_per_100` | `double precision` | Yes | 41 |
| `fat_g_flags` | `text` | Yes | 1981 |
| `fat_g_eligible` | `boolean` | No | 0 |
| `reported_saturated_fat_g_per_100` | `text` | Yes | 54 |
| `saturated_fat_g_per_100` | `double precision` | Yes | 54 |
| `saturated_fat_g_flags` | `text` | Yes | 1985 |
| `saturated_fat_g_eligible` | `boolean` | No | 0 |
| `reported_fiber_g_per_100` | `text` | Yes | 351 |
| `fiber_g_per_100` | `double precision` | Yes | 351 |
| `fiber_g_flags` | `text` | Yes | 1987 |
| `fiber_g_eligible` | `boolean` | No | 0 |
| `reported_salt_g_per_100` | `text` | Yes | 66 |
| `salt_g_per_100` | `double precision` | Yes | 67 |
| `salt_g_flags` | `text` | Yes | 1986 |
| `salt_g_eligible` | `boolean` | No | 0 |
| `protein_g_per_100kcal` | `double precision` | Yes | 783 |
| `sugar_to_carbohydrate_ratio` | `double precision` | Yes | 764 |
| `nutrition_completeness_pct` | `double precision` | No | 0 |
| `has_numeric_flags` | `boolean` | No | 0 |

## ERD and reproduction

Created `sql/schema.sql`, `reports/erd.png`, `reports/erd.dbml`, this report,
`scripts/generate_erd.py`, `scripts/validate_phase5.py`, and
`tests/test_phase5_schema.py`. README now documents fresh-database schema creation,
transaction requirements and offline reproduction.

The renderer reads column definitions, PKs, UNIQUE constraints, CHECK expressions
and all seven FKs from SQL. It writes editable DBML and renders a 4,200 x 2,380 PNG
with the existing Matplotlib dependency. Five colored table headers, all 65 columns,
full PostgreSQL type names, PK/FK/UQ markers, nullability and crow's foot cardinalities
are visible. The five relationship connectors summarize the seven physical FKs;
notes explain reciprocal nutrition and primary-membership enforcement at commit.
The PNG was visually inspected and legend spacing corrected.

DBML includes all columns, PK/UQ definitions, CHECK expressions and six explicit
references. It expresses the reciprocal nutrition FKs as one one-to-one relationship
plus the reverse-FK comment to avoid duplicate endpoint declarations. Deferred
transaction timing is documented in notes/comments because DBML cannot encode it.
SQL remains authoritative for enforcement timing and supporting indexes. No external
DBML editor/parser was available or used; third-party DBML import is not verified.

```powershell
.\.venv\Scripts\python.exe scripts/generate_erd.py
.\.venv\Scripts\python.exe scripts/validate_phase5.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

For an installed PostgreSQL server, README provides `createdb` and
`psql -X -v ON_ERROR_STOP=1 -f sql/schema.sql` instructions against a fresh database.
Schema creation is transactional and intentionally fails on existing tables.
No CREATE DATABASE, INSERT, COPY, seed records or record-loading workflow is included
in schema.sql. The documented commands were not executed here.

## Validation evidence and limitations

| Executed check | Result |
| --- | --- |
| Actual row counts | 525 / 1,987 / 4 / 2,000 / 1,987 as expected |
| CSV/SQL names, order and types | All 65 columns agree; values parse without truncation |
| PKs and name uniqueness | All five PKs and two unique names pass |
| Foreign keys | All seven references resolve, including reverse nutrition and composite membership |
| Nullability | No required column contains a blank; missing measurements remain nullable |
| Leading-zero identifiers | All 83 preserved; barcodes read as strings |
| Source relationships and nutrient observations | Existing `load_inputs`, `reload_tables`, `validate_tables` pass with HTTP blocked |
| Scalar CHECK compatibility | All actual rows pass all 25 translated CHECK expressions |
| Suspicious measurements | All 188 retained flagged numeric cells accepted |
| SQL/DBML mapping | Regenerated DBML equals checked-in DBML; all 65 columns and FK semantics represented |
| PNG | Visually reviewed; every column/type and relationship legend readable |
| Focused schema tests | 6 passed |
| Full existing + new offline suite | **60 tests passed in 6.660 seconds** |
| Dependency consistency | No broken requirements found |
| PostgreSQL execution | **Not verified: local PostgreSQL unavailable** |

The offline validator uses Python for type/key checks and SQLite only to evaluate
translated scalar expressions with bound values (regex and Infinity syntax adapted).
It creates no tables and inserts no records. This verifies dataset compatibility,
not PostgreSQL parsing, planner/catalog behavior, special-value semantics or deferred
constraint execution. PostgreSQL command-line tools (`psql`, `postgres`, `initdb`),
a PostgreSQL Windows service, the standard installation directory, and a port-5432
listener were not found. No server was installed, started or configured. Actual
fresh-PostgreSQL DDL execution remains the unresolved validation item.

Checks do not recompute eligibility flags, completeness or derived formulas in SQL;
the preserved Phase 3 values and existing transformation tests remain authoritative.
Future data updates should go through the transformation contract. Source ambiguity,
unknown measurement bases and primary-brand simplification remain unchanged.

## Preservation and final scope

Before/after relative path sets, SHA-256 hashes, sizes and modification times match
for all **54 data files and 2 notebooks**. This includes every raw, processed,
cleaned, backup and checkpoint file. Cleaned-file hashes remain:

| File | SHA-256 |
| --- | --- |
| brands.csv | `fdc10c0761c5ad7563784cb6fa6ce290c17c510f1da74adff88c23c9f0e5cbde` |
| products.csv | `9bf2bb50247d0c376efea908a3ab5cc35a5a47dd9179e9bc092d3e943127c540` |
| categories.csv | `e411db0b835028ad5a46b3e96f703239eee48a625b3937c5269402323eac7d04` |
| product_categories.csv | `d10e12fb8dc6c9be4f10cc367623f14e7766cbcfdded3a2282da47e0a75e4dea` |
| nutrition.csv | `2ce5887ab59f9f6a69a6310366092b8fd51c0a9fad68a1fd525471ca81f35ff3` |

`git diff --check` and explicit new-text-file whitespace checks passed. Git status
and diff were reviewed. Git commands used a per-command safe.directory override
for the sandbox ownership mismatch; no persistent Git configuration was changed.
The pre-existing `.gitignore` modification and untracked `.github/` directory remain
untouched. Nothing was staged, committed or pushed. No API requests were made.
No records were loaded into PostgreSQL, and no Phase 6 or Phase 7 work was implemented.

**Stop: Phase 5 complete, with PostgreSQL execution explicitly unverified.**
