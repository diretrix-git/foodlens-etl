# FoodLens Phase 3A: Data Cleaning and Transformation Plan

**Status:** planning only; Phase 3B requires user approval.
**Assessment date:** 2026-10-09.
**Input:** `data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv`.
**Input SHA-256:** `c7831ff6c476c8511365a543411d19ba090c65d89f51db537715f1b905d8776c`.

## 1. Executive summary

Retain every product and preserve all original observations. Clean representation
and relationships separately from deciding whether individual measurements are
eligible for a particular analysis. Do not invent corrected nutrients, fill
unknowns with zero, or delete products because of statistical outliers.

The Phase 1 baseline and Phase 2 counts were independently recalculated from the
current CSV and saved responses. They reconcile: 2,000 extracted records, 1,987
unique products, 24 columns, four extraction categories, 13 overlapping products,
91 products with numerical review flags, 83 energy-discrepancy candidates and 500
products with category-specific IQR flags.

Source investigation adds three important distinctions:

1. The 116 blank Nutri-Score grades represent **57 source `unknown` values and
   59 source `not-applicable` values**. These states must remain distinguishable.
2. Five retained raw records declare `nutrition_data_per="100ml"`, although their
   exported column names end in `_100g`. Another 728 records lack this basis field;
   only 1,254 explicitly declare `100g`. No density or serving-size conversion is justified.
3. Three original taxonomy tags contain literal semicolons inside entity-like
   text. Splitting the flattened `categories` field on every semicolon creates
   seven spurious relationships. Reconstruct taxonomy membership from the saved
   `categories_tags` arrays instead. Extraction memberships are unaffected.

The recommended conservative **numerical quarantine scenario Q** would retain
all 1,987 products and all original values, while withholding 193 distinct
product/nutrient measurements across 91 products from calculations that require
those measurements. This is a proposed review policy, **not 193 proven errors**.
It retains IQR-only values. Basis-sensitive analysis eligibility is an additional,
separate decision: the recommended strict per-100-g view uses explicitly declared
mass-basis records and must disclose the resulting selection bias.

Only this document is a deliverable of Phase 3A. No cleaning module, transformed
DataFrame export, database table, SQL, or replacement notebook output was created.

## 2. Verified dataset characteristics

### 2.1 Evidence and reconciliation

Reviewed the repository agent instructions, current downloader/combiner,
`README.md`, both phase validation reports, notebook code and saved outputs,
combined metadata, category checkpoints and all 20 saved page responses.
The notebook itself was not re-executed or overwritten.

| Measure | Recalculated result |
| --- | ---: |
| Source records / saved pages | 2,000 / 20 |
| Combined rows / unique exact barcodes | 1,987 / 1,987 |
| Columns / extraction categories | 24 / 4 |
| Missing or duplicate combined barcodes | 0 / 0 |
| Barcode lengths | 1,922 of length 13; 65 of length 8 |
| Barcodes beginning with zero | 83 |
| Products belonging to two extraction categories | 13 |
| Extraction membership links | 2,000 |
| Non-null nutrient observations across nine fields | 17,140 of 17,883 possible |
| Products with no values in any of the nine nutrient fields | 36 |
| Products with all nine nutrient fields present | 1,614 |
| Numeric parse, negative or non-finite nutrient issues in the export | 0 |
| Invalid non-null Nutri-Score/NOVA values; unparseable non-null extraction timestamps | 0 |

The combined CSV hash matches its metadata. All 20 canonical response hashes
match their page envelopes and checkpoints. All four checkpoints are complete.
Every combined barcode and its full extraction membership set match saved source
records. All non-null values in the nine combined nutrient fields match their
retained raw source values, using floating-point comparison tolerance
`rtol=1e-12, atol=1e-12`. No numerical export corruption was found.

All 13 cross-category duplicate barcodes have matching values, including matching
absence, for the nine raw nutrient keys examined. This does not establish equality
of every other field or guarantee that future repeated observations will agree.

| Extraction category | Source records | Primary retained rows | All memberships |
| --- | ---: | ---: | ---: |
| breakfast-cereals | 500 | 500 | 500 |
| yogurts | 500 | 498 | 500 |
| biscuits | 500 | 498 | 500 |
| cereal-bars | 500 | 491 | 500 |

The combiner keeps the first row in the configured category order: breakfast
cereals, yogurts, biscuits, cereal bars. Keep this provenance policy; do not replace
it with newest-row selection or combine nutrient values from multiple observations
without a separate approved policy.

### 2.2 Actual schema and required treatment

| Existing fields | Role and proposed treatment |
| --- | --- |
| `barcode` | Immutable string product key; no numeric casting, padding or trimming |
| `product_name`, `brands` | Preserve original strings; create separate normalized display values and brand-label links |
| `categories` | Preserve flattened original; rebuild authoritative taxonomy links from raw arrays |
| `extraction_category`, `extraction_categories`, `category_membership_count` | Preserve first-row provenance and all four-category memberships; validate the count, do not replace membership with primary category |
| `energy_kcal_100g`, `energy_kj_100g` | Separate reported measurements; validate cross-unit agreement without automatic substitution |
| `protein_g_100g`, `carbohydrates_g_100g`, `sugars_g_100g`, `fat_g_100g`, `saturated_fat_g_100g`, `fiber_g_100g`, `salt_g_100g` | Nullable numeric observations; retain original units/basis evidence and field-level review state |
| `nutriscore_grade`, `nova_group` | Nullable classifications with separate source-status fields |
| `source_page`, `source_record_index`, `extraction_id` | Exact retained observation pointer; record index is zero-based |
| `extracted_at_utc`, `record_origin` | Nullable UTC timestamp and explicit API/legacy origin; never substitute import time |
| `source_url` | Preserve the public request URL after checking for sensitive parameters; use relative local paths elsewhere |

The actual saturated-fat column is `saturated_fat_g_100g`. The shorter name in
one Phase 1 report table is a documentation typo, not an additional source field.

## 3. Data-quality issue inventory

### 3.1 Missing values and classifications

Percentages use 1,987 unique products. Ten other analytical columns have no missing values.

