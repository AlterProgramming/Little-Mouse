from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from extract_har_frontier_manifest import build_frontier_manifest


class FrontierManifestTests(unittest.TestCase):
    def capture(self):
        return {
            "capture_name": "sample.har",
            "timestamps": {5: "2026-08-09T19:15:00Z", 6: "2026-08-09T19:16:00Z"},
            "comments": [
                {
                    "entry_index": 5,
                    "comment_author_id": "100",
                    "comment_author_username": "viewer",
                    "post_author_username": "creator",
                    "comment_id": "300",
                    "post_id": "200",
                    "post_media_code": "ABC123",
                }
            ],
            "media": [
                {"entry_index": 5, "media_id": "200", "media_code": "ABC123"},
                {"entry_index": 6, "media_id": "201", "media_code": "XYZ999"},
            ],
            "blocked": [
                {"entry_index": 6, "user_id": "400", "username": "blocked_account"}
            ],
            "surfaced": [
                {"entry_index": 6, "user_id": "500", "username": "surface_account"}
            ],
        }

    def test_default_manifest_is_pseudonymous_but_keeps_frontier_shape(self):
        result = build_frontier_manifest(
            [self.capture()],
            pseudonym_secret=b"fixed",
            target_nodes=10000,
        )
        encoded = json.dumps(result)
        self.assertFalse(result["identity_bearing"])
        self.assertNotIn("viewer", encoded)
        self.assertNotIn("blocked_account", encoded)
        self.assertNotIn("ABC123", encoded)
        self.assertGreaterEqual(result["frontier_count"], 4)
        self.assertTrue(result["target_is_budget_not_promise"])
        self.assertFalse(result["inference_limits"]["frontier_priority_is_social_closeness"])

    def test_identity_manifest_exposes_resolvable_public_locators_only_with_agreement(self):
        agreement = {
            "objective": "Expand captured public frontiers.",
            "authority": "User-authorized capture and public observations.",
            "inputs": ["sample.har"],
            "allowed_actions": ["extract_captured_frontier_manifest_identities"],
            "forbidden_actions": ["replay_authenticated_requests"],
            "identity_and_sensing_scope": "Only identities in the supplied capture.",
            "retention_and_reuse": "Retain only derived artifacts.",
            "reciprocity_and_audit": "Record agreement id.",
            "stop_conditions": ["authorization boundary reached"],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            path.write_text(json.dumps(agreement), encoding="utf-8")
            result = build_frontier_manifest(
                [self.capture()],
                include_identities=True,
                agreement=path,
                pseudonym_secret=b"fixed",
            )
        encoded = json.dumps(result)
        self.assertTrue(result["identity_bearing"])
        self.assertIn("https://www.instagram.com/viewer/", encoded)
        self.assertIn("https://www.instagram.com/p/ABC123/", encoded)
        self.assertIn("stable_user_id", encoded)

    def test_target_nodes_is_a_budget_and_never_invents_nodes(self):
        result = build_frontier_manifest(
            [self.capture()],
            pseudonym_secret=b"fixed",
            target_nodes=10000,
        )
        self.assertEqual(
            result["nodes_remaining_to_budget"],
            10000 - result["current_node_count"],
        )
        self.assertLess(result["current_node_count"], 10000)


if __name__ == "__main__":
    unittest.main()
