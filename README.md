# FoodLens: Food Nutrition Quality & Data Analysis ETL Pipeline

University semester project. Phase 1 implements extraction, source preservation,
resumable pagination, and analytical exports. Phase 2 adds a read-only exploratory
notebook. Cleaning, database loading, and SQL reporting are not implemented.

## Phase 2: exploratory data analysis

Open `notebooks/01_eda.ipynb` using the project's `.venv` Python kernel. It reads
`data/processed/food_products_analysis_combined_725f8a023f0f8ee6.csv` and checks its
metadata, saved pages, and category checkpoints. Keep the complete Phase 1 data
directory available locally; source data are intentionally excluded from Git.
The notebook runs with its working directory at either the repository root or
`notebooks/`. No absolute machine paths or live API access are required.

Install the additional plotting/execution tools, then execute and validate from
the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-eda.txt
.\.venv\Scripts\python.exe scripts/execute_eda.py
```

The executor starts a fresh kernel with the same `.venv` interpreter in each
working directory. It checks all cells, seven embedded figures, and the hashes,
sizes and modification times of all existing data files. It writes the executed
notebook only after both runs pass. It does not need JupyterLab, Notebook Server
or a globally registered kernel. In an interactive editor, explicitly select
the `.venv` interpreter. Kernel startup may emit local IPython/Jupyter permission
or transport warnings under a restricted Windows account; notebook errors still
fail execution.

The notebook covers the verified 2,000 source records / 1,987 unique products,
24 fields, missingness, identities, category overlaps, brand strings, Nutri-Score,
NOVA, nutrition summaries, internal consistency and category-specific IQR flags.
Category comparisons use **all memberships**, with shared products counted once
per category. Overall summaries use unique products. Seven figures include
calculated interpretations. All numeric conversions and filtering are temporary
EDA views; no cleaning, imputation or outlier removal is saved.

See `reports/phase2_validation.md` for measured findings and execution evidence.

## Current saved data

The breakfast-cereals extraction contains **500 unique products** in its
independent checkpoint `255549a7a8a480c0`. Its raw page snapshots, manifest,
checkpoint, and analytical export are retained unchanged. Additional categories
use different configuration-derived extraction IDs and never reuse this
checkpoint.

Before editing the script, the original script and both datasets were copied to
`data/backups/pre_extraction_upgrade_20261009T040156Z/`. Its `manifest.json`
records byte sizes and SHA-256 hashes. Legacy import also creates a
content-addressed backup under `data/backups/legacy_<hash>/`.

## Resume downloading

Run from the project root in PowerShell. A real contact email is required
for live requests; it is used in the User-Agent and saved extraction metadata.

The `.venv` uses Python 3.12.4 and all ten Phase 1 dependencies from
`requirements.txt`, plus the optional Phase 2 tools in `requirements-eda.txt`.
Activate it normally; no `PYTHONPATH` workaround is needed:

```powershell
Set-Location <path-to-foodlens-etl>
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
$env:FOODLENS_CONTACT_EMAIL = Read-Host 'Enter your contact email'
python src/download_dataset.py --target 500
```

If your shell still has the earlier workaround set, clear it once with
`Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue` before activation.
The execution-policy command is needed when PowerShell blocks activation scripts;
it applies only to the current shell and does not change the user or machine policy.
You can also run `.\.venv\Scripts\python.exe` directly without activating.
The extraction script itself only needs `requests`; pandas and NumPy are also
installed for later project phases. `requirements.txt` remains unchanged.

The same command resumes automatically. It will not request completed pages.
The target is a stopping threshold: the last successful page is retained in
full, so the analytical CSV can contain slightly more than 500 unique products.
Changing the target, contact email, or retry policy reuses saved pages. Changing
the category, page size, requested fields, or source URL selects a separate
extraction ID and separate output files.

To rebuild the analytical CSV and checkpoint without contacting the API:

```powershell
python src/download_dataset.py --offline
```

For a fresh copy of this project with the original data but no saved page files,
use `--import-legacy --offline` once. This option only accepts the known
100-record page 1 with the original breakfast-cereals filter and page size 100;
it is not a general importer for arbitrary JSON files. Repeating it after import
does not add records again. The original extraction timestamp and full response
envelope were never saved, so imported rows have a blank extraction timestamp
and an explicit `legacy_import` origin. The import time is recorded separately.

## Multi-category extraction

The verified Open Food Facts taxonomy identifiers are:

| Category | Identifier | Target |
| --- | --- | ---: |
| Breakfast cereals | `breakfast-cereals` | 500 |
| Yogurts | `yogurts` | 500 |
| Biscuits | `biscuits` | 500 |
| Cereal bars | `cereal-bars` | 500 |

The category identifier is part of the extraction configuration and checkpoint
identity. The completed breakfast-cereals checkpoint is reused and does not
trigger another request. Download only the additional categories:

```powershell
python src/download_dataset.py --category yogurts --target 500
python src/download_dataset.py --category biscuits --target 500
python src/download_dataset.py --category cereal-bars --target 500
```

Each command writes independent raw page snapshots, manifests, checkpoints, and
per-category analytical CSV output. Use the same command again to resume an
interrupted category; completed categories are not downloaded again.

After all four category checkpoints are complete, combine them without network
access:

```powershell
python src/download_dataset.py --combine-categories breakfast-cereals,yogurts,biscuits,cereal-bars
```

The combined output has 24 columns, including the analytical nutrient fields,
the original `categories` taxonomy tags, the extraction category,
`extraction_categories`, and `category_membership_count`. Products are globally
deduplicated by exact barcode; the first category's row supplies the retained
product/nutrient values and all category memberships are merged. The adjacent
JSON metadata file reports raw records, per-category unique products, missing
barcodes, duplicate/invalid barcode issues, and overlapping products. The
combiner only reads saved checkpoints/pages and never makes API requests.

## Request behavior

- Source: `https://world.openfoodfacts.org/api/v2/search`.
- Category filter: `categories_tags_en=<category>`; page size 100; original
  requested fields preserved. No explicit sort is used, so the API's default
  order is retained.
