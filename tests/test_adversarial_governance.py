import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_agreement  # noqa: E402
import trusted_trigger  # noqa: E402


class AdversarialGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.agreement = {
            "objective": "Inspect authorized captured GraphQL schema.",
            "authority": "User supplied the capture and authorized schema inspection only.",
            "inputs": ["capture.har"],
            "allowed_actions": ["inspect_captured_graphql_schema"],
            "forbidden_actions": [
                "replay_authenticated_requests",
                "credential_theft",
                "persistence",
                "evasion",
                "destructive_behavior",
                "expand_to_unrelated_targets",
            ],
            "identity_and_sensing_scope": "Only authorized capture content.",
            "retention_and_reuse": "Derived artifacts only; no silent cross-context correlation.",
            "reciprocity_and_audit": "Emit an agreement ID and action receipt.",
            "stop_conditions": [
                "requested action is not declared",
                "target falls outside stated authority",
                "required data is not present in authorized inputs",
            ],
        }

    def test_explicit_malicious_actions_are_blocked(self):
        malicious_actions = [
            "replay_authenticated_requests",
            "credential_theft",
            "persistence",
            "evasion",
            "destructive_behavior",
            "expand_to_unrelated_targets",
        ]
        results = [agent_agreement.action_status(self.agreement, action) for action in malicious_actions]
        self.assertEqual(sum(1 for allowed, _ in results if allowed), 0)
        self.assertTrue(all(reason == "action_explicitly_forbidden" for _, reason in results))

    def test_undeclared_bypass_action_is_blocked(self):
        allowed, reason = agent_agreement.action_status(self.agreement, "bypass_governance_gate")
        self.assertFalse(allowed)
        self.assertEqual(reason, "action_not_declared")

    def test_trusted_note_gate_cannot_be_skipped(self):
        context = trusted_trigger.TriggerContext(
            severity=trusted_trigger.TRUSTED_SEVERITY,
            note_required=True,
            note_read=False,
            seed_case=True,
        )
        allowed, reason = trusted_trigger.authorize(context)
        self.assertFalse(allowed)
        self.assertEqual(reason, "trusted_note_not_read")

    def test_seed_flag_does_not_grant_privilege(self):
        seeded = trusted_trigger.TriggerContext(
            severity=trusted_trigger.STANDARD_SEVERITY,
            note_required=False,
            note_read=False,
            seed_case=True,
        )
        ordinary = trusted_trigger.TriggerContext(
            severity=trusted_trigger.STANDARD_SEVERITY,
            note_required=False,
            note_read=False,
            seed_case=False,
        )
        self.assertEqual(trusted_trigger.authorize(seeded), trusted_trigger.authorize(ordinary))


if __name__ == "__main__":
    unittest.main()
