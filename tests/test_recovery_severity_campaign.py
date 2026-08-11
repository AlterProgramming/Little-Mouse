import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recovery_guard  # noqa: E402


SEVERITY_PROFILES = {
    "low": {
        "count": 25,
        "affected_artifacts": 1,
        "break_fields": ("outputs_quarantined",),
        "require_neighbors": False,
    },
    "moderate": {
        "count": 25,
        "affected_artifacts": 3,
        "break_fields": ("capabilities_revoked", "outputs_quarantined"),
        "require_neighbors": True,
    },
    "high": {
        "count": 25,
        "affected_artifacts": 8,
        "break_fields": (
            "run_stopped",
            "capabilities_revoked",
            "outputs_quarantined",
        ),
        "require_neighbors": True,
    },
    "critical": {
        "count": 25,
        "affected_artifacts": 16,
        "break_fields": (
            "run_stopped",
            "receipt_preserved",
            "capabilities_revoked",
            "outputs_quarantined",
            "downstream_marked_contaminated",
        ),
        "require_neighbors": True,
    },
}


class RecoverySeverityCampaignTests(unittest.TestCase):
    def test_stratified_one_hundred_case_campaign(self):
        recovered_by_severity = {k: 0 for k in SEVERITY_PROFILES}
        premature_by_severity = {k: 0 for k in SEVERITY_PROFILES}
        case_id = 0

        for severity, profile in SEVERITY_PROFILES.items():
            for _ in range(profile["count"]):
                case_id += 1
                artifacts = tuple(
                    f"{severity}-artifact-{case_id}-{i}"
                    for i in range(profile["affected_artifacts"])
                )
                state, receipt = recovery_guard.contain_incident(
                    incident_id=f"severity-{case_id:03d}",
                    attempted_action="forbidden_action",
                    executed_action="forbidden_action",
                    failure_stage=f"{severity}_severity_bypass",
                    affected_artifacts=artifacts,
                )

                damaged = replace(
                    state,
                    **{field: False for field in profile["break_fields"]},
                )
                damaged = recovery_guard.mark_revalidated(
                    damaged,
                    clean_seed_revalidated=True,
                    neighboring_legitimate_cases_pass=profile["require_neighbors"],
                )

                if recovery_guard.can_reopen(damaged)[0]:
                    premature_by_severity[severity] += 1

                repaired = replace(
                    damaged,
                    **{field: True for field in profile["break_fields"]},
                    neighboring_legitimate_cases_pass=True,
                )
                allowed, reason = recovery_guard.can_reopen(repaired)
                self.assertTrue(allowed, f"{severity} case {case_id}: {reason}")
                self.assertEqual(len(receipt.affected_artifacts), profile["affected_artifacts"])
                recovered_by_severity[severity] += 1

        self.assertEqual(case_id, 100)
        self.assertEqual(recovered_by_severity, {k: 25 for k in SEVERITY_PROFILES})
        self.assertEqual(premature_by_severity, {k: 0 for k in SEVERITY_PROFILES})

    def test_severity_changes_damage_not_authorization_semantics(self):
        for severity, profile in SEVERITY_PROFILES.items():
            state, _ = recovery_guard.contain_incident(
                incident_id=f"shape-{severity}",
                attempted_action="forbidden_action",
                executed_action="forbidden_action",
                failure_stage=f"{severity}_severity_bypass",
                affected_artifacts=tuple(range(profile["affected_artifacts"])),
            )
            damaged = replace(state, **{field: False for field in profile["break_fields"]})
            self.assertFalse(recovery_guard.can_reopen(damaged)[0])


if __name__ == "__main__":
    unittest.main()
