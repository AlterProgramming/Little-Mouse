#!/usr/bin/env python3
"""Minimal epistemic contract for Little Mouse outputs.

The contract prevents evidence-producing workflows from manufacturing an
interpretation merely because a run must return something. A run may end in
NO_RESULT. Stronger statements must identify the evidence level that earned
them and retain their supporting records.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

LEVELS = ("OBSERVATION", "DERIVATION", "HYPOTHESIS", "CLAIM")


@dataclass(frozen=True)
class EvidenceItem:
    level: str
    statement: str
    support: tuple[str, ...] = ()
    reversible: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "statement": self.statement,
            "support": list(self.support),
            "reversible": self.reversible,
        }


def validate_item(item: EvidenceItem) -> None:
    if item.level not in LEVELS:
        raise ValueError(f"unknown evidence level: {item.level}")
    if not item.statement.strip():
        raise ValueError("evidence statement must not be empty")
    if item.level in {"DERIVATION", "CLAIM"} and not item.support:
        raise ValueError(f"{item.level} requires explicit supporting evidence")


def build_result(items: Iterable[EvidenceItem]) -> dict[str, Any]:
    checked = list(items)
    for item in checked:
        validate_item(item)

    # HYPOTHESIS is intentionally not promoted into a finding. It may be kept
    # for a future test, but a hypothesis by itself does not make the run
    # successful in the sense of having discovered something.
    substantive = [item for item in checked if item.level in {"OBSERVATION", "DERIVATION", "CLAIM"}]
    claims = [item for item in checked if item.level == "CLAIM"]
    hypotheses = [item for item in checked if item.level == "HYPOTHESIS"]

    return {
        "result_status": "EVIDENCE" if substantive else "NO_RESULT",
        "claim_count": len(claims),
        "hypothesis_count": len(hypotheses),
        "items": [item.as_dict() for item in checked],
        "delivery_obligation": False,
        "replacement_hypothesis_generated": False,
    }


def no_result() -> dict[str, Any]:
    """Canonical successful empty result."""
    return build_result([])