- Target: 500 unique usable barcodes. Default budget: 20 completed pages in total,
  including earlier runs. This prevents endlessly fetching duplicate-only pages.
- User-Agent: `FoodLensStudentProject/2.0 (your-contact-email)`.
- At least 10 seconds between request starts, including retries. Cooldowns are
  persisted across local runs and configurations sharing the data directory.
- HTTP 429, 500, 502, 503, and 504, plus connection errors/timeouts, get at most
  three retries after the first attempt. Exponential backoff starts at 10 seconds
  and caps at 120 seconds. HTTP `Retry-After` supports seconds and HTTP dates;
  the largest applicable delay wins, including on the final failed attempt.
- If a cooldown exceeds the default 300-second waiting budget, extraction stops
  incomplete and retains the deadline for a later resume. It never shortens a
  server-requested cooldown. Connection timeout is 10 seconds and read timeout
  is 45 seconds. Read timeout is not a strict whole-response deadline.
- Non-retryable HTTP errors, malformed JSON, and invalid page structures stop
  safely. Redirects are disabled to avoid uncounted additional requests.
- An empty/short page or reported total count reaching the last page marks the
  source exhausted. Below the target, the extraction remains incomplete.
- Exit codes: `0` for completed extraction or successful offline rebuilding,
  `2` for a live extraction that stops incomplete (also argparse usage errors),
  and `1` for local storage/configuration failures. Ctrl+C during downloading
  records the interrupted state and retains saved pages.

Use `python src/download_dataset.py --help` for configurable limits.

