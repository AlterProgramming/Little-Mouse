import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement  # noqa: E402
import extract_har_relational_fabric as relational_fabric  # noqa: E402


def record(entry, comment_id, post_id, commenter, author, commenter_id=""):
    return {
        "entry_index": entry,
        "comment_id": comment_id,
        "post_id": post_id,
        "comment_author_id": commenter_id,
        "comment_author_username": commenter,
        "post_author_username": author,
        "user_created_this_comment": False,
        "is_self_media": commenter == author,
    }


class RelationalFabricTests(unittest.TestCase):
    def test_same_media_creates_heterogeneous_fabric_and_coengagement_edge(self):
        records = [
            record(10, "c1", "m1", "alpha", "gamma", "u1"),
            record(10, "c2", "m1", "beta", "gamma", "u2"),
        ]
        fabric = relational_fabric.build_fabric(records)

        self.assertTrue(fabric["fabric_obtained"])
        self.assertEqual(fabric["representation"], "heterogeneous_relational_multigraph")
        self.assertEqual(fabric["person_node_count"], 3)
        self.assertEqual(fabric["media_node_count"], 1)
        self.assertEqual(fabric["node_count"], 4)
        self.assertEqual(fabric["edge_count"], 6)
        self.assertEqual(fabric["co_engagement_edge_count"], 1)
        self.assertEqual(fabric["media_with_multiple_commenters"], 1)

        relation_types = {edge["type"] for edge in fabric["edges"]}
        self.assertEqual(
            relation_types,
            {
                "commented_on_media",
                "authored_media",
                "commented_on_post_by",
                "co_commented_on_media",
            },
        )

        co_edge = next(
            edge for edge in fabric["edges"] if edge["type"] == "co_commented_on_media"
        )
        self.assertFalse(co_edge["directed"])
        self.assertEqual(co_edge["shared_media_count"], 1)
        self.assertEqual(co_edge["shared_capture_batch_count"], 1)

        dumped = json.dumps(fabric)
        self.assertNotIn("alpha", dumped)
        self.assertNotIn("beta", dumped)
        self.assertNotIn("gamma", dumped)

    def test_repeated_comments_increase_incidence_not_shared_media_count(self):
        records = [
            record(10, "c1", "m1", "alpha", "gamma"),
            record(10, "c2", "m1", "alpha", "gamma"),
            record(11, "c3", "m1", "beta", "gamma"),
        ]
        fabric = relational_fabric.build_fabric(records)

        co_edge = next(
            edge for edge in fabric["edges"] if edge["type"] == "co_commented_on_media"
        )
        self.assertEqual(co_edge["shared_media_count"], 1)
        self.assertEqual(co_edge["shared_capture_batch_count"], 0)

        comment_edges = [
            edge for edge in fabric["edges"] if edge["type"] == "commented_on_media"
        ]
        self.assertIn(2, [edge["weight"] for edge in comment_edges])

    def test_capture_does_not_upgrade_coengagement_into_sync_or_algorithmic_claim(self):
        fabric = relational_fabric.build_fabric(
            [
                record(10, "c1", "m1", "alpha", "gamma"),
                record(10, "c2", "m1", "beta", "gamma"),
            ]
        )
        limits = fabric["inference_limits"]
        self.assertFalse(limits["per_comment_timestamps_available"])
        self.assertFalse(limits["synchronized_viewing_claimed"])
        self.assertFalse(limits["shared_recommendation_delivery_claimed"])
        self.assertFalse(limits["algorithmic_causality_claimed"])

    def test_identity_labels_require_separate_agreement(self):
        records = [record(10, "c1", "m1", "alpha", "gamma")]
        with self.assertRaisesRegex(ValueError, "--agreement is required"):
            relational_fabric.build_fabric(records, include_identities=True)

    def test_starter_agreement_allows_pseudonymized_fabric_not_identities(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            agent_agreement.write_template(path)
            agreement = agent_agreement.load_json(path)

        allowed, reason = agent_agreement.action_status(
            agreement, "extract_captured_relational_fabric"
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "action_declared")

        identity_allowed, identity_reason = agent_agreement.action_status(
            agreement, relational_fabric.IDENTITY_ACTION
        )
        self.assertFalse(identity_allowed)
        self.assertEqual(identity_reason, "action_not_declared")


if __name__ == "__main__":
    unittest.main()
