#!/usr/bin/env python3
"""Recover GraphQL request/response schemas already captured in a HAR.

This is a Little Mouse computer-use workflow. It is intentionally offline:
the tool reads only the supplied HAR, never replays requests, and never exports
cookies, authorization headers, CSRF values, or other session material.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]


GRAPHQL_PATH_MARKERS = ("/graphql/query", "/api/graphql")


def parse_form(text: str) -> dict[str, str]:
    parsed = parse_qs(text or "", keep_blank_values=True)
    return {k: values[-1] if values else "" for k, values in parsed.items()}


def request_params(entry: dict[str, Any]) -> dict[str, str]:
    request = entry.get("request", {}) or {}
    params: dict[str, str] = {}

    url = str(request.get("url", "") or "")
    if url:
        params.update(
            {
                k: values[-1]
                for k, values in parse_qs(
                    urlsplit(url).query, keep_blank_values=True
                ).items()
            }
        )

    post = request.get("postData", {}) or {}
    text = str(post.get("text", "") or "")
    mime = str(post.get("mimeType", "") or "").lower()
    if text and ("x-www-form-urlencoded" in mime or "=" in text):
        params.update(parse_form(text))

    for item in post.get("params", []) or []:
        name = item.get("name")
        if name:
            params[str(name)] = str(item.get("value", "") or "")

    return params


def is_graphql_entry(entry: dict[str, Any]) -> bool:
    url = str((entry.get("request", {}) or {}).get("url", "") or "")
    path = urlsplit(url).path
    return any(marker in path for marker in GRAPHQL_PATH_MARKERS)


def parse_json_maybe(text: str) -> Any | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("for (;;);"):
        text = text[len("for (;;);") :].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def response_json(entry: dict[str, Any]) -> Any | None:
    response = entry.get("response", {}) or {}
    content = response.get("content", {}) or {}
    text = content.get("text")
    if text is None:
        return None
    return parse_json_maybe(str(text))


def merge_schema(a: Any, b: Any) -> Any:
    if a == b:
        return a

    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(set(a) | set(b))
        merged: dict[str, Any] = {}
        for key in keys:
            if key in a and key in b:
                merged[key] = merge_schema(a[key], b[key])
            elif key in a:
                merged[key] = {"optional": a[key]}
            else:
                merged[key] = {"optional": b[key]}
        return merged

    options: list[Any] = []
    for item in (a, b):
        if (
            isinstance(item, dict)
            and set(item) == {"one_of"}
            and isinstance(item["one_of"], list)
        ):
            options.extend(item["one_of"])
        else:
            options.append(item)

    unique: list[Any] = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return {"one_of": unique}


def infer_schema(value: Any) -> Any:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"

    if isinstance(value, dict):
        return {str(k): infer_schema(v) for k, v in sorted(value.items())}

    if isinstance(value, list):
        if not value:
            return {"array": "unknown"}
        merged = infer_schema(value[0])
        for item in value[1:]:
            merged = merge_schema(merged, infer_schema(item))
        return {"array": merged}

    return type(value).__name__


def observed_variables(params: dict[str, str]) -> tuple[Any, Any]:
    raw = params.get("variables")
    if raw is None:
        return None, None
    value = parse_json_maybe(raw)
    if value is None:
        return raw, "unparsed"
    return value, infer_schema(value)


def extract_record(
    index: int, entry: dict[str, Any], include_values: bool
) -> dict[str, Any]:
    request = entry.get("request", {}) or {}
    params = request_params(entry)
    variables, variable_schema = observed_variables(params)
    body = response_json(entry)

    record: dict[str, Any] = {
        "entry_index": index,
        "startedDateTime": entry.get("startedDateTime"),
        "method": request.get("method"),
        "endpoint_path": urlsplit(str(request.get("url", "") or "")).path,
        "friendly_name": params.get("fb_api_req_friendly_name"),
        "doc_id": params.get("doc_id"),
        "variables_schema": variable_schema,
        "response_schema": infer_schema(body) if body is not None else None,
    }
    if include_values:
        record["variables"] = variables
    return record


def matches(
    record: dict[str, Any],
    friendly: str | None,
    doc_id: str | None,
    contains: str | None,
) -> bool:
    if friendly and str(record.get("friendly_name") or "") != friendly:
        return False
    if doc_id and str(record.get("doc_id") or "") != doc_id:
        return False
    if contains:
        haystack = json.dumps(record, sort_keys=True).lower()
        if contains.lower() not in haystack:
            return False
    return True


def require_agreement(path: Path | None, action: str) -> str:
    if path is None:
        raise ValueError(f"--agreement is required for {action}")
    if load_json is None or action_status is None or agreement_id is None:
        raise ValueError("agent_agreement.py must be available beside this tool")
    agreement = load_json(path)
    allowed, reason = action_status(agreement, action)
    if not allowed:
        raise ValueError(f"agreement does not allow {action}: {reason}")
    return agreement_id(agreement)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Recover observed GraphQL doc_ids, variable schemas, and response "
            "schemas from a HAR"
        )
    )
    ap.add_argument("har", type=Path, help="Input .har file")
    ap.add_argument("--friendly", help="Exact fb_api_req_friendly_name filter")
    ap.add_argument("--doc-id", help="Exact doc_id filter")
    ap.add_argument(
        "--contains",
        help="Case-insensitive substring filter over extracted metadata/schema",
    )
    ap.add_argument(
        "--include-values",
        action="store_true",
        help=(
            "Include observed GraphQL variable values; requires an agent-owned "
            "agreement"
        ),
    )
    ap.add_argument(
        "--agreement",
        type=Path,
        help="Agent-owned agreement JSON authorizing value-bearing inspection",
    )
    ap.add_argument(
        "-o", "--output", type=Path, help="Write JSON to this file instead of stdout"
    )
    args = ap.parse_args()

    receipt_agreement_id = None
    if args.include_values:
        try:
            receipt_agreement_id = require_agreement(
                args.agreement, "inspect_captured_graphql_values"
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)

    records = []
    for index, entry in enumerate(har.get("log", {}).get("entries", [])):
        if not is_graphql_entry(entry):
            continue
        record = extract_record(index, entry, args.include_values)
        if matches(record, args.friendly, args.doc_id, args.contains):
            records.append(record)

    result: dict[str, Any] = {
        "source": args.har.name,
        "graphql_entries": len(records),
        "records": records,
    }
    if receipt_agreement_id:
        result["agreement_id"] = receipt_agreement_id

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
