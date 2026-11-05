# FoodLens handover

Newest entry: 5 November 2026. Prepend future dated entries and prune superseded detail; keep this a current-state record.

## 5 November 2026 - Source-backed documentation review

### Done
- Added a concise recruiter entry and `docs/source-backed-claims.md` with pinned source/test references, ownership boundaries and public-disclosure limits.
- Clarified that snapshot counts and the 16 October validation record are historical evidence or current source expectations, not checks repeated in this review.
- Distinguished per-file atomic publication from a multi-file transaction, and the fixed-snapshot PostgreSQL initial loader from a general incremental system.

### In progress
- Documentation changes are prepared for review. Branch publication and merge status must be checked separately.

### Broken
- Runtime and test status were not reverified. This documentation-only review ran no application, pipeline, tests, live API or database operations.

### Next
- Review the pinned claims and documentation diff. Reproduce only in a disposable clone using the existing guide if fresh execution evidence is needed.

### Do not touch
- Preserve ignored `data/` originals and metadata, `repro_data/` bytes and manifests, notebooks, SQL, saved reports, `submission/` and the existing archive.
- Keep credentials and original request contact metadata out of public materials. Do not regenerate outputs or run live API/database operations as part of this documentation review.

## 16 October 2026 — Public reproducibility release

### Done
- Added a 45-file `repro_data/` snapshot from the sanitized submission copies, a SHA-256 manifest, and an Open Food Facts ODbL/provenance notice. Forty-two request `user_agent` values and six local absolute metadata paths differ from the originals; all product values, CSVs, response objects and response hashes remain unchanged.
- Added `scripts/prepare_repro_data.py` with read-only `--verify` and conflict-refusing `--install`; updated root, Copilot, README and academic archive guidance.
- In a fresh isolated local clone with a new Python 3.12 environment and no original ignored data, `.env` or existing virtual environment: 92 offline tests passed (89 existing plus three installer tests); all 328 saved-result cells, transformation, offline loader, schema checks, 20 response hashes, and both notebook executors passed. The EDA and analysis executors ran from both supported directories. All 57 local Markdown links resolved.
- The existing 97-entry academic submission manifest, archive SHA-256 sidecar and ZIP integrity still pass. Original `data/` files were unchanged when installation correctly refused conflicting originals.
- Final publication review checked all 45 public file hashes and 20 response hashes, all 92 offline tests, 328 saved-result cells, the exact candidate-file privacy scan, Git whitespace, and the Open Food Facts data notice. Use Git history and `origin/main` to confirm the release commit and remote status.
- Root `.gitattributes` preserves exact `repro_data/` bytes across Windows Git line-ending conversion, recognizes existing CRLF as line endings, and exempts meaningful trailing spaces inside quoted public CSV fields from whitespace checks. The manifest hashes require those original bytes.

### In progress
- No ETL or documentation implementation is in progress. Check Git status and `origin/main` for the current publication state.

### Broken
- No known offline reproducibility defect. Live API and database operations were not performed.

### Next
- Complete final report cover placeholders and check the institution's assignment and upload rules if preparing an academic resubmission. The existing archive predates these changes and must not be silently rebuilt.

### Do not touch
- Preserve ignored `data/` originals, request metadata, backups, lock/cooldown state, `submission/` and its archive, notebooks, SQL, reports and academic deliverables.
- Do not run live API or database operations, replace differing local data, or silently regenerate existing outputs. Follow root `AGENTS.md`.
