# FoodLens Phase 1 Validation

**Validation date:** 2026-10-09  
**Mode:** Read-only; no API requests, extraction writes, commits, or pushes

## Conclusion

**PASS.** The four category extractions are complete, the combined output
reconciles correctly, barcode/category membership data is consistent, nutrition
values are numerically parseable, and all offline tests pass.

## Combined output

Files inspected:

- `data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv`
- `data/processed/food_products_analysis_combined_725f8a023f0f8ee6.json`

| Measure | Result |
| --- | ---: |
| CSV data rows | 1,987 |
| CSV columns | 24 |
| Unique barcodes | 1,987 |
| Duplicate barcode groups | 0 |
| Metadata-reported unique products | 1,987 |
| Metadata-reported raw records | 2,000 |
| Metadata SHA-256 matches CSV | Yes |
| Metadata columns match CSV header | Yes |

## Category checkpoints

All categories have five completed pages, `complete` status, and 500 raw and
500 unique products:

| Category | Extraction ID | Raw records | Unique products | Missing | Invalid | Intra-category duplicates |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| breakfast-cereals | `255549a7a8a480c0` | 500 | 500 | 0 | 0 | 0 |
| yogurts | `a7cac53fa4872087` | 500 | 500 | 0 | 0 | 0 |
| biscuits | `34e0ad749f6a0fa6` | 500 | 500 | 0 | 0 | 0 |
| cereal-bars | `ed4f16ea3c02f6ab` | 500 | 500 | 0 | 0 | 0 |

## Reconciliation and overlap

The source total is:

```text
500 + 500 + 500 + 500 = 2,000 source records
2,000 - 1,987 combined products = 13 overlapping products
```

The 13-record difference is entirely due to overlapping barcodes. No records
were excluded for missing or invalid barcodes.

Independent checks found:

- 13 products with more than one category membership.
- 0 invalid membership rows.
- Every `category_membership_count` equals the number of listed categories.
- Every combined CSV barcode is unique.
- Category membership pairs:
  - breakfast-cereals + cereal-bars: 7
  - breakfast-cereals + biscuits: 2
  - breakfast-cereals + yogurts: 2
  - biscuits + cereal-bars: 2

The per-row `extraction_category` counts are
breakfast-cereals 500, yogurts 498, biscuits 498, and cereal-bars 491 because
the first category's retained row represents products that overlap later
categories. The `extraction_categories` field preserves all memberships.

## Essential nutrition fields

All nine expected numeric nutrition columns exist. Percentages are calculated
over the 1,987 combined rows:

| Column | Present | Missing | Missing % | Numeric parse failures |
| --- | ---: | ---: | ---: | ---: |
| energy_kcal_100g | 1,948 | 39 | 1.96% | 0 |
| energy_kj_100g | 1,932 | 55 | 2.77% | 0 |
| protein_g_100g | 1,944 | 43 | 2.16% | 0 |
| carbohydrates_g_100g | 1,943 | 44 | 2.21% | 0 |
| sugars_g_100g | 1,937 | 50 | 2.52% | 0 |
| fat_g_100g | 1,946 | 41 | 2.06% | 0 |
| saturated_fat_100g | 1,933 | 54 | 2.72% | 0 |
| fiber_g_100g | 1,636 | 351 | 17.66% | 0 |
| salt_g_100g | 1,921 | 66 | 3.32% | 0 |

Missing values are expected source omissions. No cleaning or imputation was
performed.

## Raw data and saved API responses

- Current original raw JSON SHA-256:
  `0013c5a0eaf9fdee3832535a72c745793d38c4e3016726c6458cb5e435415d67`
- The current raw JSON byte-matches both existing backup copies.
- All 20 saved page response envelopes have valid canonical response hashes.
- Every page response hash matches both its page envelope and its category
  checkpoint.
- No raw JSON, checkpoint, manifest, or saved API response was modified by this
  validation.

## Tests and repository checks

Command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Result: **36 tests passed in 1.101 seconds.**

Command:

```powershell
git diff --check
```

Result: **PASS.**

The existing source changes remain uncommitted. This validation created only
this report and did not alter Git history.
