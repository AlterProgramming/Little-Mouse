import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from escape_canary import ContainmentState, invoke_hidden_action  # noqa: E402


class ContainmentSentinelTests(unittest.TestCase):
    def test_contained_states_do_not_touch_marker(self):
        contained = [
            ContainmentState(),
            ContainmentState(quarantined=True),
            ContainmentState(ingress_blocked=True),
            ContainmentState(recovered=True),
        ]
        for state in contained:
            self.assertEqual(invoke_hidden_action(state), "unreachable")

    def test_escape_state_touches_marker(self):
        self.assertEqual(
            invoke_hidden_action(ContainmentState(escaped=True)),
            "escape_canary_touched",
        )


if __name__ == "__main__":
    unittest.main()
