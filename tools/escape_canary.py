"""Escape-only canary for Little Mouse recovery tests.

The canary is an isolated test action. It must be unreachable from normal,
quarantined, ingress-blocked, or recovered states and reachable only after a
simulated containment escape.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContainmentState:
    escaped: bool = False
    quarantined: bool = False
    ingress_blocked: bool = False
    recovered: bool = False


def can_reach_hidden_action(state: ContainmentState) -> bool:
    return (
        state.escaped
        and not state.quarantined
        and not state.ingress_blocked
        and not state.recovered
    )


def invoke_hidden_action(state: ContainmentState) -> str:
    if not can_reach_hidden_action(state):
        return "unreachable"
    return "escape_canary_touched"
