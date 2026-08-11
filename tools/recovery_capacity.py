"""Finite recovery resource model for Little Mouse stress testing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryCapacity:
    queue_slots: int
    workers: int
    worker_units_per_tick: int
    timeout_ticks: int
    quarantine_slots: int


@dataclass(frozen=True)
class IncidentLoad:
    incident_id: str
    work_units: int
    quarantine_units: int
    arrival_tick: int
    deadline_tick: int


@dataclass(frozen=True)
class IncidentResult:
    incident_id: str
    recovered: bool
    reason: str
    completed_tick: int | None


def simulate(capacity: RecoveryCapacity, incidents: list[IncidentLoad]) -> list[IncidentResult]:
    queue: list[IncidentLoad] = []
    results: dict[str, IncidentResult] = {}
    remaining: dict[str, int] = {}
    quarantine_in_use: dict[str, int] = {}

    if not incidents:
        return []

    last_arrival = max(i.arrival_tick for i in incidents)
    max_deadline = max(i.deadline_tick for i in incidents)

    for tick in range(0, max(last_arrival, max_deadline) + capacity.timeout_ticks + 2):
        arriving = [i for i in incidents if i.arrival_tick == tick]
        for incident in arriving:
            if len(queue) >= capacity.queue_slots:
                results[incident.incident_id] = IncidentResult(
                    incident.incident_id, False, "queue_overflow", None
                )
                continue
            if sum(quarantine_in_use.values()) + incident.quarantine_units > capacity.quarantine_slots:
                results[incident.incident_id] = IncidentResult(
                    incident.incident_id, False, "quarantine_exhausted", None
                )
                continue
            queue.append(incident)
            remaining[incident.incident_id] = incident.work_units
            quarantine_in_use[incident.incident_id] = incident.quarantine_units

        # Expire queued work before assigning workers.
        still_queued: list[IncidentLoad] = []
        for incident in queue:
            if tick > incident.deadline_tick:
                results[incident.incident_id] = IncidentResult(
                    incident.incident_id, False, "recovery_timeout", None
                )
                quarantine_in_use.pop(incident.incident_id, None)
                remaining.pop(incident.incident_id, None)
            else:
                still_queued.append(incident)
        queue = still_queued

        # Deterministic FIFO scheduling.
        active = queue[: capacity.workers]
        completed_ids: set[str] = set()
        for incident in active:
            rem = remaining[incident.incident_id] - capacity.worker_units_per_tick
            remaining[incident.incident_id] = rem
            if rem <= 0:
                results[incident.incident_id] = IncidentResult(
                    incident.incident_id, True, "recovered", tick
                )
                completed_ids.add(incident.incident_id)
                quarantine_in_use.pop(incident.incident_id, None)
                remaining.pop(incident.incident_id, None)

        if completed_ids:
            queue = [i for i in queue if i.incident_id not in completed_ids]

        if len(results) == len(incidents):
            break

    for incident in incidents:
        if incident.incident_id not in results:
            results[incident.incident_id] = IncidentResult(
                incident.incident_id, False, "simulation_horizon_exhausted", None
            )
    return [results[i.incident_id] for i in incidents]
