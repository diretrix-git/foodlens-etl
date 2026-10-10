# FoodLens Final Submission Validation

Preparation date: **10 October 2026**. Scope: audit, academic report and separate
reproducible submission. No additional technical phase was started.

## Requirement audit

The audit reviewed the repository README and `.github/agents/AGENTS.md`, all seven
phase validation reports, both executed notebooks, all three main source scripts,
SQL schema and reporting queries, ERD PNG/DBML, five charts, eight SQL exports,
requirements files, tests, helpers and Git ignore rules. No original university
assignment sheet was found among the reviewed project files; coverage is assessed
against the repository capstone instructions and the supplied final-preparation
request, not an invented institution-specific rubric.

| Phase | Required evidence present | Audit conclusion |
| --- | --- | --- |
| 1 Extraction | Downloader, 20 pages, four checkpoint sets, legacy source, category/combined exports, validation | Present; 2,000 occurrences and 1,987 unique products |
| 2 EDA | Executed 01 notebook, executor, validation | Present; 19 executed code cells and seven figures |
| 3 Transformation | Transformer, five cleaned CSVs, tests, validation | Present; all records and memberships retained |
| 4 Analysis | Executed 02 notebook, executor, five PNG charts, validation | Present; five questions and five quantified insights |
| 5 Database design | Schema, PNG/DBML, generation/validation helpers, tests, validation | Present; five tables, 65 columns, seven FKs |
| 6 Loading | Loader, template, tests, validation | Present; offline verification and attributed historical live evidence |
| 7 SQL reporting | Eight queries, runner, eight result CSVs, validation | Present; narrative corrections required and completed |
| Final report | Complete report with references, ERD, charts and appendices | Created as editable Markdown under the permitted fallback |
| Reproducible submission | Dataset-inclusive folder, ZIP, checksum manifest, instructions | Created separately from Git |

Before this task, the consolidated academic report and standalone dataset-inclusive
submission were missing. The technical phases were already implemented. Q6-Q8 in
the Phase 7 narrative contained incorrect figures; the underlying CSVs agree with
the cleaned data and were preserved. The narrative is now corrected, with an
explicit audit note. Historical Phase 2 nutrient labels predate the recovered basis
information; the final report explains this and uses strict Phase 4 comparisons.

No missing technical requirement was found against the available instructions.
A dashboard, machine learning, more categories, another development phase and a
new live extraction are optional enhancements and were not added. Institution-only
details and a mandatory paginated format, if any, remain for the student's review.

## Checks executed

| Check | Observed result |
| --- | --- |
| Original workspace unittest suite | 89 passed in 10.580 seconds |
| Existing environment pip check | No broken requirements found |
| Loader with --offline | offline_validated; expected five counts, 83 leading-zero barcodes and 13 overlaps |
| Phase 5 offline validator | Passed CSV names/order/types/nulls, PK/UQ/FK and translated scalar CHECK compatibility, SQL/DBML mapping |
| Notebook schema and saved outputs | Both nbformat-valid; 19/19 and 9/9 code cells have execution counts; zero error outputs; seven and five PNG outputs |
| Saved results versus fresh Pandas calculations | Eight reports, 54 rows, all 328 cells passed |
| Isolated package-copy unittest suite | 89 passed in 8.706 seconds |
| Isolated package-copy transformation | Passed source/provenance and reload checks; identical cleaned outputs reused |
| Isolated EDA execution | Passed from project root and notebooks directory, 19 cells and seven figures each |
| Isolated analysis execution | Passed from both directories, nine cells and five figures each; identical chart hashes between runs |
| Isolated data preservation | All 45 submitted data files unchanged in hash, size and modification time during notebook execution |
| Original workspace preservation | All 74 protected files unchanged in hash, size and modification time |
| README script references | All referenced source/helper script paths exist |
| Final report links and images | All relative targets exist; existing charts and ERD reviewed visually |
| Git whitespace check | Passed; ordinary LF/CRLF notices only |

The 74 protected files comprise all 54 original data files, both notebooks, original
source/SQL files, five figures and eight SQL exports. Source datasets, backups,
original notebooks, main ETL code and original analytical outputs were not edited.

The isolated rehearsal was made from the same file allowlist and redaction routine
used by the final builder. Its local virtual environment reused installed project
dependencies through a temporary path file; this was a check of file sufficiency
and relative paths, not a fresh internet installation. That temporary environment,
path file, rerun notebook outputs and logs are excluded from the final archive.
The final archive retains the original executed notebooks and figures.

The notebook kernels emitted local transport/encryption warnings, but executions
finished with no cell errors. No API extraction or database connection was needed.
No live load, reset, deletion, schema creation or SQL-report rerun was performed.
The final report distinguishes historical owner-reported Neon results from these
current offline checks.

## Corrected SQL figures

