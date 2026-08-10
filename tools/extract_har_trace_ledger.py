#!/usr/bin/env python3
"""Recover a temporal ledger of capture-visible interaction traces from one or more HARs.

The ledger is deliberately append-only in spirit: later observations do not erase
older aliases or actions. Stable platform IDs, when captured, are used to join
observations before pseudonymization. A HAR entry timestamp means "observed at",
not necessarily "action happened at" or "alias changed at".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from extract_har_interaction_graph import extract_comment_records, parse_json_maybe, walk_strings
from extract_har_world_fabric import (
    enrich_comment_records,
    extract_blocked_records,
    extract_close_friends_surface_records,
    extract_liked_media_records,
)

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]

IDENTITY_ACTION = "extract_captured_trace_ledger_identities"
ACTOR_RE = re.compile(r'"actorID"\s*:\s*"(\d+)"')


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


def entry_timestamp(entry: dict[str, Any]) -> str | None:
    value = entry.get("startedDateTime")
    return str(value) if isinstance(value, str) and value else None


def extract_actor_id(har: dict[str, Any], comments: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = defaultdict(int)
    for record in comments:
        if record.get("user_created_this_comment") is True and record.get("comment_author_id") not in (None, ""):
            counts[str(record["comment_author_id"])] += 10
    for entry in har.get("log", {}).get("entries", []) or []:
        url = str((entry.get("request", {}) or {}).get("url", "") or "")
        try:
            for value in parse_qs(urlparse(url).query).get("av", []):
                if value.isdigit():
                    counts[value] += 2
        except ValueError:
            pass
        content = (entry.get("response", {}) or {}).get("content", {}) or {}
        text = str(content.get("text", "") or "")
        match = ACTOR_RE.search(text)
        if match:
            counts[match.group(1)] += 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def stable_key(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def capture_evidence(har: dict[str, Any], capture_name: str) -> dict[str, Any]:
    comments = enrich_comment_records(har)
    likes = extract_liked_media_records(har)
    blocked = extract_blocked_records(har)
    surfaced = extract_close_friends_surface_records(har)
    actor_id = extract_actor_id(har, comments)
    timestamps = {
        i: entry_timestamp(entry)
        for i, entry in enumerate(har.get("log", {}).get("entries", []) or [])
    }
    return {
        "capture_name": capture_name,
        "actor_id": actor_id,
        "comments": comments,
        "likes": likes,
        "blocked": blocked,
        "surfaced": surfaced,
        "timestamps": timestamps,
    }


def build_trace_ledger(
    captures: list[dict[str, Any]],
    *,
    include_identities: bool = False,
    agreement: Path | None = None,
    pseudonym_secret: bytes | None = None,
    focus_username: str | None = None,
    focus_user_id: str | None = None,
) -> dict[str, Any]:
    if focus_username and focus_user_id:
        raise ValueError("use only one of focus_username or focus_user_id")
    aid = require_identity_agreement(agreement) if include_identities else None
    secret = pseudonym_secret or os.urandom(32)

    raw_entities: set[tuple[str, str]] = set()
    actor_keys: set[str] = set()
    alias_obs_raw: list[dict[str, Any]] = []
    trace_raw: list[dict[str, Any]] = []
    context_obs_raw: list[dict[str, Any]] = []

    for cap_index, capture in enumerate(captures):
        name = str(capture.get("capture_name") or f"capture_{cap_index + 1}")
        timestamps = capture.get("timestamps") or {}
        actor_id = capture.get("actor_id")
        actor_key = stable_key("person_uid", str(actor_id)) if actor_id else stable_key("capture_actor", name)
        raw_entities.add(("person", actor_key))
        actor_keys.add(actor_key)

        def observed_at(record: dict[str, Any]) -> str | None:
            try:
                return timestamps.get(int(record.get("entry_index", -1)))
            except (TypeError, ValueError):
                return None

        def register_alias(user_id: Any, username: Any, source: str, record: dict[str, Any]) -> str | None:
            if user_id in (None, "") or not isinstance(username, str) or not username:
                return None
            entity_key = stable_key("person_uid", str(user_id))
            raw_entities.add(("person", entity_key))
            alias_obs_raw.append({
                "entity_key": entity_key,
                "alias": username,
                "observed_at": observed_at(record),
                "capture_index": cap_index,
                "capture": name,
                "entry_index": int(record.get("entry_index", -1)),
                "source": source,
            })
            return entity_key

        for record in capture.get("comments") or []:
            commenter_key = register_alias(
                record.get("comment_author_id"),
                record.get("comment_author_username"),
                "comment_activity",
                record,
            )
            post_id = record.get("post_id")
            comment_id = record.get("comment_id")
            if post_id not in (None, ""):
                media_key = stable_key("media", str(post_id))
                raw_entities.add(("media", media_key))
            else:
                media_key = None
            if comment_id not in (None, ""):
                comment_key = stable_key("comment", str(comment_id))
                raw_entities.add(("comment", comment_key))
            else:
                comment_key = None

            if record.get("user_created_this_comment") is True:
                source_key = commenter_key or actor_key
                if media_key:
                    trace_raw.append({
                        "actor_key": source_key,
                        "target_key": media_key,
                        "via_key": comment_key,
                        "action": "commented_on_media",
                        "trace_class": "content_interaction",
                        "observed_at": observed_at(record),
                        "capture_index": cap_index,
                        "capture": name,
                        "entry_index": int(record.get("entry_index", -1)),
                        "time_semantics": "capture_observation_time",
                    })

        for record in capture.get("likes") or []:
            mid = record.get("media_id")
            if mid in (None, ""):
                continue
            media_key = stable_key("media", str(mid))
            raw_entities.add(("media", media_key))
            trace_raw.append({
                "actor_key": actor_key,
                "target_key": media_key,
                "via_key": None,
                "action": "liked_media",
                "trace_class": "activity_history",
                "observed_at": observed_at(record),
                "capture_index": cap_index,
                "capture": name,
                "entry_index": int(record.get("entry_index", -1)),
                "time_semantics": "capture_observation_time",
            })

        for record in capture.get("blocked") or []:
            target_key = register_alias(record.get("user_id"), record.get("username"), "blocked_accounts", record)
            if target_key:
                trace_raw.append({
                    "actor_key": actor_key,
                    "target_key": target_key,
                    "via_key": None,
                    "action": "blocked_person",
                    "trace_class": "account_state",
                    "observed_at": observed_at(record),
                    "capture_index": cap_index,
                    "capture": name,
                    "entry_index": int(record.get("entry_index", -1)),
                    "time_semantics": "capture_observation_time",
                    "auto_blocked": bool(record.get("is_auto_blocked")),
                })

        for record in capture.get("surfaced") or []:
            target_key = register_alias(record.get("user_id"), record.get("username"), "close_friends_selector", record)
            if target_key:
                context_obs_raw.append({
                    "entity_key": target_key,
                    "context": "close_friends_selector",
                    "observed_at": observed_at(record),
                    "capture_index": cap_index,
                    "capture": name,
                    "entry_index": int(record.get("entry_index", -1)),
                })

    focus_key: str | None = None
    focus_resolution: str | None = None
    if focus_user_id:
        candidate = stable_key("person_uid", str(focus_user_id))
        if ("person", candidate) not in raw_entities:
            raise ValueError("focus user ID was not observed in the supplied captures")
        focus_key = candidate
        focus_resolution = "stable_user_id"
    elif focus_username:
        matches = {
            str(obs["entity_key"])
            for obs in alias_obs_raw
            if str(obs.get("alias") or "").casefold() == focus_username.casefold()
        }
        if not matches:
            raise ValueError("focus username was not observed in the supplied captures")
        if len(matches) > 1:
            raise ValueError("focus username resolves to multiple stable entities")
        focus_key = next(iter(matches))
        focus_resolution = "captured_alias"

    def pseudonym(kind: str, key: str) -> str:
        digest = hashlib.sha256(secret + b"\0" + key.encode("utf-8")).hexdigest()[:12]
        return f"{kind}_{digest}"

    entity_ids: dict[str, str] = {}
    entity_types: dict[str, str] = {}
    for kind, key in sorted(raw_entities):
        entity_ids[key] = pseudonym(kind, key)
        entity_types[key] = kind

    grouped_aliases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in alias_obs_raw:
        grouped_aliases[obs["entity_key"]].append(obs)
    alias_symbol: dict[tuple[str, str], str] = {}
    alias_history: list[dict[str, Any]] = []
    alias_transition_count = 0
    for entity_key, observations in sorted(grouped_aliases.items()):
        observations.sort(key=lambda row: (
            row["observed_at"] or "",
            row["capture_index"],
            row["entry_index"],
            row["alias"],
        ))
        distinct: list[str] = []
        for obs in observations:
            alias = obs["alias"]
            if alias not in distinct:
                distinct.append(alias)
                alias_symbol[(entity_key, alias)] = f"alias_{len(distinct):02d}"
        if len(distinct) > 1:
            alias_transition_count += len(distinct) - 1
        seen_rows: set[tuple[Any, ...]] = set()
        for obs in observations:
            row_key = (obs["alias"], obs["observed_at"], obs["capture"], obs["entry_index"], obs["source"])
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            row = {
                "entity": entity_ids[entity_key],
                "alias": alias_symbol[(entity_key, obs["alias"])],
                "observed_at": obs["observed_at"],
                "capture": obs["capture"],
                "entry_index": obs["entry_index"],
                "source": obs["source"],
                "time_semantics": "capture_observation_time",
            }
            if include_identities:
                row["alias_value"] = obs["alias"]
            alias_history.append(row)

    traces: list[dict[str, Any]] = []
    seen_trace: set[tuple[Any, ...]] = set()
    for raw in sorted(trace_raw, key=lambda row: (
        row["observed_at"] or "", row["capture_index"], row["entry_index"], row["action"], row["target_key"]
    )):
        key = (raw["capture"], raw["entry_index"], raw["action"], raw["actor_key"], raw["target_key"], raw.get("via_key"))
        if key in seen_trace:
            continue
        seen_trace.add(key)
        row = {
            "actor": entity_ids[raw["actor_key"]],
            "target": entity_ids[raw["target_key"]],
            "action": raw["action"],
            "trace_class": raw["trace_class"],
            "observed_at": raw["observed_at"],
            "capture": raw["capture"],
            "entry_index": raw["entry_index"],
            "time_semantics": raw["time_semantics"],
            "capture_visible": True,
            "public_visibility_claimed": False,
        }
        if raw.get("via_key") and raw["via_key"] in entity_ids:
            row["via"] = entity_ids[raw["via_key"]]
        if "auto_blocked" in raw:
            row["auto_blocked"] = raw["auto_blocked"]
        traces.append(row)

    context_observations = [
        {
            "entity": entity_ids[row["entity_key"]],
            "context": row["context"],
            "observed_at": row["observed_at"],
            "capture": row["capture"],
            "entry_index": row["entry_index"],
            "time_semantics": "capture_observation_time",
        }
        for row in sorted(context_obs_raw, key=lambda row: (
            row["observed_at"] or "", row["capture_index"], row["entry_index"], row["entity_key"]
        ))
    ]

    nodes = [
        {
            "id": entity_ids[key],
            "type": entity_types[key],
            "is_capture_actor": key in actor_keys,
            "is_focus": key == focus_key,
        }
        for key in sorted(entity_ids, key=lambda key: entity_ids[key])
    ]

    result: dict[str, Any] = {
        "representation": "temporal_trace_ledger",
        "capture_count": len(captures),
        "node_count": len(nodes),
        "trace_event_count": len(traces),
        "alias_observation_count": len(alias_history),
        "alias_transition_count": alias_transition_count,
        "context_observation_count": len(context_observations),
        "identity_labels_emitted": include_identities,
        "time_model": {
            "primary_timestamp": "HAR entry startedDateTime",
            "meaning": "capture observation time",
            "action_time_claimed": False,
            "alias_change_time_claimed": False,
            "history_is_append_only": True,
        },
        "visibility_model": {
            "capture_visible": "The action/state was recoverable from the authorized capture.",
            "public_visibility_claimed": False,
            "note": "Capture visibility does not by itself establish who else could see the action.",
        },
        "nodes": nodes,
        "alias_history": alias_history,
        "traces": traces,
        "context_observations": context_observations,
    }

    if focus_key:
        focus_id = entity_ids[focus_key]
        adjacency: dict[str, set[str]] = defaultdict(set)
        for row in traces:
            actor = str(row["actor"])
            target = str(row["target"])
            via = row.get("via")
            if via:
                via_id = str(via)
                adjacency[actor].add(via_id)
                adjacency[via_id].add(actor)
                adjacency[via_id].add(target)
                adjacency[target].add(via_id)
            else:
                adjacency[actor].add(target)
                adjacency[target].add(actor)
        distances: dict[str, int] = {focus_id: 0}
        queue: deque[str] = deque([focus_id])
        while queue:
            node = queue.popleft()
            for neighbor in sorted(adjacency.get(node, set())):
                if neighbor not in distances:
                    distances[neighbor] = distances[node] + 1
                    queue.append(neighbor)
        hop_counts: dict[str, int] = defaultdict(int)
        for distance in distances.values():
            hop_counts[f"hop_{distance}"] += 1
        result["focus"] = {
            "entity": focus_id,
            "resolution": focus_resolution,
            "identity_label_emitted": False,
            "alias_observation_count": sum(1 for row in alias_history if row["entity"] == focus_id),
            "incident_trace_count": sum(
                1
                for row in traces
                if focus_id in {str(row["actor"]), str(row["target"]), str(row.get("via") or "")}
            ),
            "incident_context_count": sum(1 for row in context_observations if row["entity"] == focus_id),
        }
        result["focus_view"] = {
            "center": focus_id,
            "projection_only": True,
            "underlying_graph_centerless": True,
            "hop_semantics": "Undirected evidence-path distance through captured trace relations; it is not social closeness.",
            "reachable_node_count": len(distances),
            "max_hop": max(distances.values()) if distances else 0,
            "hop_counts": dict(sorted(hop_counts.items(), key=lambda item: int(item[0].split("_")[1]))),
            "distances": dict(sorted(distances.items(), key=lambda item: (item[1], item[0]))),
        }

    if aid:
        result["agreement_id"] = aid
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover an append-only temporal trace ledger from HAR captures")
    ap.add_argument("har", nargs="+", type=Path, help="One or more HAR files, oldest-to-newest is recommended")
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--include-identities", action="store_true")
    ap.add_argument("--agreement", type=Path)
    focus = ap.add_mutually_exclusive_group()
    focus.add_argument("--focus-username", help="Center the output projection on a captured username without emitting that identity by default")
    focus.add_argument("--focus-user-id", help="Center the output projection on a captured stable user ID without emitting that identity by default")
    args = ap.parse_args()

    captures: list[dict[str, Any]] = []
    for path in args.har:
        with path.open("r", encoding="utf-8") as f:
            har = json.load(f)
        captures.append(capture_evidence(har, path.name))

    try:
        result = build_trace_ledger(
            captures,
            include_identities=args.include_identities,
            agreement=args.agreement,
            focus_username=args.focus_username,
            focus_user_id=args.focus_user_id,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
