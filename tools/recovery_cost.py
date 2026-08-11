"""Normalized loss accounting for unrecovered Little Mouse incidents.

The score is deliberately unitless. It measures simulator burden, not money or
real-world harm. Every component is explicit so campaign results remain auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from recovery_capacity import IncidentLoad, IncidentResult


REASON_WEIGHT = {
    "queue_overflow": 1.5,
    "quarantine_exhausted": 2.0,
    "recovery_timeout": 1.25,
    "simulation_horizon_exhausted": 2.5,
}


@dataclass(frozen=True)
class FailureCost:
    incident_id: str
    total: float
    unresolved_base: float
    work_burden: float
    quarantine_burden: float
    reason_multiplier: float
    reason: str


def failure_cost(incident: IncidentLoad, result: IncidentResult) -> FailureCost:
    if result.recovered:
        return FailureCost(
            incident.incident_id, 0.0, 0.0, 0.0, 0.0, 0.0, result.reason
        )

    unresolved_base = 10.0
    work_burden = float(incident.work_units)
    quarantine_burden = 2.0 * float(incident.quarantine_units)
    multiplier = REASON_WEIGHT.get(result.reason, 1.0)
    total = (unresolved_base + work_burden + quarantine_burden) * multiplier
    return FailureCost(
        incident_id=incident.incident_id,
        total=total,
        unresolved_base=unresolved_base,
        work_burden=work_burden,
        quarantine_burden=quarantine_burden,
        reason_multiplier=multiplier,
        reason=result.reason,
    )


def campaign_cost(
    incidents: list[IncidentLoad], results: list[IncidentResult]
) -> dict[str, float | int | dict[str, float]]:
    incident_by_id = {i.incident_id: i for i in incidents}
    costs = [failure_cost(incident_by_id[r.incident_id], r) for r in results]
    failures = [c for c in costs if c.total > 0]
    by_reason: dict[str, float] = {}
    for cost in failures:
        by_reason[cost.reason] = by_reason.get(cost.reason, 0.0) + cost.total
    total = sum(c.total for c in failures)
    return {
        "incidents": len(results),
        "failed": len(failures),
        "recovered": len(results) - len(failures),
        "total_loss_units": total,
        "mean_loss_per_failure": total / len(failures) if failures else 0.0,
        "mean_loss_per_incident": total / len(results) if results else 0.0,
        "loss_by_reason": by_reason,
    }
