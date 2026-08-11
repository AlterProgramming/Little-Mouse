"""Trusted-trigger governance that does not alter investigative execution.

The Trusted classification is an audit/governance property. It may require a
standing note to be read before an operation is authorized, but it must not
change the operation's externally observable request plan unless the note
explicitly blocks the operation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

TRUSTED_SEVERITY = "trusted"
STANDARD_SEVERITY = "standard"


@dataclass(frozen=True)
class TriggerContext:
    severity: str
    note_required: bool
    note_read: bool
    seed_case: bool = False


@dataclass(frozen=True)
class DistributionRecord:
    destination: str
    role: str
    severity: str
    reason: str


def authorize(context: TriggerContext) -> tuple[bool, str]:
    """Authorize governance preconditions without mutating the execution plan."""
    if context.severity == TRUSTED_SEVERITY and context.note_required and not context.note_read:
        return False, "trusted_note_not_read"
    return True, "governance_satisfied"


def build_execution_plan(subject: str, operation: str) -> dict[str, Any]:
    """Build the execution-plane plan from task inputs only.

    Trigger severity, note state, and whether a case is seeded are deliberately
    excluded so those governance properties cannot fingerprint the request path.
    """
    return {
        "subject": subject,
        "operation": operation,
        "request_profile": "default",
    }


def audit_event(
    context: TriggerContext,
    *,
    subject: str,
    operation: str,
    distribution: list[DistributionRecord] | None = None,
) -> dict[str, Any]:
    """Create a transparent audit-plane event kept separate from execution."""
    allowed, reason = authorize(context)
    return {
        "subject": subject,
        "operation": operation,
        "severity": context.severity,
        "note_required": context.note_required,
        "note_read": context.note_read,
        "seed_case": context.seed_case,
        "allowed": allowed,
        "reason": reason,
        "distribution": [asdict(item) for item in (distribution or [])],
    }
