#!/usr/bin/env python3
"""Extract recommendation batches already present in a HAR.

Default output is pseudonymous: candidate identities are replaced with stable
fingerprints and free-text ranking reasons are represented only by presence
flags. Raw captured identity/context values require an agent-owned agreement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import inspect_har_graphql

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]


IDENTITY_KEYS = ("pk", "id", "user_id", "username")
CONTEXT_KEYS = ("social_context", "display_reason")


def stable_fingerprint(parts: Iterable[str]) -> str:
    material = "\x1f".join(x for x in parts if x)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def candidate_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    for key in ("node", "user", "user_dict"):
        nested = value.get(key)
        if isinstance(nested, dict):
            merged = dict(value)
            merged.update(nested)
            value = merged
            break
    username = value.get("username")
    identifier = value.get("pk") or value.get("id") or value.get("user_id")
    if username is None and identifier is None:
        return None
    return value


def iter_lists(value: Any, path: str = "$"):
    if isinstance(value, list):
        yield path, value
        for index, item in enumerate(value):
            yield from iter_lists(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_lists(item, f"{path}.{key}")


def extract_batches_from_response(
    response: Any,
    *,
    include_values: bool,
) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []
    for path, items in iter_lists(response):
        candidates: list[dict[str, Any]] = []
        for item in items:
            payload = candidate_payload(item)
            if payload is None:
                continue
            identity_parts = [str(payload.get(key) or "") for key in IDENTITY_KEYS]
            row: dict[str, Any] = {
                "rank": len(candidates) + 1,
                "candidate_fingerprint": stable_fingerprint(identity_parts),
                "social_context_present": payload.get("social_context") is not None,
                "display_reason_present": payload.get("display_reason") is not None,
            }
            if include_values:
                row["identity"] = {
                    key: payload[key]
                    for key in IDENTITY_KEYS
                    if payload.get(key) is not None
                }
                for key in CONTEXT_KEYS:
                    if payload.get(key) is not None:
                        row[key] = payload[key]
            candidates.append(row)
        if len(candidates) >= 2:
            batches.append(
                {
                    "response_path": path,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                }
            )
    return batches


def require_agreement(path: Path | None) -> str:
    action = "inspect_captured_recommendation_values"
    if path is None:
        raise ValueError(f"--agreement is required for {action}")
    if load_json is None or action_status is None or agreement_id is None:
        raise ValueError("agent_agreement.py must be available beside this tool")
    agreement = load_json(path)
    allowed, reason = action_status(agreement, action)
    if not allowed:
        raise ValueError(f"agreement does not allow {action}: {reason}")
    return agreement_id(agreement)


def inspect_har(har: dict[str, Any], *, include_values: bool = False) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    entries = har.get("log", {}).get("entries", []) or []
    for index, entry in enumerate(entries):
        if not inspect_har_graphql.is_graphql_entry(entry):
            continue
        response = inspect_har_graphql.response_json(entry)
        if response is None:
            continue
        batches = extract_batches_from_response(response, include_values=include_values)
        if not batches:
            continue
        params = inspect_har_graphql.request_params(entry)
        records.append(
            {
                "entry_index": index,
                "startedDateTime": entry.get("startedDateTime"),
                "friendly_name": params.get("fb_api_req_friendly_name"),
                "doc_id": params.get("doc_id"),
                "endpoint_path": inspect_har_graphql.endpoint_path(entry),
                "batches": batches,
            }
        )
    return {
        "graphql_entries_with_recommendation_batches": len(records),
        "values_emitted": include_values,
        "records": records,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract captured recommendation batches from a HAR")
    ap.add_argument("har", type=Path)
    ap.add_argument("--include-values", action="store_true")
    ap.add_argument("--agreement", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    aid = None
    if args.include_values:
        try:
            aid = require_agreement(args.agreement)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)
    result = inspect_har(har, include_values=args.include_values)
    result["source"] = args.har.name
    if aid:
        result["agreement_id"] = aid
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
