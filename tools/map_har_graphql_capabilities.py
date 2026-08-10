#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

GRAPHQL_PATH_MARKERS = ("/graphql/query", "/api/graphql")
SENSITIVE_KEYS = {"fb_dtsg", "lsd", "jazoest", "csrf", "cookie", "authorization"}
TARGET_KEY_RE = re.compile(
    r"(?:^|_)(?:id|ids|igid|userid|user|users|username|target|owner|media|thread|cursor|count|first|last|after|before)(?:$|_)",
    re.I,
)


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


def parse_form(text: str) -> dict[str, str]:
    parsed = parse_qs(text or "", keep_blank_values=True)
    return {k: values[-1] if values else "" for k, values in parsed.items()}


def request_params(entry: dict[str, Any]) -> dict[str, str]:
    request = entry.get("request", {}) or {}
    params: dict[str, str] = {}
    url = str(request.get("url", "") or "")
    params.update(
        {
            k: values[-1]
            for k, values in parse_qs(urlsplit(url).query, keep_blank_values=True).items()
            if values
        }
    )
    post = request.get("postData", {}) or {}
    text = str(post.get("text", "") or "")
    if text:
        params.update(parse_form(text))
    for item in post.get("params", []) or []:
        if item.get("name"):
            params.setdefault(str(item["name"]), str(item.get("value", "") or ""))
    return params


def is_graphql_entry(entry: dict[str, Any]) -> bool:
    path = urlsplit(str((entry.get("request", {}) or {}).get("url", "") or "")).path
    return any(marker in path for marker in GRAPHQL_PATH_MARKERS)


def infer_schema(value: Any) -> Any:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        kinds = []
        for item in value[:50]:
            schema = infer_schema(item)
            if schema not in kinds:
                kinds.append(schema)
        return {"array": kinds[0] if len(kinds) == 1 else {"one_of": kinds}}
    if isinstance(value, dict):
        return {str(k): infer_schema(v) for k, v in sorted(value.items())}
    return type(value).__name__


def flatten_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths |= flatten_paths(child, path)
    elif isinstance(value, list):
        path = f"{prefix}[]" if prefix else "[]"
        paths.add(path)
        for child in value[:20]:
            paths |= flatten_paths(child, path)
    return paths


def collect_selector_identifiers(variables: Any) -> list[str]:
    """Collect schema-like setting/storage identifiers without retaining user values."""
    found: set[str] = set()
    if not isinstance(variables, dict):
        return []
    for key, value in variables.items():
        lowered = str(key).lower()
        if lowered.endswith(("_setting_ids", "_server_values_ids", "_storage_ids")) and isinstance(value, list):
            found.update(str(item) for item in value if isinstance(item, str) and item)
        elif lowered in {"storage_id", "setting_id"} and isinstance(value, str) and value:
            found.add(value)
    return sorted(found)


def candidate_axes(variables: Any) -> list[str]:
    axes: set[str] = set()
    if not isinstance(variables, dict):
        return []
    for key, value in variables.items():
        key_s = str(key)
        if TARGET_KEY_RE.search(key_s) or key_s.lower() in {"userid", "igid"}:
            axes.add(key_s)
        if isinstance(value, dict):
            for child in value:
                child_s = str(child)
                if TARGET_KEY_RE.search(child_s) or child_s.lower() in {"userid", "igid"}:
                    axes.add(f"{key_s}.{child_s}")
    return sorted(axes)


def classify(name: str) -> str:
    lowered = name.lower()
    rules = [
        ("feed", ("feedtimeline", "feed")),
        ("stories", ("stories", "story")),
        ("recommendations", ("suggested", "recommend", "omnipicker", "chaining")),
        ("messaging", ("igd", "direct", "thread", "inbox", "chat")),
        ("profile", ("profilepage", "profileposts", "hovercard", "profile")),
        ("account_state", ("accountstatus", "account_status", "disablement", "featurelimit", "restriction")),
        ("settings", ("setting", "preference", "privacy", "sensitivecontent", "notification")),
        ("intervention", ("quickpromotion", "promotion")),
        ("auth_infra", ("frcookie", "cookie", "token")),
    ]
    for label, needles in rules:
        if any(needle in lowered for needle in needles):
            return label
    return "other"


