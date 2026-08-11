"""Map recovery outcomes to containment state for sentinel checks."""

from escape_canary import ContainmentState


def containment_state_for_reason(reason: str) -> ContainmentState:
    if reason == "recovered":
        return ContainmentState(recovered=True)
    if reason == "recovery_timeout":
        return ContainmentState(quarantined=True)
    if reason in {"queue_overflow", "quarantine_exhausted", "simulation_horizon_exhausted"}:
        return ContainmentState(ingress_blocked=True)
    if reason == "containment_escape":
        return ContainmentState(escaped=True)
    return ContainmentState(ingress_blocked=True)
