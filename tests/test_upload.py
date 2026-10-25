from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from flyconn.data.registry import get_dataset
from flyconn.data.store import Store
from typer.testing import CliRunner

from flyconn_bench.cli import app
from flyconn_bench.export import export_store
from flyconn_bench.licences import STATUSES, licence_entries, licence_entry
from flyconn_bench.slices import MinWeight
from flyconn_bench.upload import plan_upload, upload

from .conftest import write_store

DOCS = Path(__file__).resolve().parents[1] / "docs" / "licences.md"


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_repo(self, repo_id: str, **kwargs: Any) -> None:
        self.calls.append(("create_repo", {"repo_id": repo_id, **kwargs}))

    def upload_folder(self, **kwargs: Any) -> str:
        self.calls.append(("upload_folder", kwargs))
        return "commit"


def _export(tmp_path: Path, dataset: str, version: str) -> Path:
    s = Store(write_store(tmp_path / f"store-{dataset}", dataset, version))
    try:
        export_store(s, tmp_path / f"export-{dataset}-{version}", [MinWeight(5)])
    finally:
        s.close()
    return tmp_path / f"export-{dataset}-{version}"


def test_licence_table_matches_docs():
    rows = {
        m.group(1).strip(): m.group(0)
        for m in re.finditer(r"^\| ([^|]+) \|.*$", DOCS.read_text(), flags=re.MULTILINE)
    }
    entries = licence_entries()
    assert entries, "licences.yaml is empty"
    for ref, e in entries.items():
        assert e.status in STATUSES
        assert e.doc_name in rows, f"{ref}: no row {e.doc_name!r} in docs/licences.md"
        assert f"**{e.status}**" in rows[e.doc_name], f"{ref}: status differs from docs"
        assert e.sources, f"{ref}: no source URLs"
        get_dataset(ref)  # every gated ref exists in flyconn's registry


def test_cleared_export_is_ready(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    export_store(store, out, [MinWeight(5)])
    plan = plan_upload(out)
    assert plan.ok, plan.problems
    assert plan.repo_id == "flyconn/malecns-1.0"
    names = [rel for rel, _ in plan.files]
    assert "README.md" in names and "data/edges_min5.parquet" in names
    assert plan.total_bytes == sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    assert plan.commit_message.startswith("malecns@1.0 snapshot")


def test_blocked_dataset_is_refused(tmp_path: Path):
    entry = licence_entry("flywire@783")
    assert entry is not None and entry.status == "blocked"
    plan = plan_upload(_export(tmp_path, "flywire", "783"))
    assert any("'blocked'" in p for p in plan.problems)
    # flyconn's registry still says CC-BY-4.0 for FlyWire; the gate notices.
    assert any("registry says CC-BY-4.0" in p for p in plan.problems)
    with pytest.raises(RuntimeError, match="refusing"):
        upload(plan, FakeApi(), execute=True)


def test_unchecked_dataset_is_refused(tmp_path: Path):
    plan = plan_upload(_export(tmp_path, "flywire", "630"))
    assert any("not in the licence table" in p for p in plan.problems)


def test_tampered_or_extra_files_block(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    export_store(store, out)
    (out / "notes.txt").write_text("scratch")
    edges = out / "data" / "edges.parquet"
    edges.write_bytes(edges.read_bytes() + b"x")
    problems = plan_upload(out).problems
    assert any("unexpected files" in p for p in problems)
    assert any("SHA-256 mismatch" in p for p in problems)


def test_upload_only_runs_when_executed(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    export_store(store, out)
    plan = plan_upload(out, repo_id="someone/test")
    api = FakeApi()
    assert upload(plan, api) is None
    assert api.calls == []
    assert upload(plan, api, execute=True) == "commit"
    assert [c[0] for c in api.calls] == ["create_repo", "upload_folder"]
    assert api.calls[0][1] == {
        "repo_id": "someone/test",
        "repo_type": "dataset",
        "private": True,
        "exist_ok": True,
    }
    assert api.calls[1][1]["folder_path"] == str(out)
    assert api.calls[1][1]["repo_type"] == "dataset"


def test_cli_upload_is_a_dry_run(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    export_store(store, out)
    res = CliRunner().invoke(app, ["upload", str(out)])
    assert res.exit_code == 0, res.output
    assert "nothing was uploaded" in res.output
    assert "--execute" not in CliRunner().invoke(app, ["upload", "--help"]).output

    blocked = _export(tmp_path, "flywire", "783")
    res = CliRunner().invoke(app, ["upload", str(blocked)])
    assert res.exit_code == 1


def test_stale_store_build_is_refused(store: Store, tmp_path: Path):
    import json

    out = tmp_path / "export"
    export_store(store, out)
    prov = out / "provenance.json"
    record = json.loads(prov.read_text())
    record["store"]["flyconn_version"] = "0.3.0"
    prov.write_text(json.dumps(record))
    assert any("built by flyconn 0.3.0" in p for p in plan_upload(out).problems)
