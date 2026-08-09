#!/usr/bin/env python3
"""Recover a richer pseudonymized relational world from evidence captured in a HAR.

This workflow preserves primitive entities before choosing a product-style projection.
It combines comment activity, liked-media activity, close-friends selector observations,
and blocked-account observations. UI co-presence is preserved as observation evidence;
it is not silently upgraded into friendship, recommendation causality, or synchronized viewing.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

from extract_har_interaction_graph import (
    extract_comment_records,
    parse_bloks,
    parse_json_maybe,
    walk_maps,
    walk_strings,
)

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]

IDENTITY_ACTION = "extract_captured_world_fabric_identities"


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


def response_maps(entry: dict[str, Any]) -> Iterable[dict[str, Any]]:
    content = (entry.get("response", {}) or {}).get("content", {}) or {}
    payload = parse_json_maybe(str(content.get("text", "") or ""))
    if payload is None:
        return
    for text in walk_strings(payload):
        if not text.lstrip().startswith("(") or "bk.action.map.Make" not in text:
            continue
        try:
            parsed = parse_bloks(text)
        except ValueError:
            continue
        yield from walk_maps(parsed)


def enrich_comment_records(har: dict[str, Any]) -> list[dict[str, Any]]:
    records = [dict(record) for record in extract_comment_records(har)]
    extras: dict[str, dict[str, Any]] = defaultdict(dict)
    for entry in har.get("log", {}).get("entries", []) or []:
        for mapping in response_maps(entry):
            comment_id = mapping.get("comment_id")
            if comment_id not in (None, ""):
                key = str(comment_id)
                if isinstance(mapping.get("comment_time"), str) and mapping["comment_time"]:
                    extras[key]["comment_time"] = mapping["comment_time"]
            post_info = mapping.get("post_info")
            if isinstance(post_info, list):
                for post in post_info:
                    if not isinstance(post, dict):
                        continue
                    cid = post.get("post_comment_id")
                    if cid not in (None, "") and isinstance(post.get("post_time"), str):
                        extras[str(cid)]["post_time"] = post.get("post_time")
    for record in records:
        record.update(extras.get(str(record.get("comment_id") or ""), {}))
    return records


def extract_liked_media_records(har: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for entry_index, entry in enumerate(har.get("log", {}).get("entries", []) or []):
        url = str((entry.get("request", {}) or {}).get("url", "") or "")
        if "activity_center.liked_media_screen" not in url and "activity_center.liked_next" not in url:
            continue
        for mapping in response_maps(entry):
            media_id = mapping.get("media_id")
            media_code = mapping.get("media_code")
            if not isinstance(media_id, str) or not media_id:
                continue
            if not isinstance(media_code, str) or not media_code:
                continue
            records.setdefault(
                media_id,
                {
                    "entry_index": entry_index,
                    "media_id": media_id,
                    "media_code": media_code,
                    "media_product_type": mapping.get("media_product_type"),
                    "media_type": mapping.get("media_type"),
                    "location_name": mapping.get("location_name") if isinstance(mapping.get("location_name"), str) else "",
                },
            )
    return sorted(records.values(), key=lambda row: (int(row["entry_index"]), str(row["media_id"])))


def extract_close_friends_surface_records(har: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for entry_index, entry in enumerate(har.get("log", {}).get("entries", []) or []):
        url = str((entry.get("request", {}) or {}).get("url", "") or "")
        if "close_friends_screen_v2" not in url:
            continue
        for mapping in response_maps(entry):
            user_id = mapping.get("user_id")
            username = mapping.get("username")
            if user_id in (None, "") or not isinstance(username, str) or not username:
                continue
            if not {"name", "profile_pic_url", "is_verified"}.issubset(mapping):
                continue
            uid = str(user_id)
            records.setdefault(uid, {"entry_index": entry_index, "user_id": uid, "username": username, "surface": "close_friends_selector"})
    return sorted(records.values(), key=lambda row: (int(row["entry_index"]), str(row["user_id"])))


def extract_blocked_records(har: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for entry_index, entry in enumerate(har.get("log", {}).get("entries", []) or []):
        url = str((entry.get("request", {}) or {}).get("url", "") or "")
        if "blocked_accounts_reloader" not in url:
            continue
        for mapping in response_maps(entry):
            user_id = mapping.get("user_id")
            username = mapping.get("username")
            if user_id in (None, "") or not isinstance(username, str) or not username:
                continue
            if "is_auto_blocked" not in mapping:
                continue
            uid = str(user_id)
            records.setdefault(uid, {"entry_index": entry_index, "user_id": uid, "username": username, "is_auto_blocked": bool(mapping.get("is_auto_blocked"))})
    return sorted(records.values(), key=lambda row: (int(row["entry_index"]), str(row["user_id"])))


def weak_components(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        adjacency[node]
    for source, target in edges:
        adjacency[source].add(target)
        adjacency[target].add(source)
    unseen = set(adjacency)
    result: list[set[str]] = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        queue: deque[str] = deque([start])
        component: set[str] = set()
        while queue:
            node = queue.popleft()
            component.add(node)
            for neighbor in adjacency[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        result.append(component)
    return sorted(result, key=lambda component: (-len(component), sorted(component)))


def build_world_fabric(
    comment_records: list[dict[str, Any]],
    *,
    liked_media_records: list[dict[str, Any]] | None = None,
    surface_people: list[dict[str, Any]] | None = None,
    blocked_people: list[dict[str, Any]] | None = None,
    include_identities: bool = False,
    agreement: Path | None = None,
) -> dict[str, Any]:
    liked_media_records = liked_media_records or []
    surface_people = surface_people or []
    blocked_people = blocked_people or []
    aid = require_identity_agreement(agreement) if include_identities else None

    username_to_uid: dict[str, str] = {}
    uid_to_username: dict[str, str] = {}
    for record in comment_records:
        username = record.get("comment_author_username")
        user_id = record.get("comment_author_id")
        if isinstance(username, str) and username and user_id not in (None, ""):
            uid = str(user_id)
            username_to_uid[username] = uid
            uid_to_username[uid] = username
    for record in [*surface_people, *blocked_people]:
        username = record.get("username")
        user_id = record.get("user_id")
        if isinstance(username, str) and username and user_id not in (None, ""):
            uid = str(user_id)
            username_to_uid[username] = uid
            uid_to_username[uid] = username

    def person_key(username: str | None = None, user_id: Any = None) -> str:
        if user_id not in (None, ""):
            return f"uid:{user_id}"
        if username and username in username_to_uid:
            return f"uid:{username_to_uid[username]}"
        return f"username:{username or 'unknown'}"

    person_keys: set[str] = set()
    media_keys: set[str] = set()
    comment_keys: set[str] = set()
    location_keys: set[str] = set()
    for record in comment_records:
        commenter = str(record.get("comment_author_username") or "")
        author = str(record.get("post_author_username") or "")
        if commenter:
            person_keys.add(person_key(commenter, record.get("comment_author_id")))
        if author:
            person_keys.add(person_key(author))
        if record.get("post_id") not in (None, ""):
            media_keys.add(str(record["post_id"]))
        if record.get("comment_id") not in (None, ""):
            comment_keys.add(str(record["comment_id"]))
    for record in liked_media_records:
        if record.get("media_id") not in (None, ""):
            media_keys.add(str(record["media_id"]))
        location = record.get("location_name")
        if isinstance(location, str) and location.strip():
            location_keys.add(location.strip())
    for record in [*surface_people, *blocked_people]:
        person_keys.add(person_key(str(record.get("username") or ""), record.get("user_id")))

    viewer_candidates = Counter()
    for record in comment_records:
        if record.get("user_created_this_comment") is True:
            viewer_candidates[person_key(str(record.get("comment_author_username") or ""), record.get("comment_author_id"))] += 1
    viewer_key = viewer_candidates.most_common(1)[0][0] if viewer_candidates else None
    if viewer_key:
        person_keys.add(viewer_key)

    person_ids = {key: f"person_{i:03d}" for i, key in enumerate(sorted(person_keys), 1)}
    media_ids = {key: f"media_{i:03d}" for i, key in enumerate(sorted(media_keys), 1)}
    comment_ids = {key: f"comment_{i:03d}" for i, key in enumerate(sorted(comment_keys), 1)}
    location_ids = {key: f"location_{i:03d}" for i, key in enumerate(sorted(location_keys), 1)}
    surface_id = "surface_close_friends_selector" if surface_people else None
    actor_id = "capture_actor_001" if (liked_media_records or blocked_people) and viewer_key is None else None

    nodes: list[dict[str, Any]] = []
    for key, node_id in person_ids.items():
        node: dict[str, Any] = {"id": node_id, "type": "person"}
        if include_identities:
            if key.startswith("uid:"):
                uid = key[4:]
                node["observed_user_id"] = uid
                if uid in uid_to_username:
                    node["username"] = uid_to_username[uid]
            else:
                node["username"] = key.split(":", 1)[1]
        nodes.append(node)
    for key, node_id in media_ids.items():
        node = {"id": node_id, "type": "media"}
        if include_identities:
            node["observed_media_id"] = key
        nodes.append(node)
    for key, node_id in comment_ids.items():
        node = {"id": node_id, "type": "comment"}
        if include_identities:
            node["observed_comment_id"] = key
        nodes.append(node)
    for key, node_id in location_ids.items():
        node = {"id": node_id, "type": "location"}
        if include_identities:
            node["name"] = key
        nodes.append(node)
    if surface_id:
        nodes.append({"id": surface_id, "type": "ui_surface", "surface_kind": "close_friends_selector"})
    if actor_id:
        nodes.append({"id": actor_id, "type": "capture_actor"})

    edges: list[dict[str, Any]] = []
    commented_media: Counter[tuple[str, str]] = Counter()
    authored_media: set[tuple[str, str]] = set()
    person_interaction: Counter[tuple[str, str]] = Counter()
    commenters_by_media: dict[str, set[str]] = defaultdict(set)
    relative_labels_by_media_person: dict[tuple[str, str], set[str]] = defaultdict(set)

    for record in comment_records:
        commenter = str(record.get("comment_author_username") or "")
        author = str(record.get("post_author_username") or "")
        post_id = str(record.get("post_id") or "")
        comment_id = str(record.get("comment_id") or "")
        if not commenter or not author or not post_id:
            continue
        commenter_key = person_key(commenter, record.get("comment_author_id"))
        author_key = person_key(author)
        commenter_id = person_ids[commenter_key]
        media_id = media_ids[post_id]
        commented_media[(commenter_key, post_id)] += 1
        authored_media.add((author_key, post_id))
        person_interaction[(commenter_key, author_key)] += 1
        commenters_by_media[post_id].add(commenter_key)
        label = record.get("comment_time")
        if isinstance(label, str) and label:
            relative_labels_by_media_person[(post_id, commenter_key)].add(label)
        if comment_id and comment_id in comment_ids:
            comment_node = comment_ids[comment_id]
            edge = {"source": commenter_id, "target": comment_node, "type": "authored_comment", "directed": True, "weight": 1}
            if isinstance(label, str) and label:
                edge["observed_relative_time_label"] = label
            edges.append(edge)
            edges.append({"source": comment_node, "target": media_id, "type": "comment_on_media", "directed": True, "weight": 1})

    for (person, post_id), weight in sorted(commented_media.items()):
        edges.append({"source": person_ids[person], "target": media_ids[post_id], "type": "commented_on_media", "directed": True, "weight": weight})
    for person, post_id in sorted(authored_media):
        edges.append({"source": person_ids[person], "target": media_ids[post_id], "type": "authored_media", "directed": True, "weight": 1})
    for (commenter, author), weight in sorted(person_interaction.items()):
        edges.append({"source": person_ids[commenter], "target": person_ids[author], "type": "commented_on_post_by", "directed": True, "weight": weight, "self_loop": commenter == author})

    co_shared_media: Counter[tuple[str, str]] = Counter()
    co_same_relative_bucket: Counter[tuple[str, str]] = Counter()
    for post_id, commenters in sorted(commenters_by_media.items()):
        for a, b in combinations(sorted(commenters), 2):
            pair = (a, b)
            co_shared_media[pair] += 1
            if relative_labels_by_media_person[(post_id, a)] & relative_labels_by_media_person[(post_id, b)]:
                co_same_relative_bucket[pair] += 1
    for (a, b), shared_media_count in sorted(co_shared_media.items()):
        edges.append({
            "source": person_ids[a],
            "target": person_ids[b],
            "type": "co_commented_on_media",
            "directed": False,
            "weight": shared_media_count,
            "shared_media_count": shared_media_count,
            "same_relative_time_label_count": co_same_relative_bucket[(a, b)],
        })

    viewer_node = person_ids.get(viewer_key) if viewer_key else actor_id
    for record in liked_media_records:
        mid = str(record.get("media_id") or "")
        if not mid or mid not in media_ids or not viewer_node:
            continue
        edges.append({"source": viewer_node, "target": media_ids[mid], "type": "activity_owner_liked_media", "directed": True, "weight": 1})
        location = record.get("location_name")
        if isinstance(location, str) and location.strip() and location.strip() in location_ids:
            edges.append({"source": media_ids[mid], "target": location_ids[location.strip()], "type": "media_observed_at_location", "directed": True, "weight": 1})

    if surface_id:
        seen: set[str] = set()
        for record in surface_people:
            pkey = person_key(str(record.get("username") or ""), record.get("user_id"))
            if pkey in person_ids and pkey not in seen:
                edges.append({"source": surface_id, "target": person_ids[pkey], "type": "surface_contains_person", "directed": True, "weight": 1})
                seen.add(pkey)
    if viewer_node:
        for record in blocked_people:
            pkey = person_key(str(record.get("username") or ""), record.get("user_id"))
            if pkey in person_ids:
                edges.append({"source": viewer_node, "target": person_ids[pkey], "type": "activity_owner_blocked_person", "directed": True, "weight": 1, "auto_blocked": bool(record.get("is_auto_blocked"))})

    relation_types = sorted({str(edge["type"]) for edge in edges})
    comps = weak_components([str(node["id"]) for node in nodes], [(str(edge["source"]), str(edge["target"])) for edge in edges])
    result: dict[str, Any] = {
        "representation": "heterogeneous_world_multigraph",
        "node_types": sorted({str(node["type"]) for node in nodes}),
        "relation_types": relation_types,
        "identity_labels_emitted": include_identities,
        "content_text_emitted": False,
        "person_node_count": len(person_ids),
        "media_node_count": len(media_ids),
        "comment_node_count": len(comment_ids),
        "location_node_count": len(location_ids),
        "ui_surface_node_count": 1 if surface_id else 0,
        "capture_actor_node_count": 1 if actor_id else 0,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "co_engagement_edge_count": len(co_shared_media),
        "co_engagement_edges_with_same_relative_time_label": sum(1 for count in co_same_relative_bucket.values() if count > 0),
        "liked_media_evidence_count": len(liked_media_records),
        "close_friends_selector_observation_count": len(surface_people),
        "blocked_account_evidence_count": len(blocked_people),
        "weak_component_count": len(comps),
        "largest_weak_component_nodes": len(comps[0]) if comps else 0,
        "fabric_obtained": len(nodes) >= 3 and len(edges) >= 2,
        "evidence_semantics": {
            "surface_contains_person": "The account was surfaced in the captured close-friends selection UI; close-friend membership is not claimed.",
            "same_relative_time_label_count": "Both captured comments displayed the same coarse relative-time label on the same media; simultaneity is not claimed.",
            "activity_owner_liked_media": "The liked-media activity surface records the capture owner as having liked the media.",
            "activity_owner_blocked_person": "The blocked-accounts surface records the capture owner as blocking the account.",
        },
        "inference_limits": {
            "close_friends_membership_claimed": False,
            "synchronized_viewing_claimed": False,
            "shared_recommendation_delivery_claimed": False,
            "algorithmic_causality_claimed": False,
            "relative_time_labels_are_exact_timestamps": False,
        },
        "nodes": nodes,
        "edges": edges,
    }
    if aid:
        result["agreement_id"] = aid
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover a richer relational world from a HAR")
    ap.add_argument("har", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--include-identities", action="store_true")
    ap.add_argument("--agreement", type=Path)
    ap.add_argument("--require-fabric", action="store_true")
    args = ap.parse_args()
    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)
    try:
        fabric = build_world_fabric(
            enrich_comment_records(har),
            liked_media_records=extract_liked_media_records(har),
            surface_people=extract_close_friends_surface_records(har),
            blocked_people=extract_blocked_records(har),
            include_identities=args.include_identities,
            agreement=args.agreement,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    fabric["source"] = args.har.name
    output = json.dumps(fabric, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    else:
        print(output, end="")
    if args.require_fabric and not fabric["fabric_obtained"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