| Report | Correction based on saved CSV and offline recomputation |
| --- | --- |
| Q6 NOVA 4 among classified | Biscuits 85.3%, breakfast cereals 54.1%, cereal bars 91.0%, yogurts 55.6% |
| Q7 leading primary brands | Nestlé 70, Gerblé 69, Danone 65, MERCADONA 64, Bjorg 56 |
| Q8 numeric null means | Yogurts 0.93, biscuits 0.31, cereal bars 0.14, breakfast cereals 0.12 |
| Q8 flagged shares | Yogurts 6.0%, biscuits 3.6%, cereal bars 6.4%, breakfast cereals 2.2% |

`scripts/verify_saved_results.py` reads only local cleaned CSVs and saved results.
It checks all columns, result keys, row counts and the explicit Q4 ranking. Values
are compared with a small floating-point tolerance after query-equivalent displayed
rounding. This is independent Pandas reconciliation, not PostgreSQL execution.
Source observations and SQL exports were not rewritten.

## Source inclusion and privacy

Git tracks no data files in the current tree. `.gitignore` excludes raw/processed
datasets, extraction state and cleaned tables, so a Git checkout alone cannot
reproduce the notebooks. The package includes 45 necessary/provenance data files:
20 page snapshots, four checkpoints, four manifests, four barcode audits, two
legacy test fixtures, six processed files and five cleaned tables. Nine original
data files are excluded: seven backup files, one lock and one cooldown file.

For privacy, contact addresses are replaced by `[CONTACT REDACTED]` only in copied
request `user_agent` fields: four checkpoints and 19 nonlegacy page envelopes,
23 JSON files in total. `reports/submission_redactions.json` lists the relative
paths and field paths, never the removed addresses. All 20 canonical response
hashes remain valid. Response payloads, query configuration, source pointers,
timestamps, dataset values and every CSV byte are preserved. Original source
envelopes remain untouched in the repository.

The builder scans for forbidden paths, credential patterns, actual local database
URL/password matches without printing them, non-placeholder contacts and local
absolute paths. The only non-example-domain email allowed is an existing mocked
User-Agent test fixture in `tests/test_download_dataset.py`; it is not a real
extraction contact. `.env.example` contains only a host placeholder, without a
username or password. `.env`, tokens, private keys, virtual environments, caches,
temporary files and backups are excluded. Automated pattern checks cannot prove
the absence of every conceivable secret; the allowlist and scoped redaction avoid
copying local environment state in the first place.

## Archive validation and rebuild

`scripts/package_submission.py` builds `submission/FoodLens` and
`submission/FoodLens_Submission.zip`. It refuses to overwrite existing outputs.
It scans selected content, writes a SHA-256/size manifest, verifies the exact file
set, checks ZIP CRC integrity, rejects duplicate/unsafe paths and compares every
archive member byte-for-byte with its folder counterpart. Archive paths have one
`FoodLens/` root and portable forward slashes. The manifest excludes itself to
avoid a self-referential hash. A separate ZIP SHA-256 sidecar covers the archive.

Run `scripts/verify_submission_manifest.py` with standard Python immediately after
extraction, before re-execution generates local caches or a virtual environment.
`SUBMISSION_README.md` supplies exact offline and optional fresh-database commands.
Every source/helper script referenced there and by README exists in the package.

## Format and remaining manual steps

The editable report is `reports/FoodLens_Final_Report.md`. The required managed
Word authoring runtime was not available through the installed tools; the project
environment lacked `docx`, `reportlab`, `pdf2image` and `pypdf`, and LibreOffice was
not installed at either standard Windows location or available on PATH. Poppler
alone does not generate or convert a Word report. The user-authorized Markdown
fallback was used instead of delivering an unverified DOCX/PDF. No dependency or
working environment changes were made to force an export.

The student must complete cover placeholders and verify the university's actual
rubric, required format and upload rules. If a PDF is mandatory, export locally,
review all pages and rebuild the submission manifest/ZIP after final edits. The
readable report requires its accompanying relative image paths.

A fresh reviewer needs no Neon database for offline analysis. To reproduce live
loading and SQL execution, use a separate fresh database with private credentials;
Neon is suitable but not mandatory if another PostgreSQL service satisfies the
loader checks. Historical live success does not prove a reviewer's new deployment.
Pinned packages and Python must be available; package wheels are not included.

## Working tree and scope

Changed tracked files: `.gitignore` (exclude separate submission artifacts),
`README.md` (submission links), and `reports/phase7_validation.md` (evidence-based
corrections). Added files: final Markdown report, this validation report,
`SUBMISSION_README.md`, and the three submission helpers `package_submission.py`,
`verify_saved_results.py`, `verify_submission_manifest.py`. Submission outputs
are intentionally ignored rather than staged. Temporary QA work remains under
ignored `tmp/` and is not part of the deliverable.

Git status, diff and whitespace checks were reviewed. A command-local
`safe.directory` override was used for the sandbox ownership check; no global Git
settings were changed. Nothing was staged, committed or pushed.