| Field | Missing | % | Interpretation |
| --- | ---: | ---: | --- |
| Energy, kcal | 39 | 1.96 | No usable exported observation; do not reconstruct from kJ by default |
| Energy, kJ | 55 | 2.77 | Includes 14 records with a separate generic raw `energy_100g` and `energy_unit="kJ"`; recovery would be optional source enrichment, not an automatic fill |
| Protein | 43 | 2.16 | Unknown, not zero |
| Carbohydrates | 44 | 2.21 | Unknown, not zero |
| Sugars | 50 | 2.52 | Unknown, not zero |
| Fat | 41 | 2.06 | Unknown, not zero |
| Saturated fat | 54 | 2.72 | Unknown, not zero |
| Fiber | 351 | 17.66 | Particularly incomplete for yogurts: 273/500 memberships missing, 54.6% |
| Salt | 66 | 3.32 | Unknown, not zero |
| Product name | 40 | 2.01 | Product identity remains available through barcode |
| Brand string | 32 | 1.61 | No invented brand entity or membership |
| Nutri-Score grade | 116 | 5.84 | Raw source states: 57 `unknown`, 59 `not-applicable` |
| NOVA | 130 | 6.54 | Source key absent in all 130 retained records |
| Original extraction timestamp | 100 | 5.03 | All are legacy imports; original timestamp is unavailable |

The extractor maps invalid/negative/non-finite numeric inputs to blanks and maps
unrecognized classification values to empty cells. Therefore preserve source
absence/reason information rather than assigning every blank the same cause.
The current source audit did not identify negative or non-finite nutrient inputs.

### 3.2 Numerical rules reproduced from the EDA

| Rule | Products | Confidence interpretation |
| --- | ---: | --- |
| A gram-valued nutrient exceeds 100 on the exported per-100 basis | 2 | Contradicts exported mass-basis interpretation; original basis must be checked |
| Energy >1,000 kcal or >4,184 kJ per reported 100 units | 3 | Strong screening evidence, not a substitute for a label |
| Sugars > carbohydrates +0.5 g | 5 | Incompatible component/total values; which field is wrong is unresolved |
| Saturated fat > total fat +0.5 g | 2 | Incompatible component/total values; do not guess the correction |
| Protein + carbohydrates + fat >105 g | 4 | Likely scale/content inconsistency; fiber excluded to avoid double counting |
| `abs(kcal - kJ/4.184) > max(20, 0.10*kcal)` | 83 of 1,931 pairs | Discrepancy candidate; rounding, estimation or mixed source basis may contribute |
| Union of numerical review rules | 91 | Counts above overlap |
| Category-specific 1.5-IQR flags | 500 unique products | 781 distinct product/field pairs, 782 category/field events |
| IQR-flagged products without a numerical rule flag | 438 | Retain values; unusual does not mean erroneous |

IQR uses Pandas linear-interpolated quartiles and strict comparisons outside
`[Q1-1.5*IQR, Q3+1.5*IQR]`, separately for every category and nutrient. When IQR is
zero, no flag is assigned. These thresholds reproduce Phase 2; they are not
regulatory limits. Freeze this baseline for audit, rather than repeatedly
recalculating fences after removing observations.

## 4. Investigation of suspicious source records

### 4.1 Reading the evidence

Use the paths below plus `products[record_index]` inside the envelope's `response`.
Page numbers are one-based; record indexes are zero-based.

| Source prefix | Directory |
| --- | --- |
| BC | `data/raw/extractions/255549a7a8a480c0/pages/` |
| YO | `data/raw/extractions/a7cac53fa4872087/pages/` |
| BI | `data/raw/extractions/34e0ad749f6a0fa6/pages/` |
| CB | `data/raw/extractions/ed4f16ea3c02f6ab/pages/` |

For example, `BI 2:38` means `BI/page_000002.json`,
`response.products[38]`. All 91 flagged products were traced by their retained
extraction ID/page/index, with barcode and nutrient values checked against raw
responses. The table includes every product with a non-energy-only rule flag.

| Barcode | Source | Saved evidence | Assessment; proposed treatment |
| --- | --- | --- | --- |
| `8901063139329` | BI 2:38 | Salt 295, sodium 118, `salt_unit="g"`; original basis field absent | Likely unit/decimal error; confirmed incompatible with the CSV's mass-basis label. Salt and sodium are not independent corroboration. Hold salt; do not infer 0.295 or any other replacement. |
| `0602652419263` | CB 5:5 | Carbohydrates 120, fat 28, protein 8; sum 156; `nutrition_data_per="100g"` | Confirmed contradiction of the declared mass basis. Actual corrected values are unknown. Hold the three subtotal operands. |
| `8410376033267` | BI 2:19 | 3,305.109489 kcal vs 1,835 kJ; saved kcal per serving 453 | Likely serving/basis mix-up, not proven corrected kcal. Hold both energy measurements. |
| `5000168036755` | BI 3:8 | 2,092.857143 kcal vs 2,012.7 kJ; kcal per serving 314 | Strong energy inconsistency; likely scale error. Hold both energy measurements. |
| `3175681135024` | BI 3:12 | 1,364.285714 kcal vs 1,524 kJ; kcal per serving 382 | Strong energy inconsistency; no recoverable serving mass. Hold both energies. |
| `8410076610737` | BC 1:10 | Sugars 17.1 > carbohydrates 11; 195 kcal vs 2,035 kJ | Multiple unresolved inconsistencies. Hold both carbohydrate/sugar and energy pairs. |
| `6111032001010` | YO 1:7 | Sugars 14.3 vs carbohydrates 0 | Likely erroneous zero or mismatched data; do not select the wrong operand by assumption. Hold both. |
| `3280249801201` | YO 5:75 | Sugars 16 vs carbohydrates 4.5; source declares 100 g | Confirmed internal contradiction under a common basis; actual correction unresolved. Hold both. |
| `3017760221597` | BI 2:88 | Sugars 39 vs carbohydrates 0.062; both unit fields say g | Likely scale error, but do not replace 0.062 with 62. Hold both. |
| `6111126002626` | YO 2:7 | Saturated fat 15.1 vs total fat 1.1 | Likely error in at least one operand. Hold both fat measurements. |
| `0687456211091` | CB 3:55 | Sugars 25 > carbohydrates 17; saturated fat 4.17 > fat 3 | Likely mixed scale/basis. Hold four implicated fields, leaving other measurements available subject to their own rules. |
| `6111270960056` | BI 4:23 | Protein 6 + carbohydrates 69 + fat 33 =108; 200 kcal vs 387 kJ | Likely measurement inconsistency; hold the subtotal operands and both energies. |
| `4011800548513` | CB 4:12 | Protein 30 + carbohydrates 66.8 + fat 13.8 =110.6; 420 kcal vs 2,184.2 kJ | Likely source inconsistency; do not assume protein should be 3.0. Hold subtotal operands and both energies. |
| `4066447124132` | CB 5:3 | Protein 30 + carbohydrates 77 + fat 6 =113 | Likely subtotal inconsistency. Hold the three operands, not the product. |

