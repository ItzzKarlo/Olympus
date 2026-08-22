from datetime import datetime, time
import unittest

from olympus_core.config import NightSettings, parse_core_config
from olympus_core.services.time_policy import TimePolicyService


def at(value: str) -> datetime:
    return datetime.fromisoformat(value)


class TimePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = TimePolicyService(NightSettings(), "Europe/Berlin")

    def assert_night(self, value: str, expected: bool) -> None:
        self.assertEqual(self.policy.is_night(at(value)), expected, value)

    def test_weekday_boundaries(self) -> None:
        self.assert_night("2026-08-24T21:59:00+02:00", False)
        self.assert_night("2026-08-24T22:00:00+02:00", True)
        self.assert_night("2026-08-25T07:29:00+02:00", True)
        self.assert_night("2026-08-25T07:30:00+02:00", False)

    def test_friday_midnight_semantics(self) -> None:
        self.assert_night("2026-08-28T22:00:00+02:00", False)
        self.assert_night("2026-08-28T23:59:00+02:00", False)
        self.assert_night("2026-08-29T00:00:00+02:00", True)
        self.assert_night("2026-08-29T07:29:00+02:00", True)
        self.assert_night("2026-08-29T07:30:00+02:00", False)

    def test_saturday_and_sunday_boundaries(self) -> None:
        self.assert_night("2026-08-29T23:59:00+02:00", False)
        self.assert_night("2026-08-30T00:00:00+02:00", True)
        self.assert_night("2026-08-30T07:29:00+02:00", True)
        self.assert_night("2026-08-30T07:30:00+02:00", False)
        self.assert_night("2026-08-30T22:00:00+02:00", True)

    def test_period_context_and_next_transition(self) -> None:
        active = self.policy.evaluate(at("2026-08-24T23:30:00+02:00"))
        self.assertTrue(active.is_night)
        self.assertEqual(active.period_started_at, at("2026-08-24T22:00:00+02:00"))
        self.assertEqual(active.period_ends_at, at("2026-08-25T07:30:00+02:00"))
        self.assertEqual(active.next_transition_at, active.period_ends_at)

        day = self.policy.evaluate(at("2026-08-28T23:59:00+02:00"))
        self.assertFalse(day.is_night)
        self.assertEqual(day.next_transition_at, at("2026-08-29T00:00:00+02:00"))

    def test_disabled_and_custom_schedule(self) -> None:
        disabled = TimePolicyService(NightSettings(enabled=False), "Europe/Berlin")
        self.assertFalse(disabled.is_night(at("2026-08-24T23:00:00+02:00")))
        self.assertIsNone(disabled.evaluate(at("2026-08-24T23:00:00+02:00")).next_transition_at)

        custom = TimePolicyService(NightSettings(
            weekday_start=time(21, 15),
            weekend_start=time(1, 30),
            end=time(8, 45),
            weekend_days=(3, 4),
        ), "Europe/Berlin")
        self.assertTrue(custom.is_night(at("2026-08-24T21:15:00+02:00")))
        self.assertFalse(custom.is_night(at("2026-08-28T01:29:00+02:00")))
        self.assertTrue(custom.is_night(at("2026-08-28T01:30:00+02:00")))
        self.assertFalse(custom.is_night(at("2026-08-28T08:45:00+02:00")))

    def test_timezone_and_dst_are_zoneinfo_aware(self) -> None:
        before_jump = self.policy.evaluate(at("2026-03-29T00:30:00+00:00"))
        after_jump = self.policy.evaluate(at("2026-03-29T01:30:00+00:00"))
        self.assertTrue(before_jump.is_night)
        self.assertTrue(after_jump.is_night)
        self.assertEqual(before_jump.period_ends_at.utcoffset().total_seconds(), 7_200)

    def test_naive_datetime_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.policy.is_night(datetime(2026, 8, 24, 23))


class NightConfigTests(unittest.TestCase):
    def test_defaults_and_custom_values(self) -> None:
        defaults = parse_core_config({}).night
        self.assertTrue(defaults.enabled)
        self.assertEqual(defaults.weekend_days, (4, 5))
        custom = parse_core_config({"night": {
            "enabled": False,
            "weekday_start": "21:15",
            "weekend_start": "01:30",
            "end": "08:45",
            "weekend_days": ["thursday", "friday"],
        }}).night
        self.assertFalse(custom.enabled)
        self.assertEqual(custom.weekday_start, time(21, 15))
        self.assertEqual(custom.weekend_days, (3, 4))

    def test_invalid_time_and_weekend_days_fail_usefully(self) -> None:
        with self.assertRaisesRegex(ValueError, "night.weekday_start"):
            parse_core_config({"night": {"weekday_start": "25:61"}})
        with self.assertRaisesRegex(ValueError, "Invalid night weekend day"):
            parse_core_config({"night": {"weekend_days": ["funday"]}})


if __name__ == "__main__":
    unittest.main()
