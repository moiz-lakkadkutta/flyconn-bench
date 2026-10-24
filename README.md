# flyconn-bench

Hugging Face-ready snapshots of the harmonized Drosophila connectomes produced by
[flyconn](https://github.com/moiz-lakkadkutta/flyconn), and later the FlyGraphBench ML
benchmark (cross-animal splits, baselines, leaderboard). See `PLAN.md` for scope and milestones
and `PROGRESS.md` to resume.

Status: **M0 (local only).** Nothing has been uploaded; no Hub org or repo exists yet. Uploads
are gated by [`docs/licences.md`](docs/licences.md) and the owner's explicit approval.

## Install and check

```bash
uv sync --group dev
scripts/check.sh            # ruff, format, pyright (strict), offline unit tests
```

The unit tests run on flyconn's synthetic connectome (`flyconn.testing`) and never touch the
network.

## Export a store

```bash
flyconn data pull malecns@1.0 --level weights     # flyconn builds the store (once)
flyconn-bench export malecns@1.0 --out exports/malecns-1.0 \
    --slice min_weight=5 --slice types
flyconn-bench verify exports/malecns-1.0           # checksums + datasets.load_dataset round trip
```

An export folder holds `README.md` (the dataset card), `data/<config>.parquet`,
`checksums.sha256` and `provenance.json`. Full tables are byte-for-byte copies of the store files;
slices are written by DuckDB (capped by `--memory-limit`, default 2GB, and `--threads`, default 2)
in a fixed sort order, so re-running an export reproduces the same bytes.

- `--slice min_weight=N`: `edges_minN` keeps neuron pairs with at least N synapses in total;
  `edges_roi_minN` (when the store has per-ROI edges) keeps every ROI row of those pairs.
- `--slice types`: `cell_types` (neurons per type, most common `super_class`) and `type_edges`
  (synapses summed over all pairs of each type pair, `n_pairs`, `n_pre`, `n_post`,
  `weight_per_post`). Untyped neurons are left out; the card records how many.

## Local dry run (2026-10-24)

From `flyconn-bench export ... --slice min_weight=5 --slice types` and `flyconn-bench verify`
on an Apple-silicon Mac (macOS 26.2), flyconn 0.4.0, DuckDB 2.0.0, pyarrow 26.0.0, datasets 5.1.0,
with other sessions running. Rows, bytes and seconds come from each export's `provenance.json`;
peak memory is `/usr/bin/time -l` maximum resident set size.

| Table | MaleCNS v1.0 rows | MB | s | BANC v888 rows | MB | s |
|---|---:|---:|---:|---:|---:|---:|
| `neurons` (copy) | 166,700 | 4.4 | 0.00 | 155,858 | 2.7 | 0.00 |
| `edges` (copy) | 25,582,938 | 74.9 | 0.02 | 11,401,953 | 39.9 | 0.01 |
| `edges_min5` | 6,242,118 | 22.3 | 0.68 | 1,526,465 | 6.7 | 0.25 |
| `cell_types` | 11,751 | 0.04 | 0.00 | 11,489 | 0.04 | 0.00 |
| `type_edges` | 3,830,931 | 17.1 | 1.86 | 2,527,036 | 10.9 | 1.05 |
| **Export total** | 114 MB on disk | | 3.45 | 58 MB on disk | | 1.86 |

- Peak memory: MaleCNS export 1.37 GB, verify (load_dataset of all five tables) 2.49 GB;
  the `datasets` cache for the MaleCNS round trip took 1.5 GB on disk (deleted afterwards).
- `verify` passed for both: every SHA-256 matched `checksums.sha256`, and `load_dataset`
  returned the recorded row counts and column types. A second MaleCNS export gave byte-identical
  files.
- The stores used were the cached ones: MaleCNS built by flyconn 0.3.0 at level `weights` (so
  `nt_p_*` is empty: 0 of 166,700 neurons), BANC built by flyconn 0.1.0. Rebuild both with
  flyconn 0.4.0 before a real upload.

## Docs

- [`docs/licences.md`](docs/licences.md): redistribution terms per dataset (gates every upload).
- [`docs/flyconn-adr-draft.md`](docs/flyconn-adr-draft.md): ADR text for flyconn.
- [`docs/upstream-notes.md`](docs/upstream-notes.md): flyconn API friction.

## Licence

Code: Apache-2.0. Data in exports keep their creators' licences (stated on each card).
