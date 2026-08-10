#!/usr/bin/env python3
"""Recover a heterogeneous relational fabric from interaction evidence captured in a HAR.

The first adapter builds on Instagram activity-center comment records already
recognized by extract_har_interaction_graph.py. It preserves the media object
instead of projecting everything immediately into a person-to-person edge.

Default output is pseudonymized. The tool does not claim that co-commenters were
shown the post by the same recommendation event, watched simultaneously, or were
causally grouped by an algorithm. Those interpretations require additional
captured evidence, especially timestamps or delivery/ranking observations.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

from extract_har_interaction_graph import extract_comment_records

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]


IDENTITY_ACTION = "extract_captured_relational_fabric_identities"


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


def components(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[set[str]]:
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
    return sorted(result, key=lambda c: (-len(c), sorted(c)))


def build_fabric(
    records: list[dict[str, Any]],
    *,
    include_identities: bool = False,
    agreement: Path | None = None,
) -> dict[str, Any]:
    aid = require_identity_agreement(agreement) if include_identities else None

    people = sorted(
        {
            str(record[field])
            for record in records
            for field in ("comment_author_username", "post_author_username")
            if record.get(field)
        }
    )
    media = sorted({str(record["post_id"]) for record in records if record.get("post_id")})

    person_ids = {name: f"person_{i:03d}" for i, name in enumerate(people, 1)}
    media_ids = {post_id: f"media_{i:03d}" for i, post_id in enumerate(media, 1)}

    comment_incidence: Counter[tuple[str, str]] = Counter()
    authored_incidence: set[tuple[str, str]] = set()
    person_interaction: Counter[tuple[str, str]] = Counter()
    commenters_by_media: dict[str, set[str]] = defaultdict(set)
    commenters_by_media_batch: dict[tuple[str, int], set[str]] = defaultdict(set)
    observed_user_ids: dict[str, set[str]] = defaultdict(set)

    for record in records:
        post_id = str(record.get("post_id") or "")
        commenter = str(record.get("comment_author_username") or "")
        author = str(record.get("post_author_username") or "")
        if not post_id or not commenter or not author:
            continue

        comment_incidence[(commenter, post_id)] += 1
        authored_incidence.add((author, post_id))
        person_interaction[(commenter, author)] += 1
        commenters_by_media[post_id].add(commenter)
        commenters_by_media_batch[(post_id, int(record["entry_index"]))].add(commenter)

        raw_user_id = record.get("comment_author_id")
        if raw_user_id not in (None, ""):
            observed_user_ids[commenter].add(str(raw_user_id))

    shared_media: Counter[tuple[str, str]] = Counter()
    for post_id, commenters in commenters_by_media.items():
        for a, b in combinations(sorted(commenters), 2):
            shared_media[(a, b)] += 1

    shared_batches: Counter[tuple[str, str]] = Counter()
    for (_, _entry_index), commenters in commenters_by_media_batch.items():
        for a, b in combinations(sorted(commenters), 2):
            shared_batches[(a, b)] += 1

    nodes: list[dict[str, Any]] = []
    for name in people:
        node: dict[str, Any] = {"id": person_ids[name], "type": "person"}
        if include_identities:
            node["username"] = name
            ids = sorted(observed_user_ids.get(name, set()))
            if ids:
                node["observed_user_ids"] = ids
        nodes.append(node)

    for post_id in media:
        node = {"id": media_ids[post_id], "type": "media"}
        if include_identities:
            node["observed_media_id"] = post_id
        nodes.append(node)

    edges: list[dict[str, Any]] = []

    for (person, post_id), weight in sorted(
        comment_incidence.items(), key=lambda item: (person_ids[item[0][0]], media_ids[item[0][1]])
    ):
        edges.append(
            {
                "source": person_ids[person],
                "target": media_ids[post_id],
                "type": "commented_on_media",
                "directed": True,
                "weight": weight,
            }
        )

    for person, post_id in sorted(
        authored_incidence, key=lambda item: (person_ids[item[0]], media_ids[item[1]])
    ):
        edges.append(
            {
                "source": person_ids[person],
                "target": media_ids[post_id],
                "type": "authored_media",
                "directed": True,
                "weight": 1,
            }
        )

    for (commenter, author), weight in sorted(
        person_interaction.items(), key=lambda item: (person_ids[item[0][0]], person_ids[item[0][1]])
    ):
        edges.append(
            {
                "source": person_ids[commenter],
                "target": person_ids[author],
                "type": "commented_on_post_by",
                "directed": True,
                "weight": weight,
                "self_loop": commenter == author,
            }
        )

    for (a, b), media_weight in sorted(
        shared_media.items(), key=lambda item: (person_ids[item[0][0]], person_ids[item[0][1]])
    ):
        edges.append(
            {
                "source": person_ids[a],
                "target": person_ids[b],
                "type": "co_commented_on_media",
                "directed": False,
                "weight": media_weight,
                "shared_media_count": media_weight,
                "shared_capture_batch_count": shared_batches[(a, b)],
            }
        )

    topology_edges = [(str(edge["source"]), str(edge["target"])) for edge in edges]
    node_ids = [str(node["id"]) for node in nodes]
    comps = components(node_ids, topology_edges)

    media_with_multiple_commenters = sum(
        1 for commenters in commenters_by_media.values() if len(commenters) >= 2
    )

    result: dict[str, Any] = {
        "representation": "heterogeneous_relational_multigraph",
        "node_types": ["person", "media"],
        "relation_types": [
            "commented_on_media",
            "authored_media",
            "commented_on_post_by",
            "co_commented_on_media",
        ],
        "identity_labels_emitted": include_identities,
        "content_text_emitted": False,
        "person_node_count": len(people),
        "media_node_count": len(media),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "comment_evidence_count": len(records),
        "media_with_multiple_commenters": media_with_multiple_commenters,
        "co_engagement_edge_count": len(shared_media),
        "weak_component_count": len(comps),
        "largest_weak_component_nodes": len(comps[0]) if comps else 0,
        "fabric_obtained": len(nodes) >= 3 and len(edges) >= 2,
        "evidence_semantics": {
            "co_commented_on_media": (
                "Two captured commenters appeared on at least one of the same media objects."
            ),
            "shared_capture_batch_count": (
                "The pair appeared in the same HAR response entry this many times; "
                "this is observation-batch evidence, not an interaction timestamp."
            ),
        },
        "inference_limits": {
            "per_comment_timestamps_available": False,
            "synchronized_viewing_claimed": False,
            "shared_recommendation_delivery_claimed": False,
            "algorithmic_causality_claimed": False,
        },
        "nodes": nodes,
        "edges": edges,
    }
    if aid:
        result["agreement_id"] = aid
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Recover a post-mediated heterogeneous relational fabric from a HAR"
    )
    ap.add_argument("har", type=Path, help="Input .har file")
    ap.add_argument("-o", "--output", type=Path, help="Write JSON to this path")
    ap.add_argument(
        "--include-identities",
        action="store_true",
        help="Include captured usernames/user and media IDs; requires an agreement",
    )
    ap.add_argument("--agreement", type=Path, help="Agent-owned agreement JSON")
    ap.add_argument(
        "--require-fabric",
        action="store_true",
        help="Exit nonzero unless a heterogeneous graph is recovered",
    )
    args = ap.parse_args()

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)

    try:
        fabric = build_fabric(
            extract_comment_records(har),
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
