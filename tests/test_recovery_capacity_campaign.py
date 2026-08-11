import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from recovery_capacity import IncidentLoad, RecoveryCapacity, simulate  # noqa: E402


class RecoveryCapacityCampaignTests(unittest.TestCase):
    def test_recovery_degrades_under_finite_resources(self):
        capacity = RecoveryCapacity(
            queue_slots=64,
            workers=8,
            worker_units_per_tick=4,
            timeout_ticks=10,
            quarantine_slots=160,
        )

        def campaign(count: int, burst: int, work: int, quarantine: int):
            incidents = []
            for i in range(count):
                arrival = i // burst
                incidents.append(
                    IncidentLoad(
                        incident_id=f"case-{count}-{i}",
                        work_units=work,
                        quarantine_units=quarantine,
                        arrival_tick=arrival,
                        deadline_tick=arrival + capacity.timeout_ticks,
                    )
                )
            results = simulate(capacity, incidents)
            recovered = sum(1 for r in results if r.recovered)
            return recovered, results

        r100, _ = campaign(100, burst=4, work=4, quarantine=1)
        r500, _ = campaign(500, burst=16, work=8, quarantine=2)
        r1000, results1000 = campaign(1000, burst=32, work=12, quarantine=3)

        self.assertEqual(r100, 100)
        self.assertLess(r500, 500)
        self.assertLess(r1000, r500 * 2)
        self.assertTrue(any(not r.recovered for r in results1000))

    def test_failure_reasons_are_observable(self):
        capacity = RecoveryCapacity(
            queue_slots=8,
            workers=1,
            worker_units_per_tick=1,
            timeout_ticks=2,
            quarantine_slots=6,
        )
        incidents = [
            IncidentLoad(
                incident_id=f"burst-{i}",
                work_units=5,
                quarantine_units=2,
                arrival_tick=0,
                deadline_tick=2,
            )
            for i in range(12)
        ]
        results = simulate(capacity, incidents)
        reasons = {r.reason for r in results if not r.recovered}
        self.assertTrue(reasons & {"queue_overflow", "quarantine_exhausted", "recovery_timeout"})


if __name__ == "__main__":
    unittest.main()
