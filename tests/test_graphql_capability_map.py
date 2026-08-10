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
                            "content": {
                                "text": json.dumps({"data": {"x": {"id": "1"}}})
                            },
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


if __name__ == "__main__":
    unittest.main()