These findings confirm that suspicious values are present in saved source
responses, not introduced by Pandas. A source response proves what was recorded;
it does not verify a package label or reveal the correct replacement value.

### 4.2 Energy discrepancies are not 83 confirmed kcal errors

Of the 83 pairs, 42 contain the saved marker `energy-kj_modifier="~"`; none
contains that marker for kcal. Preserve the marker as source evidence rather
than assuming it identifies which measurement is authoritative. Two flagged pairs
have zero kJ, and none has zero kcal. The three extreme kcal cases are included
within the 83, so they must not be counted twice.

A borderline example is `0687456217062` (CB 3:35): 416.666667 kcal and
1,918.75 kJ, with the kJ marker `~`. It passes the broad plausibility limits but
just exceeds the selected discrepancy tolerance. Its correctness is **unresolved**.
Do not force every pair into exact 4.184 agreement or infer a new kcal value from
macronutrients; the available data do not establish a complete energy calculation.

### 4.3 Statistical extremes: retain or investigate, not automatically delete

| Barcode | Source | Evidence | Assessment |
| --- | --- | --- | --- |
| `3111900350908` | BC 3:77 | Protein 43; name includes soja/protein; no numerical review flag | Unusual but potentially valid formulation; name is supporting context, not validation |
| `3159470001424` | BC 1:77 | Fiber 27; source names a bran/fiber product; no numerical review flag | Potentially valid high-fiber product; retain |
| `6111259344426` | BI 4:19 | Fiber 50 for a nougat-labelled product; no numerical rule flag | Unresolved; source review warranted, but IQR alone is insufficient to invalidate it |
| `3760151011146` | CB 2:47 | Salt 12 for a chocolate/hazelnut bar; no numerical rule flag | Likely suspicious in context, but no approved numeric error/correction established; retain with contextual review |
| `3431590015100` | CB 4:39 | Name `Sauce de soja`, source taxonomy includes both soy sauce and cereal bars; salt 8.5 | Unresolved identity/category conflict, not proof that salt is wrong; keep original memberships and flag scope review |

Absence of a numerical rule flag is not proof of validity. The plan leaves these
values available with review annotations; any additional manual quarantine needs
explicit evidence and changes the scenario counts below.

### 4.4 Measurement basis: confirmed metadata conflict, not a density conversion

The following five retained raw records explicitly say `100ml`:

| Barcode | Source |
| --- | --- |
| `6111250010207` | YO 2:97 |
| `6111246953181` | YO 3:9 |
| `6111242102590` | YO 4:7 |
| `3760122960749` | YO 5:22 |
| `4014500520032` | YO 5:97 |

All have nine observed nutrient values and none has a Phase 2 numerical review
flag. Preserve these 45 observations on their declared volume basis; exclude them
from a strictly mass-based comparison without discarding the products. For the
1,254 records declaring `100g`, record that basis. For 728 with no basis field,
use `unknown`, not an inferred gram basis. `nutrition_data_prepared_per` is not a
substitute for `nutrition_data_per` and does not prove which preparation state was measured.

No retained raw product has a non-null `serving_size`, `serving_quantity` or
`quantity`. Some nutrient `_serving` values exist, but a serving denominator cannot
be reliably reconstructed from them. No per-serving analysis or mass/volume
conversion is recommended. The repeated source `_unit` fields identify nutrient
numerator units; they do not establish the denominator basis.

### 4.5 Taxonomy delimiter defects and text quality

The extractor joins `categories_tags` with `;` without escaping embedded
semicolons. Confirmed cases:

- `8002590043353` (BI 5:97) has one raw Italian tag containing entity-like text
  and several semicolons. Naive splitting creates five extra tokens.
- `0016000264601` (CB 3:40) has two Spanish tags containing the literal text
  `&gt;`. Naive splitting creates two extra tokens.

The combined string itself matches `';'.join(raw_tags)`; the defect is its
ambiguous flattening, not a changed source response. **Read the original arrays**
for the new relationships. Source arrays contain 880 distinct taxonomy tags and
17,417 unique product/tag links, versus the misleading CSV-split counts of 887
and 17,424. All raw tags have a language prefix; the seven unprefixed split
fragments are artifacts. Do not HTML-decode and then split, strip markup from
identifiers, or execute/render source tag text as HTML.

Two raw tag values across two products change under NFC/whitespace normalization:
`3580281080122` and `8000500273883`. The latter contains a long compound-looking
tag and needs content review even after whitespace normalization. Counts remain
880 tags and 17,417 links after that limited normalization.

For product names, NFC plus trimming/collapsing whitespace changes 10 strings;
it leaves 1,857 distinct non-null names. Casefolding would reduce that count to
1,801, but names must not become identity or deduplication keys.

## 5. Proposed cleaning policies

### 5.1 Missingness and retention

| Situation | Recommended policy |
| --- | --- |
| Missing protein, carbohydrates, sugars, fat, saturated fat, fiber or salt | Preserve nullable missing; no zero/mean/median imputation. A product remains eligible for analyses of its other usable fields. |
| Missing energy | Retain missing. Source enrichment from generic energy keys or deriving a second unit is a separate, approval-dependent action with a distinct derived/source flag. |
| Missing product name | Keep null; a UI may display the barcode, but do not save it as a fabricated product name. |
| Missing brands | Keep original null, create zero brand links; do not create a shared `Unknown` brand entity. |
| Missing Nutri-Score grade | Restore source status `unknown` versus `not_applicable`; grade remains null. No inference from nutrient values. |
| Missing NOVA | Keep null with status `missing`; no inference from product name, category or ingredients. |
| Missing extraction timestamp | Keep `NaT`/null and `legacy_import`; pipeline run time is separate provenance, not a replacement. |
| Product with every nutrient missing | Retain the product and its category/brand relationships; exclude only from nutrient calculations requiring absent observations. |

Define source absence independently of quarantine: an original missing value and
an observed-but-withheld value may both have null usable values, but must have
different statuses, audit records and availability flags.

