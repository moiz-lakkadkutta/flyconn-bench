"""Generate the Hugging Face dataset card (README.md) for an export.

Everything on the card comes from flyconn's registry entry, the store's
``provenance.json`` and the export run itself; nothing is typed by hand except
the per-dataset caveats below, which summarise flyconn's ``docs/caveats.md``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import yaml
from flyconn.data.registry import DatasetSpec

if TYPE_CHECKING:
    from flyconn_bench.export import ExportResult

FLYCONN_URL = "https://github.com/moiz-lakkadkutta/flyconn"

HF_LICENSES: Mapping[str, str] = {"CC-BY-4.0": "cc-by-4.0", "MIT": "mit"}
"""Registry licence id -> Hugging Face licence id; anything else becomes ``other``."""

REQUIRED_SECTIONS: tuple[str, ...] = (
    "## Summary",
    "## Files",
    "## Licence",
    "## Citation",
    "## Edge thresholds",
    "## Neurotransmitter predictions are predictions",
    "## Caveats",
    "## Provenance",
    "## How to load",
)
REQUIRED_METADATA: tuple[str, ...] = (
    "license",
    "pretty_name",
    "configs",
    "tags",
    "source_datasets",
)

NT_CAVEAT = (
    "Neurotransmitter columns (`nt_pred`, `nt_conf`, `nt_p_*`) are **classifier predictions** "
    "made from EM images (the Eckstein et al. 2024 lineage), not measurements. They can be "
    "systematically wrong for whole cell classes. Do not use them as ground-truth labels; "
    "`nt_known`, where filled, carries the source's own known-transmitter annotation. "
    "Which classes exist differs per dataset (3 in MANC, 6 in FlyWire, 7 in MaleCNS, 8 in BANC); "
    "absent classes are null, not zero evidence."
)

GENERAL_CAVEATS: tuple[str, ...] = (
    "A connectome is wiring. It carries no measured activity, and edge weights are synapse "
    "counts under a detection and confidence threshold that differs per dataset.",
    "Compare datasets only after applying the same `min_weight` to both; residual technical "
    "differences (synapse detection, proofreading completeness) remain.",
    "Two individuals of the same sex differ in connectivity more than the left and right sides "
    "of one brain (Schlegel et al. 2024). Cross-animal differences need that baseline.",
)

DATASET_CAVEATS: Mapping[str, tuple[str, ...]] = {
    "malecns": (
        "Edges are between neurons only (bodies with a `superclass`). Synapses onto unannotated "
        "fragments are not in `edges`, so per-neuron input totals computed from it undercount; "
        "the raw totals are under Provenance.",
        "Body-level transmitter calls are an argmax plus a confidence. Where `nt_p_*` columns "
        "are filled they are means of per-presynapse probabilities, not calibrated posteriors.",
        "Cross-references such as `fafb_783_cell_type` were assigned by the MaleCNS team. How "
        "much connectivity informed them is an open question, so scores that use them as labels "
        "for cross-animal prediction may be inflated.",
    ),
    "banc": (
        "Both antennal nerves were damaged in the BANC sample, so antennal inputs are "
        "under-represented; the left optic lobe is less completely typed.",
        "The released edge list contains self-connections although its documentation says they "
        "were removed. flyconn drops them; the count is under Provenance (`autapses_dropped`).",
        "BANC's MaleCNS cross-reference refers to MaleCNS v0.9, not v1.0.",
    ),
    "flywire": (
        "FlyWire root IDs change with proofreading, so IDs are only meaningful together with "
        "the version. Join tables on `dataset` and `version` as well as the ID.",
        "Codex exports keep neuron pairs with at least 5 synapses (Buhmann et al. 2021 synapses).",
    ),
    "hemibrain": (
        "The hemibrain volume is mostly the right hemisphere. Left-side neurons and arbors are "
        "truncated, which distorts degree and left/right comparisons.",
        "Weights count every postsynaptic density (the dataset's confidence threshold is 0).",
        "The body-level transmitter file has no published README (provenance UNVERIFIED); it "
        "predicts Kenyon cells as dopaminergic although they are cholinergic.",
    ),
    "manc": (
        "Built from the sjcabs compiled MANC v1.2.1 files; their synapse confidence threshold "
        "is not documented, and counts differ slightly from neuPrint.",
        "Transmitter predictions are 3-class (acetylcholine, GABA, glutamate); no MANC neuron "
        "is predicted monoaminergic.",
    ),
}


def hf_license(spec: DatasetSpec) -> dict[str, str]:
    lic = HF_LICENSES.get(spec.license)
    if lic:
        return {"license": lic}
    meta = {"license": "other", "license_name": spec.license.lower()}
    if spec.license_url:
        meta["license_link"] = spec.license_url
    return meta


def _size_category(n: int) -> str:
    bounds = [
        (1_000, "n<1K"),
        (10_000, "1K<n<10K"),
        (100_000, "10K<n<100K"),
        (1_000_000, "100K<n<1M"),
        (10_000_000, "1M<n<10M"),
        (100_000_000, "10M<n<100M"),
        (1_000_000_000, "100M<n<1B"),
    ]
    for bound, label in bounds:
        if n < bound:
            return label
    return "1B<n<10B"


def card_metadata(spec: DatasetSpec, result: ExportResult) -> dict[str, Any]:
    configs: list[dict[str, Any]] = []
    for t in result.tables:
        cfg: dict[str, Any] = {
            "config_name": t.config,
            "data_files": [{"split": "train", "path": t.path}],
        }
        if t.config == "neurons":
            cfg["default"] = True
        configs.append(cfg)
    largest = max((t.rows for t in result.tables), default=0)
    return {
        **hf_license(spec),
        "pretty_name": f"{spec.title} — flyconn harmonized snapshot",
        "tags": ["connectome", "drosophila", "neuroscience", "graph", "flyconn"],
        "task_categories": ["graph-ml"],
        "size_categories": [_size_category(largest)],
        "source_datasets": [spec.homepage or spec.ref],
        "configs": configs,
    }


def _fmt(n: int) -> str:
    return f"{n:,}"


def _kv_lines(d: Mapping[str, Any], indent: str = "") -> list[str]:
    lines: list[str] = []
    for k, v in sorted(d.items()):
        if isinstance(v, Mapping):
            lines.append(f"{indent}- `{k}`:")
            lines.extend(_kv_lines(v, indent + "  "))  # pyright: ignore[reportUnknownArgumentType]
        else:
            shown = _fmt(v) if isinstance(v, int) and not isinstance(v, bool) else v
            lines.append(f"{indent}- `{k}`: {shown}")
    return lines


def render_card(spec: DatasetSpec, provenance: Mapping[str, Any], result: ExportResult) -> str:
    info = result.info
    meta = yaml.safe_dump(card_metadata(spec, result), sort_keys=False, allow_unicode=True)
    files = [
        "| Config | File | Rows | Bytes | SHA-256 | Description |",
        "|---|---|---|---|---|---|",
        *(
            f"| `{t.config}` | `{t.path}` | {_fmt(t.rows)} | {_fmt(t.bytes)} | `{t.sha256}` | "
            f"{t.description} |"
            for t in result.tables
        ),
    ]
    cites = [
        f"- {c.text}" + (f" doi:[{c.doi}](https://doi.org/{c.doi})" if c.doi else "")
        for c in spec.citations
    ]
    thresholds = _kv_lines(provenance.get("edge_threshold", {})) or ["- none recorded"]
    reg_threshold = spec.extra.get("synapse_threshold")
    if isinstance(reg_threshold, Mapping):
        thresholds += ["", "Registry description of the source threshold:", ""]
        thresholds += _kv_lines(reg_threshold)  # pyright: ignore[reportUnknownArgumentType]
    slice_lines: list[str] = []
    for name, s in info.get("slices", {}).items():
        slice_lines += [f"- Slice `{name}`:", *_kv_lines(s, "  ")]
    caveats = [*GENERAL_CAVEATS, *DATASET_CAVEATS.get(spec.name, ())]
    env = info.get("environment", {})
    inputs = [
        f"| `{i.get('name')}` | {_fmt(int(i.get('bytes', 0)))} | `{i.get('sha256')}` |"
        for i in provenance.get("inputs", [])
    ]
    first = result.tables[0].config if result.tables else "neurons"
    lic_line = f"[{spec.license}]({spec.license_url})" if spec.license_url else spec.license

    body = [
        f"# {spec.title}",
        "",
        "## Summary",
        "",
        f"Harmonized tables of `{spec.ref}` produced by [flyconn]({FLYCONN_URL}) and exported "
        "with flyconn-bench. This is an unofficial mirror: the source of truth is the original "
        f"release ({spec.homepage or 'see Citation'}). Column names follow flyconn's harmonized "
        "schema (the SJCABS/BANC vocabulary); source spellings are kept in `*_raw` columns.",
        "",
        f"- Dataset: `{spec.ref}`"
        + (f", released {spec.release_date}" if spec.release_date else ""),
        f"- Neuron definition: {provenance.get('neuron_definition', 'not recorded')}",
        f"- Planned Hub repo: `{result.repo_id}`",
        "",
        "## Files",
        "",
        *files,
        "",
        "`checksums.sha256` lists the same digests (`sha256sum -c checksums.sha256`). Full tables "
        "are byte-for-byte copies of the flyconn store files.",
        "",
        "## Licence",
        "",
        f"The data are licensed {lic_line} by their creators. This snapshot redistributes them "
        "with attribution; if you use it, cite the original papers below. flyconn and "
        "flyconn-bench code are Apache-2.0.",
        "",
        "## Citation",
        "",
        *cites,
        f"- flyconn (harmonization and export): {FLYCONN_URL}",
        "",
        "## Edge thresholds",
        "",
        *thresholds,
        *(["", *slice_lines] if slice_lines else []),
        "",
        "## Neurotransmitter predictions are predictions",
        "",
        NT_CAVEAT,
        "",
        "## Caveats",
        "",
        *[f"- {c}" for c in caveats],
        "",
        "## Provenance",
        "",
        f"- Store converter: `{provenance.get('converter')}` "
        f"v{provenance.get('converter_version', '?')}, built by flyconn "
        f"{provenance.get('flyconn_version')} at {provenance.get('created_utc')}",
        f"- Export: flyconn-bench {info.get('flyconn_bench_version')} "
        f"(git `{info.get('flyconn_bench_git_sha') or 'unavailable'}`), flyconn "
        f"{env.get('flyconn_version')} (git `{env.get('git_sha') or 'installed release'}`), "
        f"at {info.get('created_utc')}",
        "- Converter counts:",
        *_kv_lines(provenance.get("counts", {}), "  "),
        "",
        "| Source file | Bytes | SHA-256 |",
        "|---|---|---|",
        *(inputs or ["| none recorded | | |"]),
        "",
        "`provenance.json` holds the full store and export records.",
        "",
        "## How to load",
        "",
        "```python",
        "from datasets import load_dataset",
        "",
        f'neurons = load_dataset("{result.repo_id}", "{first}", split="train")',
        "# or, from a local copy of this folder:",
        f'neurons = load_dataset("parquet", data_files="data/{first}.parquet", split="train")',
        "```",
        "",
        "With flyconn installed, `flyconn data pull " + spec.ref + "` builds the same store "
        "from the original release.",
        "",
    ]
    return f"---\n{meta}---\n\n" + "\n".join(body)


def missing_card_fields(card: str, result: ExportResult) -> list[str]:
    """Return what a generated card lacks (empty list when complete)."""
    missing: list[str] = []
    m = re.match(r"^---\n(.*?)\n---\n", card, flags=re.DOTALL)
    meta: dict[str, Any] = (yaml.safe_load(m.group(1)) or {}) if m else {}
    missing += [f"metadata:{k}" for k in REQUIRED_METADATA if not meta.get(k)]
    configs = {c.get("config_name") for c in meta.get("configs", [])}
    missing += [f"config:{t.config}" for t in result.tables if t.config not in configs]
    missing += [f"section:{s}" for s in REQUIRED_SECTIONS if f"\n{s}\n" not in card]
    missing += [f"sha256:{t.path}" for t in result.tables if t.sha256 not in card]
    info = result.info
    env = info.get("environment", {})
    for label, value in (
        ("flyconn_version", env.get("flyconn_version")),
        ("flyconn_bench_version", info.get("flyconn_bench_version")),
    ):
        if not value or str(value) not in card:
            missing.append(f"provenance:{label}")
    if "doi:" not in card:
        missing.append("citation:doi")
    return missing
