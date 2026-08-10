import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract_har_trace_ledger as trace  # noqa: E402
import render_trace_viewer  # noqa: E402


class TraceLedgerTests(unittest.TestCase):
    def test_alias_history_joins_on_stable_id_across_captures(self):
        captures = [
            {
                "capture_name": "old.har",
                "actor_id": "1",
                "timestamps": {0: "2026-01-01T00:00:00Z"},
                "comments": [
                    {
                        "entry_index": 0,
                        "comment_author_id": "1",
                        "comment_author_username": "old_name",
                        "post_id": "m1",
                        "comment_id": "c1",
                        "user_created_this_comment": True,
                    }
                ],
                "likes": [],
                "blocked": [],
                "surfaced": [],
            },
            {
                "capture_name": "new.har",
                "actor_id": "1",
                "timestamps": {0: "2026-02-01T00:00:00Z"},
                "comments": [
                    {
                        "entry_index": 0,
                        "comment_author_id": "1",
                        "comment_author_username": "new_name",
                        "post_id": "m2",
                        "comment_id": "c2",
                        "user_created_this_comment": True,
                    }
                ],
                "likes": [],
                "blocked": [],
                "surfaced": [],
            },
        ]
        ledger = trace.build_trace_ledger(captures, pseudonym_secret=b"x" * 32)
        actor_nodes = [node for node in ledger["nodes"] if node["is_capture_actor"]]
        self.assertEqual(len(actor_nodes), 1)
        aliases = [
            row for row in ledger["alias_history"] if row["entity"] == actor_nodes[0]["id"]
        ]
        self.assertEqual({row["alias"] for row in aliases}, {"alias_01", "alias_02"})
        self.assertEqual(ledger["alias_transition_count"], 1)
        dumped = json.dumps(ledger)
        self.assertNotIn("old_name", dumped)
        self.assertNotIn("new_name", dumped)

    def test_only_owner_actions_become_trace_events(self):
        capture = {
            "capture_name": "x.har",
            "actor_id": "1",
            "timestamps": {
                0: "2026-01-01T00:00:00Z",
                1: "2026-01-01T00:01:00Z",
                2: "2026-01-01T00:02:00Z",
            },
            "comments": [
                {
                    "entry_index": 0,
                    "comment_author_id": "2",
                    "comment_author_username": "peer",
                    "post_id": "m1",
                    "comment_id": "c1",
                    "user_created_this_comment": False,
                }
            ],
            "likes": [{"entry_index": 1, "media_id": "m2"}],
            "blocked": [
                {
                    "entry_index": 2,
                    "user_id": "3",
                    "username": "blocked",
                    "is_auto_blocked": False,
                }
            ],
            "surfaced": [{"entry_index": 2, "user_id": "4", "username": "candidate"}],
        }
        ledger = trace.build_trace_ledger([capture], pseudonym_secret=b"y" * 32)
        self.assertEqual(
            [row["action"] for row in ledger["traces"]],
            ["liked_media", "blocked_person"],
        )
        self.assertEqual(ledger["context_observation_count"], 1)
        self.assertTrue(all(row["capture_visible"] for row in ledger["traces"]))
        self.assertTrue(
            all(not row["public_visibility_claimed"] for row in ledger["traces"])
        )

    def test_focus_username_resolves_to_pseudonymous_center(self):
        capture = {
            "capture_name": "x.har",
            "actor_id": "1",
            "timestamps": {0: "2026-01-01T00:00:00Z"},
            "comments": [],
            "likes": [],
            "blocked": [
                {
                    "entry_index": 0,
                    "user_id": "3",
                    "username": "secret_alias",
                    "is_auto_blocked": False,
                }
            ],
            "surfaced": [],
        }
        ledger = trace.build_trace_ledger(
            [capture],
            pseudonym_secret=b"z" * 32,
            focus_username="secret_alias",
        )
        self.assertEqual(ledger["focus"]["resolution"], "captured_alias")
        self.assertFalse(ledger["focus"]["identity_label_emitted"])
        self.assertEqual(ledger["focus"]["incident_trace_count"], 1)
        self.assertTrue(ledger["focus_view"]["projection_only"])
        self.assertTrue(ledger["focus_view"]["underlying_graph_centerless"])
        self.assertEqual(ledger["focus_view"]["hop_counts"], {"hop_0": 1, "hop_1": 1})
        self.assertNotIn("secret_alias", json.dumps(ledger))

    def test_viewer_embeds_ledger_without_inventing_public_visibility(self):
        ledger = {
            "trace_event_count": 1,
            "alias_observation_count": 0,
            "alias_transition_count": 0,
            "node_count": 2,
            "focus": {"entity": "person_a", "incident_trace_count": 1},
            "focus_view": {
                "center": "person_a",
                "reachable_node_count": 2,
                "max_hop": 1,
            },
            "nodes": [
                {"id": "person_a", "type": "person", "is_capture_actor": False, "is_focus": True},
                {"id": "media_b", "type": "media", "is_capture_actor": False, "is_focus": False},
            ],
            "traces": [
                {
                    "actor": "person_a",
                    "target": "media_b",
                    "action": "liked_media",
                    "trace_class": "activity_history",
                    "observed_at": "2026-01-01T00:00:00Z",
                    "capture": "x.har",
                    "entry_index": 1,
                }
            ],
            "alias_history": [],
        }
        text = render_trace_viewer.render(ledger)
        self.assertIn("Profile-centered evidence map", text)
        self.assertIn("temporary focus projection", text)
        self.assertIn("underlying graph remains centerless", text)
        self.assertIn("liked_media", text)


if __name__ == "__main__":
    unittest.main()
