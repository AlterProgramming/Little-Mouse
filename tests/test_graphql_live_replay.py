import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import replay_har_graphql as replay  # noqa: E402


def captured_entry(target="111"):
    variables = {"target_id": target, "first": 12}
    text = "&".join(
        [
            "fb_api_req_friendly_name=PolarisProfileSuggestedUsersWithPreloadableQuery",
            "doc_id=27147525484948245",
            "variables=" + quote(json.dumps(variables)),
        ]
    )
    return {
        "request": {
            "method": "POST",
            "url": "https://www.instagram.com/api/graphql",
            "headers": [
                {"name": "Cookie", "value": "sessionid=secret"},
                {
                    "name": "Content-Type",
                    "value": "application/x-www-form-urlencoded",
                },
                {"name": "Content-Length", "value": "999"},
            ],
            "postData": {"text": text},
        }
    }


class HarGraphqlReplayTests(unittest.TestCase):
    def test_target_inventory_emits_fingerprints_not_raw_values(self):
        hars = [{"log": {"entries": [captured_entry("111"), captured_entry("222")]}}]
        inventory = replay.public_target_inventory(hars)
        rendered = json.dumps(inventory)
        self.assertNotIn("111", rendered)
        self.assertNotIn("222", rendered)
        self.assertEqual(len(inventory), 2)

    def test_rewrite_changes_only_selected_target_variable(self):
        url, body, location = replay._rewrite_url_or_body(
            captured_entry("111"), "target_id", "222"
        )
        self.assertEqual(location, "body")
        self.assertEqual(url, "https://www.instagram.com/api/graphql")
        variables = json.loads(parse_qs(body.decode())["variables"][0])
        self.assertEqual(variables["target_id"], "222")
        self.assertEqual(variables["first"], 12)

    def test_auth_material_is_preserved_in_memory_but_transport_headers_are_dropped(self):
        headers = replay._safe_headers(captured_entry())
        self.assertEqual(headers["Cookie"], "sessionid=secret")
        self.assertFalse(any(key.lower() == "content-length" for key in headers))

    def test_live_destination_is_restricted_to_instagram_graphql_https(self):
        replay._validate_endpoint("https://www.instagram.com/api/graphql")
        with self.assertRaises(ValueError):
            replay._validate_endpoint("https://evil.example/api/graphql")
        with self.assertRaises(ValueError):
            replay._validate_endpoint("http://www.instagram.com/api/graphql")

    def test_response_summary_keeps_field_paths_but_not_values(self):
        result = replay.summarize_response(
            200,
            json.dumps(
                {
                    "data": {
                        "user": {
                            "username": "secretname",
                            "followed_by_viewer": True,
                        }
                    }
                }
            ).encode(),
        )
        rendered = json.dumps(result)
        self.assertNotIn("secretname", rendered)
        self.assertIn("followed_by_viewer", rendered)


if __name__ == "__main__":
    unittest.main()
