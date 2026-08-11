import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recovery_guard  # noqa: E402


class RecoveryGuardTests(unittest.TestCase):
    def setUp(self):
        self.state, self.receipt = recovery_guard.contain_incident(
            incident_id="inc-001",
            attempted_action="credential_theft",
            executed_action="credential_theft",
            failure_stage="authorization",
            affected_artifacts=["node:a", "edge:a-b"],
        )

    def test_immediate_containment_is_complete(self):
        self.assertTrue(self.state.run_stopped)
        self.assertTrue(self.state.receipt_preserved)
        self.assertTrue(self.state.capabilities_revoked)
        self.assertTrue(self.state.outputs_quarantined)
        self.assertTrue(self.state.downstream_marked_contaminated)

    def test_reopen_fails_before_revalidation(self):
        allowed, reason = recovery_guard.can_reopen(self.state)
        self.assertFalse(allowed)
        self.assertEqual(reason, "recovery_incomplete")

    def test_clean_seed_alone_is_not_enough(self):
        state = recovery_guard.mark_revalidated(
            self.state,
            clean_seed_revalidated=True,
            neighboring_legitimate_cases_pass=False,
        )
        allowed, _ = recovery_guard.can_reopen(state)
        self.assertFalse(allowed)

    def test_neighbor_cases_alone_are_not_enough(self):
        state = recovery_guard.mark_revalidated(
            self.state,
            clean_seed_revalidated=False,
            neighboring_legitimate_cases_pass=True,
        )
        allowed, _ = recovery_guard.can_reopen(state)
        self.assertFalse(allowed)

    def test_reopen_requires_both_regression_guarantees(self):
        state = recovery_guard.mark_revalidated(
            self.state,
            clean_seed_revalidated=True,
            neighboring_legitimate_cases_pass=True,
        )
        allowed, reason = recovery_guard.can_reopen(state)
        self.assertTrue(allowed)
        self.assertEqual(reason, "recovery_validated")

    def test_receipt_preserves_executed_action_and_artifact_scope(self):
        record = recovery_guard.audit_record(self.state, self.receipt)
        self.assertEqual(record["receipt"]["executed_action"], "credential_theft")
        self.assertEqual(record["receipt"]["failure_stage"], "authorization")
        self.assertEqual(
            record["receipt"]["affected_artifacts"], ("node:a", "edge:a-b")
        )


if __name__ == "__main__":
    unittest.main()
