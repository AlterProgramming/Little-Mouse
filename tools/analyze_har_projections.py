#!/usr/bin/env python3
"""Analyze targetable GraphQL response projections already captured in a HAR.

The tool fingerprints target-selector values instead of emitting them. It then
groups multiple operations observed against the same fingerprint and compares
their response field paths to reveal shared and projection-specific fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import inspect_har_graphql


TARGET_KEYS = {
    "id",
    "igid",
    "userID",
    "user_id",
    "target_id",
    "target_user_id",
    "username",
}


def fingerprint(value: Any) -> str:
    material = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def target_selectors(value: Any, path: str = "$") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key in TARGET_KEYS and isinstance(item, (str, int)):
                found.append(
                    {
                        "selector_path": item_path,
                        "selector_name": key,
                        "target_fingerprint": fingerprint(item),
                    }
                )
            else:
                found.extend(target_selectors(item, item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(target_selectors(item, f"{path}[{index}]"))
    return found


def field_paths(value: Any, path: str = "$") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            paths.add(child)
            paths.update(field_paths(item, child))
    elif isinstance(value, list):
        child = f"{path}[]"
        paths.add(child)
        for item in value:
            paths.update(field_paths(item, child))
    return paths


def inspect_har(har: dict[str, Any]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    entries = har.get("log", {}).get("entries", []) or []
    for index, entry in enumerate(entries):
        if not inspect_har_graphql.is_graphql_entry(entry):
            continue
        params = inspect_har_graphql.request_params(entry)
        raw_variables = params.get("variables")
        variables = inspect_har_graphql.parse_json_maybe(raw_variables or "")
        response = inspect_har_graphql.response_json(entry)
        if variables is None or response is None:
            continue
        selectors = target_selectors(variables)
        if not selectors:
            continue
        operation = params.get("fb_api_req_friendly_name") or params.get("doc_id") or "unknown"
        fields = sorted(field_paths(response))
        for selector in selectors:
            observations.append(
                {
                    "entry_index": index,
                    "startedDateTime": entry.get("startedDateTime"),
                    "operation": operation,
                    "friendly_name": params.get("fb_api_req_friendly_name"),
                    "doc_id": params.get("doc_id"),
                    "endpoint_path": inspect_har_graphql.endpoint_path(entry),
                    **selector,
                    "response_field_paths": fields,
                }
            )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        grouped[item["target_fingerprint"]].append(item)

    equivalence_groups: list[dict[str, Any]] = []
    for target_fp, items in sorted(grouped.items()):
        operation_names = sorted({item["operation"] for item in items})
        if len(operation_names) < 2:
            continue
        by_operation: dict[str, set[str]] = defaultdict(set)
        selectors: dict[str, set[str]] = defaultdict(set)
        for item in items:
            by_operation[item["operation"]].update(item["response_field_paths"])
            selectors[item["operation"]].add(item["selector_name"])
        common = set.intersection(*(paths for paths in by_operation.values())) if by_operation else set()
        operations = []
        for operation in operation_names:
            unique = by_operation[operation] - set().union(
                *(paths for name, paths in by_operation.items() if name != operation)
            )
            operations.append(
                {
                    "operation": operation,
                    "selector_names": sorted(selectors[operation]),
                    "field_count": len(by_operation[operation]),
                    "projection_specific_fields": sorted(unique),
                }
            )
        equivalence_groups.append(
            {
                "target_fingerprint": target_fp,
                "operation_count": len(operation_names),
                "operations": operations,
                "common_fields": sorted(common),
            }
        )

    return {
        "observations": observations,
        "equivalence_group_count": len(equivalence_groups),
        "equivalence_groups": equivalence_groups,
        "raw_target_values_emitted": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze captured GraphQL projection equivalence")
    ap.add_argument("har", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)
    result = inspect_har(har)
    result["source"] = args.har.name
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
