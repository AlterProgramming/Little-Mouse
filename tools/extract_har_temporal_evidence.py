#!/usr/bin/env python3
"""Recover typed temporal evidence already present in a browser HAR.

The extractor keeps timestamp semantics separate. Capture-observation times,
server transport times, content creation times, and read/seen watermarks are
all real timestamps, but they are not interchangeable with a participant's
viewing-action timestamp.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

try:
    from extract_har_interaction_graph import extract_comment_records
except ImportError:  # pragma: no cover
    extract_comment_records = None  # type: ignore[assignment]


IDENTIFIER_KEYS = (
    "participant_fbid",
    "viewer_id",
    "viewer_igid",
    "user_id",
    "id",
    "pk",
    "thread_id",
    "thread_fbid",
    "media_id",
    "post_id",
    "comment_id",
    "code",
    "username",
)


def _response_text(entry: dict[str, Any]) -> str | None:
    content = (entry.get("response", {}) or {}).get("content", {}) or {}
    text = content.get("text")
    if text is None:
        return None
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(str(text)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return str(text)


def _json_maybe(text: str | None) -> Any | None:
    if text is None:
        return None
    value = text.strip()
    if value.startswith("for (;;);"):
        value = value[len("for (;;);") :].lstrip()
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _iso_from_ms(ms: int) -> str:
    return (
        datetime.fromtimestamp(ms / 1000.0, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _normalize_numeric(value: Any, unit: str) -> tuple[int, str] | None:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    if unit == "s":
        ms = number * 1000
        precision = "second"
    elif unit == "ms":
        ms = number
        precision = "millisecond"
    else:
        return None
    # Reject counters and positions that merely look numeric.
    if not (1262304000000 <= ms <= 4102444800000):
        return None
    return ms, precision


def _parse_iso(value: Any) -> tuple[int, str] | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    ms = int(dt.timestamp() * 1000)
    return ms, "millisecond" if "." in value else "second"


def _subject_fingerprint(
    ancestors: list[dict[str, Any]],
    parent: dict[str, Any] | None,
    fallback: str,
) -> tuple[str, list[str]]:
    parts: list[str] = []
    names: list[str] = []
    for mapping in ([parent] if parent else []) + list(reversed(ancestors)):
        if not isinstance(mapping, dict):
            continue
        for key in IDENTIFIER_KEYS:
            value = mapping.get(key)
            if value in (None, "") or isinstance(value, (dict, list)):
                continue
            token = f"{key}={value}"
            if token not in parts:
                parts.append(token)
                names.append(key)
            if len(parts) >= 3:
                break
        if len(parts) >= 3:
            break
    material = "\x1f".join(parts) if parts else fallback
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], sorted(set(names))


def _classify(path: str, key: str) -> tuple[str, str, str, bool] | None:
    # semantic, role, unit, supports synchronized-viewing inference
    if key == "request_start_time_ms" and ".extensions.server_metadata." in path:
        return "server_request_start", "server_transport_time", "ms", False
    if key == "time_at_flush_ms" and ".extensions.server_metadata." in path:
        return "server_response_flush", "server_transport_time", "ms", False
    if key == "last_activity_timestamp_ms" and "as_ig_direct_thread" in path:
        return "thread_last_activity", "conversation_activity_time", "ms", False
    if key == "watermark_timestamp_ms" and "slide_read_receipts" in path:
        return "read_through_watermark", "watermark_position_time", "ms", False
    if key == "seen" and "reels_tray.tray" in path:
        return "story_seen_through_watermark", "watermark_position_time", "s", False
    if key == "reel_media_seen_timestamp":
        return "story_seen_through_watermark", "watermark_position_time", "s", False
    if key == "latest_reel_media" and "reels_tray.tray" in path:
        return "story_latest_media", "content_creation_time", "s", False
    if key == "taken_at":
        return "media_taken_at", "content_creation_time", "s", False
    if key in {"created_at", "created_at_utc"} and ".caption." in path:
        return "caption_created_at", "content_creation_time", "s", False
    # These deliberately narrow names are future-compatible direct action fields.
    # The extractor never synthesizes them from `seen` or read-watermark fields.
    if key in {"viewed_at_ms", "view_timestamp_ms"}:
        return "view_action", "participant_action_time", "ms", True
    if key in {"viewed_at", "view_timestamp"}:
        return "view_action", "participant_action_time", "s", True
    return None


def _walk(
    value: Any,
    path: str = "$",
    ancestors: list[dict[str, Any]] | None = None,
):
    ancestors = ancestors or []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child, value, ancestors
            yield from _walk(child, child_path, ancestors + [value])
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]", ancestors)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _co_observation_evidence(har: dict[str, Any]) -> list[dict[str, Any]]:
    """Timestamp comment co-observation without upgrading it to event synchrony."""
    if extract_comment_records is None:
        return []
    records = extract_comment_records(har)
    entries = har.get("log", {}).get("entries", []) or []
    groups: dict[tuple[str, int], set[str]] = {}
    for record in records:
        post_id = str(record.get("post_id") or "")
        commenter = str(record.get("comment_author_username") or "")
        if not post_id or not commenter:
            continue
        entry_index = int(record.get("entry_index", -1))
        groups.setdefault((post_id, entry_index), set()).add(commenter)

    result: list[dict[str, Any]] = []
    for (post_id, entry_index), commenters in sorted(groups.items()):
        if len(commenters) < 2 or not (0 <= entry_index < len(entries)):
            continue
        observed = entries[entry_index].get("startedDateTime")
        parsed = _parse_iso(observed)
        if parsed is None:
            continue
        timestamp_ms, precision = parsed
        for a, b in combinations(sorted(commenters), 2):
            result.append(
                {
                    "participant_fingerprints": sorted([_fingerprint(a), _fingerprint(b)]),
                    "media_fingerprint": _fingerprint(post_id),
                    "capture_entry_index": entry_index,
                    "co_observed_at": _iso_from_ms(timestamp_ms),
                    "timestamp_ms": timestamp_ms,
                    "precision": precision,
                    "role": "browser_observation_time",
                    "participant_event_time": False,
                    "synchronized_viewing_claimed": False,
                }
            )
    return result


def inspect_har(har: dict[str, Any]) -> dict[str, Any]:
    aggregate: dict[tuple[Any, ...], dict[str, Any]] = {}
    capture_times: list[str] = []
    direct_view_action_count = 0

    for entry_index, entry in enumerate(har.get("log", {}).get("entries", []) or []):
        observed = entry.get("startedDateTime")
        observed_ms = _parse_iso(observed)
        if observed_ms is not None:
            capture_times.append(str(observed))
            key = ("capture_observation", observed_ms[0], f"entry:{entry_index}")
            aggregate[key] = {
                "semantic": "capture_observation",
                "role": "browser_observation_time",
                "timestamp_ms": observed_ms[0],
                "timestamp_utc": _iso_from_ms(observed_ms[0]),
                "precision": observed_ms[1],
                "source_field": "startedDateTime",
                "subject_fingerprint": _fingerprint(f"entry:{entry_index}"),
                "context_identifier_fields": [],
                "supports_synchronized_viewing": False,
                "observation_count": 1,
                "first_capture_observed_at": str(observed),
                "last_capture_observed_at": str(observed),
            }

        payload = _json_maybe(_response_text(entry))
        if payload is None:
            continue
        for path, field, raw, parent, ancestors in _walk(payload):
            spec = _classify(path, field)
            if spec is None:
                continue
            semantic, role, unit, supports_sync = spec
            normalized = _normalize_numeric(raw, unit)
            if normalized is None:
                continue
            timestamp_ms, precision = normalized
            subject, context_fields = _subject_fingerprint(
                ancestors, parent, fallback=f"entry:{entry_index}:{path}"
            )
            dedupe_key = (semantic, timestamp_ms, subject)
            row = aggregate.get(dedupe_key)
            if row is None:
                row = {
                    "semantic": semantic,
                    "role": role,
                    "timestamp_ms": timestamp_ms,
                    "timestamp_utc": _iso_from_ms(timestamp_ms),
                    "precision": precision,
                    "source_field": field,
                    "subject_fingerprint": subject,
                    "context_identifier_fields": context_fields,
                    "supports_synchronized_viewing": supports_sync,
                    "observation_count": 0,
                    "first_capture_observed_at": str(observed) if observed else None,
                    "last_capture_observed_at": str(observed) if observed else None,
                }
                aggregate[dedupe_key] = row
            row["observation_count"] += 1
            if observed:
                if row["first_capture_observed_at"] is None or str(observed) < row["first_capture_observed_at"]:
                    row["first_capture_observed_at"] = str(observed)
                if row["last_capture_observed_at"] is None or str(observed) > row["last_capture_observed_at"]:
                    row["last_capture_observed_at"] = str(observed)
            if supports_sync:
                direct_view_action_count += 1

    events = sorted(
        aggregate.values(),
        key=lambda row: (row["timestamp_ms"], row["semantic"], row["subject_fingerprint"]),
    )
    semantic_counts = Counter(row["semantic"] for row in events)
    role_counts = Counter(row["role"] for row in events)
    exact_non_capture = [row for row in events if row["semantic"] != "capture_observation"]
    co_observations = _co_observation_evidence(har)

    return {
        "representation": "typed_temporal_evidence",
        "values_emitted": True,
        "identity_labels_emitted": False,
        "event_count": len(events),
        "unique_exact_non_capture_timestamp_count": len(
            {row["timestamp_ms"] for row in exact_non_capture}
        ),
        "semantic_counts": dict(sorted(semantic_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "capture_window": {
            "first": min(capture_times) if capture_times else None,
            "last": max(capture_times) if capture_times else None,
        },
        "same_response_batch_co_observation_count": len(co_observations),
        "co_observations": co_observations,
        "inference_limits": {
            "exact_temporal_values_available": bool(exact_non_capture),
            "exact_view_action_timestamps_available": direct_view_action_count > 0,
            "capture_observation_time_is_participant_event_time": False,
            "same_response_batch_time_is_participant_event_time": False,
            "read_watermark_is_read_action_time": False,
            "story_seen_watermark_is_view_action_time": False,
            "synchronized_viewing_claimed": False,
        },
        "events": events,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover typed temporal evidence from a HAR")
    ap.add_argument("har", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()
    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)
    result = {"source": args.har.name, **inspect_har(har)}
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(args.output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
