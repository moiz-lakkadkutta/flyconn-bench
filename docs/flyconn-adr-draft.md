# ADR-00XX (draft for flyconn): Publish Hugging Face mirrors from a separate `flyconn-bench` repo

Status: Draft (2026-10-24). Written in flyconn-bench because sessions must not edit the flyconn
repo; copy into `flyconn/docs/adr/` with the next free number once the owner approves.

## Context

The only fly connectomes on the Hugging Face Hub are unofficial re-uploads with unlabelled
versions, and they still get a few hundred downloads each (HF API, read 2026-10-24; see
flyconn-bench `PLAN.md`). flyconn already produces harmonized, checksummed Parquet stores with
`provenance.json`, which is most of what a good dataset repo needs. The owner wants ML users to
reach the data where they already are, and later to build the FlyGraphBench benchmark on it.

Options for where the export and publishing code lives:

1. Inside flyconn (`flyconn hf export`): one package, but it adds `huggingface_hub` and
   `datasets` (large dependency trees) to a toolkit whose core is offline and laptop-sized, and it
   couples flyconn releases to Hub publishing.
2. A separate package `flyconn-bench` that depends on `flyconn>=0.4,<0.5`: keeps flyconn lean and
   gives the benchmark (PyG loaders, splits, metrics, baselines) a home with its own release cycle.
3. Reuse an existing HF exporter: none exists for connectomes. Generic tools
   (`huggingface_hub.upload_folder`, `datasets` Parquet configs) are reused for the mechanics.

## Decision

- **Option 2.** flyconn-bench owns `flyconn-bench export <ref>`, which turns a flyconn store into
  an HF dataset folder: byte-for-byte copies of the store's Parquet tables, optional slices
  (`min_weight=N`, type-aggregated), `checksums.sha256`, `provenance.json` (store record plus
  export record) and a generated `README.md` dataset card.
- **The flyconn store is the source of truth; the HF repo is a mirror.** The card records the
  registry entry (licence, citations, homepage), the store provenance (converter, flyconn version
  that built it, input SHA-256s, edge thresholds) and the export run (flyconn-bench version and
  git SHA, package versions).
- **Reuse:** `huggingface_hub` for cards and (later) uploads, `datasets` only to verify the
  round trip, DuckDB for slices. No new file formats.
- **One Hub repo per `dataset@version`.** Slices are extra configs in the same repo, not
  separate repos.
- **Licence gate.** Nothing is uploaded unless `docs/licences.md` in flyconn-bench marks the
  dataset cleared, with source URLs, and the owner approves the upload.

## Consequences

- flyconn stays free of Hub dependencies; flyconn-bench must track flyconn's store schema
  (pinned to `<0.5`) and has to be updated when a converter version changes.
- flyconn-bench reads store internals that flyconn does not expose as API (the Parquet files
  in `Store.root`, `provenance.json` keys); see flyconn-bench `docs/upstream-notes.md`.
- Cards repeat flyconn caveats; when flyconn's `docs/caveats.md` changes, the per-dataset caveat
  text in `flyconn_bench/card.py` must be reviewed.

## Alternatives considered

- Option 1 (inside flyconn): rejected for dependency weight and release coupling.
- Uploading the original Feather files instead of flyconn's harmonized tables: rejected; that is
  what the existing unofficial mirrors do, and the harmonized schema is the point.
