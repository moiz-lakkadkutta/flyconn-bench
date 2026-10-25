"""Plan (and, only when explicitly asked, perform) an upload of an export to the Hub.

``plan_upload`` never touches the network: it checks the licence gate, the
export's checksums and its card, and lists what would be sent. ``upload`` runs
the plan through a ``huggingface_hub.HfApi``-like object only with
``execute=True`` and a plan without problems.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import flyconn
import yaml
from flyconn.data.registry import get_dataset

from flyconn_bench.card import hf_license
from flyconn_bench.export import CARD, CHECKSUMS, PROVENANCE
from flyconn_bench.licences import licence_entry
from flyconn_bench.verify import verify_export

IGNORE_PATTERNS: tuple[str, ...] = (".duckdb_tmp/*", ".DS_Store")


class HubApi(Protocol):
    def create_repo(self, repo_id: str, **kwargs: Any) -> Any: ...

    def upload_folder(self, **kwargs: Any) -> Any: ...


@dataclass
class UploadPlan:
    out: Path
    ref: str
    repo_id: str
    files: list[tuple[str, int]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    commit_message: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def total_bytes(self) -> int:
        return sum(n for _, n in self.files)


def plan_upload(out: Path, repo_id: str | None = None) -> UploadPlan:
    out = Path(out)
    record: dict[str, Any] = json.loads((out / PROVENANCE).read_text())
    export: dict[str, Any] = record["export"]
    ref = str(export["registry_ref"])
    plan = UploadPlan(out=out, ref=ref, repo_id=repo_id or str(export["repo_id"]))

    entry = licence_entry(ref)
    spec = get_dataset(ref)
    if entry is None:
        plan.problems.append(f"{ref} is not in the licence table (licences.yaml); not checked")
    else:
        if entry.status != "cleared":
            why = f": {entry.reason}" if entry.reason else ""
            plan.problems.append(f"licence status for {ref} is {entry.status!r}{why}")
        if entry.licence != spec.license:
            plan.problems.append(
                f"licence table says {entry.licence} but flyconn's registry says {spec.license}"
            )
    built_by = str(record["store"].get("flyconn_version", "unknown"))
    if _minor(built_by) != _minor(flyconn.__version__):
        plan.problems.append(
            f"store was built by flyconn {built_by}, installed is {flyconn.__version__}; "
            f"rebuild it (flyconn data pull {ref} --force) before uploading"
        )
    card_licence = _card_metadata(out / CARD).get("license")
    if card_licence != hf_license(spec)["license"]:
        plan.problems.append(f"card licence {card_licence!r} does not match the registry")

    report = verify_export(out, load=False)
    plan.problems += [f"verify: {p}" for p in report.problems]

    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = path.relative_to(out).as_posix()
        if not any(Path(rel).match(pat) for pat in IGNORE_PATTERNS):
            plan.files.append((rel, path.stat().st_size))
    expected = {CARD, CHECKSUMS, PROVENANCE, *(t["path"] for t in export["tables"])}
    extra = sorted({rel for rel, _ in plan.files} - expected)
    if extra:
        plan.problems.append(f"unexpected files in export: {extra}")

    sha = export.get("flyconn_bench_git_sha") or "unknown"
    plan.commit_message = (
        f"{ref} snapshot (flyconn-bench {export['flyconn_bench_version']}, {sha[:12]})"
    )
    return plan


def upload(plan: UploadPlan, api: HubApi, *, execute: bool = False, private: bool = True) -> Any:
    """Create the dataset repo and upload the folder. Without ``execute`` this does nothing."""
    if not execute:
        return None
    if not plan.ok:
        msg = f"refusing to upload {plan.ref}: {plan.problems}"
        raise RuntimeError(msg)
    api.create_repo(plan.repo_id, repo_type="dataset", private=private, exist_ok=True)
    return api.upload_folder(
        repo_id=plan.repo_id,
        repo_type="dataset",
        folder_path=str(plan.out),
        commit_message=plan.commit_message,
        ignore_patterns=list(IGNORE_PATTERNS),
    )


def _minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def _card_metadata(card: Path) -> dict[str, Any]:
    if not card.exists():
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", card.read_text(), flags=re.DOTALL)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}
