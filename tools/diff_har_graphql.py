#!/usr/bin/env python3
"""Compare observed GraphQL shapes across two HAR captures.

The comparison is offline and value-blind. It matches captured operations by
friendly name and/or persisted doc_id, merges the observed variable/response
schemas within each capture, and reports added, removed, or changed schema
paths. It never emits captured variable values or authentication material.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import inspect_har_graphql


def _load_records(path: Path, friendly: str | None, doc_id: str | None) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        har = json.load(f)

    records: list[dict[str, Any]] = []
    for index, entry in enumerate(har.get("log", {}).get("entries", []) or []):
        if not inspect_har_graphql.is_graphql_entry(entry):
            continue
        record = inspect_har_graphql.extract_record(index, entry, include_values=False)
        if inspect_har_graphql.matches(record, friendly, doc_id, None):
            records.append(record)
    return records


def _merge(records: list[dict[str, Any]], key: str) -> Any:
    schemas = [record.get(key) for record in records if record.get(key) is not None]
    if not schemas:
        return None
    merged = schemas[0]
    for schema in schemas[1:]:
        merged = inspect_har_graphql.merge_schema(merged, schema)
    return merged


def _flatten(value: Any, prefix: str = "$") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(value, dict):
        if not value:
            out[prefix] = "{}"
            return out
        for key, child in sorted(value.items()):
            marker = "[]" if key == "array" else f".{key}"
            out.update(_flatten(child, prefix + marker))
        return out
    if isinstance(value, list):
        if not value:
            out[prefix] = "[]"
            return out
        for index, child in enumerate(value):
            out.update(_flatten(child, f"{prefix}[{index}]"))
        return out
    out[prefix] = json.dumps(value, sort_keys=True)
    return out


def schema_diff(before: Any, after: Any) -> dict[str, Any]:
    left = _flatten(before)
    right = _flatten(after)
    added = sorted(path for path in right if path not in left)
    removed = sorted(path for path in left if path not in right)
    changed = [
        {"path": path, "before": left[path], "after": right[path]}
        for path in sorted(set(left) & set(right))
        if left[path] != right[path]
    ]
    return {"added": added, "removed": removed, "changed": changed}


def compare(
    before_path: Path,
    after_path: Path,
    friendly: str | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    before_records = _load_records(before_path, friendly, doc_id)
    after_records = _load_records(after_path, friendly, doc_id)

    before_variables = _merge(before_records, "variables_schema")
    after_variables = _merge(after_records, "variables_schema")
    before_response = _merge(before_records, "response_schema")
    after_response = _merge(after_records, "response_schema")

    return {
        "before": {"source": before_path.name, "matching_entries": len(before_records)},
        "after": {"source": after_path.name, "matching_entries": len(after_records)},
        "filter": {"friendly_name": friendly, "doc_id": doc_id},
        "variables_schema_diff": schema_diff(before_variables, after_variables),
        "response_schema_diff": schema_diff(before_response, after_response),
        "values_emitted": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare observed GraphQL schemas across two HAR captures"
    )
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--friendly", help="Exact fb_api_req_friendly_name filter")
    ap.add_argument("--doc-id", help="Exact persisted doc_id filter")
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    result = compare(args.before, args.after, args.friendly, args.doc_id)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
