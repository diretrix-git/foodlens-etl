# FoodLens Academic Submission Package

This guide applies to the existing separate submission folder and ZIP. For a
public GitHub clone, use the [clone setup in README](README.md#reproduce-from-a-public-clone-offline).
Its public data notice is at `repro_data/README.md` in the Git repository.

The seven technical phases are complete. Start with
`reports/FoodLens_Final_Report.md` and `reports/submission_validation.md`.
The former is the complete editable academic report, including existing figures
and ERD. Keep it in this directory structure so its image links resolve.

## Included materials

The package contains `src/`, `scripts/`, `tests/`, both executed notebooks,
both requirements files, the SQL schema and eight queries, ERD PNG/DBML,
all seven validation reports, the historical cleaning plan, five analytical
charts, eight actual SQL result CSVs, the final report and saved datasets.
`README.md` preserves detailed phase instructions; use the offline sequence below
for submission review instead of its live extraction examples.

The archive includes its own copies of the inputs. The working `data/` directory
remains ignored by Git, while a reviewed public copy is tracked separately under
`repro_data/`. The archive has 45 data files: 20 saved response pages, four
checkpoints, four manifests, four barcode audit files, two legacy source
fixtures, six processed files and five cleaned CSVs. The per-category
processed CSVs are needed by the EDA notebook's
checksum assertions. The two legacy files are needed by existing extraction tests.
Backups, lock and cooldown state are unnecessary for offline reproduction.

Request metadata contact emails were redacted in these submission copies. The 20
response payloads and their canonical hashes are unchanged, as are every source
and cleaned CSV. Original repository datasets were not edited. A file manifest
records the bytes actually submitted. No `.env`, credentials, virtual environment,
Python caches, temporary files or backups are included. The safe `.env.example`
is a configuration template, not a credential file.

## Reproduce offline on Windows

Extract the ZIP to a writable directory and open PowerShell in its `FoodLens`
folder, where `src`, `data` and the requirements files are immediate children.
Use Python 3.12. Commands invoke the virtual environment directly, so activation
and PowerShell execution-policy changes are unnecessary.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-eda.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.clean_transform
.\.venv\Scripts\python.exe -m src.load_postgres --offline
.\.venv\Scripts\python.exe scripts/validate_phase5.py
.\.venv\Scripts\python.exe scripts/verify_saved_results.py
.\.venv\Scripts\python.exe scripts/execute_eda.py
.\.venv\Scripts\python.exe scripts/execute_analysis.py
```

Dependency installation needs a package index or a separately supplied wheel cache.
After dependencies are installed, these commands require no Open Food Facts request
or database connection. Existing tests mock HTTP and database connections. Do not
use `python -O`, which disables assertions used by existing validation code.

Expected results: 89 existing tests pass; transformation reuses the five identical
cleaned outputs; loader returns `offline_validated`; source table counts are 525,
4, 1,987, 2,000 and 1,987; schema compatibility checks pass; all eight saved result
sets agree (54 rows, 328 cells). The EDA executor checks 19 code cells and seven
figures; the analysis executor checks nine code cells and five figures. Each
executes from the root and notebook directory. Notebook execution rewrites its
outputs, and the analysis executor rewrites chart exports. Perform re-execution
in a working copy if you need to retain an exact copy of the submitted bytes.

No source dataset must be downloaded or regenerated. `src.clean_transform` verifies
sources and refuses to replace conflicting outputs. The package already contains
the complete analysis inputs. The optional ERD regeneration command is
`.\.venv\Scripts\python.exe scripts/generate_erd.py` and writes ERD PNG/DBML only.

On other operating systems, use `python3.12 -m venv .venv` and substitute
`.venv/bin/python` for the Windows interpreter path. That platform sequence was
not tested during preparation.

## Verify package integrity

Run before creating a virtual environment or rerunning notebooks. The manifest
covers every delivered file except itself and rejects missing or extra files:

```powershell
py -3.12 scripts/verify_submission_manifest.py
```

An independently supplied SHA-256 sidecar accompanies the ZIP. Compare it with:

```powershell
Get-FileHash -Algorithm SHA256 .\FoodLens_Submission.zip
```

Run that last command from the directory holding the ZIP, not the extracted
project. The manifest detects accidental changes, not malicious replacement of
both the data and its manifest.

## Optional fresh database reproduction

A database is **not needed** to inspect results or reproduce the Pandas analysis.
To rerun the actual PostgreSQL load and SQL reports, use a separate fresh database
that you control. A new Neon database or branch is suitable; another compatible
PostgreSQL service can also work when the loader's TLS and schema checks pass.
Do not ask for or reuse the owner's credentials, and do not reset the existing
FoodLens database.

1. Create a fresh database using your provider's controls. Run the complete
   `sql/schema.sql` in its SQL editor. This creates five empty tables in one
   transaction and deliberately fails if tables already exist.
2. Copy the template to `.env` only if the file does not exist, then privately
   replace its entire `DATABASE_URL` value with your own TLS-enabled URL.
3. Run the read-only check. It must report a compatible `empty` database before
   you intentionally authorize inserts into your own database with `--load`.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
.\.venv\Scripts\python.exe -m src.load_postgres --verify-only
# The next command intentionally inserts into your own fresh database:
.\.venv\Scripts\python.exe -m src.load_postgres --load
.\.venv\Scripts\python.exe -m src.load_postgres --verify-only
.\.venv\Scripts\python.exe -m src.load_postgres --load
.\.venv\Scripts\python.exe scripts/run_sql_reports.py
.\.venv\Scripts\python.exe scripts/verify_saved_results.py
```

Expected initial load is `loaded`, followed by two `identical` results and 6,503
rows across five tables. The reporting runner executes eight SELECTs and writes
the CSVs in `reports/sql_results`. Use a working copy to keep submitted exports
unchanged. Equal-rank display ordering can depend on database collation; compare
category result rows by key. Q4 defines an explicit barcode tie-break.

No command in this optional database section was run during final preparation.
The report attributes historical live results to their recorded sources. Offline
tests are not a replacement for testing a reviewer's fresh database. The existing
reporting runner has a generic exception branch that can print a traceback;
keep diagnostics private and redact connection details before sharing them.

## Before submitting

Fill in the report's student, university, course and date placeholders. Check the
institution's original assignment sheet, required format, naming and upload limits;
that sheet was not present in the repository. No missing technical deliverable was
found against the available project requirements. A dashboard, machine learning,
larger dataset and new technical phase are optional and were not added.

The report uses the explicitly permitted Markdown fallback. Word/PDF tools could
not be reliably rendered here. If a PDF is mandatory, export using a suitable
local editor and inspect all pages, especially the wide ERD and tables. Rebuild
the manifest and ZIP after filling placeholders or adding an approved final export:

```powershell
.\.venv\Scripts\python.exe scripts/package_submission.py
```

Run this in the original project or a separate extracted working copy. It creates
`submission/FoodLens` and `submission/FoodLens_Submission.zip` and refuses to replace
an existing output folder or archive. Move any earlier submission outputs aside
yourself before rebuilding. Re-run manifest verification on the new package.
No commit or push is needed to submit the archive.
