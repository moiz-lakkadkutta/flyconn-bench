"""Check an export: checksums, and a round trip through ``datasets.load_dataset``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from flyconn_bench.export import PROVENANCE, read_checksums, sha256_file


@dataclass
class VerifyReport:
    checked: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_export(
    out: Path, *, load: bool = True, deep: bool = False, cache_dir: Path | None = None
) -> VerifyReport:
    """Verify ``out``.

    Always recomputes every SHA-256 against ``checksums.sha256`` and the row
    counts recorded in ``provenance.json``. With ``load``, also reads each table
    through ``datasets.load_dataset("parquet", ...)`` and compares rows and
    columns; with ``deep``, compares the full contents too (small exports only).
    """
    out = Path(out)
    report = VerifyReport()
    record: dict[str, Any] = json.loads((out / PROVENANCE).read_text())
    tables: list[dict[str, Any]] = record["export"]["tables"]
    checksums = read_checksums(out)
    if sorted(checksums) != sorted(t["path"] for t in tables):
        report.problems.append("checksums.sha256 and provenance.json list different files")
    for t in tables:
        path = out / t["path"]
        digest = sha256_file(path)
        if digest != checksums.get(t["path"]) or digest != t["sha256"]:
            report.problems.append(f"{t['path']}: SHA-256 mismatch ({digest})")
        rows = pq.ParquetFile(path).metadata.num_rows
        if rows != t["rows"]:
            report.problems.append(f"{t['path']}: {rows} rows, provenance says {t['rows']}")
        report.checked.append(f"{t['path']}: sha256 ok, {rows:,} rows")
    if load:
        _round_trip(out, tables, report, deep=deep, cache_dir=cache_dir)
    return report


def _round_trip(
    out: Path,
    tables: list[dict[str, Any]],
    report: VerifyReport,
    *,
    deep: bool,
    cache_dir: Path | None,
) -> None:
    from datasets import load_dataset  # optional dependency

    for t in tables:
        path = out / t["path"]
        ds = load_dataset(
            "parquet",
            data_files=str(path),
            split="train",
            cache_dir=str(cache_dir) if cache_dir else None,
        )
        original = pq.read_schema(path)
        if ds.num_rows != t["rows"]:
            report.problems.append(f"{t['path']}: datasets loaded {ds.num_rows} rows")
        loaded = ds.data.table
        # datasets drops NOT NULL flags (DuckDB sets them), so compare names and types only.
        if [(f.name, f.type) for f in loaded.schema] != [(f.name, f.type) for f in original]:
            report.problems.append(f"{t['path']}: datasets columns or types differ")
        elif deep and not loaded.equals(pq.read_table(path).cast(loaded.schema)):
            report.problems.append(f"{t['path']}: datasets contents differ from the Parquet file")
        report.checked.append(f"{t['path']}: load_dataset ok ({ds.num_rows:,} rows)")
