import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement  # noqa: E402
import extract_har_temporal_evidence as temporal  # noqa: E402


class TemporalEvidenceTests(unittest.TestCase):
    def _har(self):
        payload = {
            "extensions": {
                "server_metadata": {
                    "request_start_time_ms": 1786242255106,
                    "time_at_flush_ms": 1786242255166,
                }
            },
            "data": {
                "xdt_api__v1__feed__reels_tray": {
                    "tray": [{"id": "story-user", "seen": 1786239452}]
                },
                "get_slide_mailbox_for_iris_subscription": {
                    "threads_by_folder": {
                        "edges": [
                            {
                                "node": {
                                    "as_ig_direct_thread": {
                                        "id": "thread-secret",
                                        "last_activity_timestamp_ms": "1786240524413",
                                        "slide_read_receipts": [
                                            {
                                                "participant_fbid": "participant-secret",
                                                "watermark_timestamp_ms": "1786240501065",
                                            }
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                },
                "media": {"pk": "media-secret", "taken_at": 1786210165},
            },
        }
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        return {
            "log": {
                "entries": [
                    {
                        "startedDateTime": "2026-08-09T02:24:15.143Z",
                        "response": {"content": {"encoding": "base64", "text": encoded}},
                    }
                ]
            }
        }

    def test_typed_timestamps_preserve_semantics_and_hide_ids(self):
        result = temporal.inspect_har(self._har())
        semantics = set(result["semantic_counts"])
        self.assertIn("server_request_start", semantics)
        self.assertIn("server_response_flush", semantics)
        self.assertIn("thread_last_activity", semantics)
        self.assertIn("read_through_watermark", semantics)
        self.assertIn("story_seen_through_watermark", semantics)
        self.assertIn("media_taken_at", semantics)
        self.assertTrue(result["inference_limits"]["exact_temporal_values_available"])
        self.assertFalse(result["inference_limits"]["exact_view_action_timestamps_available"])
        self.assertFalse(result["inference_limits"]["read_watermark_is_read_action_time"])
        self.assertFalse(result["inference_limits"]["story_seen_watermark_is_view_action_time"])
        self.assertFalse(result["inference_limits"]["synchronized_viewing_claimed"])

        dumped = json.dumps(result)
        self.assertNotIn("participant-secret", dumped)
        self.assertNotIn("thread-secret", dumped)
        self.assertNotIn("media-secret", dumped)
        self.assertNotIn("story-user", dumped)

    def test_same_batch_gets_exact_capture_time_without_event_time_claim(self):
        old = temporal.extract_comment_records
        temporal.extract_comment_records = lambda har: [
            {
                "entry_index": 0,
                "post_id": "m1",
                "comment_author_username": "alpha",
            },
            {
                "entry_index": 0,
                "post_id": "m1",
                "comment_author_username": "beta",
            },
        ]
        try:
            result = temporal.inspect_har(
                {
                    "log": {
                        "entries": [
                            {
                                "startedDateTime": "2026-08-09T19:16:19.456Z",
                                "response": {"content": {"text": "{}"}},
                            }
                        ]
                    }
                }
            )
        finally:
            temporal.extract_comment_records = old

        self.assertEqual(result["same_response_batch_co_observation_count"], 1)
        row = result["co_observations"][0]
        self.assertEqual(row["co_observed_at"], "2026-08-09T19:16:19.456Z")
        self.assertFalse(row["participant_event_time"])
        self.assertFalse(row["synchronized_viewing_claimed"])
        dumped = json.dumps(result)
        self.assertNotIn("alpha", dumped)
        self.assertNotIn("beta", dumped)
        self.assertNotIn('"m1"', dumped)

    def test_starter_agreement_registers_temporal_evidence_action(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            agent_agreement.write_template(path)
            agreement = agent_agreement.load_json(path)
        allowed, reason = agent_agreement.action_status(
            agreement, "extract_captured_temporal_evidence"
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "action_declared")


if __name__ == "__main__":
    unittest.main()
