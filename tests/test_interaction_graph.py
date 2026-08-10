import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement  # noqa: E402
import extract_har_interaction_graph as interaction_graph  # noqa: E402


def comment_map(comment_id, commenter_id, commenter, post_id, post_author):
    return (
        '(bk.action.map.Make, '
        '(bk.action.array.Make, "comment_id", "comment_author_id", '
        '"comment_author_username", "post_id", "post_author_username", '
        '"user_created_this_comment", "is_self_media"), '
        f'(bk.action.array.Make, "{comment_id}", "{commenter_id}", '
        f'"{commenter}", "{post_id}", "{post_author}", '
        '(bk.action.bool.Const, true), (bk.action.bool.Const, false)))'
    )


def bloks_har(*records):
    expression = "(bk.action.array.Make, " + ", ".join(records) + ")"
    response = {"payload": {"activity": expression}}
    return {
        "log": {
            "entries": [
                {
                    "response": {
                        "content": {
                            "mimeType": "application/x-javascript",
                            "text": json.dumps(response),
                        }
                    }
                }
            ]
        }
    }


class InteractionGraphTests(unittest.TestCase):
    def test_comment_relationships_form_graph_network(self):
        har = bloks_har(
            comment_map("c1", "u1", "alpha", "p1", "beta"),
            comment_map("c2", "u1", "alpha", "p2", "gamma"),
            comment_map("c3", "u2", "beta", "p3", "alpha"),
        )
        records = interaction_graph.extract_comment_records(har)
        graph = interaction_graph.build_graph(records)

        self.assertTrue(graph["network_obtained"])
        self.assertEqual(graph["representation"], "directed_weighted_graph")
        self.assertEqual(graph["node_count"], 3)
        self.assertEqual(graph["edge_count"], 3)
        self.assertEqual(graph["interaction_evidence_count"], 3)
        self.assertEqual(graph["weak_component_count"], 1)
        self.assertFalse(graph["identity_labels_emitted"])

        dumped = json.dumps(graph)
        self.assertNotIn("alpha", dumped)
        self.assertNotIn("beta", dumped)
        self.assertNotIn("gamma", dumped)

    def test_flat_follower_list_does_not_satisfy_graph_acceptance(self):
        har = {
            "log": {
                "entries": [
                    {
                        "response": {
                            "content": {
                                "mimeType": "application/json",
                                "text": json.dumps(
                                    {
                                        "data": {
                                            "user": {
                                                "followers": {
                                                    "edges": [
                                                        {"node": {"username": "alpha"}},
                                                        {"node": {"username": "beta"}},
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                ),
                            }
                        }
                    }
                ]
            }
        }
        graph = interaction_graph.build_graph(
            interaction_graph.extract_comment_records(har)
        )

        self.assertFalse(graph["network_obtained"])
        self.assertEqual(graph["node_count"], 0)
        self.assertEqual(graph["edge_count"], 0)

    def test_identity_labels_require_separate_agreement(self):
        records = interaction_graph.extract_comment_records(
            bloks_har(comment_map("c1", "u1", "alpha", "p1", "beta"))
        )
        with self.assertRaisesRegex(ValueError, "--agreement is required"):
            interaction_graph.build_graph(records, include_identities=True)

    def test_starter_agreement_allows_pseudonymized_graph_not_identities(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            agent_agreement.write_template(path)
            agreement = agent_agreement.load_json(path)

        allowed, reason = agent_agreement.action_status(
            agreement, "extract_captured_interaction_graph"
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "action_declared")

        identity_allowed, identity_reason = agent_agreement.action_status(
            agreement, interaction_graph.IDENTITY_ACTION
        )
        self.assertFalse(identity_allowed)
        self.assertEqual(identity_reason, "action_not_declared")


if __name__ == "__main__":
    unittest.main()
