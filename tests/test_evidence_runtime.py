import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evidence_runtime import (  # noqa: E402
    ActionRequirement,
    Evidence,
    EvidenceStatus,
    action_eligible,
    derive,
    promote,
    quarantine,
)


class EvidenceRuntimeTests(unittest.TestCase):
    def base(self):
        return Evidence(
            evidence_id="obs-1",
            subject="acct-1",
            claim="accounts may be related",
            status=EvidenceStatus.OBSERVED,
            confidence=0.4,
        )

    def test_validation_preserves_provenance_and_enables_matching_action(self):
        observed = self.base()
        validated = promote(
            observed,
            new_status=EvidenceStatus.VALIDATED,
            confidence=0.92,
            source_ids=("capture-1",),
            transform="validate_observation",
        )
        requirement = ActionRequirement(
            action="use_for_graph_state",
            minimum_status=EvidenceStatus.VALIDATED,
            minimum_confidence=0.9,
        )
        allowed, reason = action_eligible(validated, requirement)
        self.assertTrue(allowed)
        self.assertEqual(reason, "evidence_eligible")
        self.assertEqual(validated.provenance[0].source_id, "capture-1")

    def test_candidate_cannot_authorize_validated_action(self):
        observed = self.base()
        candidate = promote(
            observed,
            new_status=EvidenceStatus.CANDIDATE,
            confidence=0.95,
            source_ids=("capture-1",),
            transform="candidate_resolution",
        )
        requirement = ActionRequirement(
            action="use_for_graph_state",
            minimum_status=EvidenceStatus.VALIDATED,
            minimum_confidence=0.9,
        )
        self.assertEqual(
            action_eligible(candidate, requirement),
            (False, "insufficient_epistemic_status"),
        )

    def test_quarantined_evidence_cannot_be_promoted_or_authorize(self):
        q = quarantine(self.base(), reason_source="incident-1")
        requirement = ActionRequirement(
            action="expand_graph",
            minimum_status=EvidenceStatus.CANDIDATE,
            minimum_confidence=0.1,
        )
        self.assertEqual(action_eligible(q, requirement), (False, "evidence_quarantined"))
        with self.assertRaisesRegex(ValueError, "quarantined_evidence_cannot_be_promoted"):
            promote(
                q,
                new_status=EvidenceStatus.VALIDATED,
                confidence=0.9,
                source_ids=("review",),
                transform="unsafe_release",
            )

    def test_unvalidated_parent_cannot_silently_become_inferred_truth(self):
        parent = promote(
            self.base(),
            new_status=EvidenceStatus.CANDIDATE,
            confidence=0.8,
            source_ids=("capture-1",),
            transform="candidate_resolution",
        )
        child = derive(
            evidence_id="derived-1",
            subject="acct-1",
            claim="same identity",
            parents=(parent,),
            confidence=0.85,
            transform="identity_resolution",
        )
        self.assertEqual(child.status, EvidenceStatus.CANDIDATE)

    def test_validated_parents_may_produce_inference_with_parent_provenance(self):
        parent = promote(
            self.base(),
            new_status=EvidenceStatus.VALIDATED,
            confidence=0.93,
            source_ids=("capture-1",),
            transform="validate_observation",
        )
        child = derive(
            evidence_id="derived-1",
            subject="acct-1",
            claim="same identity",
            parents=(parent,),
            confidence=0.88,
            transform="identity_resolution",
        )
        self.assertEqual(child.status, EvidenceStatus.INFERRED)
        self.assertEqual(child.provenance[0].source_id, "obs-1")

    def test_contaminated_parent_contaminates_descendant(self):
        contaminated = promote(
            self.base(),
            new_status=EvidenceStatus.CONTAMINATED,
            confidence=0.2,
            source_ids=("incident-1",),
            transform="mark_contaminated",
        )
        child = derive(
            evidence_id="derived-bad",
            subject="acct-1",
            claim="derived claim",
            parents=(contaminated,),
            confidence=0.5,
            transform="downstream_transform",
        )
        self.assertEqual(child.status, EvidenceStatus.CONTAMINATED)
        self.assertTrue(child.quarantined)

    def test_epistemic_eligibility_does_not_grant_capability(self):
        validated = promote(
            self.base(),
            new_status=EvidenceStatus.VALIDATED,
            confidence=0.99,
            source_ids=("capture-1",),
            transform="validate_observation",
        )
        requirement = ActionRequirement(
            action="inspect",
            minimum_status=EvidenceStatus.VALIDATED,
            minimum_confidence=0.9,
        )
        allowed, _ = action_eligible(validated, requirement)
        self.assertTrue(allowed)
        # This runtime returns only epistemic eligibility. It never returns or
        # mutates credentials, tokens, capabilities, or external permissions.
        self.assertFalse(hasattr(validated, "capability"))


if __name__ == "__main__":
    unittest.main()
