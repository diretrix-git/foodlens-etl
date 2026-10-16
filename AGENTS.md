# FoodLens repository instructions

At the start of every session, read `HANDOVER.md` first for the current state. Then inspect the files relevant to the task. `README.md` is the project entry point; `SUBMISSION_README.md` contains reproduction steps; the dated reports preserve validation evidence.

At the end of every session where file changes are allowed, update `HANDOVER.md` last. Prepend a concise dated entry with the fixed sections **Done**, **In progress**, **Broken**, **Next**, and **Do not touch**. Keep current facts, prune superseded detail, and distinguish historical results from checks performed in the current session. An explicit read-only or no-write request prohibits this update.

Preserve raw JSON, saved API responses, manifests, checkpoints, backups, original nutritional values, and existing processed or cleaned outputs. Do not silently regenerate them. Keep barcode strings exact, including leading zeroes, and do not treat missing nutrients as errors without evidence.

Use offline data and mocked connections for routine work. Make live Open Food Facts requests or database changes only when the task explicitly authorizes them. Never expose credentials or contact addresses. Do not commit, push, release, or alter Git history without explicit authorization.

For implementation changes, inspect the relevant code and tests, use Python 3.12, run focused offline checks, and report what actually ran. Keep historical phase reports as dated evidence; record current status in `HANDOVER.md`.
