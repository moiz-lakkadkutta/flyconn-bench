"""Export a flyconn store to a Hugging Face-ready folder.

Layout of an export::

    README.md            dataset card (YAML front matter + Markdown)
    data/<config>.parquet
    checksums.sha256     ``sha256sum``-compatible list of the data files
    provenance.json      {"store": <store provenance.json>, "export": <this run>}

Full tables are byte-for-byte copies of the store's Parquet files, so their
SHA-256 equals the store's. Slices are written by DuckDB with a fixed sort
order so that re-running the export gives the same rows.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import resource
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq
from flyconn.data.registry import DatasetSpec
from flyconn.data.store import Store
from flyconn.provenance import run_environment

import flyconn_bench
from flyconn_bench.card import missing_card_fields, render_card
from flyconn_bench.slices import MinWeight, Slice, Types

DATA_DIR = "data"
CHECKSUMS = "checksums.sha256"
PROVENANCE = "provenance.json"
CARD = "README.md"

TABLE_DESCRIPTIONS: dict[str, str] = {
    "neurons": "One row per neuron: harmonized annotations and predicted transmitter.",
    "edges": "Neuron-to-neuron edges; `weight` is the synapse count of the pair.",
    "edges_roi": "Edges split by ROI / neuropil (one row per pair and ROI).",
    "nt_probs": "Per-neuron transmitter probabilities aggregated from per-synapse predictions.",
    "cell_types": "One row per `cell_type`: neuron count and most common `super_class`.",
    "type_edges": "Type-level graph: synapses summed over all neuron pairs of each type pair.",
}


@dataclass(frozen=True)
class ExportedTable:
    config: str
    path: str
    rows: int
    bytes: int
    sha256: str
    seconds: float
    description: str
    source: str
    """``"copy"`` for a byte copy of the store file, else the slice that produced it."""


@dataclass
class ExportResult:
    out: Path
    ref: str
    repo_id: str
    tables: list[ExportedTable] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)

    def table(self, config: str) -> ExportedTable:
        for t in self.tables:
            if t.config == config:
                return t
        msg = f"export has no table {config!r}"
        raise KeyError(msg)


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def default_repo_id(spec: DatasetSpec) -> str:
    return f"flyconn/{spec.name}-{spec.version}"


def export_store(
    store: Store,
    out: Path,
    slices: Sequence[Slice] = (),
    *,
    repo_id: str | None = None,
    force: bool = False,
    memory_limit: str = "2GB",
    threads: int = 2,
) -> ExportResult:
    """Write ``store`` (plus ``slices``) to ``out`` as an HF dataset folder.

    ``memory_limit`` and ``threads`` cap DuckDB while it writes slices; the full
    tables are plain file copies and need no memory.

    Raises:
        FileExistsError: if ``out`` is non-empty and not a previous export (or
            ``force`` is false).
    """
    spec = store.spec
    out = Path(out)
    _prepare_out(out, force=force)
    t_start = time.perf_counter()
    result = ExportResult(out=out, ref=store.ref, repo_id=repo_id or default_repo_id(spec))
    (out / DATA_DIR).mkdir(parents=True)

    for src in sorted(store.root.glob("*.parquet")):
        t0 = time.perf_counter()
        dest = out / DATA_DIR / src.name
        shutil.copyfile(src, dest)
        result.tables.append(_describe(out, dest, src.stem, time.perf_counter() - t0, "copy"))

    slice_info: dict[str, Any] = {}
    if slices:
        con = _duckdb(store.root, out, memory_limit=memory_limit, threads=threads)
        try:
            for s in dict.fromkeys(slices):  # de-duplicate, keep order
                if isinstance(s, MinWeight):
                    slice_info[s.suffix] = _min_weight(con, store, out, s, result)
                else:
                    slice_info["types"] = _types(con, out, s, result)
        finally:
            con.close()
            shutil.rmtree(out / ".duckdb_tmp", ignore_errors=True)

    result.info = {
        "flyconn_bench_version": flyconn_bench.__version__,
        "flyconn_bench_git_sha": _own_git_sha(),
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "environment": run_environment(("flyconn", "duckdb", "pyarrow", "huggingface_hub")),
        "store_path": str(store.root),
        "registry_ref": spec.ref,
        "repo_id": result.repo_id,
        "slices": slice_info,
        "duckdb": {"memory_limit": memory_limit, "threads": threads},
        "seconds_total": round(time.perf_counter() - t_start, 2),
        "peak_rss_mb": _peak_rss_mb(),
        "tables": [asdict(t) for t in result.tables],
    }
    _write_checksums(out, result.tables)
    record = {"store": store.provenance, "export": result.info}
    (out / PROVENANCE).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    card = render_card(spec, store.provenance, result)
    missing = missing_card_fields(card, result)
    if missing:
        msg = f"generated card for {store.ref} is incomplete: {missing}"
        raise RuntimeError(msg)
    (out / CARD).write_text(card)
    return result


def _prepare_out(out: Path, *, force: bool) -> None:
    if not out.exists() or not any(out.iterdir()):
        out.mkdir(parents=True, exist_ok=True)
        return
    previous = (out / PROVENANCE).exists() and (out / CARD).exists()
    if not (force and previous):
        why = "pass force=True / --force to replace it" if previous else "it is not an export"
        msg = f"{out} is not empty; {why}"
        raise FileExistsError(msg)
    shutil.rmtree(out)
    out.mkdir(parents=True)


def _duckdb(root: Path, out: Path, *, memory_limit: str, threads: int) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    tmp = out / ".duckdb_tmp"
    tmp.mkdir()
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute(f"SET threads = {int(threads)}")
    con.execute(f"SET temp_directory = '{_sql_path(tmp)}'")
    con.execute("SET preserve_insertion_order = true")
    for t in ("neurons", "edges", "edges_roi"):
        path = root / f"{t}.parquet"
        if path.exists():
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{_sql_path(path)}')")
    return con


def _copy_to(con: duckdb.DuckDBPyConnection, sql: str, dest: Path) -> None:
    con.execute(
        f"COPY ({sql}) TO '{_sql_path(dest)}' "
        "(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 1000000)"
    )


def _min_weight(
    con: duckdb.DuckDBPyConnection, store: Store, out: Path, s: MinWeight, result: ExportResult
) -> dict[str, Any]:
    n = int(s.n)
    t0 = time.perf_counter()
    dest = out / DATA_DIR / f"edges_{s.suffix}.parquet"
    _copy_to(con, f"SELECT * FROM edges WHERE weight >= {n} ORDER BY pre, post", dest)
    result.tables.append(
        _describe(out, dest, dest.stem, time.perf_counter() - t0, f"min_weight={n}")
    )
    if "edges_roi" in store.tables:
        # The threshold applies to the pair total, not to each ROI row (as in FlyWire's export).
        t0 = time.perf_counter()
        dest = out / DATA_DIR / f"edges_roi_{s.suffix}.parquet"
        sql = (
            "SELECT r.* FROM edges_roi r SEMI JOIN "
            f"(SELECT pre, post FROM edges WHERE weight >= {n}) e "
            "ON r.pre = e.pre AND r.post = e.post ORDER BY r.pre, r.post, r.roi"
        )
        _copy_to(con, sql, dest)
        result.tables.append(
            _describe(out, dest, dest.stem, time.perf_counter() - t0, f"min_weight={n}")
        )
    row = con.execute(
        f"SELECT count(*), coalesce(sum(weight), 0) FROM edges WHERE weight >= {n}"
    ).fetchone()
    total = con.execute("SELECT count(*), coalesce(sum(weight), 0) FROM edges").fetchone()
    assert row is not None and total is not None
    return {
        "min_weight": n,
        "applies_to": "pair total synapse count",
        "edges_kept": int(row[0]),
        "edges_total": int(total[0]),
        "weight_kept": int(row[1]),
        "weight_total": int(total[1]),
    }


def _types(
    con: duckdb.DuckDBPyConnection, out: Path, s: Types, result: ExportResult
) -> dict[str, Any]:
    del s  # no parameters yet
    con.execute(
        "CREATE TEMP TABLE typed AS SELECT neuron_id, cell_type, super_class FROM neurons "
        "WHERE cell_type IS NOT NULL AND cell_type <> ''"
    )
    con.execute(
        "CREATE TEMP TABLE type_sizes AS "
        "WITH sc AS (SELECT cell_type, super_class, count(*) AS c FROM typed GROUP BY ALL), "
        "ranked AS (SELECT *, row_number() OVER "
        "(PARTITION BY cell_type ORDER BY c DESC, super_class NULLS LAST) AS r FROM sc) "
        "SELECT t.cell_type, t.n_neurons, ranked.super_class FROM "
        "(SELECT cell_type, count(*) AS n_neurons FROM typed GROUP BY cell_type) t "
        "JOIN ranked ON ranked.cell_type = t.cell_type AND ranked.r = 1"
    )
    t0 = time.perf_counter()
    dest = out / DATA_DIR / "cell_types.parquet"
    _copy_to(con, "SELECT * FROM type_sizes ORDER BY cell_type", dest)
    result.tables.append(_describe(out, dest, "cell_types", time.perf_counter() - t0, "types"))

    t0 = time.perf_counter()
    dest = out / DATA_DIR / "type_edges.parquet"
    sql = (
        "WITH agg AS (SELECT a.cell_type AS pre_type, b.cell_type AS post_type, "
        "CAST(sum(e.weight) AS BIGINT) AS weight, count(*) AS n_pairs FROM edges e "
        "JOIN typed a ON e.pre = a.neuron_id JOIN typed b ON e.post = b.neuron_id "
        "GROUP BY ALL) "
        "SELECT agg.pre_type, agg.post_type, agg.weight, agg.n_pairs, "
        "sp.n_neurons AS n_pre, so.n_neurons AS n_post, "
        "agg.weight / so.n_neurons AS weight_per_post FROM agg "
        "JOIN type_sizes sp ON sp.cell_type = agg.pre_type "
        "JOIN type_sizes so ON so.cell_type = agg.post_type "
        "ORDER BY agg.pre_type, agg.post_type"
    )
    _copy_to(con, sql, dest)
    result.tables.append(_describe(out, dest, "type_edges", time.perf_counter() - t0, "types"))

    neurons = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE cell_type IS NULL OR cell_type = '') FROM neurons"
    ).fetchone()
    weights = con.execute(
        "SELECT coalesce(sum(e.weight), 0) FROM edges e "
        "JOIN typed a ON e.pre = a.neuron_id JOIN typed b ON e.post = b.neuron_id"
    ).fetchone()
    total = con.execute("SELECT coalesce(sum(weight), 0) FROM edges").fetchone()
    assert neurons is not None and weights is not None and total is not None
    return {
        "group_by": "cell_type",
        "neurons_total": int(neurons[0]),
        "neurons_untyped_excluded": int(neurons[1]),
        "weight_between_typed": int(weights[0]),
        "weight_total": int(total[0]),
        "edge_min_weight": 1,
    }


def _describe(out: Path, path: Path, config: str, seconds: float, source: str) -> ExportedTable:
    base = re.sub(r"_min\d+$", "", config)
    desc = TABLE_DESCRIPTIONS.get(base, "Table copied from the flyconn store.")
    if source.startswith("min_weight="):
        desc = f"{desc} Only pairs with at least {source.split('=')[1]} synapses."
    return ExportedTable(
        config=config,
        path=path.relative_to(out).as_posix(),
        rows=pq.ParquetFile(path).metadata.num_rows,
        bytes=path.stat().st_size,
        sha256=sha256_file(path),
        seconds=round(seconds, 2),
        description=desc,
        source=source,
    )


def _write_checksums(out: Path, tables: Sequence[ExportedTable]) -> None:
    lines = [f"{t.sha256}  {t.path}" for t in tables]
    (out / CHECKSUMS).write_text("\n".join(lines) + "\n")


def read_checksums(out: Path) -> dict[str, str]:
    """Map ``data/<file>`` to SHA-256 from an export's ``checksums.sha256``."""
    result: dict[str, str] = {}
    for line in (Path(out) / CHECKSUMS).read_text().splitlines():
        if line.strip():
            digest, _, path = line.partition("  ")
            result[path] = digest
    return result


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _own_git_sha() -> str | None:
    """HEAD of this repo when running from its source tree, else None."""
    pkg = Path(flyconn_bench.__file__).resolve().parent
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=pkg,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        if Path(top, "src", "flyconn_bench").resolve() != pkg:
            return None
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=top,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _peak_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is bytes on macOS and kilobytes on Linux.
    return round(rss / (1 << 20) if sys.platform == "darwin" else rss / 1024, 1)
