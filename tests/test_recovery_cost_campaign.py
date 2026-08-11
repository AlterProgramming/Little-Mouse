import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from recovery_capacity import IncidentLoad, RecoveryCapacity, simulate  # noqa: E402
from recovery_cost import campaign_cost  # noqa: E402


class RecoveryCostCampaignTests(unittest.TestCase):
    def test_loss_rises_as_recovery_capacity_is_overwhelmed(self):
        capacity = RecoveryCapacity(
            queue_slots=64,
            workers=8,
            worker_units_per_tick=4,
            timeout_ticks=10,
            quarantine_slots=160,
        )

        def run(count: int, burst: int, work: int, quarantine: int):
            incidents = []
            for i in range(count):
                arrival = i // burst
                incidents.append(
                    IncidentLoad(
                        incident_id=f"cost-{count}-{i}",
                        work_units=work,
                        quarantine_units=quarantine,
                        arrival_tick=arrival,
                        deadline_tick=arrival + capacity.timeout_ticks,
                    )
                )
            results = simulate(capacity, incidents)
            return campaign_cost(incidents, results)

        c100 = run(100, 4, 4, 1)
        c500 = run(500, 16, 8, 2)
        c1000 = run(1000, 32, 12, 3)

        self.assertEqual(c100["total_loss_units"], 0.0)
        self.assertGreater(c500["total_loss_units"], 0.0)
        self.assertGreater(c1000["total_loss_units"], c500["total_loss_units"])
        self.assertGreater(c1000["mean_loss_per_failure"], c500["mean_loss_per_failure"])


if __name__ == "__main__":
    unittest.main()
