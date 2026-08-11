"""Provenance-preserving evidence runtime for Little Mouse.

Evidence carries epistemic status and provenance through each state transition.
Downstream actions may only be eligible when supporting evidence has crossed the
required validation boundary. Unresolved or contaminated evidence remains
representable but cannot silently become trusted operational state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Iterable


class EvidenceStatus(IntEnum):
    OBSERVED = 0
    CANDIDATE = 1
    VALIDATED = 2
    INFERRED = 3
    CONTAMINATED = 4


@dataclass(frozen=True)
class ProvenanceEdge:
    source_id: str
    transform: str


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    subject: str
    claim: str
    status: EvidenceStatus
    confidence: float
    provenance: tuple[ProvenanceEdge, ...] = ()
    quarantined: bool = False


@dataclass(frozen=True)
class ActionRequirement:
    action: str
    minimum_status: EvidenceStatus
    minimum_confidence: float


def promote(
    evidence: Evidence,
    *,
    new_status: EvidenceStatus,
    confidence: float,
    source_ids: Iterable[str],
    transform: str,
) -> Evidence:
    """Create a new evidence state while preserving provenance.

    Promotion is monotonic except for explicit contamination. A quarantined
    record cannot be promoted into ordinary trusted state.
    """
    if evidence.quarantined:
        raise ValueError("quarantined_evidence_cannot_be_promoted")
    if new_status == EvidenceStatus.CONTAMINATED:
        return replace(
            evidence,
            status=new_status,
            confidence=confidence,
            provenance=evidence.provenance
            + tuple(ProvenanceEdge(str(s), transform) for s in source_ids),
            quarantined=True,
        )
    if new_status < evidence.status:
        raise ValueError("epistemic_status_cannot_move_backwards")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence_out_of_range")
    return replace(
        evidence,
        status=new_status,
        confidence=confidence,
        provenance=evidence.provenance
        + tuple(ProvenanceEdge(str(s), transform) for s in source_ids),
    )


def quarantine(evidence: Evidence, *, reason_source: str) -> Evidence:
    """Keep unresolved evidence representable while preventing propagation."""
    return replace(
        evidence,
        quarantined=True,
        provenance=evidence.provenance
        + (ProvenanceEdge(reason_source, "quarantine"),),
    )


def action_eligible(
    evidence: Evidence, requirement: ActionRequirement
) -> tuple[bool, str]:
    """Authorize epistemic eligibility only; capability/auth checks remain separate."""
    if evidence.quarantined:
        return False, "evidence_quarantined"
    if evidence.status == EvidenceStatus.CONTAMINATED:
        return False, "evidence_contaminated"
    if evidence.status < requirement.minimum_status:
        return False, "insufficient_epistemic_status"
    if evidence.confidence < requirement.minimum_confidence:
        return False, "insufficient_confidence"
    if not evidence.provenance:
        return False, "missing_provenance"
    return True, "evidence_eligible"


def derive(
    *,
    evidence_id: str,
    subject: str,
    claim: str,
    parents: Iterable[Evidence],
    confidence: float,
    transform: str,
) -> Evidence:
    """Derive an inference without silently promoting unresolved parents."""
    parent_list = tuple(parents)
    if not parent_list:
        raise ValueError("derived_evidence_requires_parents")
    if any(p.quarantined or p.status == EvidenceStatus.CONTAMINATED for p in parent_list):
        return Evidence(
            evidence_id=evidence_id,
            subject=subject,
            claim=claim,
            status=EvidenceStatus.CONTAMINATED,
            confidence=confidence,
            provenance=tuple(
                ProvenanceEdge(p.evidence_id, transform) for p in parent_list
            ),
            quarantined=True,
        )
    minimum_parent_status = min(p.status for p in parent_list)
    status = (
        EvidenceStatus.INFERRED
        if minimum_parent_status >= EvidenceStatus.VALIDATED
        else EvidenceStatus.CANDIDATE
    )
    return Evidence(
        evidence_id=evidence_id,
        subject=subject,
        claim=claim,
        status=status,
        confidence=confidence,
        provenance=tuple(ProvenanceEdge(p.evidence_id, transform) for p in parent_list),
    )
