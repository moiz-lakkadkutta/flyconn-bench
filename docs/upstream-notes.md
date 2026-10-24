# Notes for flyconn (API friction found while building flyconn-bench)

Collected here because sessions must not edit the flyconn repo. Each item names what we did
instead. Observed with flyconn 0.4.0 from PyPI, 2026-10-24.

1. **`Store` cannot write query results to a file.** `Store.query` returns a pandas DataFrame,
   which for MaleCNS edges (25.6M rows) means materialising everything in memory. flyconn-bench
   opens its own DuckDB connection over the files in `Store.root` and uses `COPY ... TO`.
   *Suggestion:* `Store.copy_to(sql, path)` or a public `Store.connection`.
2. **`Store.tables` ignores `nt_probs.parquet`.** Stores built at `--level nt-probs` contain an
   `nt_probs.parquet` (seen in `google-fly/.cache/flyconn/store/malecns/1.0/`), but `_TABLES` is
   `("neurons", "edges", "edges_roi")`. flyconn-bench exports every `*.parquet` in the store
   folder instead. *Suggestion:* list it in `_TABLES` or document that it is internal.
3. **The store's `provenance.json` has no git SHA of the flyconn that built it**, only
   `flyconn_version`. Two stores built by different commits of the same version cannot be told
   apart. *Suggestion:* add `run_environment()` (it already has `git_sha`/`git_dirty`) to
   `write_provenance`.
4. **`flyconn.provenance.git_sha()` is `None` for an installed release**, which is expected but
   means the card says "installed release". Fine; noted so nobody reads it as a bug.
5. **No public "store schema version".** flyconn-bench pins `flyconn>=0.4,<0.5` and trusts the
   column set. *Suggestion:* a `schema_version` key in `provenance.json`.
6. **Two caches with different builds.** `~/.cache/flyconn/store/malecns/1.0` (flyconn 0.3.0,
   level `weights`, `nt_p_*` all null) and `google-fly/.cache/flyconn/store/malecns/1.0`
   (flyconn 0.0.1, level `nt-probs`). Nothing in flyconn warns that a store is older than the
   installed converter. *Suggestion:* `flyconn data info` could compare `converter_version` and
   `flyconn_version` with the installed package.
7. **Writing a test store needs `flyconn.data.convert.common`** (`write_parquet`,
   `write_provenance`), which is not documented as public. flyconn-bench's fixture uses it like
   flyconn's own tests do. *Suggestion:* `flyconn.testing.write_synthetic_store(path, ...)`.