### 5.2 Severity and evidence vocabulary

Severity expresses operational handling; confidence expresses what is known.
Do not conflate a conservative quarantine with a proven data error.

| Severity | Meaning | Action |
| --- | --- | --- |
| BLOCKER | Input hash/schema mismatch, nonunique product identity or broken source/FK trace | Stop publication; preserve the prior output; do not silently drop records |
| HIGH | Invalid numeric representation, strong range/consistency conflict | Preserve original; quarantine only affected measurement(s) under scenario Q |
| REVIEW | IQR/contextual outlier, unknown basis, suspect source text, unresolved alias | Retain with flags; apply analysis-specific basis restrictions separately |
| INFO | Missing field, source `not-applicable`, mechanical whitespace normalization | Retain and document without assigning a health/quality penalty |

Use evidence labels `confirmed_representation_conflict`, `likely_error`,
`potentially_valid`, and `unresolved`. Do not label unflagged products verified.
Proposed product status precedence: `quarantined_measurements` > `needs_review`
> `incomplete` > `no_detected_issue`. `needs_review` includes IQR/context/basis
issues; absent metadata/classification is not equivalent to a nutritional defect.
Treat missingness, source status and field eligibility as separate columns/flags.

## 6. Explicit transformation and validation rules

Rules are proposed, versioned as `foodlens-clean-v1`, and evaluated against the
unchanged observations before any field is withheld. There is no iterative
recalculation of rules on already-quarantined values.

| Code | Deterministic rule | Proposed action / current affected count |
| --- | --- | --- |
| ID_INVALID / ID_DUPLICATE | Missing barcode, non-ASCII digit string outside length 8–14, or repeated combined barcode | BLOCKER for this input contract; 0. Never repair or numerically cast. No GTIN checksum deletion policy. |
| TEXT_WHITESPACE | NFC, trim edge whitespace, collapse whitespace runs to one space; preserve case, accents and punctuation | Separate display value and original; 10 names, 0 whole brand strings change |
| BRAND_TOKENIZE | Split original `brands` on literal comma only; NFC/trim/collapse each nonempty token; exact case-sensitive key | Proposed 379 multi-token products; 644 labels and 2,399 unique product/label links; source token text/order retained |
| BRAND_ALIAS_REVIEW | Group tokens by NFC/whitespace-normalized casefold key for review only | 74 case-variant groups; no automatic fuzzy, accent, punctuation, company/sub-brand or case merges |
| CATEGORY_ARRAY_REQUIRED | Recover taxonomy tags from the retained source array; do not split its flattened CSV string | Fix future representation for 2 products / 3 delimiter-containing tags; avoid 7 spurious relationships |
| CATEGORY_TEXT_REVIEW | Preserve source strings including entity-like or compound text; keep language prefix; normalize only NFC/whitespace | 2 raw tag strings change mechanically; separately review suspect tag content and the soy-sauce/cereal-bar case |
| MEMBERSHIP_INVALID | All membership lists must use the four exact extraction slugs, have no repeats, contain primary category and match source occurrences/count | BLOCKER on failure; 0 currently; retain 2,000 extraction links |
| NUM_PARSE / NUM_NONFINITE / NUM_NEGATIVE | Parse nullable floats, reject booleans, require finite and nonnegative where present | HIGH; preserve source string/value and quarantine that field; 0 current measurements |
| RANGE_GT100 | Gram nutrient >100 on a declared mass basis; same observation on unknown basis is an unresolved plausibility screen | HIGH; quarantine that field pending review; 2 observations. Do not apply a mass limit blindly to per-volume facts. |
| ENERGY_EXTREME | Reported energy >1,000 kcal or >4,184 kJ per 100 units | HIGH screening rule; 3 kcal observations, all also energy-discrepancy candidates |
| SUGAR_GT_CARB | Both finite/present; sugars > carbohydrates +0.5 | HIGH; quarantine both operands under Q; 5 products / 10 field incidences |
| SATFAT_GT_FAT | Both finite/present; saturated fat > total fat +0.5 | HIGH; quarantine both operands under Q; 2 products / 4 field incidences |
| MACRO_SUM_GT105 | All three finite/present; protein + carbohydrates + fat >105; exclude fiber | HIGH screening; quarantine all three operands under Q; 4 products / 12 incidences |
| ENERGY_DISAGREEMENT | Both energies present; absolute kcal difference from kJ/4.184 >max(20 kcal, 10% of reported kcal) | HIGH unresolved review; quarantine both energies under Q; 83 products / 166 incidences |
| IQR_CATEGORY | Reproduce the Phase 2 category/field fences on the original finite values | REVIEW only; 500 products, no automatic quarantine |
| BASIS_VOLUME / BASIS_UNKNOWN | Read retained raw `nutrition_data_per`; recognized values `100g`, `100ml`; otherwise unknown or unexpected | Preserve basis; 5 volume / 728 unknown products. Restrict mass analyses without losing facts. |
| CLASS_STATUS | Grade in a–e and NOVA integer 1–4 when present; preserve raw grade reason | 116 null grades, including 59 not applicable; 130 missing NOVA; no invented class |
| TIME_UNKNOWN / TIME_PARSE | Parse known timestamps as UTC; missing stays unknown; malformed non-null gets review | 100 unknown legacy times, 0 parse failures |

Thresholds remain explicitly review rules rather than claims of universal food
limits. If authoritative evidence resolves a field, use a reviewed override with
original value, approved replacement, source evidence, reviewer and decision
timestamp. There are **no proposed numerical replacement values** in this plan.

## 7. Proposed related DataFrame schemas

These are in-memory/output contracts for a later implementation, not database
DDL. Pandas dtypes below use nullable `string`, `Float64`, `Int64`, `boolean`, and
`datetime64[ns, UTC]`. Keys are case-sensitive Unicode strings. Do not infer keys
from row order. Derived IDs are stable textual prefixes plus normalized source
identifiers, with collision checks before publication.

### 7.1 `products` — one row per exact barcode; expected 1,987 rows

