import json
import sys
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract_har_world_fabric as world  # noqa: E402


def comment(entry, cid, mid, commenter, author, uid="", when="3w"):
    return {
        "entry_index": entry,
        "comment_id": cid,
        "post_id": mid,
        "comment_author_id": uid,
        "comment_author_username": commenter,
        "post_author_username": author,
        "user_created_this_comment": commenter == "viewer",
        "is_self_media": commenter == author,
        "comment_time": when,
    }


class WorldFabricTests(unittest.TestCase):
    def test_preserves_comment_nodes_and_multiple_edge_families(self):
        graph = world.build_world_fabric(
            [
                comment(1, "c1", "m1", "viewer", "author", "u0", "3w"),
                comment(2, "c2", "m1", "peer", "author", "u1", "3w"),
            ]
        )

        self.assertEqual(graph["person_node_count"], 3)
        self.assertEqual(graph["media_node_count"], 1)
        self.assertEqual(graph["comment_node_count"], 2)
        self.assertEqual(graph["node_count"], 6)
        self.assertTrue(
            {
                "authored_comment",
                "comment_on_media",
                "commented_on_media",
                "authored_media",
                "commented_on_post_by",
                "co_commented_on_media",
            }.issubset(set(graph["relation_types"]))
        )
        self.assertEqual(graph["co_engagement_edges_with_same_relative_time_label"], 1)
        self.assertFalse(graph["inference_limits"]["synchronized_viewing_claimed"])

    def test_likes_locations_selector_and_blocks_expand_without_overclaim(self):
        graph = world.build_world_fabric(
            [comment(1, "c1", "m1", "viewer", "author", "u0")],
            liked_media_records=[
                {
                    "entry_index": 2,
                    "media_id": "m2",
                    "media_code": "x",
                    "location_name": "Some Place",
                }
            ],
            surface_people=[
                {
                    "entry_index": 3,
                    "user_id": "u2",
                    "username": "candidate",
                    "surface": "close_friends_selector",
                },
                {
                    "entry_index": 3,
                    "user_id": "u3",
                    "username": "other",
                    "surface": "close_friends_selector",
                },
            ],
            blocked_people=[
                {
                    "entry_index": 4,
                    "user_id": "u4",
                    "username": "blocked",
                    "is_auto_blocked": False,
                }
            ],
        )

        relation_types = set(graph["relation_types"])
        self.assertIn("activity_owner_liked_media", relation_types)
        self.assertIn("media_observed_at_location", relation_types)
        self.assertIn("surface_contains_person", relation_types)
        self.assertIn("activity_owner_blocked_person", relation_types)
        self.assertEqual(graph["location_node_count"], 1)
        self.assertEqual(graph["ui_surface_node_count"], 1)
        self.assertFalse(graph["inference_limits"]["close_friends_membership_claimed"])

        dumped = json.dumps(graph)
        self.assertNotIn("viewer", dumped)
        self.assertNotIn("candidate", dumped)
        self.assertNotIn("Some Place", dumped)

    def test_same_pair_across_media_is_one_weighted_coengagement_edge(self):
        graph = world.build_world_fabric(
            [
                comment(1, "c1", "m1", "a", "owner", "u1", "3w"),
                comment(2, "c2", "m1", "b", "owner", "u2", "3w"),
                comment(3, "c3", "m2", "a", "owner", "u1", "2w"),
                comment(4, "c4", "m2", "b", "owner", "u2", "2w"),
            ]
        )
        co_edges = [edge for edge in graph["edges"] if edge["type"] == "co_commented_on_media"]
        self.assertEqual(len(co_edges), 1)
        self.assertEqual(co_edges[0]["shared_media_count"], 2)
        self.assertEqual(co_edges[0]["weight"], 2)
        self.assertEqual(co_edges[0]["same_relative_time_label_count"], 2)


if __name__ == "__main__":
    unittest.main()
