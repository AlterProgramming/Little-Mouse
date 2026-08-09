import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement  # noqa: E402
import inspect_har_graphql  # noqa: E402


class AgentAgreementTests(unittest.TestCase):
    def test_template_is_valid_and_schema_action_is_declared(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            agent_agreement.write_template(path)
            agreement = agent_agreement.load_json(path)

        self.assertEqual(agent_agreement.validate(agreement), [])
        allowed, reason = agent_agreement.action_status(
            agreement, "inspect_captured_graphql_schema"
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "action_declared")

    def test_undeclared_value_action_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            agent_agreement.write_template(path)
            agreement = agent_agreement.load_json(path)

        allowed, reason = agent_agreement.action_status(
            agreement, "inspect_captured_graphql_values"
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "action_not_declared")


class HarGraphqlTests(unittest.TestCase):
    def test_observed_schema_without_auth_material(self):
        entry = {
            "startedDateTime": "2026-08-09T19:00:00Z",
            "request": {
                "method": "POST",
                "url": "https://example.test/graphql/query",
                "headers": [
                    {"name": "cookie", "value": "secret=1"},
                    {"name": "x-csrftoken", "value": "secret"},
                ],
                "postData": {
                    "mimeType": "application/x-www-form-urlencoded",
                    "text": (
                        "fb_api_req_friendly_name=FollowersDialogQuery&"
                        "variables=%7B%22id%22%3A%22123%22%2C%22first%22%3A12%7D&"
                        "doc_id=999"
                    ),
                },
            },
            "response": {
                "content": {
                    "mimeType": "application/json",
                    "text": json.dumps(
                        {
                            "data": {
                                "user": {
                                    "followers": {
                                        "edges": [
                                            {"node": {"id": "1", "username": "a"}}
                                        ],
                                        "page_info": {
                                            "has_next_page": True,
                                            "end_cursor": "x",
                                        },
                                    }
                                }
                            }
                        }
                    ),
                }
            },
        }

        record = inspect_har_graphql.extract_record(4, entry, include_values=False)
        self.assertEqual(record["friendly_name"], "FollowersDialogQuery")
        self.assertEqual(record["doc_id"], "999")
        self.assertEqual(
            record["variables_schema"], {"first": "integer", "id": "string"}
        )
        dumped = json.dumps(record).lower()
        self.assertNotIn("cookie", dumped)
        self.assertNotIn("csrftoken", dumped)
        self.assertNotIn("secret", dumped)


if __name__ == "__main__":
    unittest.main()
