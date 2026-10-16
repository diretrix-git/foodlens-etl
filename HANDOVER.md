# FoodLens handover

Newest entry: 16 October 2026. Prepend future dated entries and prune superseded detail; keep this a current-state record.

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
