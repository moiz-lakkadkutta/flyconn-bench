from __future__ import annotations

from pathlib import Path

import pytest
from flyconn.data.store import Store
from huggingface_hub import DatasetCard
from typer.testing import CliRunner

from flyconn_bench.card import REQUIRED_SECTIONS, missing_card_fields
from flyconn_bench.cli import app
from flyconn_bench.export import export_store
from flyconn_bench.slices import MinWeight, Types
from flyconn_bench.verify import verify_export


@pytest.fixture
def exported(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    return export_store(store, out, [MinWeight(5), Types()])


def test_card_has_every_required_field(exported):
    card = (exported.out / "README.md").read_text()
    assert missing_card_fields(card, exported) == []
    for section in REQUIRED_SECTIONS:
        assert section in card
    assert "Berg S" in card and "10.1016/j.cell.2026.08.015" in card  # registry citation
    assert "pair_min_synapses" in card and "minconf" in card  # thresholds from provenance
    assert "classifier predictions" in card
    assert "- `nt_p_*` (any class): 40 of 40" in card  # fill counts come from the data
    assert "- `cell_type`: 35 of 40" in card
    assert 'neurons = load_dataset("flyconn/malecns-1.0", "neurons"' in card


def test_card_metadata_parses_as_hf_card(exported):
    card = DatasetCard.load(exported.out / "README.md")
    meta = card.data.to_dict()
    assert meta["license"] == "cc-by-4.0"
    configs = {c["config_name"]: c for c in meta["configs"]}
    assert set(configs) == {t.config for t in exported.tables}
    assert configs["neurons"]["default"] is True
    assert configs["edges_min5"]["data_files"] == [
        {"split": "train", "path": "data/edges_min5.parquet"}
    ]


def test_missing_fields_are_detected(exported):
    card = (exported.out / "README.md").read_text()
    broken = card.replace("## Citation\n", "## References\n").replace("license: cc-by-4.0\n", "")
    missing = missing_card_fields(broken, exported)
    assert "section:## Citation" in missing
    assert "metadata:license" in missing


def test_load_dataset_round_trip(exported, tmp_path: Path):
    report = verify_export(exported.out, deep=True, cache_dir=tmp_path / "hf-cache")
    assert report.ok, report.problems
    assert len(report.checked) == 2 * len(exported.tables)


def test_verify_detects_tampering(exported):
    path = exported.out / exported.table("edges_min5").path
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    report = verify_export(exported.out, load=False)
    assert any("SHA-256 mismatch" in p for p in report.problems)


def test_cli_export_and_verify(store_root: Path, tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "cli"
    args = ["export", "malecns@1.0", "--out", str(out), "--store", str(store_root)]
    res = runner.invoke(app, [*args, "--slice", "min_weight=5", "--slice", "types"])
    assert res.exit_code == 0, res.output
    assert "data/edges_min5.parquet" in res.output
    res = runner.invoke(app, ["verify", str(out), "--no-load"])
    assert res.exit_code == 0, res.output
    assert res.output.strip().endswith("ok")

    res = runner.invoke(
        app, ["export", "malecns@1.0", "--out", str(out), "--slice", "min_weight=1"]
    )
    assert res.exit_code != 0
    res = runner.invoke(
        app, ["export", "banc@888", "--out", str(tmp_path / "x"), "--store", str(store_root)]
    )
    assert res.exit_code != 0
