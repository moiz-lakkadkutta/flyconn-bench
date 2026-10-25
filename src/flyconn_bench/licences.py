"""The upload gate: per-dataset redistribution status from ``licences.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any, Literal

import yaml

Status = Literal["cleared", "review", "blocked"]
STATUSES: tuple[Status, ...] = ("cleared", "review", "blocked")


@dataclass(frozen=True)
class LicenceEntry:
    ref: str
    doc_name: str
    status: Status
    licence: str
    sources: tuple[str, ...]
    reason: str = ""


@cache
def _load() -> tuple[str, dict[str, LicenceEntry]]:
    text = (resources.files("flyconn_bench") / "licences.yaml").read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    entries: dict[str, LicenceEntry] = {}
    for ref, d in data["datasets"].items():
        if d["status"] not in STATUSES:
            msg = f"licences.yaml: {ref} has unknown status {d['status']!r}"
            raise ValueError(msg)
        entries[ref] = LicenceEntry(
            ref=ref,
            doc_name=d["doc_name"],
            status=d["status"],
            licence=d["licence"],
            sources=tuple(d.get("sources", ())),
            reason=d.get("reason", ""),
        )
    return str(data["checked"]), entries


def licence_entries() -> dict[str, LicenceEntry]:
    return dict(_load()[1])


def checked_date() -> str:
    return _load()[0]


def licence_entry(ref: str) -> LicenceEntry | None:
    """The gate entry for ``name@version``, or None if the dataset was never checked."""
    return _load()[1].get(ref)
