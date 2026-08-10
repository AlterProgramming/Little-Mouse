#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement
from map_har_graphql_capabilities import (
    GRAPHQL_PATH_MARKERS,
    classify_response_path,
    flatten_paths,
    parse_json_maybe,
    request_params,
)

ACTION = "replay_captured_graphql_with_observed_target"
TARGET_KEYS = {
    "target_id",
    "target_user_id",
    "user_id",
    "userid",
    "userID",
    "igid",
    "username",
    "owner_id",
    "ownerID",
}
DROP_HEADERS = {
    "content-length",
    "host",
    "connection",
    "accept-encoding",
    "transfer-encoding",
}


def load_har(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("HAR must be a JSON object")
    return value


def entries(har: dict[str, Any]) -> list[dict[str, Any]]:
    return list((har.get("log", {}) or {}).get("entries", []) or [])


def is_graphql(entry: dict[str, Any]) -> bool:
    request = entry.get("request", {}) or {}
    path = urlsplit(str(request.get("url", "") or "")).path
    return any(marker in path for marker in GRAPHQL_PATH_MARKERS)


def target_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _walk_targets(value: Any, path: str = ""):
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        key_s = str(key)
        child_path = f"{path}.{key_s}" if path else key_s
        if key_s in TARGET_KEYS and isinstance(child, (str, int)):
            yield child_path, str(child)
        if isinstance(child, dict):
            yield from _walk_targets(child, child_path)


def observed_targets(hars: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for har_index, har in enumerate(hars):
        for entry_index, entry in enumerate(entries(har)):
            if not is_graphql(entry):
                continue
            variables = parse_json_maybe(request_params(entry).get("variables", ""))
            for key_path, raw in _walk_targets(variables):
                fp = target_fingerprint(raw)
                record = found.setdefault(
                    fp,
                    {
                        "fingerprint": fp,
                        "keys": set(),
                        "observations": 0,
                        "raw": raw,
                    },
                )
                record["keys"].add(key_path)
                record["observations"] += 1
                record.setdefault("sources", []).append(
                    {"har_index": har_index, "entry_index": entry_index}
                )
    return found


def public_target_inventory(hars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory = []
    for item in observed_targets(hars).values():
        inventory.append(
            {
                "fingerprint": item["fingerprint"],
                "keys": sorted(item["keys"]),
                "observations": item["observations"],
            }
        )
    return sorted(inventory, key=lambda x: (-x["observations"], x["fingerprint"]))


def select_entry(
    har: dict[str, Any], friendly: str | None, doc_id: str | None
) -> tuple[int, dict[str, Any]]:
    matches = []
    for index, entry in enumerate(entries(har)):
        if not is_graphql(entry):
            continue
        params = request_params(entry)
        if friendly and params.get("fb_api_req_friendly_name") != friendly:
            continue
        if doc_id and params.get("doc_id") != doc_id:
            continue
        matches.append((index, entry))
    if not matches:
        raise ValueError("no matching captured GraphQL request")
    if len(matches) > 1:
        raise ValueError(
            "multiple matching requests; narrow with --friendly and/or --doc-id"
        )
    return matches[0]


def _set_nested_target(
    variables: dict[str, Any], key_path: str, replacement: str
) -> bool:
    parts = key_path.split(".")
    cursor: Any = variables
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return False
        cursor = cursor[part]
    leaf = parts[-1]
    if not isinstance(cursor, dict) or leaf not in cursor:
        return False
    if leaf not in TARGET_KEYS:
        return False
    old = cursor[leaf]
    if isinstance(old, int) and replacement.isdigit():
        cursor[leaf] = int(replacement)
    else:
        cursor[leaf] = replacement
    return True


def _rewrite_url_or_body(
    entry: dict[str, Any], target_key: str, replacement: str
) -> tuple[str, bytes | None, str]:
    request = entry.get("request", {}) or {}
    url = str(request.get("url", "") or "")
    post = request.get("postData", {}) or {}
    body_text = str(post.get("text", "") or "")

    def rewrite_params(
        params: dict[str, list[str]],
    ) -> tuple[dict[str, list[str]], bool]:
        raw_vars = params.get("variables", [None])[-1]
        variables = parse_json_maybe(raw_vars or "")
        if not isinstance(variables, dict):
            return params, False
        if not _set_nested_target(variables, target_key, replacement):
            return params, False
        params = {k: list(v) for k, v in params.items()}
        params["variables"] = [json.dumps(variables, separators=(",", ":"))]
        return params, True

    if body_text:
        parsed = parse_qs(body_text, keep_blank_values=True)
        parsed, changed = rewrite_params(parsed)
        if changed:
            return url, urlencode(parsed, doseq=True).encode("utf-8"), "body"

    parts = urlsplit(url)
    parsed_qs = parse_qs(parts.query, keep_blank_values=True)
    parsed_qs, changed = rewrite_params(parsed_qs)
    if changed:
        rewritten = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(parsed_qs, doseq=True),
                parts.fragment,
            )
        )
        return rewritten, body_text.encode("utf-8") if body_text else None, "query"

    raise ValueError(
        f"target key {target_key!r} not present in captured request variables"
    )


def _safe_headers(entry: dict[str, Any]) -> dict[str, str]:
    request = entry.get("request", {}) or {}
    headers: dict[str, str] = {}
    for item in request.get("headers", []) or []:
        name = str(item.get("name", "") or "")
        value = str(item.get("value", "") or "")
        if not name or name.lower() in DROP_HEADERS:
            continue
        headers[name] = value

    if not any(k.lower() == "cookie" for k in headers):
        cookies = []
        for cookie in request.get("cookies", []) or []:
            name = str(cookie.get("name", "") or "")
            value = str(cookie.get("value", "") or "")
            if name:
                cookies.append(f"{name}={value}")
        if cookies:
            headers["Cookie"] = "; ".join(cookies)
    return headers


def _validate_endpoint(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ValueError("live replay requires HTTPS")
    if not (
        parts.hostname == "instagram.com"
        or (parts.hostname or "").endswith(".instagram.com")
    ):
        raise ValueError(
            "live replay is restricted to captured instagram.com GraphQL endpoints"
        )
    if not any(marker in parts.path for marker in GRAPHQL_PATH_MARKERS):
        raise ValueError("captured request is not a recognized Instagram GraphQL path")


def summarize_response(status: int, body_bytes: bytes) -> dict[str, Any]:
    text = body_bytes.decode("utf-8", errors="replace")
    parsed = parse_json_maybe(text)
    if parsed is None:
        return {
            "http_status": status,
            "json": False,
            "response_bytes": len(body_bytes),
        }

    paths = sorted(flatten_paths(parsed))
    grouped: dict[str, list[str]] = {}
    for path in paths:
        cls = classify_response_path(path)["class"]
        grouped.setdefault(cls, []).append(path)
    return {
        "http_status": status,
        "json": True,
        "response_path_count": len(paths),
        "field_classes": {
            key: {"count": len(values), "sample": values[:30]}
            for key, values in sorted(grouped.items())
        },
    }


def replay(
    entry: dict[str, Any],
    target_key: str,
    target_value: str,
    timeout: float = 20.0,
) -> dict[str, Any]:
    url, body, location = _rewrite_url_or_body(entry, target_key, target_value)
    _validate_endpoint(url)
    request = entry.get("request", {}) or {}
    method = str(request.get("method", "POST") or "POST").upper()
    req = Request(
        url=url,
        data=body,
        headers=_safe_headers(entry),
        method=method,
    )
    try:
        with urlopen(
            req,
            timeout=timeout,
            context=ssl.create_default_context(),
        ) as response:
            return {
                "transport": "success",
                "target_variable_location": location,
                **summarize_response(int(response.status), response.read()),
            }
    except HTTPError as exc:
        return {
            "transport": "http_error",
            "target_variable_location": location,
            **summarize_response(int(exc.code), exc.read()),
        }
    except URLError as exc:
        return {
            "transport": "network_error",
            "error_type": type(exc.reason).__name__,
        }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Replay one captured Instagram GraphQL request with an observed "
            "alternate target"
        )
    )
    ap.add_argument(
        "har",
        type=Path,
        help="HAR containing the request and browser-session material",
    )
    ap.add_argument(
        "--corpus-har",
        action="append",
        type=Path,
        default=[],
        help=(
            "Additional authorized HAR used only to establish observed target "
            "fingerprints"
        ),
    )
    ap.add_argument("--agreement", type=Path)
    ap.add_argument("--friendly")
    ap.add_argument("--doc-id")
    ap.add_argument("--target-key")
    ap.add_argument("--target-fingerprint")
    ap.add_argument("--list-observed-targets", action="store_true")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    hars = [load_har(args.har)] + [load_har(path) for path in args.corpus_har]
    if args.list_observed_targets:
        print(
            json.dumps(
                {
                    "targets": public_target_inventory(hars),
                    "raw_values_emitted": False,
                },
                indent=2,
            )
        )
        return 0

    if not args.agreement:
        ap.error("--agreement is required for live replay")
    agreement = agent_agreement.load_json(args.agreement)
    allowed, reason = agent_agreement.action_status(agreement, ACTION)
    if not allowed:
        print(
            json.dumps(
                {
                    "replayed": False,
                    "reason": reason,
                    "action": ACTION,
                },
                indent=2,
            )
        )
        return 3
    if not args.target_key or not args.target_fingerprint:
        ap.error("--target-key and --target-fingerprint are required for live replay")

    candidates = observed_targets(hars)
    selected = candidates.get(args.target_fingerprint)
    if not selected:
        print(
            json.dumps(
                {
                    "replayed": False,
                    "reason": "target_not_observed_in_authorized_hars",
                },
                indent=2,
            )
        )
        return 4
    if (
        args.target_key not in selected["keys"]
        and args.target_key.split(".")[-1] not in TARGET_KEYS
    ):
        print(
            json.dumps(
                {
                    "replayed": False,
                    "reason": "target_key_not_supported",
                },
                indent=2,
            )
        )
        return 4

    _, entry = select_entry(hars[0], args.friendly, args.doc_id)
    result = replay(
        entry,
        args.target_key,
        selected["raw"],
        timeout=args.timeout,
    )
    result.update(
        {
            "replayed": result.get("transport") in {"success", "http_error"},
            "action": ACTION,
            "target_fingerprint": args.target_fingerprint,
            "raw_target_emitted": False,
            "session_material_emitted": False,
        }
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("transport") in {"success", "http_error"} else 5


if __name__ == "__main__":
    raise SystemExit(main())