| Column(s) | Pandas dtype | Nullable | Definition / constraint |
| --- | --- | --- | --- |
| `barcode` | string | No | Primary key; unchanged exact identifier |
| `product_name_original`, `product_name` | string | Yes | Original and NFC/whitespace-normalized name |
| `brands_original`, `categories_original` | string | Yes | Unchanged source CSV strings; not parsed relationship substitutes |
| `nutriscore_grade` | string | Yes | a–e only |
| `nutriscore_status` | string | No | `reported`, `unknown`, `not_applicable`, `missing`, `invalid`; based on saved source |
| `nova_group` | Int64 | Yes | 1–4 only |
| `nova_status` | string | No | `reported`, `missing`, `invalid` |
| `extracted_at_utc` | datetime64[ns, UTC] | Yes | Original extraction time only |
| `record_origin` | string | No | Preserve source API/legacy origin |
| `primary_category_id` | string | No | FK to the corresponding extraction category in `categories` |
| `category_membership_count` | Int64 | No | Count extraction namespace links only, not taxonomy links |
| `source_extraction_id` | string | No | Retained source extraction ID |
| `source_page`, `source_record_index` | Int64 | No | Page >=1, record index >=0 |
| `source_relative_path`, `source_response_sha256`, `source_url` | string | No | Relative page path, canonical response checksum and public request URL |
| `source_completeness_pct`, `usable_completeness_pct` | Float64 | No | Eight-field formulas in Section 8; not a health score |
| `protein_g_per_100kcal`, `sugar_to_carbohydrate_ratio` | Float64 | Yes | Derived only under the stated operand and basis rules |
| `data_quality_status` | string | No | Severity precedence in Section 5; never imply externally verified validity |
| `transformation_run_id` | string | No | Reference the immutable output manifest, not a new database table |

One product has zero or more brand links, one or two current extraction category
links, many taxonomy links and exactly nine proposed nutrient slots. The retained
observation pointer is unique in this snapshot and must resolve to the same barcode.

### 7.2 `brands` — source brand labels, not inferred legal companies

| Column | dtype | Nullable | Definition / constraint |
| --- | --- | --- | --- |
| `brand_id` | string | No | PK: `brand:` plus case-preserving normalized token |
| `brand_label` | string | No | Unique case-sensitive normalized token |
| `casefold_match_key` | string | No | Nonunique review/search key; not an automatic identity rule |
| `normalization_status` | string | No | `literal_source_token` or later approved alias mapping |

Recommended first-pass size: **644 labels**. Some source labels represent retailers,
sub-brands or companies; no corporate ownership inference is supported. Casefold
merging is an approval option, not part of this recommended baseline.

### 7.3 `product_brands` — many-to-many source-label membership

| Column | dtype | Nullable | Definition / constraint |
| --- | --- | --- | --- |
| `barcode` | string | No | FK `products.barcode` |
| `brand_id` | string | No | FK `brands.brand_id` |
| `source_token` | string | No | Original token before normalization |
| `source_token_index` | Int64 | No | Zero-based comma token position |

Composite PK/uniqueness: `(barcode, brand_id)`. Expected **2,399 links** for 1,955
products with a source brand string; 32 products have no link. If future repeated
tokens normalize to one key, preserve every token/position in the transformation
audit while emitting one relationship. No current exact-token duplicates or empty
tokens were found. Comma splitting treats values as source-asserted labels, not
proof that a comma cannot occur inside a company's name; approve this assumption.

### 7.4 `categories` — explicitly separate extraction and taxonomy namespaces

| Column | dtype | Nullable | Definition / constraint |
| --- | --- | --- | --- |
| `category_id` | string | No | PK: `extraction:<slug>` or `taxonomy:<normalized_source_tag>` |
| `namespace` | string | No | `extraction` or `taxonomy` |
| `category_key` | string | No | Exact verified extraction slug or case-preserving normalized raw tag |
| `display_label` | string | No | Four documented readable extraction names; taxonomy tag text otherwise |
| `language_code` | string | Yes | Parse source tag prefix for taxonomy; null for extraction slugs |
| `validation_status` | string | No | `extraction_verified`, `taxonomy_source_unverified`, `taxonomy_review_required` |

Unique `(namespace, category_key)`. Expected **884 rows: 4 extraction +880 source
taxonomy labels**. Do not infer a taxonomy tree, translate labels, strip language
prefixes, or merge an extraction category with a taxonomy tag that has similar text.
No live taxonomy lookup is required or authorized for Phase 3B by this plan.

### 7.5 `product_categories` — many-to-many memberships with observation evidence

| Column | dtype | Nullable | Definition / constraint |
| --- | --- | --- | --- |
| `barcode`, `category_id` | string | No | Composite PK; FKs to products and categories |
| `is_primary_extraction` | boolean | No | True for exactly one extraction link per product; false for taxonomy |
| `source_extraction_id` | string | No | The extraction that actually returned this membership |
| `source_page`, `source_record_index` | Int64 | No | Pointer to the corresponding raw observation |
| `source_relative_path`, `source_response_sha256` | string | No | Relative response location and verified checksum |
| `source_tag`, `source_tag_index` | string / Int64 | Yes | Original array tag/index for taxonomy links; null for extraction links |

Expected **19,417 links: 2,000 extraction +17,417 taxonomy**. Recover extraction
link pointers from all original occurrences, so both observations of each shared
product remain traceable. Taxonomy links use the retained product's source array
to preserve Phase 1 semantics; do not silently union taxonomy tags from later
duplicate observations. Product-to-category counts must be namespace-aware.

### 7.6 `nutritional_facts` — long-form measurements, including missing slots

| Column | dtype | Nullable | Definition / constraint |
| --- | --- | --- | --- |
| `barcode` | string | No | FK to products |
| `nutrient_code` | string | No | One of the nine codes below; composite PK with barcode |
| `observed_value_per_100` | Float64 | Yes | Exact numeric observation; null only when originally unavailable |
| `usable_value_per_100` | Float64 | Yes | Same value if available under Q; null if missing or quarantined; no imputed replacement |
| `numerator_unit` | string | No | g for seven nutrients, kcal or kJ for the two energy measures |
| `basis` | string | No | `100g`, `100ml`, `unknown`, or future `unexpected`; from retained raw source evidence |
| `basis_evidence_field` | string | Yes | `nutrition_data_per` when present, null if absent |
| `source_field` | string | No | Original nutriment dictionary key |
| `source_unit`, `source_modifier` | string | Yes | Raw `_unit` and `_modifier` values if present; do not manufacture missing metadata |
| `source_present`, `available_for_analysis` | boolean | No | Distinguish an observed measurement from one eligible under Q |
| `mass_comparable` | boolean | No | `available_for_analysis` and explicit `basis=100g` |
| `quality_state` | string | No | `missing`, `available`, `quarantined`; IQR is separate |
| `is_iqr_outlier` | boolean | No | Any category-specific IQR flag; detailed category events live in the audit |

