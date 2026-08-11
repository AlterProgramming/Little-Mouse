"""Recovery controls for Little Mouse governance failures.

This module models incident containment in the audit/governance plane. It does
not execute external actions. Its purpose is to make recovery state explicit,
traceable, and testable after a guardrail failure.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class RecoveryState:
    run_stopped: bool = False
    receipt_preserved: bool = False
    capabilities_revoked: bool = False
    outputs_quarantined: bool = False
    downstream_marked_contaminated: bool = False
    clean_seed_revalidated: bool = False
    neighboring_legitimate_cases_pass: bool = False


@dataclass(frozen=True)
class RecoveryReceipt:
    incident_id: str
    attempted_action: str
    executed_action: str
    failure_stage: str
    affected_artifacts: tuple[str, ...]


def contain_incident(
    *,
    incident_id: str,
    attempted_action: str,
    executed_action: str,
    failure_stage: str,
    affected_artifacts: Iterable[str] = (),
) -> tuple[RecoveryState, RecoveryReceipt]:
    """Apply the minimum immediate recovery invariants for a bad execution."""
    receipt = RecoveryReceipt(
        incident_id=incident_id,
        attempted_action=attempted_action,
        executed_action=executed_action,
        failure_stage=failure_stage,
        affected_artifacts=tuple(affected_artifacts),
    )
    state = RecoveryState(
        run_stopped=True,
        receipt_preserved=True,
        capabilities_revoked=True,
        outputs_quarantined=True,
        downstream_marked_contaminated=True,
    )
    return state, receipt


def can_reopen(state: RecoveryState) -> tuple[bool, str]:
    """Require containment plus clean-seed and neighbor-case validation."""
    required = (
        state.run_stopped,
        state.receipt_preserved,
        state.capabilities_revoked,
        state.outputs_quarantined,
        state.downstream_marked_contaminated,
        state.clean_seed_revalidated,
        state.neighboring_legitimate_cases_pass,
    )
    if not all(required):
        return False, "recovery_incomplete"
    return True, "recovery_validated"


def mark_revalidated(
    state: RecoveryState,
    *,
    clean_seed_revalidated: bool,
    neighboring_legitimate_cases_pass: bool,
) -> RecoveryState:
    """Return a new immutable state after regression validation."""
    return RecoveryState(
        run_stopped=state.run_stopped,
        receipt_preserved=state.receipt_preserved,
        capabilities_revoked=state.capabilities_revoked,
        outputs_quarantined=state.outputs_quarantined,
        downstream_marked_contaminated=state.downstream_marked_contaminated,
        clean_seed_revalidated=clean_seed_revalidated,
        neighboring_legitimate_cases_pass=neighboring_legitimate_cases_pass,
    )


def audit_record(state: RecoveryState, receipt: RecoveryReceipt) -> dict:
    return {"recovery": asdict(state), "receipt": asdict(receipt)}
