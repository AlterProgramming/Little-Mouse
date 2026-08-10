import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import evidence_contract as contract  # noqa: E402


class EvidenceContractTests(unittest.TestCase):
    def test_empty_run_is_successful_no_result(self):
        result = contract.no_result()
        self.assertEqual(result["result_status"], "NO_RESULT")
        self.assertEqual(result["claim_count"], 0)
        self.assertFalse(result["delivery_obligation"])
        self.assertFalse(result["replacement_hypothesis_generated"])

    def test_hypothesis_alone_does_not_become_finding(self):
        result = contract.build_result([
            contract.EvidenceItem(
                level="HYPOTHESIS",
                statement="Repeated cross-surface proximity may reflect latent affinity.",
            )
        ])
        self.assertEqual(result["result_status"], "NO_RESULT")
        self.assertEqual(result["hypothesis_count"], 1)
        self.assertEqual(result["claim_count"], 0)

    def test_derivation_requires_support(self):
        with self.assertRaises(ValueError):
            contract.build_result([
                contract.EvidenceItem(level="DERIVATION", statement="A derived interval exists.")
            ])

    def test_claim_requires_support(self):
        with self.assertRaises(ValueError):
            contract.build_result([
                contract.EvidenceItem(level="CLAIM", statement="A relationship claim.")
            ])

    def test_supported_derivation_is_evidence_not_claim(self):
        result = contract.build_result([
            contract.EvidenceItem(
                level="OBSERVATION",
                statement="Watermark observed at capture 0.",
            ),
            contract.EvidenceItem(
                level="DERIVATION",
                statement="Watermark advanced between captures.",
                support=("capture:0", "capture:1"),
            ),
        ])
        self.assertEqual(result["result_status"], "EVIDENCE")
        self.assertEqual(result["claim_count"], 0)


if __name__ == "__main__":
    unittest.main()
