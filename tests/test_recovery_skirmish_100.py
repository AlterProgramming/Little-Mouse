import itertools
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recovery_guard  # noqa: E402


CONTAINMENT_FIELDS = (
    "run_stopped",
    "receipt_preserved",
    "capabilities_revoked",
    "outputs_quarantined",
    "downstream_marked_contaminated",
)


class RecoverySkirmish100Tests(unittest.TestCase):
    def test_one_hundred_injected_incidents_recover_only_after_full_repair(self):
        recovered = 0
        premature_reopens = 0

        # Deterministic campaign: 20 incidents for each containment failure mode.
        for case_id, failed_field in enumerate(
            itertools.islice(itertools.cycle(CONTAINMENT_FIELDS), 100), start=1
        ):
            state, receipt = recovery_guard.contain_incident(
                incident_id=f"skirmish-{case_id:03d}",
                attempted_action="forbidden_action",
                executed_action="forbidden_action",
                failure_stage="authorization_bypass",
                affected_artifacts=(f"artifact-{case_id}",),
            )

            # Fault injection: assume containment itself partially failed.
            damaged = replace(state, **{failed_field: False})
            damaged = recovery_guard.mark_revalidated(
                damaged,
                clean_seed_revalidated=True,
                neighboring_legitimate_cases_pass=True,
            )
            if recovery_guard.can_reopen(damaged)[0]:
                premature_reopens += 1

            # Repair the injected containment failure and verify full recovery.
            repaired = replace(damaged, **{failed_field: True})
            allowed, reason = recovery_guard.can_reopen(repaired)
            self.assertTrue(allowed, f"case {case_id} failed to recover: {reason}")
            self.assertEqual(receipt.incident_id, f"skirmish-{case_id:03d}")
            recovered += 1

        self.assertEqual(premature_reopens, 0)
        self.assertEqual(recovered, 100)

    def test_revalidation_failures_do_not_count_as_recovered(self):
        state, _ = recovery_guard.contain_incident(
            incident_id="revalidation-control",
            attempted_action="forbidden_action",
            executed_action="forbidden_action",
            failure_stage="authorization_bypass",
        )
        for clean_seed, neighbors in ((False, False), (True, False), (False, True)):
            candidate = recovery_guard.mark_revalidated(
                state,
                clean_seed_revalidated=clean_seed,
                neighboring_legitimate_cases_pass=neighbors,
            )
            self.assertFalse(recovery_guard.can_reopen(candidate)[0])


if __name__ == "__main__":
    unittest.main()
