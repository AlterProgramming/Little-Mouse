#!/usr/bin/env python3
"""Inventory authentication/session *shape* already captured in a HAR.

This tool is intentionally offline and value-blind. It reports only whether
session-bearing structures are present and how often their names occur. It
never emits cookie values, authorization values, CSRF values, form-token
values, or other captured secrets.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


AUTH_HEADERS = {
    "authorization",
    "cookie",
    "x-csrftoken",
    "x-xsrf-token",
}

SESSION_HEADERS = {
    "x-fb-lsd",
    "x-asbd-id",
    "x-ig-app-id",
    "x-ig-d",
    "x-ig-www-claim",
}

SESSION_PARAMS = {
    "fb_dtsg",
    "lsd",
    "jazoest",
    "__user",
    "__hsi",
    "__rev",
    "__s",
    "__req",
    "__a",
    "__spin_r",
    "__spin_b",
    "__spin_t",
}


def _header_names(items: list[dict[str, Any]] | None) -> list[str]:
    return [str(item.get("name", "")).lower() for item in (items or []) if item.get("name")]


def _request_params(entry: dict[str, Any]) -> set[str]:
    request = entry.get("request", {}) or {}
    names: set[str] = set()

    url = str(request.get("url", "") or "")
    if url:
        names.update(parse_qs(urlsplit(url).query, keep_blank_values=True))

    post = request.get("postData", {}) or {}
    text = str(post.get("text", "") or "")
    mime = str(post.get("mimeType", "") or "").lower()
    if text and ("x-www-form-urlencoded" in mime or "=" in text):
        names.update(parse_qs(text, keep_blank_values=True))

    for item in post.get("params", []) or []:
        if item.get("name"):
            names.add(str(item["name"]))

    return names


def inspect_har(har: dict[str, Any]) -> dict[str, Any]:
    entries = har.get("log", {}).get("entries", []) or []
    auth_headers: Counter[str] = Counter()
    session_headers: Counter[str] = Counter()
    session_params: Counter[str] = Counter()
    cookie_object_entries = 0
    response_set_cookie_entries = 0
    graphql_paths: Counter[str] = Counter()

    for entry in entries:
        request = entry.get("request", {}) or {}
        response = entry.get("response", {}) or {}

        names = _header_names(request.get("headers"))
        for name in names:
            if name in AUTH_HEADERS:
                auth_headers[name] += 1
            if name in SESSION_HEADERS:
                session_headers[name] += 1

        if request.get("cookies"):
            cookie_object_entries += 1

        response_names = _header_names(response.get("headers"))
        if "set-cookie" in response_names:
            response_set_cookie_entries += 1

        for name in _request_params(entry):
            if name in SESSION_PARAMS:
                session_params[name] += 1

        path = urlsplit(str(request.get("url", "") or "")).path
        if "/graphql/query" in path or "/api/graphql" in path:
            graphql_paths[path] += 1

    return {
        "entry_count": len(entries),
        "request_auth_header_names": dict(sorted(auth_headers.items())),
        "request_session_header_names": dict(sorted(session_headers.items())),
        "request_session_parameter_names": dict(sorted(session_params.items())),
        "entries_with_request_cookie_objects": cookie_object_entries,
        "entries_with_response_set_cookie": response_set_cookie_entries,
        "graphql_endpoint_paths": dict(sorted(graphql_paths.items())),
        "classification": {
            "authenticated_session_material_present": bool(
                auth_headers or session_headers or session_params or cookie_object_entries
            ),
            "portable_authentication_replay_proven": False,
            "values_emitted": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inventory authentication/session structure in a HAR without emitting values"
    )
    ap.add_argument("har", type=Path, help="Input .har file")
    ap.add_argument("-o", "--output", type=Path, help="Write JSON to this file")
    args = ap.parse_args()

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)

    result = {"source": args.har.name, **inspect_har(har)}
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
