"""A small synthetic flyconn store (registered as malecns@1.0 so the registry applies)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from flyconn.data.convert.common import write_parquet, write_provenance
from flyconn.data.schema import conform_edges, conform_neurons
from flyconn.data.store import Store
from flyconn.testing import synthetic_connectome


def write_store(d: Path, dataset: str = "malecns", version: str = "1.0") -> Path:
    """Write a synthetic store at ``d`` that claims to be ``dataset@version``."""
    neurons, edges = synthetic_connectome(n_neurons=40, n_edges=300, seed=7)
    neurons["dataset"] = edges["dataset"] = dataset
    neurons["version"] = edges["version"] = version
    neurons.loc[:4, "cell_type"] = None  # untyped neurons must drop out of the types slice
    # Split each pair over two ROIs so the per-ROI slice can be checked against pair totals.
    first = edges.assign(roi="AL_R", weight=(edges["weight"] + 1) // 2)
    second = edges.assign(roi="LH_R", weight=edges["weight"] // 2)
    roi = pd.concat([first, second[second["weight"] > 0]], ignore_index=True)
    d.mkdir(parents=True)
    write_parquet(conform_neurons(neurons), d / "neurons.parquet")
    write_parquet(conform_edges(edges), d / "edges.parquet")
    write_parquet(conform_edges(roi), d / "edges_roi.parquet")
    write_provenance(
        d,
        dataset=dataset,
        version=version,
        converter="test",
        inputs=[],
        counts={"neurons": len(neurons), "edges": len(edges)},
        edge_threshold={"minconf": 0.5, "pair_min_synapses": 1},
        neuron_definition="synthetic",
    )  # write_provenance stamps the installed flyconn version, as a fresh rebuild would
    return d


@pytest.fixture
def store_root(tmp_path: Path) -> Path:
    return write_store(tmp_path / "store")


@pytest.fixture
def store(store_root: Path) -> Iterator[Store]:
    s = Store(store_root)
    yield s
    s.close()
