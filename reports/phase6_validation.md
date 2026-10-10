# FoodLens Phase 6: PostgreSQL ETL loading validation

**Date:** 2026-10-10. **Status: Phase 6 completed successfully.**
Neon loading, full content verification and an identical rerun have succeeded.

## Final live results

The project owner supplied the following actual Neon PostgreSQL results after
the fixes below. They are recorded as owner-reported live execution evidence;
this documentation update did not connect to Neon or rerun any database command.

| Operation | Returned status |
| --- | --- |
| Initial successful load | `loaded` |
| First verification | `identical` |
| Second load (rerun) | `identical` |
| Schema validation | `verified` |
| Complete content comparison | `passed` |

| Table | Actual live PostgreSQL rows |
| --- | ---: |
| brands | 525 |
| categories | 4 |
| products | 1,987 |
| product_categories | 2,000 |
| nutrition | 1,987 |
| **Total** | **6,503** |

The total counts rows across five relational tables, not unique products; there
are 1,987 unique products. The reported `identical` rerun confirms that the loader
accepted the complete existing data without inserting duplicates.

Review of the unchanged implementation confirms that `content_comparison: passed`
requires all five counts, unique primary keys, all seven foreign-key checks,
complete CSV-to-database row comparisons, 83 leading-zero barcodes and 13 overlapping
products. Complete comparison includes nutrient SQL NULL positions, all category
memberships, text, numeric values and timestamp instants. These results establish
successful loading and verification, not just matching counts. The earlier
zero-row observations and pending-load notes below describe historical debugging
stages and are superseded by these final results.

## Historical SQLSTATE 42601 after the first loading attempt

The owner reported that the first authorized load failed with SQLSTATE 42601.
The failing statement is the last SELECT in `verify_contents`, after the inserts
and deferred-constraint check but before the loading transaction commits:

```sql
SELECT count(*) FROM
    (SELECT barcode FROM public.product_categories
     GROUP BY barcode HAVING count(*) > 1) overlaps
```