Open Food Facts currently documents **10 search requests/minute/IP** and asks
clients to identify themselves with a custom User-Agent. It recommends bulk
exports for larger extractions beyond a few hundred products. This small,
bounded semester-project extraction retains the requested API workflow; use
bulk exports if the project expands. Other clients on the same IP can consume
the same rate limit. See the [official API guidance](https://github.com/openfoodfacts/openfoodfacts-server/blob/main/docs/api/index.md)
and [search endpoint documentation](https://openfoodfacts.github.io/documentation/docs/Product-Opener/v2/search/get-search/).

## Saved artifacts and recovery

```text
data/
  backups/                                  Original files and checksum manifests
  raw/
    food_products_raw.json                  Original 100 records; never overwritten
    food_products_extracted.csv             Original wide CSV; never overwritten
    extractions/<extraction_id>/
      manifest.json                         Configuration and extraction creation time
      pages/page_000001.json                Immutable page with response + metadata
      checkpoint.json                       Completed pages, progress, counts, policy
      barcode_issues.json                   Exclusions with page/record references
  processed/
    food_products_analysis_<id>.csv          Separate, deduplicated 21-column export
  request_cooldown.json                      Created when a live request is attempted
  .extraction.lock                          Persistent file; OS releases its lock on exit
```

Each successful API response is preserved in full as parsed JSON under the page's
`response` key, including duplicate records and unused nutrients. JSON whitespace
and object key order are normalized; this is not a byte-for-byte HTTP capture.
Page metadata includes the requested URL/parameters, UTC extraction and save
timestamps, row count, response checksum, successful attempt count, HTTP status,
server Date header, User-Agent, and request policy.

The page file is the durable commit point. The CSV and barcode audit file are
rebuilt next; the checkpoint is published last. All writes use a temporary file
in the destination directory, flush + `fsync`, and `os.replace`. A process crash
between page and checkpoint writes is recovered by scanning and validating saved
pages, without requesting them again. A malformed checkpoint is preserved in a
`checkpoint.corrupt-<hash>.json` file and rebuilt from valid pages. Missing or
damaged raw pages stop recovery instead of being silently replaced or discarded.

The checkpoint includes the CSV hash, response hashes, completed pages, next
page, query parameters, target, actual row counts, status, and stop reason.
If an export/write fails, the checkpoint may lag; fix the filesystem issue and
run `--offline` to rebuild it. Writes are atomic per file, not across all files;
only use the exported CSV when its hash matches the published checkpoint. Local
disk failure or power loss can still require restoration from backups. Do not
edit raw pages or remove checkpoints to force a refresh.

An OS file lock prevents concurrent writers using the same data directory. It
is released on normal exit or process death, so a leftover lock file is harmless.
Separate data directories or machines do not share that lock or cooldown.

## Analytical CSV and barcode policy

The 21 columns are:

| Fields | Meaning |
| --- | --- |
| `barcode`, `product_name`, `brands`, `categories` | Product identity; category tags separated by semicolons |
| `energy_kcal_100g`, `energy_kj_100g` | API energy values per 100 g |
| `protein_g_100g`, `carbohydrates_g_100g`, `sugars_g_100g` | API macronutrient values per 100 g |
| `fat_g_100g`, `saturated_fat_g_100g`, `fiber_g_100g`, `salt_g_100g` | API nutrient values per 100 g |
| `nutriscore_grade`, `nova_group` | Valid grades a-e and NOVA groups 1-4 |
| `source_page`, `source_record_index`, `extracted_at_utc` | Traceability; record index is zero-based |
| `source_url`, `record_origin`, `extraction_id` | Request URL, API/legacy origin, configuration ID |

Only explicit API `_100g` nutrient values are exported. No missing values are
filled, no serving conversions are inferred, and missing/negative/non-finite
nutrient values become blank cells. Zero remains zero. For future liquid-product
filters, verify whether OFF's `_100g` basis means 100 ml before analysis.

Usable barcodes are exact ASCII digit strings of length 8-14. Leading zeroes
are preserved. Blank/missing codes and malformed/non-string codes are excluded
from the analytical CSV and listed in `barcode_issues.json`; their source records
remain intact in raw pages. First occurrence in page/record order wins for a
duplicate barcode. Duplicate versions remain available for auditing. There is
no zero-padding, UPC/EAN equivalence conversion, or GTIN checksum validation;
this avoids guessing identifiers and accommodates OFF internal numeric codes.
When importing CSV into pandas or spreadsheets, explicitly treat `barcode` as
text to prevent loss of leading zeroes. Product text is retained as source text.

## Offline verification

From the project root, with the same Python environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip check
python -m unittest discover -s tests -v
python src/download_dataset.py --help
```

The tests use the existing real dataset as fixture input and temporary directories
for all generated test artifacts. HTTP responses and clocks are mocked; accidental
real `requests` HTTP calls raise an error. Deliberately malformed identifiers are
confined to test cases and never enter the project dataset. No extra test package
is needed beyond Python's `unittest` and the downloader's `requests` dependency.

The executed extraction suite has **36 passing tests**, covering category combination,
completion checks, retryable status codes,
exponential backoff, both Retry-After formats, persisted cooldowns, network errors,
checkpoint recovery, missing/corrupt pages, legacy preservation, deduplication,
invalid barcodes, CSV fields, atomic write failures, source exhaustion, page
budgets, interruption, and concurrent-writer exclusion.

## Reproducibility limits

Saved pages and their exact query/response provenance make the local analytical
export reproducible. Open Food Facts is a changing public database: requesting
the same query later need not return the same ordering or products. Pagination
across different times can have overlaps or omissions; deduplication removes
overlaps but cannot recover unseen products. Historical page-1 extraction time
and HTTP response metadata cannot be reconstructed. Reaching 500 depends on API
availability, matching source records, usable barcodes, and request limits.
