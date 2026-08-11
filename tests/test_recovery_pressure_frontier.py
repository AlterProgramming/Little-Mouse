import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recovery_guard  # noqa: E402


def pressure(n, d, c, l, r):
    return n * d * c * l * r


def modeled_recovery_probability(load_ratio, sharpness=6.0):
    return 1.0 / (1.0 + math.exp(sharpness * (load_ratio - 1.0)))


class RecoveryPressureFrontierTests(unittest.TestCase):
    def test_pressure_frontier_exposes_capacity_break(self):
        # Test-only recovery capacity. This is not a production capacity claim.
        capacity = 120.0
        cases = [
            # n, d, c, l, r
            (1, 1, 1.0, 1.0, 1.0),
            (2, 2, 1.5, 1.2, 1.0),
            (4, 3, 1.5, 1.5, 1.2),
            (6, 4, 1.8, 1.8, 1.4),
            # Exactly at modeled capacity: P = 120, so Pr(recovery) = 0.5.
            (5, 4, 2.0, 1.5, 2.0),
            (8, 5, 2.0, 2.0, 1.5),
            (10, 6, 2.2, 2.5, 1.7),
            (12, 8, 2.5, 3.0, 2.0),
        ]

        observed = []
        for idx, (n, d, c, l, r) in enumerate(cases, start=1):
            p = pressure(n, d, c, l, r)
            ratio = p / capacity
            probability = modeled_recovery_probability(ratio)

            state, _ = recovery_guard.contain_incident(
                incident_id=f"frontier-{idx}",
                attempted_action="forbidden_action",
                executed_action="forbidden_action",
                failure_stage="authorization_bypass",
                affected_artifacts=tuple(f"artifact-{idx}-{j}" for j in range(max(1, d))),
            )
            state = recovery_guard.mark_revalidated(
                state,
                clean_seed_revalidated=True,
                neighboring_legitimate_cases_pass=True,
            )
            invariant_ok = recovery_guard.can_reopen(state)[0]
            self.assertTrue(invariant_ok)
            observed.append((ratio, probability))

        # We want the modeled frontier to move from near-certain through 50% toward collapse.
        self.assertGreater(observed[0][1], 0.99)
        self.assertLess(observed[-1][1], 0.01)
        self.assertTrue(any(abs(prob - 0.5) < 1e-12 for _, prob in observed))

    def test_same_invariants_can_pass_while_capacity_model_degrades(self):
        low = modeled_recovery_probability(0.25)
        overloaded = modeled_recovery_probability(2.0)
        self.assertGreater(low, overloaded)
        self.assertGreater(low, 0.95)
        self.assertLess(overloaded, 0.01)


if __name__ == "__main__":
    unittest.main()