`OVERLAPS` is a reserved PostgreSQL keyword and cannot be used as this unquoted
subquery alias. See the [PostgreSQL keyword list](https://www.postgresql.org/docs/18/sql-keywords-appendix.html).
Executing this exact SELECT in a read-only Neon transaction reproduced SQLSTATE
42601, with the server's statement position pointing at `overlaps`. No INSERT or
load retry was needed to reproduce the failure. The earlier empty-table preflight
returned after the five count queries, so it never reached the invalid SELECT.
The former fake database explicitly accepted the invalid alias, hiding this error
from the original offline tests.

The corrected statement uses an ordinary, explicit alias:

```sql
SELECT count(*) FROM
    (SELECT barcode FROM public.product_categories
     GROUP BY barcode HAVING count(*) > 1) AS category_overlaps
```

The query now also has the sanitized operation label `Category overlap count
verification`, so any future SQL error at this point identifies the exact step.
INSERT generation is unchanged: schema-qualified quoted table/column identifiers,
one `%s` placeholder per column, and separate row parameters through `executemany`.
All five mappings were inspected: 2 brands columns, 2 categories columns,
16 products columns, 2 membership columns and 43 nutrition columns. Tests now
check column order, placeholder counts and every row's parameter arity.

The fake database now rejects the old reserved alias. The new regression test was
run against the unfixed loader and failed at the exact overlap SELECT; it passes
after the alias correction. A second test injects SQLSTATE 42601 at that SELECT
after all five mocked inserts and confirms zero commits, one rollback, all five
tables restored to empty, and no sensitive server detail in the error message.
The transaction boundary, insertion order and rollback behavior are unchanged.

Only `src/load_postgres.py`, `tests/test_load_postgres.py`, and this report were
modified for this correction. No live write statements or automatic load retry
were executed. SSL certificate/hostname verification remains enabled.

Read-only checks after the reported failed transaction found zero rows in all
five tables, confirming that no partially loaded records remained at that stage.
Schema verification passed. The subsequent successful load and populated-data
comparison are recorded in the final live results above.

| SQL-fix validation | Actual result |
| --- | --- |
| Regression against unfixed SQL | Failed at the reserved alias, as intended |
| Focused loader suite after fix | 29 tests passed in 10.336 seconds |
| Complete offline suite | 89 tests passed in 48.915 seconds |
| Original SELECT on Neon, read-only | Reproduced 42601 at `overlaps` |
| Corrected SELECT on Neon, read-only | Succeeded; count 0 for the empty bridge |
| Complete content-validation SQL path | All 24 SELECTs executed successfully in a read-only transaction |
| Final `--verify-only` | Exit 0; schema verified; all five table counts 0 |
| Parameterization and mapping | All five INSERT shapes retain bound values and exact column order/arity |
| Transaction regression | Error after all five mocked inserts rolls back all five tables |
| Preservation | All 58 protected files unchanged: 54 data files, 2 notebooks, schema and `.env` |
| Dependency/diff checks | `pip check`, `git diff --check`, and code diff review passed |

The 24-query diagnostic captured the populated-data SELECT path using the offline
fixture and executed only those SELECT statements against empty Neon tables. It
checked SQL syntax and column access without attempting inserts, executing
`EXPLAIN INSERT`, or claiming that empty-table values match the populated CSVs.
The original failing SELECT and the corrected SELECT ran in separate read-only
transactions. The temporary diagnostic was removed after verification.

## Earlier TLS verification failure and fix

The reported generic error was traced to `psycopg.connect`, before schema queries.
The loader enforced `sslmode=verify-full` and defaulted `sslrootcert` to `system`.
With the installed Windows/libpq trust configuration, that produced a certificate
verification failure (client `OperationalError`, no SQLSTATE). The broad error
handler concealed the failure point. The successful direct connection did not
establish that the loader's stronger TLS settings would work.

A controlled read-only diagnostic kept the same endpoint, database, credentials
and `verify-full`, changing only the default CA source to `certifi.where()`.
Connection and complete schema verification then succeeded, returning five empty
tables. No schema assumption, column type or empty-table handling bug was found.
The network-restricted sandbox initially blocked the socket; the authorized
diagnostic outside that sandbox exposed the actual TLS failure.

The loader now defaults to the already-pinned certifi CA file. Explicit URL
`sslrootcert` settings and then `PGSSLROOTCERT` take precedence; they are never
silently bypassed after a failure. Full certificate/hostname verification and
channel-binding settings remain intact. Certifi provides a portable CA bundle;
see its [official documentation](https://github.com/certifi/python-certifi).
The example URL no longer forces `sslrootcert=system`, and README reflects the fix.

Database failures now name the operation, identify a safe cause/action, and include
a validated SQLSTATE when available. Table, column and constraint catalog queries
have individual operation labels. TLS errors specifically point to CA configuration.
Raw exception text, server diagnostic details, URLs, passwords and hostnames are
never emitted. Regression tests cover the CA default/overrides, endpoint/database
preservation, TLS error sanitization, exact catalog failure locations, content
query errors and stopping before verification/loading on connection failure.

SQL confirmed the connected database is `neondb`. The diagnostic verified that the
loader does not change the URL's endpoint/database, and the project owner explicitly
confirmed that this URL was copied with the Neon `production` branch selected.
The production branch name is therefore owner-confirmed; it was not inferred from
the database name or independently resolved through the Neon management API.

Follow-up files modified: `src/load_postgres.py`, `tests/test_load_postgres.py`,
`.env.example`, `README.md`, and this report. Dependencies, SQL schema and source
datasets were not changed. The agent did not edit `.env`; its checksum/size/mtime
changed externally during the session, and the successful final command used the
current local configuration without overwriting it.

| Follow-up check | Result |
| --- | --- |
| Focused loader tests | 27 passed in 12.163 seconds |
| Complete offline suite | 87 passed in 55.924 seconds |
| Final `python -m src.load_postgres --verify-only` | Exit 0; `status: empty`, `schema: verified` |
| Live row counts | 0 in each of all five tables |
| Live content comparison | Pending initial load; correctly short-circuits for empty tables |
| Dependency check | No broken requirements |
| Protected schema/data/notebooks | 57 files unchanged by path, hash, size and mtime |
| Credentials file | Still ignored; not written by the agent |

At the end of the TLS fix, the project passed read-only preflight. No INSERT,
UPDATE, DELETE, DROP, TRUNCATE, schema creation or other persistent database-changing
operation was executed during that debugging task. No commit or push was performed.

## Connection and authorization status

During the initial offline implementation, no process `DATABASE_URL` or local
`.env` existed, so verification stopped before connecting. During this follow-up,
the owner supplied a local `.env` configuration, which remains ignored by Git.
Live read-only verification now confirms the existing schema in Neon `neondb`.

The first authorized attempt failed with SQLSTATE 42601 and left all five tables
empty. After the SQL fix, the owner reported successful loading and verification
as shown above. This final task updates documentation and runs offline checks
only; it does not authorize another load or any database changes. Mocked tests
remain separate from the owner-reported live evidence.

| Table | Verified CSV rows | Actual live PostgreSQL rows |
| --- | ---: | --- |
| brands | 525 | 525 |
| categories | 4 | 4 |
| products | 1,987 | 1,987 |
| product_categories | 2,000 | 2,000 |
| nutrition | 1,987 | 1,987 |
| **Total** | **6,503** | **6,503** |

## Files and implementation

Created `src/load_postgres.py`, `tests/test_load_postgres.py`, `.env.example`, and
this report. Updated `README.md`, the secret-ignore comment in `.gitignore`, and
`requirements.txt`. Existing `.env`/`.env.*` ignore rules and the example exception
were already correct. Added pinned `psycopg[binary]==3.3.6`,
`python-dotenv==1.2.4`, and Psycopg's `typing_extensions==4.16.0` dependency;
preserved the existing requirements file's UTF-16 encoding and original packages.
The new packages were installed into the project Python 3.12 environment.

Inspected the repository agent instructions, README, cleaning implementation,
schema, Phase 3/5 validation reports, all five actual CSV headers and relevant
existing tests. The loader reuses the repository's narrow SQL schema reader.
No existing table definitions, transformation code or source data were changed.

Pandas reads all CSV cells as strings with only blank cells treated as missing.
Explicit conversion produces Python text, integers, finite floats, Booleans,
timezone-aware datetimes and `None` parameters. Literal NA labels and multiline
original text are preserved. All 65 columns follow the existing SQL names/order.
Source checks cover the expected row counts, five PKs, two unique names, seven
FKs (including reciprocal nutrition and primary membership), required values,
types, scalar CHECK compatibility and overlap/barcode totals. Source validation
uses explicit exceptions rather than removable Python assertions.

The default command and `--verify-only` open a repeatable-read, read-only
transaction. Catalog queries check ordinary tables, columns/types/nullability,
defaults, generated/identity columns, PK/UQ/FK definitions, FK actions/timing,
validated/enforced constraints, and all 25 CHECK expressions. Unexpected RLS,
user triggers, disabled internal triggers, rules or inheritance stop the loader.
CHECK expressions from SQL/catalog are compared through PostgreSQL-normalized
`EXPLAIN (VERBOSE, FORMAT JSON)` output, without `ANALYZE`; no temporary schema
is created. This supports PostgreSQL's equivalent IN/ANY and BETWEEN forms.
A catalog/plan difference stops for review; no automatic DDL repair is attempted.
PostgreSQL documents the output and execution distinction in
[EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html).

`--load` is the explicit insert opt-in. After successful read-only preflight,
it locks the five tables against concurrent writers, rechecks their schema and
contents, and inserts only if all five remain empty. Bound `%s` parameters carry
every CSV value; quoted identifiers come from the repository schema. The order is
brands, categories, products, product_categories, nutrition. One transaction
contains all inserts, immediate checking of deferred constraints and full result
validation. Success is reported only after the transaction context commits.
Psycopg's context commits on success and rolls back on failure; see its
[transaction documentation](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

Actual SQL validation is implemented for all five counts, duplicate PKs, every
FK, all selected columns/records, 83 leading-zero barcodes and 13 overlaps.
Complete row multisets are compared with the source parameters, so order is
irrelevant and duplicated or changed records cannot pass merely by matching
counts. Numeric equality compares the parsed binary64 value without rounding
or a tolerance that could hide edits. Datetimes compare instants; `None` only
matches SQL NULL. Full comparisons verify every text/numeric value, every NULL
position and every category pair. Identical complete contents produce no inserts;
partial or changed contents stop for manual review. No DROP, TRUNCATE, DELETE,
UPDATE, upsert, schema recreation, live API extraction or Phase 7 reporting exists
in the new loader.

Connection settings come only from the environment or local `.env`; dotenv never
overrides an existing environment variable and does not expand password contents.
TLS is required and strengthened to certificate/hostname verification, preserving
other settings such as channel binding. The loader uses certifi's CA bundle unless
an explicit URL/environment CA setting is configured. Errors printed by the CLI omit raw exceptions, URLs,
connection details and source values. A lost connection around commit can leave
the result uncertain: the safe recovery is read-only verification, not deleting
records or assuming rollback occurred.

## Initial offline evidence

| Check | Actual result |
| --- | --- |
| Focused Phase 6 suite | 22 tests passed in 13.533 seconds |
| Full suite after final implementation edits | 82 tests passed in 48.425 seconds |
| Existing cleaning command | Passed; identical outputs reused |
| Loader `--offline` | Passed, five expected source counts |
| Loader `--verify-only` without credentials | Safe stop before connection |
| PK/UQ/FK and source CHECK compatibility | Passed |
| Product/nutrition identity | Matching 1,987 barcode sets, reciprocal FK checks passed |
| Leading-zero identifiers | All 83 preserved, including `00038317` |
| Category overlaps | 13 with two memberships; 1,974 with one |
| Missing nutrient conversion | Python `None` verified; actual SQL NULL storage pending live load |
| Complete content comparison | Mocked success and same-count changed-content rejection passed |
| Rerun behavior | Mocked initial load followed by identical rerun inserted no duplicates |
| Rollback | Mocked insertion, post-insert validation and commit failures restored empty state |
| Schema drift | Mocked table/column/key/CHECK/FK timing/action/unvalidated changes rejected |
| Connection safety | Missing/malformed/placeholder/insecure URLs rejected; sanitized errors passed |
| Dependency consistency | `pip check`: no broken requirements |
| Diff and text hygiene | `git diff --check` and new-file whitespace checks passed; final diff/status reviewed |
| Data preservation | All 54 data files and 2 notebooks unchanged |

Missing numeric nutrient counts match the Phase 3/5 sources:

| Nutrient | Source blanks / prepared SQL NULL parameters |
| --- | ---: |
| energy_kcal | 42 |
| energy_kj | 55 |
| protein_g | 43 |
| carbohydrates_g | 45 |
| sugars_g | 50 |
| fat_g | 41 |
| saturated_fat_g | 54 |
| fiber_g | 351 |
| salt_g | 67 |

Before/after file path sets, SHA-256 hashes, sizes and nanosecond modification
times match for all 56 protected files. The five cleaned hashes remain:

| CSV | SHA-256 |
| --- | --- |
| brands | `fdc10c0761c5ad7563784cb6fa6ce290c17c510f1da74adff88c23c9f0e5cbde` |
| categories | `e411db0b835028ad5a46b3e96f703239eee48a625b3937c5269402323eac7d04` |
| products | `9bf2bb50247d0c376efea908a3ab5cc35a5a47dd9179e9bc092d3e943127c540` |
| product_categories | `d10e12fb8dc6c9be4f10cc367623f14e7766cbcfdded3a2282da47e0a75e4dea` |
| nutrition | `2ce5887ab59f9f6a69a6310366092b8fd51c0a9fad68a1fd525471ca81f35ff3` |

## Reproduction reference

The following is a reproduction reference, not an outstanding task. The live
sequence has already succeeded; it was not repeated for this documentation update.
From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.clean_transform
.\.venv\Scripts\python.exe -m src.load_postgres --offline
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
# Configure DATABASE_URL privately, then inspect without writing:
.\.venv\Scripts\python.exe -m src.load_postgres --verify-only
# Only after explicit live-load approval:
.\.venv\Scripts\python.exe -m src.load_postgres --load
.\.venv\Scripts\python.exe -m src.load_postgres --verify-only
.\.venv\Scripts\python.exe -m src.load_postgres --load
```

README provides fresh-environment and fresh-database schema creation commands.
Do not rerun schema creation on the already-created Neon tables. The live checks
are intentionally separate from unit-test discovery; tests never use real
credentials, even when a local URL is present.

No Phase 6 loading or verification work remains pending on the supplied evidence.
Live success is documented from the owner's results; this update did not perform
an independent fresh database audit. Rollback regression tests remain mocked, with
the earlier live zero-row check documenting the failed attempt's preserved state.
The loader, tests, schema, dependencies and datasets were left unchanged during
this documentation update. Phase 7 has not been started.

No files were committed or pushed. Work stops at Phase 6.
