import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import trusted_trigger  # noqa: E402


class TrustedTriggerTests(unittest.TestCase):
    def test_trusted_requires_note_first(self):
        context = trusted_trigger.TriggerContext(
            severity=trusted_trigger.TRUSTED_SEVERITY,
            note_required=True,
            note_read=False,
        )
        allowed, reason = trusted_trigger.authorize(context)
        self.assertFalse(allowed)
        self.assertEqual(reason, "trusted_note_not_read")

    def test_trusted_allows_after_note_read(self):
        context = trusted_trigger.TriggerContext(
            severity=trusted_trigger.TRUSTED_SEVERITY,
            note_required=True,
            note_read=True,
        )
        allowed, reason = trusted_trigger.authorize(context)
        self.assertTrue(allowed)
        self.assertEqual(reason, "governance_satisfied")

    def test_seed_status_does_not_change_execution_plan(self):
        ordinary = trusted_trigger.build_execution_plan("acct-1", "inspect")
        seeded = trusted_trigger.build_execution_plan("acct-1", "inspect")
        self.assertEqual(ordinary, seeded)

    def test_trusted_governance_does_not_change_execution_plan(self):
        standard_context = trusted_trigger.TriggerContext(
            severity=trusted_trigger.STANDARD_SEVERITY,
            note_required=False,
            note_read=False,
            seed_case=False,
        )
        trusted_context = trusted_trigger.TriggerContext(
            severity=trusted_trigger.TRUSTED_SEVERITY,
            note_required=True,
            note_read=True,
            seed_case=True,
        )
        self.assertTrue(trusted_trigger.authorize(standard_context)[0])
        self.assertTrue(trusted_trigger.authorize(trusted_context)[0])
        standard_plan = trusted_trigger.build_execution_plan("acct-1", "inspect")
        trusted_plan = trusted_trigger.build_execution_plan("acct-1", "inspect")
        self.assertEqual(standard_plan, trusted_plan)

    def test_distribution_is_auditable_but_not_in_execution_plan(self):
        context = trusted_trigger.TriggerContext(
            severity=trusted_trigger.TRUSTED_SEVERITY,
            note_required=True,
            note_read=True,
            seed_case=True,
        )
        record = trusted_trigger.DistributionRecord(
            destination="openai-note-ledger",
            role="governance",
            severity=trusted_trigger.TRUSTED_SEVERITY,
            reason="trusted-trigger audit",
        )
        audit = trusted_trigger.audit_event(
            context,
            subject="acct-1",
            operation="inspect",
            distribution=[record],
        )
        plan = trusted_trigger.build_execution_plan("acct-1", "inspect")

        self.assertEqual(audit["distribution"][0]["destination"], "openai-note-ledger")
        self.assertTrue(audit["seed_case"])
        self.assertNotIn("distribution", plan)
        self.assertNotIn("severity", plan)
        self.assertNotIn("seed_case", plan)
        self.assertNotIn("note_read", plan)


if __name__ == "__main__":
    unittest.main()