Nine codes: `energy_kcal`, `energy_kj`, `protein`, `carbohydrates`, `sugars`, `fat`,
`saturated_fat`, `fiber`, `salt`. Units and keys are mapped explicitly from the
nine actual CSV fields listed in Section 2. Do not add vitamins or other nutrients
just because additional raw keys happen to exist.

Expected **17,883 rows =1,987 products x9 nutrient slots**. Of these, 17,140
currently have observed values and 743 are missing. Under Q, 193 additional
usable values would be null, leaving 16,947 available observations. This design
avoids embedding an unverified `_100g` assumption in transformed column names.
The product FK supplies the retained source pointer; the source field supplies
the precise original dictionary key.

## 8. Derived analytical fields and formulas

These are availability/measurement summaries, not an overall health score.
Retain full precision; round only displays. Do not clamp inconsistent ratios to 1.

| Derived field | Formula and unit | Missing/zero/basis behavior |
| --- | --- | --- |
| `protein_g_per_100kcal` | `100 * protein / energy_kcal`; g per 100 kcal | Both operands available under Q, same retained observation and explicit common basis (`100g` or `100ml`); energy >0. Otherwise null with reason. Denominator basis cancels, so no density conversion is needed. |
| `sugar_to_carbohydrate_ratio` | `sugars / carbohydrates`; dimensionless; display x100 as % only if labelled | Both operands available under Q, explicit common basis and carbohydrates >0. If denominator zero, including 0/0, return null; never infinity. |
| `source_completeness_pct` | `100 * count_present(core8) / 8` | Core8: kcal energy plus protein, carbohydrates, sugars, fat, saturated fat, fiber, salt. kJ excluded to avoid counting energy twice. Every product receives a value, including 0. |
| `usable_completeness_pct` | `100 * count_available_under_Q(core8) / 8` | Counts numerical eligibility, not proof of correct units, nutritional merit or strict mass comparability. Publish basis separately. |
| Nutrient availability | `source_present = observed non-null`; `available_for_analysis = present and not quarantined` | Missing and quarantined remain distinct; no unknown-to-zero conversion. |
| Mass-analysis eligibility | Availability AND explicit 100 g basis | Unknown/volume records remain stored but do not enter the strict per-100-g view. |
| `data_quality_status` | Deterministic maximum-severity status from Section 5 | Source incompleteness is not an arbitrary health penalty; preserve reason codes. |

Measured denominator cases: one product has zero kcal and three have zero
carbohydrates. Zero is retained as an observation unless a separate consistency
rule flags it. No epsilon substitution or guessed positive denominator is proposed.

## 9. Estimated consequences of the proposed rules

All numbers in this section are **read-only calculations on current data**.
They describe conditional results if the named policy is approved. No output
dataset was transformed. They do not include future manually adjudicated changes.

### 9.1 Numerical quarantine scenario Q

Q quarantines each directly implausible measurement, both operands of either
component/total inconsistency, all three operands of an excessive macro subtotal,
and both energies of a conversion discrepancy. A measurement with several reasons
is counted once. Ordinary missingness, IQR-only flags and basis metadata issues
do not add numerical quarantine measurements to Q.

| Nutrient | Present now | Q quarantine | Available under Q | Available under Q with explicit 100 g basis |
| --- | ---: | ---: | ---: | ---: |
| Energy kcal | 1,948 | 83 | 1,865 | 1,201 |
| Energy kJ | 1,932 | 83 | 1,849 | 1,189 |
| Protein | 1,944 | 4 | 1,940 | 1,231 |
| Carbohydrates | 1,943 | 9 | 1,934 | 1,229 |
| Sugars | 1,937 | 5 | 1,932 | 1,224 |
| Fat | 1,946 | 6 | 1,940 | 1,231 |
| Saturated fat | 1,933 | 2 | 1,931 | 1,222 |
| Fiber | 1,636 | 0 | 1,636 | 1,009 |
| Salt | 1,921 | 1 | 1,920 | 1,219 |
| **Total observations** | **17,140** | **193** | **16,947** | **10,755** |

Per-rule incidences are 2 +3 +10 +4 +12 +166 =197; overlapping reasons reduce
these to **193 distinct observations**. All 1,987 products remain, including
1,951 with at least one available nutrient and 36 with none. No additional product
loses every nutrient under Q. All 2,000 extraction links remain.

All-nine complete cases decrease from 1,614 to 1,535. Core8 complete cases decrease
from 1,622 to 1,542; average core8 source completeness is 95.6719%, and Q usable
completeness would be 94.9799%. These aggregate percentages can conceal substantial
field/category gaps, especially fiber in yogurts.

| Major analysis | Numerically evaluable before Q | Numerically eligible under Q | Recommended basis-aware eligibility |
| --- | ---: | ---: | --- |
| Protein per 100 kcal | 1,944 | 1,859 | 1,204 with explicit common basis; 1,199 of these on a gram basis |
| Sugar/carbohydrate ratio | 1,931 | 1,923 | 1,223 with explicit common basis; 1,218 on a gram basis |
| Energy-versus-sugar paired analysis | Not used as a headline baseline | 1,850 | 1,191 with explicit 100 g basis |
| Nutri-Score distribution | 1,871 graded products | Unchanged | Show 57 unknown and 59 not applicable separately; total product denominator remains 1,987 |
| NOVA distribution | 1,857 classified products | Unchanged | Include 130 missing as a separate state |
| Identity/category/brand analyses | Up to 1,987 products | Unchanged | Preserve relevant text missingness and brand-token assumptions |

### 9.2 Category consequences and bias

All counts use full extraction membership, so a shared product can contribute to
two categories. The 91 numerical-flagged products happen to total 91 affected
memberships here; this equality is not a general property of overlapping samples.

| Category | Members retained | Numerical-flagged members | Q measurements withheld | Energy kcal present -> Q eligible | Sugars present -> Q eligible |
| --- | ---: | ---: | ---: | --- | --- |
| Breakfast cereals | 500 | 11 | 24 | 494 ->483 | 494 ->493 |
| Yogurts | 500 | 30 | 60 | 482 ->455 | 474 ->472 |
| Biscuits | 500 | 18 | 38 | 490 ->474 | 488 ->487 |
| Cereal bars | 500 | 32 | 71 | 495 ->466 | 494 ->493 |

