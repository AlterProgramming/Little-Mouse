import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import promote_temporal_evidence as promotion  # noqa: E402


def event(ms, observed, subject="actor", semantic="read_through_watermark"):
    return {
        "semantic": semantic,
        "role": "watermark_position_time",
        "timestamp_ms": ms,
        "subject_fingerprint": subject,
        "first_capture_observed_at": observed,
        "last_capture_observed_at": observed,
        "supports_synchronized_viewing": False,
    }


class TemporalPromotionTests(unittest.TestCase):
    def test_advancing_watermark_promotes_to_bounded_interval_only(self):
        result = promotion.promote([
            {"events": [event(1786240501065, "2026-08-09T19:16:19.456Z")]},
            {"events": [event(1786240601065, "2026-08-09T19:24:00.000Z")]},
        ])
        self.assertEqual(result["bounded_action_interval_count"], 1)
        row = result["promotions"][0]
        self.assertEqual(row["lower_bound_observed_at"], "2026-08-09T19:16:19.456Z")
        self.assertEqual(row["upper_bound_observed_at"], "2026-08-09T19:24:00.000Z")
        self.assertFalse(row["exact_event_time_claimed"])
        self.assertFalse(row["participant_action_semantics_claimed"])
        self.assertTrue(row["reversible"])

    def test_unchanged_watermark_does_not_invent_action(self):
        result = promotion.promote([
            {"events": [event(1786240501065, "2026-08-09T19:16:19.456Z")]},
            {"events": [event(1786240501065, "2026-08-09T19:24:00.000Z")]},
        ])
        self.assertEqual(result["bounded_action_interval_count"], 0)

    def test_regression_is_retained_as_contradiction(self):
        result = promotion.promote([
            {"events": [event(1786240601065, "2026-08-09T19:16:19.456Z")]},
            {"events": [event(1786240501065, "2026-08-09T19:24:00.000Z")]},
        ])
        self.assertEqual(result["bounded_action_interval_count"], 0)
        self.assertEqual(result["contradiction_count"], 1)
        self.assertEqual(result["contradictions"][0]["type"], "non_monotonic_watermark")

    def test_direct_action_requires_explicit_action_semantics(self):
        direct = event(1786240601065, "2026-08-09T19:24:00.000Z", semantic="view_action")
        direct["supports_synchronized_viewing"] = True
        result = promotion.promote([{"events": [direct]}])
        self.assertEqual(result["direct_action_count"], 1)
        self.assertTrue(result["inference_limits"]["direct_view_action_timestamps_available"])
        self.assertFalse(result["inference_limits"]["synchronized_viewing_claimed"])


if __name__ == "__main__":
    unittest.main()
