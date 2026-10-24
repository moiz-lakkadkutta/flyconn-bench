"""Slice specifications for ``flyconn-bench export --slice``.

A slice adds smaller tables to an export, for Colab and teaching:

- ``min_weight=N``: edges (and per-ROI edges) of pairs with at least ``N`` synapses.
- ``types``: the type-aggregated graph (one node per ``cell_type``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MinWeight:
    """Keep neuron pairs whose total synapse count is at least ``n``."""

    n: int

    @property
    def suffix(self) -> str:
        return f"min{self.n}"


@dataclass(frozen=True)
class Types:
    """Aggregate weights between all neurons of each ``cell_type`` pair."""


Slice = MinWeight | Types


def parse_slice(text: str) -> Slice:
    """Parse ``"min_weight=5"`` or ``"types"``."""
    key, sep, value = text.strip().partition("=")
    if key == "types" and not sep:
        return Types()
    if key == "min_weight" and sep:
        try:
            n = int(value)
        except ValueError:
            n = 0
        if n >= 2:
            return MinWeight(n)
        msg = f"min_weight must be an integer >= 2, got {value!r}"
        raise ValueError(msg)
    msg = f"unknown slice {text!r}; expected 'min_weight=N' or 'types'"
    raise ValueError(msg)