Separately, declared-basis membership counts and strict eligibility are:

| Category | Declared 100 g / unknown / 100 ml | Strict mass energy count | Strict mass sugars count |
| --- | --- | ---: | ---: |
| Breakfast cereals | 294 /206 /0 | 289 | 292 |
| Yogurts | 324 /171 /5 | 299 | 307 |
| Biscuits | 332 /168 /0 | 319 | 324 |
| Cereal bars | 309 /191 /0 | 299 | 306 |

Basis selection changes the population more than Q alone. For example:

| Category | Observed median kcal | Median under Q only | Median under Q +explicit 100 g | Observed median sugars | Median under Q +explicit 100 g |
| --- | ---: | ---: | ---: | ---: | ---: |
| Breakfast cereals | 397.39 | 397.78 | 406.00 | 15.00 | 17.00 |
| Yogurts | 78.00 | 78.00 | 83.08 | 5.50 | 8.10 |
| Biscuits | 467.00 | 467.50 | 476.00 | 25.00 | 26.00 |
| Cereal bars | 416.67 | 418.43 | 410.00 | 23.73 | 24.00 |

The first two columns use the export's reported basis and are sensitivity
calculations, not newly validated mass comparisons. Sugar units for the last
column are g/100 g on the explicit-basis subset. The movements are selection
effects, not evidence that underlying products improved nutritionally.

Unknown-basis records contain 6,266 observed measurements, of which 119 are
quarantined under Q. The remaining 6,147 are retained but excluded from a strict
mass view. All 45 volume-basis observations remain available for appropriately
labelled volume or basis-cancelling analyses. A secondary analysis that admits
unknown basis under an explicit assumption may be informative, but must never
silently label those values independently verified g/100 g.

### 9.3 Text, brands and category relationship impact

| Proposed operation | Measured consequence |
| --- | --- |
| Name NFC/whitespace normalization | 10 display values change; 1,987 products retained; 1,857 distinct non-null names remain |
| Whole brand string whitespace/NFC normalization | 0 changes; 688 distinct non-null whole strings remain |
| Comma tokenization, case-preserving | 379 multi-token products; 644 brand-label rows; 2,399 links; 32 products without links |
| Optional casefold merging, NOT recommended automatically | 554 labels and 2,392 links; 74 case-variant groups collapse 90 labels and seven within-product duplicate links |
| Taxonomy reconstruction from raw arrays | 880 taxonomy labels /17,417 links; avoids seven false split fragments; no source tag is discarded |
| Limited raw-tag normalization | Two tag strings change across two products; no change in dimension/link counts |
| Namespaced categories including extraction groups | 884 category rows /19,417 product-category links |
| Nutrient quarantine | 193 usable values withheld; original observations remain auditable |
| IQR-only rule | Zero measurements automatically withheld; all 438 statistical-only products remain available subject to basis/missingness rules |

Potential losses are losses of **analysis eligibility**, not deletion of source
information. Conservative pair quarantine may withhold a correct operand alongside
an incorrect one. Case/brand merging may conflate distinct source labels. Strict
basis filtering selects better-documented records and can introduce bias. These
tradeoffs must be reported, rather than presenting the output as error-free.

## 10. Reproducibility, audit and validation strategy

### 10.1 Proposed implementation layout and commands — not implemented

Keep the future implementation small: `src/clean_transform.py` for orchestration
and the six DataFrames; `src/quality_rules.py` for pure predicates/derivations;
`config/cleaning_rules.json` for thresholds, alias decisions and version; and
`tests/test_clean_transform.py` for focused offline tests. Reuse existing schemas
and hash conventions but do not instantiate extraction `Store` or call any
downloader publication/combination command: those can write existing artifacts.

Proposed CLI contract, available only after an approved Phase 3B implementation:

