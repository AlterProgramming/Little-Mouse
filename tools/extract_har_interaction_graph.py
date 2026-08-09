#!/usr/bin/env python3
"""Recover a pseudonymized user-interaction graph from relationships captured in a HAR.

The extractor is offline. It currently recognizes Instagram Bloks activity-center
comment records where a captured comment author is related to the author of the
post they commented on. The default graph preserves topology and weights without
emitting usernames, comment text, post text, cookies, tokens, or request secrets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from agent_agreement import action_status, agreement_id, load_json
except ImportError:  # pragma: no cover
    action_status = agreement_id = load_json = None  # type: ignore[assignment]


@dataclass
class Call:
    name: str
    args: list[Any]


TOKEN_RE = re.compile(
    r'\s*(?:(?P<string>"(?:\\.|[^"\\])*")|(?P<left>\()|(?P<right>\))|'
    r'(?P<comma>,)|(?P<atom>[^(),\s]+))',
    re.S,
)

RELATION_TYPE = "commented_on_post_by"
IDENTITY_ACTION = "extract_captured_interaction_graph_identities"


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


def walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, str):
        yield value


def tokenize(text: str) -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    pos = 0
    while pos < len(text):
        match = TOKEN_RE.match(text, pos)
        if not match:
            raise ValueError(f"unable to tokenize Bloks expression at offset {pos}")
        pos = match.end()
        kind = str(match.lastgroup)
        raw = match.group(kind)
        if kind == "comma":
            continue
        if kind == "string":
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                pass
        result.append((kind, raw))
    return result


def parse_expr(tokens: list[tuple[str, Any]], index: int = 0) -> tuple[Any, int]:
    kind, value = tokens[index]
    if kind == "left":
        if index + 1 >= len(tokens) or tokens[index + 1][0] != "atom":
            raise ValueError("Bloks call missing function name")
        name = str(tokens[index + 1][1])
        args: list[Any] = []
        cursor = index + 2
        while cursor < len(tokens) and tokens[cursor][0] != "right":
            item, cursor = parse_expr(tokens, cursor)
            args.append(item)
        if cursor >= len(tokens):
            raise ValueError("unterminated Bloks expression")
        return Call(name, args), cursor + 1
    if kind == "string":
        return value, index + 1
    if kind == "atom":
        text = str(value)
        if text == "null":
            return None, index + 1
        if text == "true":
            return True, index + 1
        if text == "false":
            return False, index + 1
        if re.fullmatch(r"-?\d+", text):
            return int(text), index + 1
        if re.fullmatch(r"-?\d+\.\d+", text):
            return float(text), index + 1
        return text, index + 1
    raise ValueError(f"unexpected Bloks token: {kind}")


def evaluate(value: Any) -> Any:
    if not isinstance(value, Call):
        return value
    args = [evaluate(arg) for arg in value.args]
    if value.name == "bk.action.array.Make":
        return args
    if value.name == "bk.action.map.Make":
        if len(args) >= 2 and isinstance(args[0], list) and isinstance(args[1], list):
            return {str(key): item for key, item in zip(args[0], args[1])}
        return Call(value.name, args)
    if value.name.endswith(".bool.Const") and args:
        return bool(args[0])
    if re.search(r"\.(?:i32|i64|f32|f64)\.Const$", value.name) and args:
        return args[0]
    if value.name.endswith(".string.Const") and args:
        return str(args[0])
    return Call(value.name, args)


def parse_bloks(text: str) -> Any:
    tokens = tokenize(text)
    if not tokens:
        return None
    parsed, end = parse_expr(tokens)
    if end != len(tokens):
        raise ValueError("unexpected trailing Bloks tokens")
    return evaluate(parsed)


def walk_maps(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_maps(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_maps(child)
    elif isinstance(value, Call):
        for child in value.args:
            yield from walk_maps(child)


def extract_comment_records(har: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[tuple[Any, ...], dict[str, Any]] = {}
    entries = har.get("log", {}).get("entries", []) or []

    for entry_index, entry in enumerate(entries):
        content = (entry.get("response", {}) or {}).get("content", {}) or {}
        payload = parse_json_maybe(str(content.get("text", "") or ""))
        if payload is None:
            continue
        for text in walk_strings(payload):
            if not text.lstrip().startswith("("):
                continue
            if "bk.action.map.Make" not in text:
                continue
            if "comment_author_username" not in text or "post_author_username" not in text:
                continue
            try:
                parsed = parse_bloks(text)
            except ValueError:
                continue
            for mapping in walk_maps(parsed):
                commenter = mapping.get("comment_author_username")
                post_author = mapping.get("post_author_username")
                if not isinstance(commenter, str) or not commenter:
                    continue
                if not isinstance(post_author, str) or not post_author:
                    continue
                record = {
                    "entry_index": entry_index,
                    "comment_id": mapping.get("comment_id"),
                    "post_id": mapping.get("post_id"),
                    "comment_author_id": mapping.get("comment_author_id"),
                    "comment_author_username": commenter,
                    "post_author_username": post_author,
                    "user_created_this_comment": mapping.get("user_created_this_comment"),
                    "is_self_media": mapping.get("is_self_media"),
                }
                key = (
                    record["comment_id"],
                    record["post_id"],
                    commenter,
                    post_author,
                )
                current = records.get(key)
                if current is None or entry_index < int(current["entry_index"]):
                    records[key] = record

    return sorted(
        records.values(),
        key=lambda row: (
            int(row["entry_index"]),
            str(row.get("comment_id") or ""),
            str(row.get("post_id") or ""),
        ),
    )


def weak_components(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        adjacency[node]
    for source, target in edges:
        adjacency[source].add(target)
        adjacency[target].add(source)

    unseen = set(adjacency)
    components: list[set[str]] = []
    while unseen:
        start = min(unseen)
        component: set[str] = set()
        queue: deque[str] = deque([start])
        unseen.remove(start)
        while queue:
            node = queue.popleft()
            component.add(node)
            for neighbor in adjacency[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return sorted(components, key=lambda component: (-len(component), sorted(component)))


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


def build_graph(
    records: list[dict[str, Any]],
    *,
    include_identities: bool = False,
    agreement: Path | None = None,
) -> dict[str, Any]:
    aid = None
    if include_identities:
        aid = require_identity_agreement(agreement)

    usernames = sorted(
        {
            str(record[field])
            for record in records
            for field in ("comment_author_username", "post_author_username")
            if record.get(field)
        }
    )
    node_ids = {username: f"person_{index:03d}" for index, username in enumerate(usernames, 1)}

    author_ids: dict[str, set[str]] = defaultdict(set)
    edge_counts: Counter[tuple[str, str]] = Counter()
    edge_entries: dict[tuple[str, str], list[int]] = defaultdict(list)
    for record in records:
        source = str(record["comment_author_username"])
        target = str(record["post_author_username"])
        author_id = record.get("comment_author_id")
        if author_id not in (None, ""):
            author_ids[source].add(str(author_id))
        edge_counts[(source, target)] += 1
        edge_entries[(source, target)].append(int(record["entry_index"]))

    indegree_actions: Counter[str] = Counter()
    outdegree_actions: Counter[str] = Counter()
    for (source, target), weight in edge_counts.items():
        outdegree_actions[source] += weight
        indegree_actions[target] += weight

    nodes = []
    for username in usernames:
        node: dict[str, Any] = {
            "id": node_ids[username],
            "comment_actions_out": outdegree_actions[username],
            "comment_actions_in": indegree_actions[username],
        }
        if include_identities:
            node["username"] = username
            ids = sorted(author_ids.get(username, set()))
            if ids:
                node["observed_user_ids"] = ids
        nodes.append(node)

    edges = []
    for (source, target), weight in sorted(
        edge_counts.items(), key=lambda item: (node_ids[item[0][0]], node_ids[item[0][1]])
    ):
        entries = edge_entries[(source, target)]
        edges.append(
            {
                "source": node_ids[source],
                "target": node_ids[target],
                "type": RELATION_TYPE,
                "weight": weight,
                "self_loop": source == target,
                "first_observed_entry": min(entries),
                "last_observed_entry": max(entries),
            }
        )

    components = weak_components(usernames, edge_counts.keys())
    result: dict[str, Any] = {
        "representation": "directed_weighted_graph",
        "relation_types": [RELATION_TYPE],
        "identity_labels_emitted": include_identities,
        "content_text_emitted": False,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "interaction_evidence_count": sum(edge_counts.values()),
        "weak_component_count": len(components),
        "largest_weak_component_nodes": len(components[0]) if components else 0,
        "network_obtained": len(nodes) >= 2 and len(edges) >= 1,
        "nodes": nodes,
        "edges": edges,
    }
    if aid:
        result["agreement_id"] = aid
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Recover a user-interaction graph from relationships captured in a HAR"
    )
    ap.add_argument("har", type=Path, help="Input .har file")
    ap.add_argument("-o", "--output", type=Path, help="Write graph JSON to this path")
    ap.add_argument(
        "--include-identities",
        action="store_true",
        help="Include captured usernames/user IDs; requires an agent-owned agreement",
    )
    ap.add_argument("--agreement", type=Path, help="Agent-owned agreement JSON")
    ap.add_argument(
        "--require-network",
        action="store_true",
        help="Exit nonzero unless the capture yields at least two nodes and one edge",
    )
    args = ap.parse_args()

    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)

    try:
        graph = build_graph(
            extract_comment_records(har),
            include_identities=args.include_identities,
            agreement=args.agreement,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    graph["source"] = args.har.name
    output = json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    else:
        print(output, end="")

    if args.require_network and not graph["network_obtained"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
