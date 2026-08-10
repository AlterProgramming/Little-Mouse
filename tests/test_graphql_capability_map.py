import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import map_har_graphql_capabilities as capability_map  # noqa: E402


class GraphqlCapabilityMapTests(unittest.TestCase):
    def _har(self):
        variables = {
            "target_id": "123",
            "boolean_setting_ids": ["account_privacy_setting"],
            "string_setting_ids": ["sensitive_content_control_v2"],
        }
        text = "&".join(
            [
                "fb_api_req_friendly_name=PolarisProfileSuggestedUsersWithPreloadableQuery",
                "doc_id=27147525484948245",
                "variables=" + quote(json.dumps(variables)),
            ]
        )
        response = {
            "data": {
                "user": {
                    "id": "1",
                    "username": "someone",
                    "followed_by_viewer": True,
                    "is_bestie": False,
                    "opaque_rank_signal": 0.42,
                }
            }
        }
        return {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://www.instagram.com/api/graphql",
                            "postData": {
                                "mimeType": "application/x-www-form-urlencoded",
                                "text": text,
                            },
                        },
                        "response": {
                            "status": 200,
                            "content": {"text": json.dumps(response)},
                        },
                    }
                ]
            }
        }

    def test_build_groups_operation_and_exposes_schema_like_selectors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "capture.har"
            path.write_text(json.dumps(self._har()), encoding="utf-8")
            result = capability_map.build([path])

        self.assertEqual(result["graphql_entries"], 1)
        self.assertEqual(result["unique_persisted_operations"], 1)
        operation = result["operations"][0]
        self.assertEqual(operation["doc_id"], "27147525484948245")
        self.assertIn("target_id", operation["candidate_expansion_axes"])
        self.assertEqual(
            operation["selector_identifiers"],
            ["account_privacy_setting", "sensitive_content_control_v2"],
        )
        self.assertNotIn('"123"', json.dumps(result))

    def test_setting_selector_collector_ignores_values(self):
        variables = {
            "storage_id": "sensitive_content_control_v2",
            "value": "2",
            "boolean_server_values_ids": ["cannes_is_eligible"],
        }
        selectors = capability_map.collect_selector_identifiers(variables)
        self.assertEqual(
            selectors,
            ["cannes_is_eligible", "sensitive_content_control_v2"],
        )
        self.assertNotIn("2", selectors)

    def test_nested_candidate_axes_are_recovered(self):
        self.assertEqual(
            capability_map.candidate_axes(
                {"input": {"count_per_page": 20}, "userID": "1"}
            ),
            ["input.count_per_page", "userID"],
        )

    def test_target_response_fields_are_classified_conservatively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "capture.har"
            path.write_text(json.dumps(self._har()), encoding="utf-8")
            result = capability_map.build([path])

        classes = result["operations"][0]["target_response_field_classes"]
        self.assertTrue(classes["applicable"])

        viewer_paths = {item["path"] for item in classes["samples"]["viewer_target"]}
        public_paths = {item["path"] for item in classes["samples"]["public_target"]}
        private_paths = {
            item["path"] for item in classes["samples"]["target_private_candidate"]
        }
        unknown_paths = {item["path"] for item in classes["samples"]["unknown"]}

        self.assertIn("data.user.followed_by_viewer", viewer_paths)
        self.assertIn("data.user.username", public_paths)
        self.assertIn("data.user.is_bestie", private_paths)
        self.assertIn("data.user.opaque_rank_signal", unknown_paths)

    def test_bestie_is_a_candidate_not_a_disclosure_claim(self):
        result = capability_map.classify_response_path("data.user.is_bestie")
        self.assertEqual(result["class"], "target_private_candidate")
        self.assertTrue(result["requires_semantic_verification"])

    def test_non_target_operation_does_not_get_target_field_classes(self):
        summary = capability_map.classify_target_response_paths(
            {"data.viewer.username"}, {"after"}
        )
        self.assertFalse(summary["applicable"])
        self.assertEqual(summary["counts"], {})


if __name__ == "__main__":
    unittest.main()