```powershell
.\.venv\Scripts\python.exe -m src.clean_transform --input data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv --rules config/cleaning_rules.json --dry-run
.\.venv\Scripts\python.exe -m src.clean_transform --input data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv --rules config/cleaning_rules.json --output-root data/cleaned
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The first two commands are a proposed interface, **not working commands for the
current repository**; the unittest command already runs the existing offline suite.
Dry-run would report counts only. Use a new content-addressed run
directory under `data/cleaned/`; reject replacement of existing outputs. CSV plus
explicit dtype/schema metadata is sufficient initially; preserve barcode strings
on reimport. Do not add a database or unnecessary serialization dependencies.

### 10.2 Audit records and original-to-output traceability

Propose three supporting artifacts, not additional database tables:

- `quality_issues.jsonl`: one event per product/rule/context, with rule version,
  affected fields, observed values, severity, confidence, action, category/IQR
  context, applicable thresholds, and original source pointer/hash.
- `quarantined_measurements.jsonl`: one row per distinct `(barcode, nutrient_code)`
  with original value, all reason codes and evidence pointers. Deduplicate audit
  measurement keys, not source products; this reconciles to 193 under Q.
- `manifest.json`: relative inputs and file hashes, canonical response hashes,
  rules/configuration hash, code version/digest, environment versions, UTC run
  time, schema/dtypes, row and eligibility counts, and output hashes. Derive the
  deterministic run identity from content/configuration, not clock time.

Mechanical text edits must record original and normalized strings. Brand and
taxonomy links must retain original token/tag position or an accompanying mapping
for any many-to-one normalization. Preserve every original observation through
the six DataFrames and immutable source pointers. Store no contact email, full
private checkpoint metadata, credentials or machine-specific absolute paths.

### 10.3 Automated tests required in Phase 3B

1. Block real HTTP in tests; fixtures are real saved-record excerpts or deliberate
   malformed test inputs confined to temporary directories.
2. Read-only preservation: all pre-existing data files and notebooks retain
   path sets, hashes, sizes and modification times even after failed runs.
3. Identity: leading-zero barcode round trips (83 current cases), missing/duplicate
   rejection, no numeric key coercion, no product-name deduplication.
4. Baseline/rule regression: 1,987 products, 2,000 source memberships, 91 numerical
   review products, 83 energy pairs, 193 distinct Q measurements; reason incidence
   and union counts reconciled separately. Assert the source hash before applying
   these snapshot-specific expectations.
5. Rule boundaries: equality at 100/1,000/105 and at the 0.5/energy discrepancy
   tolerances; missing operands; zero denominators; booleans, nonnumeric strings,
   infinities, negatives; no cascading flags caused by previously quarantined data.
6. Outliers: category-specific fences, overlap event counting, zero-IQR handling,
   and no quarantine solely because a point is outside a fence.
7. Units: five volume-basis records preserved, 728 unknown bases not invented,
   no density conversion, nine slots per product including missing values, flags
   separate from basis eligibility.
8. Classifications: preserve 57 unknown and 59 not-applicable Nutri-Score statuses;
   retain 130 missing NOVA and 100 missing legacy timestamps without fabrication.
9. Taxonomy: preserve raw array tags containing semicolons and entity text as one
   tag; assert 880 taxonomy labels and 17,417 relationships, not the CSV-split counts.
10. Text/brands: NFC, whitespace, accents, punctuation and case preservation;
    comma-only splitting, empty/repeated tokens, no unapproved alias or fuzzy merge.
11. Derivations: operand eligibility, explicit common basis, zero/null denominator
    behavior and core8 denominator; no infinity or arbitrary health score.
12. Determinism and safe publication: stable key/sort order, repeat run with the
    same input/configuration produces identical data, no clobbering of a prior
    run, temporary sibling writes with atomic final publication and recoverable
    failure before manifest publication.

### 10.4 Row-count and referential-integrity checks

Validate PK uniqueness/non-nullness for all six frames. Every brand/category/fact
FK resolves to its dimension/product. Every product has one primary extraction
link contained within its source membership set; exactly 13 have two extraction
memberships. Namespace-filtered category counts are 500 each. No extra barcodes
are introduced; all original 1,987 remain.

Reconcile 644 brands/2,399 links under the recommended case-preserving rule and
884 categories/19,417 links under source-array reconstruction. Nutritional facts
have nine rows per product, no duplicate code, 17,883 slots, 743 original nulls
and 193 additional withheld values under Q. Available +missing +quarantined slots
must equal the total. Non-null usable values must equal their original observations
unless an explicitly approved, audited override is introduced in a later version.
Validate the 100 g/100 ml/unknown counts and analysis-specific denominators as
separate checks, not inferred from a single completeness score.

### 10.5 Checks performed for this planning phase

Recomputed missingness, all numerical predicates and original category-specific
IQR calculations independently using the project Python environment. Verified
CSV metadata/hash, all raw page/checkpoint response hashes, all combined-to-source
nutrient matches, membership sets, cross-category nutrient equality, raw taxonomy
arrays, classification reasons and basis metadata. Impact calculations used only
temporary in-memory masks and counts; no cleaned DataFrames were exported.

Before writing the plan, recorded hashes/sizes/modification times for all 49
existing data files, the EDA notebook and relevant existing source/documentation
files. The final comparison passed for all 58 baseline files: hashes, sizes and
modification times are unchanged. The data path set remains exactly 49 files;
no dataset, backup, checkpoint or extraction artifact was added or removed.

Executed `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`:
**36 tests passed in 1.163 seconds**, with no errors or failures. These are the
existing mocked/offline extraction tests, not validation of an implemented
cleaning pipeline. No live API request was made.

Reviewed Git status and diff: no tracked files changed; only this report is new,
in addition to the pre-existing untracked `.github/` directory. `git diff --check`
and the new report's no-index whitespace check found no whitespace errors.
Git emitted its normal LF-to-CRLF working-copy warning for the new Markdown file.

The notebook execution command was deliberately not run because it rewrites
notebook outputs. No automated cleaning tests exist yet; their specification above
must not be mistaken for tests already executed.

## 11. Unresolved decisions requiring approval

| Decision | Recommendation for approval | Alternative / risk |
| --- | --- | --- |
| Numerical quarantine scope | Approve Q: both operands of unresolved pairs and all subtotal operands; 193 measurements, no product removal | Flag-only or choosing one energy source retains more values but needs stronger source-preference evidence |
| Measurement-basis policy | Recover raw basis, use neutral per-100 columns, strict explicit-mass view for g/100-g comparisons; optional separately labelled sensitivity view | Treating all 728 unknown bases as grams silently is not supported; strict filtering changes category composition |
| Taxonomy representation | Recover all original arrays; separate extraction and taxonomy namespaces; retain suspicious strings with review state | CSV splitting introduces seven false links; keeping only four extraction categories would omit useful source taxonomy |
| Brand entities | Approve comma-separated source-label tokens with case preserved; review aliases separately | Casefold merging reduces 644 labels to 554 and links by seven; fuzzy or corporate-brand merging lacks evidence |
| Classification statuses | Preserve source unknown/not-applicable distinction and nullable grade/NOVA | A single `Unknown` placeholder loses source meaning |
| Source enrichment | Use raw metadata/tag arrays for provenance only; defer nutrient filling/correction | Recovering 14 generic-kJ observations is possible to investigate but changes the measured-value contract and all affected counts |
| Contextual outliers | Keep IQR-only values, flag contextually suspicious cases for review | Additional manual holds would change the 193-measurement scenario and must be separately audited |

Approval of this plan must specify any changed thresholds, aliases, overrides or
basis assumptions before implementation. No label image, external verification
or new API request is implicitly authorized by approval of an offline pipeline.

## 12. Recommended Phase 3B implementation sequence

1. Obtain approval for the decisions in Section 11 and freeze the rule version.
2. Implement a read-only input/provenance verifier and small failing offline tests
   for the measured baseline and newly discovered basis/tag/classification cases.
3. Construct exact-barcode products and all extraction provenance relationships;
   recover source taxonomy arrays and classification reasons without modifying inputs.
4. Build the source-preserving six DataFrames with explicit dtypes and nullable
   fields, then add approved text/brand normalization and source mappings.
5. Evaluate flags once on unchanged observations, generate distinct measurement
   quarantine/audit records, and expose separate numerical and basis eligibility.
6. Calculate only approved derived fields with stated units and eligibility rules.
7. Run unit, integration, reconciliation, FK, preservation and deterministic-output
   tests. Review the impact report against this plan; explain every count difference.
8. Publish a new versioned offline output directory and validation report only
   after all checks pass. Database design/loading and SQL reporting remain separate
   future work and are not authorized by this planning task.

**Stop after Phase 3A. Await user approval before implementing Phase 3B.**
