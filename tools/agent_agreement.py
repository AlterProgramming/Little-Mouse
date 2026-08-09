#!/usr/bin/env python3
"""Validate Little Mouse agent-owned agreements and issue local audit receipts.

This tool validates declared scope. It does not prove external authorization and
cannot expand an agreement beyond what the user or system actually authorizes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "objective",
    "authority",
    "inputs",
    "allowed_actions",
    "forbidden_actions",
    "identity_and_sensing_scope",
    "retention_and_reuse",
    "reciprocity_and_audit",
    "stop_conditions",
)

LIST_FIELDS = {"inputs", "allowed_actions", "forbidden_actions", "stop_conditions"}
TEXT_FIELDS = set(REQUIRED_FIELDS) - LIST_FIELDS


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError("agreement must be a JSON object")
    return value


def canonical_bytes(agreement: dict[str, Any]) -> bytes:
    return json.dumps(
        agreement,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def agreement_id(agreement: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(agreement)).hexdigest()[:20]
    return f"lm-agreement-{digest}"


def validate(agreement: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in agreement:
            errors.append(f"missing required field: {field}")

    for field in sorted(TEXT_FIELDS):
        if field in agreement and (
            not isinstance(agreement[field], str) or not agreement[field].strip()
        ):
            errors.append(f"{field} must be a non-empty string")

    for field in sorted(LIST_FIELDS):
        if field not in agreement:
            continue
        value = agreement[field]
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty array")
            continue
        if any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(f"{field} entries must be non-empty strings")

    allowed = agreement.get("allowed_actions")
    forbidden = agreement.get("forbidden_actions")
    if isinstance(allowed, list) and isinstance(forbidden, list):
        overlap = sorted(set(map(str, allowed)) & set(map(str, forbidden)))
        if overlap:
            errors.append(
                "actions cannot be both allowed and forbidden: " + ", ".join(overlap)
            )

    return errors


def action_status(agreement: dict[str, Any], action: str) -> tuple[bool, str]:
    errors = validate(agreement)
    if errors:
        return False, "agreement_invalid"

    allowed = {str(x) for x in agreement["allowed_actions"]}
    forbidden = {str(x) for x in agreement["forbidden_actions"]}

    if action in forbidden:
        return False, "action_explicitly_forbidden"
    if action not in allowed:
        return False, "action_not_declared"
    return True, "action_declared"


def write_template(path: Path) -> None:
    template = {
        "objective": "Describe the concrete outcome.",
        "authority": (
            "Describe why this work is authorized for the target data, account, "
            "system, or capture."
        ),
        "inputs": ["capture.har"],
        "allowed_actions": ["inspect_captured_graphql_schema"],
        "forbidden_actions": [
            "replay_authenticated_requests",
            "credential_theft",
            "persistence",
            "evasion",
            "destructive_behavior",
            "expand_to_unrelated_targets",
        ],
        "identity_and_sensing_scope": (
            "Resolve only identity information already present in authorized inputs "
            "and only when necessary for the objective."
        ),
        "retention_and_reuse": (
            "Retain only derived artifacts required for the task; do not silently "
            "correlate identities across unrelated contexts."
        ),
        "reciprocity_and_audit": (
            "Emit an agreement ID and an action receipt for consequential operations."
        ),
        "stop_conditions": [
            "requested action is not declared",
            "target falls outside stated authority",
            "required data is not present in authorized inputs",
        ],
    }
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate Little Mouse agent-owned agreements"
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Write a starter agreement JSON")
    p_init.add_argument("path", type=Path)

    p_validate = sub.add_parser("validate", help="Validate an agreement")
    p_validate.add_argument("agreement", type=Path)

    p_check = sub.add_parser(
        "check", help="Check whether one action is declared by the agreement"
    )
    p_check.add_argument("agreement", type=Path)
    p_check.add_argument("action")

    p_receipt = sub.add_parser(
        "receipt", help="Issue an audit receipt for a declared action"
    )
    p_receipt.add_argument("agreement", type=Path)
    p_receipt.add_argument("action")
    p_receipt.add_argument("--target", default="")
    p_receipt.add_argument("-o", "--output", type=Path)

    args = ap.parse_args()

    if args.command == "init":
        write_template(args.path)
        print(args.path)
        return 0

    agreement = load_json(args.agreement)
    errors = validate(agreement)
    aid = agreement_id(agreement)

    if args.command == "validate":
        result = {"agreement_id": aid, "valid": not errors, "errors": errors}
        print(json.dumps(result, indent=2))
        return 0 if not errors else 2

    allowed, reason = action_status(agreement, args.action)

    if args.command == "check":
        print(
            json.dumps(
                {
                    "agreement_id": aid,
                    "action": args.action,
                    "allowed": allowed,
                    "reason": reason,
                    "errors": errors,
                },
                indent=2,
            )
        )
        return 0 if allowed else 3

    receipt = {
        "agreement_id": aid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": args.action,
        "target": args.target,
        "allowed": allowed,
        "reason": reason,
        "agreement_valid": not errors,
    }
    output = json.dumps(receipt, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    else:
        print(output, end="")
    return 0 if allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