def operation_kind(name: str) -> str:
    if name.endswith("Mutation"):
        return "mutation"
    if name.endswith("Query"):
        return "query"
    return "unknown"


def load_entries(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        har = json.load(handle)
    return har.get("log", {}).get("entries", []) or []


def build(paths: list[Path]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    files_seen: list[str] = []
    total_entries = 0
    graphql_entries = 0

    for path in paths:
        files_seen.append(path.name)
        for entry in load_entries(path):
            total_entries += 1
            if not is_graphql_entry(entry):
                continue
            graphql_entries += 1
            request = entry.get("request", {}) or {}
            params = request_params(entry)
            friendly_name = params.get("fb_api_req_friendly_name") or "<unnamed>"
            doc_id = params.get("doc_id") or ""
            endpoint = urlsplit(str(request.get("url", "") or "")).path
            key = (friendly_name, doc_id, endpoint)
            group = groups.setdefault(
                key,
                {
                    "friendly_name": friendly_name,
                    "doc_id": doc_id or None,
                    "endpoint_path": endpoint,
                    "kind": operation_kind(friendly_name),
                    "family": classify(friendly_name),
                    "observations": 0,
                    "captures": set(),
                    "variable_keys": set(),
                    "variable_key_frequency": Counter(),
                    "variable_schemas": defaultdict(set),
                    "response_paths": set(),
                    "candidate_axes": set(),
                    "selector_identifiers": set(),
                    "statuses": Counter(),
                },
            )
            group["observations"] += 1
            group["captures"].add(path.name)
            group["statuses"][str((entry.get("response", {}) or {}).get("status"))] += 1

            variables = parse_json_maybe(params.get("variables", ""))
            if isinstance(variables, dict):
                group["candidate_axes"].update(candidate_axes(variables))
                group["selector_identifiers"].update(collect_selector_identifiers(variables))
                for variable_key, variable_value in variables.items():
                    if str(variable_key).lower() in SENSITIVE_KEYS:
                        continue
                    group["variable_keys"].add(str(variable_key))
                    group["variable_key_frequency"][str(variable_key)] += 1
                    group["variable_schemas"][str(variable_key)].add(
                        json.dumps(infer_schema(variable_value), sort_keys=True)
                    )

            content = ((entry.get("response", {}) or {}).get("content", {}) or {}).get("text")
            body = parse_json_maybe(str(content)) if content is not None else None
            if body is not None:
                group["response_paths"] |= flatten_paths(body)

    operations = []
    for group in groups.values():
        operations.append(
            {
                "friendly_name": group["friendly_name"],
                "doc_id": group["doc_id"],
                "endpoint_path": group["endpoint_path"],
                "kind": group["kind"],
                "family": group["family"],
                "observations": group["observations"],
                "capture_count": len(group["captures"]),
                "captures": sorted(group["captures"]),
                "variable_keys": sorted(group["variable_keys"]),
                "candidate_expansion_axes": sorted(group["candidate_axes"]),
                "selector_identifiers": sorted(group["selector_identifiers"]),
                "variable_schemas": {
                    key: [json.loads(item) for item in sorted(values)]
                    for key, values in sorted(group["variable_schemas"].items())
                },
                "response_path_count": len(group["response_paths"]),
                "response_paths_sample": sorted(group["response_paths"])[:80],
                "statuses": dict(sorted(group["statuses"].items())),
            }
        )

    operations.sort(
        key=lambda item: (
            item["family"],
            -item["observations"],
            item["friendly_name"],
            item["doc_id"] or "",
        )
    )
    family_counts = Counter(operation["family"] for operation in operations)
    family_observations = Counter()
    for operation in operations:
        family_observations[operation["family"]] += operation["observations"]

    return {
        "captures": files_seen,
        "har_entries_scanned": total_entries,
        "graphql_entries": graphql_entries,
        "unique_persisted_operations": len(operations),
        "families": {
            family: {
                "operations": family_counts[family],
                "observations": family_observations[family],
            }
            for family in sorted(family_counts)
        },
        "operations": operations,
        "note": (
            "Capability map is observational: candidate_expansion_axes are accepted "
            "variable names observed in captured requests, not proof that arbitrary "
            "values are authorized or meaningful. Selector identifiers preserve "
            "setting/storage schema names but not user values."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an observational GraphQL capability map from HAR captures"
    )
    parser.add_argument("hars", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    result = build(args.hars)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
