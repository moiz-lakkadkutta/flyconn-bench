from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from flyconn.data.store import Store

from flyconn_bench.export import export_store, read_checksums, sha256_file
from flyconn_bench.slices import MinWeight, Types, parse_slice


def test_parse_slice():
    assert parse_slice("min_weight=5") == MinWeight(5)
    assert parse_slice(" types ") == Types()
    for bad in ("min_weight=1", "min_weight=x", "min_weight", "types=2", "roi"):
        with pytest.raises(ValueError):
            parse_slice(bad)


def test_full_tables_are_byte_copies(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    result = export_store(store, out)
    assert [t.config for t in result.tables] == ["edges", "edges_roi", "neurons"]
    sums = read_checksums(out)
    for t in result.tables:
        src = store.root / Path(t.path).name
        assert t.sha256 == sha256_file(src) == sums[t.path]
        assert t.rows == pq.ParquetFile(src).metadata.num_rows
    assert {p.name for p in out.iterdir()} == {
        "README.md",
        "checksums.sha256",
        "data",
        "provenance.json",
    }


def test_min_weight_slice_thresholds_pair_totals(store: Store, tmp_path: Path):
    result = export_store(store, tmp_path / "export", [MinWeight(5)])
    edges = store.edges()
    got = pd.read_parquet(tmp_path / "export" / result.table("edges_min5").path)
    expected = edges[edges["weight"] >= 5].reset_index(drop=True)
    cols = ["pre", "post", "weight"]
    pd.testing.assert_frame_equal(got[cols], expected[cols], check_dtype=False)
    assert list(got.columns) == list(expected.columns)

    roi = pd.read_parquet(tmp_path / "export" / result.table("edges_roi_min5").path)
    # Every ROI row of a kept pair survives, even when that row alone is below 5.
    kept = set(zip(expected["pre"], expected["post"], strict=True))
    assert set(zip(roi["pre"], roi["post"], strict=True)) == kept
    assert (roi["weight"] < 5).any()
    assert roi.groupby(["pre", "post"])["weight"].sum().min() >= 5
    info = result.info["slices"]["min5"]
    assert info["edges_kept"] == len(expected)
    assert info["weight_total"] == int(edges["weight"].sum())


def test_types_slice_matches_pandas(store: Store, tmp_path: Path):
    result = export_store(store, tmp_path / "export", [Types()])
    neurons = store.neurons()
    typed = neurons.dropna(subset=["cell_type"]).set_index("neuron_id")["cell_type"]
    edges = store.edges()
    edges = edges[edges["pre"].isin(typed.index) & edges["post"].isin(typed.index)]
    edges = edges.assign(pre_type=edges["pre"].map(typed), post_type=edges["post"].map(typed))
    expected = edges.groupby(["pre_type", "post_type"])["weight"].agg(["sum", "count"])

    got = pd.read_parquet(tmp_path / "export" / result.table("type_edges").path)
    got = got.set_index(["pre_type", "post_type"])
    assert got["weight"].to_dict() == expected["sum"].to_dict()
    assert got["n_pairs"].to_dict() == expected["count"].to_dict()
    sizes = typed.value_counts()
    assert (got["n_post"] == got.index.get_level_values("post_type").map(sizes)).all()
    assert got["weight_per_post"].tolist() == pytest.approx(
        (got["weight"] / got["n_post"]).tolist()
    )

    types = pd.read_parquet(tmp_path / "export" / result.table("cell_types").path)
    assert types.set_index("cell_type")["n_neurons"].to_dict() == sizes.to_dict()
    info = result.info["slices"]["types"]
    assert info["neurons_untyped_excluded"] == 5
    assert info["weight_between_typed"] == int(expected["sum"].sum())


def test_slices_are_deterministic(store: Store, tmp_path: Path):
    a = export_store(store, tmp_path / "a", [MinWeight(3), Types()])
    b = export_store(store, tmp_path / "b", [MinWeight(3), Types()])
    assert [t.sha256 for t in a.tables] == [t.sha256 for t in b.tables]


def test_refuses_to_overwrite(store: Store, tmp_path: Path):
    out = tmp_path / "export"
    out.mkdir()
    (out / "notes.txt").write_text("keep me")
    with pytest.raises(FileExistsError, match="not an export"):
        export_store(store, out)
    assert (out / "notes.txt").read_text() == "keep me"

    out2 = tmp_path / "export2"
    export_store(store, out2)
    with pytest.raises(FileExistsError, match="--force"):
        export_store(store, out2)
    result = export_store(store, out2, [MinWeight(5)], force=True)
    assert "edges_min5" in {t.config for t in result.tables}
    assert not (out2 / ".duckdb_tmp").exists()


def test_provenance_records_the_run(store: Store, tmp_path: Path):
    import json

    result = export_store(store, tmp_path / "export", [MinWeight(5)])
    record = json.loads((tmp_path / "export" / "provenance.json").read_text())
    assert record["store"] == store.provenance
    export = record["export"]
    assert export["registry_ref"] == "malecns@1.0"
    assert export["environment"]["flyconn_version"].startswith("0.4")
    assert export["seconds_total"] >= 0
    assert [t["sha256"] for t in export["tables"]] == [t.sha256 for t in result.tables]
