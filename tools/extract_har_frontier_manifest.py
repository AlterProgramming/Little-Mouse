#!/usr/bin/env python3
"""Build a bounded expansion frontier from identifiers already captured in HAR evidence.

The manifest is the bridge between capture recovery and later web/computer-use expansion:
it preserves stable IDs, aliases, media shortcodes, provenance, and explicit stop conditions
without pretending that newly observed public evidence was part of the original capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from extract_har_world_fabric import (
    enrich_comment_records,
    extract_blocked_records,
    extract_close_friends_surface_records,
    extract_liked_media_records,
    response_maps,
)

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]

IDENTITY_ACTION = "extract_captured_frontier_manifest_identities"


def require_identity_agreement(path: Path | None) -> str:
    if path is None:
        raise ValueError("--agreement is required with --include-identities")
    if load_json is None or action_status is None or agreement_id is None:
        raise ValueError("agent_agreement.py must be available beside this tool")
    agreement = load_json(path)
    allowed, reason = action_status(agreement, IDENTITY_ACTION)
    if not allowed:
        raise ValueError(f"agreement does not allow {IDENTITY_ACTION}: {reason}")
    return agreement_id(agreement)


def capture_timestamp(har: dict[str, Any], entry_index: int) -> str | None:
    entries = har.get("log", {}).get("entries", []) or []
    if entry_index < 0 or entry_index >= len(entries):
        return None
    value = entries[entry_index].get("startedDateTime")
    return str(value) if isinstance(value, str) and value else None


def extract_media_records(har: dict[str, Any]) -> list[dict[str, Any]]:
    """Recover media IDs/codes from any captured response map, not only liked-media history."""
    found: dict[str, dict[str, Any]] = {}
    for entry_index, entry in enumerate(har.get("log", {}).get("entries", []) or []):
        for mapping in response_maps(entry):
            media_id = mapping.get("media_id")
            media_code = mapping.get("media_code")
            if media_id in (None, ""):
                media_id = mapping.get("post_id")
            if not isinstance(media_code, str) or not media_code:
                media_code = mapping.get("post_media_code")
            if media_id in (None, ""):
                continue
            key = str(media_id)
            row = found.setdefault(
                key,
                {
                    "entry_index": entry_index,
                    "media_id": key,
                    "media_code": "",
                    "media_product_type": None,
                    "media_type": None,
                },
            )
            if isinstance(media_code, str) and media_code:
                row["media_code"] = media_code
            for field in ("media_product_type", "media_type"):
                if mapping.get(field) not in (None, ""):
                    row[field] = mapping.get(field)
    for row in extract_liked_media_records(har):
        key = str(row["media_id"])
        merged = found.setdefault(key, dict(row))
        for field, value in row.items():
            if value not in (None, ""):
                merged[field] = value
    return sorted(found.values(), key=lambda row: (int(row.get("entry_index", -1)), row["media_id"]))


def capture_evidence(har: dict[str, Any], capture_name: str) -> dict[str, Any]:
    return {
        "capture_name": capture_name,
        "comments": enrich_comment_records(har),
        "media": extract_media_records(har),
        "blocked": extract_blocked_records(har),
        "surfaced": extract_close_friends_surface_records(har),
        "timestamps": {
            i: capture_timestamp(har, i)
            for i, _ in enumerate(har.get("log", {}).get("entries", []) or [])
        },
    }


def build_frontier_manifest(
    captures: list[dict[str, Any]],
    *,
    include_identities: bool = False,
    agreement: Path | None = None,
    pseudonym_secret: bytes | None = None,
    target_nodes: int = 10_000,
) -> dict[str, Any]:
    if target_nodes <= 0:
        raise ValueError("target_nodes must be positive")
    aid = require_identity_agreement(agreement) if include_identities else None
    secret = pseudonym_secret or os.urandom(32)

    people: dict[str, dict[str, Any]] = {}
    media: dict[str, dict[str, Any]] = {}
    comments: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def pseudo(prefix: str, raw: str) -> str:
        digest = hashlib.sha256(secret + b"\0" + raw.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}_{digest}"

    def person_key(user_id: Any = None, username: Any = None) -> str | None:
        if user_id not in (None, ""):
            return f"uid:{user_id}"
        if isinstance(username, str) and username:
            return f"username:{username.casefold()}"
        return None

    def register_person(*, user_id: Any = None, username: Any = None, capture: str, entry_index: int, observed_at: str | None, source: str) -> str | None:
        key = person_key(user_id, username)
        if key is None:
            return None
        row = people.setdefault(
            key,
            {"kind": "person", "stable_user_id": str(user_id) if user_id not in (None, "") else None, "aliases": set(), "provenance": []},
        )
        if isinstance(username, str) and username:
            row["aliases"].add(username)
        row["provenance"].append({"capture": capture, "entry_index": entry_index, "observed_at": observed_at, "source": source})
        return key

    def register_media(*, media_id: Any, media_code: Any = None, capture: str, entry_index: int, observed_at: str | None, source: str) -> str | None:
        if media_id in (None, ""):
            return None
        key = f"media:{media_id}"
        row = media.setdefault(key, {"kind": "media", "media_id": str(media_id), "media_codes": set(), "provenance": []})
        if isinstance(media_code, str) and media_code:
            row["media_codes"].add(media_code)
        row["provenance"].append({"capture": capture, "entry_index": entry_index, "observed_at": observed_at, "source": source})
        return key

    def register_comment(*, comment_id: Any, capture: str, entry_index: int, observed_at: str | None) -> str | None:
        if comment_id in (None, ""):
            return None
        key = f"comment:{comment_id}"
        comments.setdefault(key, {"kind": "comment", "comment_id": str(comment_id), "provenance": []})["provenance"].append(
            {"capture": capture, "entry_index": entry_index, "observed_at": observed_at, "source": "comment_activity"}
        )
        return key

    for cap_index, capture in enumerate(captures):
        name = str(capture.get("capture_name") or f"capture_{cap_index + 1}")
        timestamps = capture.get("timestamps") or {}

        def observed(record: dict[str, Any]) -> str | None:
            try:
                return timestamps.get(int(record.get("entry_index", -1)))
            except (TypeError, ValueError):
                return None

        for record in capture.get("comments") or []:
            idx = int(record.get("entry_index", -1))
            ts = observed(record)
            actor = register_person(user_id=record.get("comment_author_id"), username=record.get("comment_author_username"), capture=name, entry_index=idx, observed_at=ts, source="comment_activity")
            author = register_person(username=record.get("post_author_username"), capture=name, entry_index=idx, observed_at=ts, source="post_author")
            mkey = register_media(media_id=record.get("post_id"), media_code=record.get("post_media_code"), capture=name, entry_index=idx, observed_at=ts, source="comment_activity")
            ckey = register_comment(comment_id=record.get("comment_id"), capture=name, entry_index=idx, observed_at=ts)
            base = {"capture": name, "entry_index": idx, "observed_at": ts, "provenance_class": "captured"}
            if actor and ckey:
                edges.append({**base, "source": actor, "target": ckey, "relation": "authored_comment"})
            if ckey and mkey:
                edges.append({**base, "source": ckey, "target": mkey, "relation": "comment_on_media"})
            if actor and mkey:
                edges.append({**base, "source": actor, "target": mkey, "relation": "commented_on_media"})
            if author and mkey:
                edges.append({**base, "source": author, "target": mkey, "relation": "authored_media"})
            if actor and author:
                edges.append({**base, "source": actor, "target": author, "relation": "commented_on_post_by"})

        for record in capture.get("media") or []:
            idx = int(record.get("entry_index", -1))
            register_media(media_id=record.get("media_id"), media_code=record.get("media_code"), capture=name, entry_index=idx, observed_at=observed(record), source="media_record")

        for source_name in ("blocked", "surfaced"):
            for record in capture.get(source_name) or []:
                idx = int(record.get("entry_index", -1))
                register_person(user_id=record.get("user_id"), username=record.get("username"), capture=name, entry_index=idx, observed_at=observed(record), source="blocked_accounts" if source_name == "blocked" else "selection_surface")

    degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        degree[str(edge["source"])] += 1
        degree[str(edge["target"])] += 1

    def public_entity(key: str, row: dict[str, Any]) -> dict[str, Any]:
        kind = row["kind"]
        if kind == "person":
            aliases = sorted(row["aliases"])
            if include_identities:
                entity_id = row["stable_user_id"] or (aliases[-1] if aliases else key)
                return {"entity": f"person:{entity_id}", "kind": "person", "stable_user_id": row["stable_user_id"], "aliases": aliases, "locators": [{"type": "instagram_profile", "value": f"https://www.instagram.com/{alias}/"} for alias in aliases], "degree": degree.get(key, 0), "provenance": row["provenance"]}
            return {"entity": pseudo("person", key), "kind": "person", "alias_count": len(aliases), "locator_count": len(aliases), "degree": degree.get(key, 0), "provenance": row["provenance"]}
        if kind == "media":
            codes = sorted(row["media_codes"])
            if include_identities:
                return {"entity": f"media:{row['media_id']}", "kind": "media", "media_id": row["media_id"], "media_codes": codes, "locators": [{"type": "instagram_media", "value": f"https://www.instagram.com/p/{code}/"} for code in codes], "degree": degree.get(key, 0), "provenance": row["provenance"]}
            return {"entity": pseudo("media", key), "kind": "media", "locator_count": len(codes), "degree": degree.get(key, 0), "provenance": row["provenance"]}
        if include_identities:
            return {"entity": f"comment:{row['comment_id']}", "kind": "comment", "comment_id": row["comment_id"], "degree": degree.get(key, 0), "provenance": row["provenance"]}
        return {"entity": pseudo("comment", key), "kind": "comment", "degree": degree.get(key, 0), "provenance": row["provenance"]}

    entities = [public_entity(k, v) for k, v in people.items()]
    entities += [public_entity(k, v) for k, v in media.items()]
    entities += [public_entity(k, v) for k, v in comments.items()]
    entities.sort(key=lambda row: (row["kind"], -int(row.get("degree", 0)), str(row["entity"])))

    frontier = []
    for row in entities:
        locator_count = len(row.get("locators", [])) if include_identities else int(row.get("locator_count", 0))
        if row["kind"] not in {"person", "media"} or locator_count <= 0:
            continue
        frontier.append({"entity": row["entity"], "kind": row["kind"], "priority": int(row.get("degree", 0)), "status": "open", "locator_count": locator_count, **({"locators": row["locators"]} if include_identities else {}), "expansion_semantics": "public_observation_frontier"})
    frontier.sort(key=lambda row: (-row["priority"], row["kind"], str(row["entity"])))

    current_nodes = len(entities)
    return {
        "schema_version": 1,
        "projection": "expansion_frontier_manifest",
        "identity_bearing": include_identities,
        "agreement_id": aid,
        "current_node_count": current_nodes,
        "captured_edge_count": len(edges),
        "frontier_count": len(frontier),
        "target_node_budget": target_nodes,
        "target_is_budget_not_promise": True,
        "nodes_remaining_to_budget": max(0, target_nodes - current_nodes),
        "entities": entities,
        "frontier": frontier,
        "edge_semantics": {
            "captured_edges": "relationships observed in supplied captures",
            "future_expansion_edges": "must be labeled newly_observed and retain source/time provenance",
        },
        "stop_conditions": [
            "target node budget reached",
            "no open frontier remains",
            "authorization boundary reached",
            "resource or rate cap reached",
            "source no longer publicly observable",
        ],
        "inference_limits": {
            "frontier_priority_is_social_closeness": False,
            "public_locator_proves_relationship": False,
            "future_observation_was_present_in_original_capture": False,
            "absence_in_future_observation_deletes_capture_history": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a bounded expansion frontier from captured HAR identifiers")
    ap.add_argument("har", nargs="+", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--target-nodes", type=int, default=10_000)
    ap.add_argument("--include-identities", action="store_true")
    ap.add_argument("--agreement", type=Path)
    args = ap.parse_args()

    captures = []
    for path in args.har:
        with path.open("r", encoding="utf-8") as f:
            har = json.load(f)
        captures.append(capture_evidence(har, path.name))

    manifest = build_frontier_manifest(captures, include_identities=args.include_identities, agreement=args.agreement, target_nodes=args.target_nodes)
    text = json.dumps(manifest, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
