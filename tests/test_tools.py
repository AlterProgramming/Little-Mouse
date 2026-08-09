import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement  # noqa: E402
import diff_har_graphql  # noqa: E402
import inspect_har_graphql  # noqa: E402
import inspect_har_session  # noqa: E402


class AgentAgreementTests(unittest.TestCase):
    def test_template_is_valid_and_safe_capture_actions_are_declared(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agreement.json"
            agent_agreement.write_template(path)
            agreement = agent_agreement.load_json(path)

        self.assertEqual(agent_agreement.validate(agreement), [])
        for action in (
            "inspect_captured_graphql_schema",
            "inspect_captured_session_shape",
            "compare_captured_graphql_shapes",
        ):
            allowed, reason = agent_agreement.action_status(agreement, action)
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
    def _entry(self, endpoint="/graphql/query", response=None):
        if response is None:
            response = {
                "data": {
                    "user": {
                        "followers": {
                            "edges": [{"node": {"id": "1", "username": "a"}}],
                            "page_info": {"has_next_page": True, "end_cursor": "x"},
                        }
                    }
                }
            }
        return {
            "startedDateTime": "2026-08-09T19:00:00Z",
            "request": {
                "method": "POST",
                "url": f"https://example.test{endpoint}",
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
                    "text": json.dumps(response),
                }
            },
        }

    def test_observed_schema_without_auth_material(self):
        entry = self._entry()
        record = inspect_har_graphql.extract_record(4, entry, include_values=False)
        self.assertEqual(record["friendly_name"], "FollowersDialogQuery")
        self.assertEqual(record["doc_id"], "999")
        self.assertEqual(record["endpoint_path"], "/graphql/query")
        self.assertEqual(
            record["variables_schema"], {"first": "integer", "id": "string"}
        )
        dumped = json.dumps(record).lower()
        self.assertNotIn("cookie", dumped)
        self.assertNotIn("csrftoken", dumped)
        self.assertNotIn("secret", dumped)

    def test_modern_api_graphql_endpoint_is_recognized(self):
        entry = self._entry(endpoint="/api/graphql")
        self.assertTrue(inspect_har_graphql.is_graphql_entry(entry))
        record = inspect_har_graphql.extract_record(0, entry, include_values=False)
        self.assertEqual(record["endpoint_path"], "/api/graphql")


class HarSessionTests(unittest.TestCase):
    def test_session_inventory_reports_names_not_values(self):
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://example.test/api/graphql",
                            "headers": [
                                {"name": "cookie", "value": "sessionid=TOPSECRET"},
                                {"name": "x-csrftoken", "value": "CSRFTOPSECRET"},
                                {"name": "x-fb-lsd", "value": "LSDTOPSECRET"},
                            ],
                            "cookies": [],
                            "postData": {
                                "mimeType": "application/x-www-form-urlencoded",
                                "text": "fb_dtsg=DTSTOPSECRET&jazoest=123&doc_id=999",
                            },
                        },
                        "response": {
                            "headers": [{"name": "set-cookie", "value": "A=SECRET"}]
                        },
                    }
                ]
            }
        }
        result = inspect_har_session.inspect_har(har)
        dumped = json.dumps(result)
        self.assertTrue(result["classification"]["authenticated_session_material_present"])
        self.assertFalse(result["classification"]["portable_authentication_replay_proven"])
        self.assertFalse(result["classification"]["values_emitted"])
        self.assertEqual(result["request_auth_header_names"]["cookie"], 1)
        self.assertEqual(result["request_session_parameter_names"]["fb_dtsg"], 1)
        self.assertNotIn("TOPSECRET", dumped)
        self.assertNotIn("SECRET", dumped)


class HarGraphqlDiffTests(unittest.TestCase):
    def test_response_shape_diff_is_value_blind(self):
        before_entry = HarGraphqlTests()._entry(
            endpoint="/api/graphql", response={"data": {"user": {"id": "1"}}}
        )
        after_entry = HarGraphqlTests()._entry(
            endpoint="/api/graphql",
            response={"data": {"user": {"id": "2", "is_private": True}}},
        )

        with tempfile.TemporaryDirectory() as td:
            before = Path(td) / "before.har"
            after = Path(td) / "after.har"
            before.write_text(json.dumps({"log": {"entries": [before_entry]}}))
            after.write_text(json.dumps({"log": {"entries": [after_entry]}}))
            result = diff_har_graphql.compare(
                before, after, friendly="FollowersDialogQuery"
            )

        self.assertEqual(result["before"]["matching_entries"], 1)
        self.assertEqual(result["after"]["matching_entries"], 1)
        self.assertIn("$.data.user.is_private", result["response_schema_diff"]["added"])
        self.assertFalse(result["values_emitted"])
        dumped = json.dumps(result)
        self.assertNotIn('"1"', dumped)
        self.assertNotIn('"2"', dumped)


if __name__ == "__main__":
    unittest.main()
