#!/usr/bin/env python3
"""Promote repeated typed temporal observations without inventing exact events.

Input is one or more JSON outputs from extract_har_temporal_evidence.py, ordered
by capture time. Promotion is monotonic in evidence strength but reversible in
interpretation: source observations are retained and every derived interval
records its parents.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evidence_contract import EvidenceItem, build_result, no_result

WATERMARK_SEMANTICS = {"read_through_watermark", "story_seen_through_watermark"}
DIRECT_ACTION_SEMANTICS = {"view_action"}


def _observation_time(row: dict[str, Any]) -> str | None:
    return row.get("last_capture_observed_at") or row.get("first_capture_observed_at")


def promote(captures: list[dict[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for capture_index, capture in enumerate(captures):
        for row in capture.get("events", []):
            observations.append({**row, "capture_index": capture_index})

    by_subject_semantic: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        semantic = str(row.get("semantic") or "")
        subject = str(row.get("subject_fingerprint") or "")
        if semantic in WATERMARK_SEMANTICS and subject:
            by_subject_semantic[(subject, semantic)].append(row)

    intervals: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    epistemic_items: list[EvidenceItem] = []

    for (subject, semantic), rows in sorted(by_subject_semantic.items()):
        rows.sort(key=lambda r: (r.get("capture_index", -1), r.get("timestamp_ms", 0)))
        for previous, current in zip(rows, rows[1:]):
            old = int(previous.get("timestamp_ms", 0))
            new = int(current.get("timestamp_ms", 0))
            previous_ref = f"capture:{previous['capture_index']}:{subject}:{semantic}:{old}"
            current_ref = f"capture:{current['capture_index']}:{subject}:{semantic}:{new}"

            if new < old:
                contradictions.append({
                    "type": "non_monotonic_watermark",
                    "subject_fingerprint": subject,
                    "semantic": semantic,
                    "previous_timestamp_ms": old,
                    "current_timestamp_ms": new,
                    "previous_capture_index": previous["capture_index"],
                    "current_capture_index": current["capture_index"],
                })
                epistemic_items.append(EvidenceItem(
                    level="OBSERVATION",
                    statement="Comparable watermark observations are non-monotonic; no action interval is promoted.",
                    support=(previous_ref, current_ref),
                ))
                continue
            if new == old:
                continue

            lower = _observation_time(previous)
            upper = _observation_time(current)
            intervals.append({
                "promotion_level": "bounded_action_interval",
                "semantic": semantic,
                "subject_fingerprint": subject,
                "watermark_from_ms": old,
                "watermark_to_ms": new,
                "lower_bound_observed_at": lower,
                "upper_bound_observed_at": upper,
                "parent_capture_indices": [previous["capture_index"], current["capture_index"]],
                "exact_event_time_claimed": False,
                "participant_action_semantics_claimed": False,
                "reversible": True,
            })
            epistemic_items.append(EvidenceItem(
                level="DERIVATION",
                statement="A comparable watermark advanced between two exact capture observations, yielding a bounded interval only.",
                support=(previous_ref, current_ref),
            ))

    direct_actions = [
        row for row in observations if row.get("semantic") in DIRECT_ACTION_SEMANTICS
        and row.get("supports_synchronized_viewing") is True
    ]
    for row in direct_actions:
        epistemic_items.append(EvidenceItem(
            level="OBSERVATION",
            statement="An explicit participant action-time field was present in the typed temporal evidence.",
            support=(
                f"capture:{row.get('capture_index')}:{row.get('subject_fingerprint')}:{row.get('semantic')}:{row.get('timestamp_ms')}",
            ),
        ))

    epistemic = build_result(epistemic_items) if epistemic_items else no_result()

    return {
        "representation": "promoted_temporal_evidence",
        "result_status": epistemic["result_status"],
        "capture_count": len(captures),
        "source_observation_count": len(observations),
        "bounded_action_interval_count": len(intervals),
        "direct_action_count": len(direct_actions),
        "contradiction_count": len(contradictions),
        "promotions": intervals,
        "direct_actions": direct_actions,
        "contradictions": contradictions,
        "epistemic": epistemic,
        "inference_limits": {
            "watermark_transition_is_exact_action_time": False,
            "bounded_interval_is_direct_view_action": False,
            "direct_view_action_timestamps_available": bool(direct_actions),
            "synchronized_viewing_claimed": False,
            "replacement_hypothesis_generated": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote temporal evidence across captures")
    ap.add_argument("captures", nargs="+", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()
    captures = [json.loads(path.read_text(encoding="utf-8")) for path in args.captures]
    result = promote(captures)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
