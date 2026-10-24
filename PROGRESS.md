# Progress

Read `PLAN.md` for scope. Newest entry first.

## 2026-10-24: M0 basic implementation (branch `m0-export`, local commits only)

Done:
- Scaffold: uv project, `src/flyconn_bench/`, Apache-2.0, ruff + strict pyright + pytest,
  `scripts/check.sh` (same gate as flyconn), `.github/workflows/ci.yml` (not pushed; no remote).
  Depends on `flyconn>=0.4,<0.5`, `duckdb`, `pyarrow`, `huggingface_hub`; `datasets` is an
  optional extra and a dev dependency (only used by `verify`). Locked: datasets 5.1.0,
  huggingface_hub 2.3.0, duckdb 2.0.0, pyarrow 26.0.0.
- `flyconn-bench export <ref> --out DIR [--slice min_weight=N] [--slice types] [--store PATH]`
  (`src/flyconn_bench/export.py`): byte copies of the store tables, DuckDB-written slices,
  `checksums.sha256`, `provenance.json` (store + export records), generated card
  (`card.py`). Export fails if the card is missing a required field (`missing_card_fields`).
  Refuses to write into a non-empty folder unless it is a previous export and `--force` is given.
- `flyconn-bench verify DIR` (`verify.py`): SHA-256 and row counts against the records, then a
  `datasets.load_dataset("parquet", ...)` round trip (rows, column names and types; `--deep`
  compares contents).
- 13 offline tests on a synthetic store registered as `malecns@1.0` (`tests/conftest.py`).
- Local dry run on cached MaleCNS v1.0 and BANC v888: export and verify pass; numbers in
  `README.md` ("Local dry run"). Exports are in `exports/` (gitignored).
- Docs: `docs/licences.md` (upload gate), `docs/flyconn-adr-draft.md` (ADR to copy into flyconn
  once the owner approves), `docs/upstream-notes.md` (flyconn API friction).

Licences (`docs/licences.md`, read 2026-10-24): MaleCNS v1.0 and BANC v888 **cleared**
(CC BY 4.0); FlyWire **blocked** (Zenodo says CC BY 4.0, flywire.ai says CC BY-NC 4.0);
hemibrain and MANC **review** (CC BY 4.0 at source, open ambiguities listed).

Decisions taken in this session (owner can override):
- Snapshots first; the benchmark (M2+) later (owner, 2026-10-24).
- The snapshot edge table is flyconn's neuron-to-neuron `edges` (MaleCNS: 25,582,938 edges of
  151,856,684 raw); fragments are not exported. The card says so and gives the raw totals.
- Slices live in the same Hub repo as extra configs (`edges_min5`, `cell_types`, `type_edges`).
- Default Hub repo id is `flyconn/<name>-<version>` (e.g. `flyconn/malecns-1.0`); PLAN.md wrote
  `flyconn/malecns-v1.0`. Pick one before the first upload (`--repo-id` overrides).

Next:
1. Owner decisions: confirm the repo naming; approve creating the HF org `flyconn`; approve the
   first upload (MaleCNS v1.0 and BANC v888 only, per `docs/licences.md`).
2. Rebuild the MaleCNS and BANC stores with flyconn 0.4.0 before uploading (the cached ones were
   built by 0.3.0 and 0.1.0). Decide whether MaleCNS ships `nt_probs` (level `nt-probs`, needs the
   2.65 GB tbar file).
3. Add an `upload` command (`huggingface_hub.upload_folder`) that refuses unless the dataset is
   marked cleared in `docs/licences.md` (make that table machine-readable first), then a
   `verify --hub` that downloads and re-checks checksums.
4. Push the repo to GitHub (owner's yes) so CI runs; copy the ADR draft into flyconn.
5. Then FlyWire 783 (licence check first), MANC, hemibrain; then M2 (task 1).
