# FoodLens public data snapshot

This directory contains the 45 saved inputs needed to reproduce FoodLens offline.
Its paths mirror `data/`. Run `py -3.12 scripts/prepare_repro_data.py --verify`
to check the [SHA-256 manifest](MANIFEST.json), then use `--install` in a fresh
clone to copy the checked files into the ignored `data/` workspace. Installation
will not overwrite a differing file.

## Source, attribution and reuse

**Source: [Open Food Facts](https://world.openfoodfacts.org/).** The product
records came from its `api/v2/search` endpoint. Open Food Facts states that
its database is available under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1.0/),
subject to attribution and share-alike conditions; see its [API reuse guidance](https://support.openfoodfacts.org/help/en-gb/12-api-data-reuse/94-are-there-conditions-to-use-the-api)
and [terms of use](https://world.openfoodfacts.org/terms-of-use).

The FoodLens data snapshot, including its processed and cleaned database
derivatives, is made available under ODbL 1.0. Preserve this source and license
notice when redistributing it. Publicly used adapted databases must be shared
under ODbL or a permitted compatible license, with the adapted database
available to recipients. The license and source must remain clear in work
produced from the data. No product photographs are included. This notice applies
to the data in `repro_data/`; it does not assign a license to the project's code,
notebooks, report prose or figures.

## Provenance and contents

Four category queries requested `code`, `product_name`, `brands`,
`categories_tags`, `nutriments`, `nutriscore_grade` and `nova_group`, with
`page_size=100`. The categories were breakfast cereals, yogurts, biscuits and
cereal bars. Each extraction preserves five pages, its query configuration,
checkpoint, manifest and barcode audit. Nineteen API pages were saved on
9 October 2026 UTC. The first breakfast-cereals page was imported from an
earlier 100-record local snapshot; its original extraction time and complete
HTTP response envelope were not preserved. The four per-category CSVs contain
500 rows each. The combined CSV contains 1,987 unique products from 2,000
category records. Five cleaned CSVs contain the relational load inputs.

The snapshot was copied from the already redacted academic submission copy.
Only request `user_agent` contact values and six local absolute metadata paths
were sanitized further for publication. The six path values now refer to
repository-relative processed CSVs or state that a private backup was omitted.
All product values, barcode strings, CSV bytes, response objects and saved
response hashes remain unchanged. The original ignored `data/` files, including
backups and extraction state, are separate and were not edited. `submission/`
and its existing archive remain separate academic artifacts.

These are fixed historical snapshots. A new API request may return different
records. Product fields are community-supplied observations, not verified
nutritional advice. The manifest checks accidental changes to these published
bytes; it is not a signature or proof of source authenticity.
