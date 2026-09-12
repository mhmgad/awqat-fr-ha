"""Tests for Awqat timetable calculation and fetch scheduling."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from awqat.calculator import (  # noqa: E402
    apply_fixed_time,
    compute_mosque_times,
    duration_minutes,
    next_prayer_at,
)
from awqat.schedule import next_scheduled_refresh, retry_delay  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PARIS = ZoneInfo("Europe/Paris")


def _cfg(name: str) -> dict:
    payload = json.loads((FIXTURES / name).read_text())
    return payload["result"]["cfg"]


def _calendar() -> dict:
    return json.loads((FIXTURES / "badr-lille-cal.json").read_text())["awqat"]


class DurationTests(unittest.TestCase):
    def test_minutes_and_seconds(self) -> None:
        self.assertEqual(duration_minutes({"m": 10}), 10)
        self.assertEqual(duration_minutes({"m": 10, "s": 30}), 10.5)
        self.assertEqual(duration_minutes(None), 0)


class FixedTimeTests(unittest.TestCase):
    def test_dst_yes_in_september(self) -> None:
        setting = {"fixedTimes": [{"type": "dst_yes", "time": "1400"}, {"type": "dst_no", "time": "1300"}]}
        clock, source = apply_fixed_time("13:49", setting, datetime(2026, 9, 12).date(), PARIS)
        self.assertEqual(clock, "14:00")
        self.assertEqual(source, "fixed")

    def test_dst_no_in_january(self) -> None:
        setting = {"fixedTimes": [{"type": "dst_yes", "time": "1400"}, {"type": "dst_no", "time": "1300"}]}
        clock, source = apply_fixed_time("12:56", setting, datetime(2026, 1, 15).date(), PARIS)
        self.assertEqual(clock, "13:00")
        self.assertEqual(source, "fixed")

    def test_min_raises_early_isha(self) -> None:
        setting = {"fixedTimes": [{"type": "min", "time": "1905"}]}
        clock, source = apply_fixed_time("18:40", setting, datetime(2026, 9, 12).date(), PARIS)
        self.assertEqual(clock, "19:05")
        self.assertEqual(source, "fixed")

    def test_min_keeps_later_isha(self) -> None:
        setting = {"fixedTimes": [{"type": "min", "time": "1905"}]}
        clock, source = apply_fixed_time("21:45", setting, datetime(2026, 9, 12).date(), PARIS)
        self.assertEqual(clock, "21:45")
        self.assertEqual(source, "calculated")


class CalendarMosqueTests(unittest.TestCase):
    def test_badr_lille_uses_calendar_and_fixed_dhuhr(self) -> None:
        now = datetime(2026, 9, 12, 10, 0, tzinfo=PARIS)
        times = compute_mosque_times(
            cfg=_cfg("badr-lille.json"),
            tz=PARIS,
            now=now,
            calendar=_calendar(),
            mosque_code="badr-lille",
        )
        today = times.today.prayers
        self.assertEqual(today["fajr"].adhan.strftime("%H:%M"), "06:00")
        self.assertEqual(today["sunrise"].adhan.strftime("%H:%M"), "07:19")
        self.assertEqual(today["dhuhr"].adhan.strftime("%H:%M"), "14:00")
        self.assertEqual(today["dhuhr"].source, "fixed")
        self.assertEqual(today["asr"].adhan.strftime("%H:%M"), "17:15")
        self.assertEqual(today["maghrib"].adhan.strftime("%H:%M"), "20:13")
        self.assertEqual(today["isha"].adhan.strftime("%H:%M"), "21:45")
        self.assertEqual(today["fajr"].iqama.strftime("%H:%M"), "06:10")
        self.assertEqual(today["maghrib"].iqama.strftime("%H:%M"), "20:18")
        self.assertEqual(today["fajr"].source, "calendar")
        self.assertTrue(times.use_calendar)
        self.assertEqual(times.next_prayer, "dhuhr")

    def test_jumua_lands_on_next_friday(self) -> None:
        now = datetime(2026, 9, 12, 10, 0, tzinfo=PARIS)  # Saturday
        times = compute_mosque_times(
            cfg=_cfg("badr-lille.json"),
            tz=PARIS,
            now=now,
            calendar=_calendar(),
        )
        jumua = times.today.prayers["jumua"].adhan
        self.assertEqual(jumua.date().isoformat(), "2026-09-18")
        self.assertEqual(jumua.weekday(), 4)


class CalculatedMosqueTests(unittest.TestCase):
    def test_villeparisis_applies_offsets_and_fixed_times(self) -> None:
        now = datetime(2026, 9, 12, 8, 0, tzinfo=PARIS)
        times = compute_mosque_times(
            cfg=_cfg("villeparisis.json"),
            tz=PARIS,
            now=now,
        )
        today = times.today.prayers
        self.assertEqual(times.method, "UOIF")
        self.assertFalse(times.use_calendar)
        self.assertEqual(today["dhuhr"].adhan.strftime("%H:%M"), "14:00")
        self.assertEqual(today["dhuhr"].source, "fixed")
        self.assertEqual(today["jumua"].adhan.strftime("%H:%M"), "13:00")
        self.assertEqual(today["jumua"].source, "fixed")
        # Isha is maghrib + 90 minutes, then raised to the 19:05 minimum if needed.
        maghrib = today["maghrib"].adhan
        isha = today["isha"].adhan
        self.assertGreaterEqual(isha, maghrib)
        self.assertGreaterEqual(isha.strftime("%H:%M"), "19:05")
        self.assertEqual((today["fajr"].iqama - today["fajr"].adhan).total_seconds(), 10 * 60)

    def test_custom_method_uses_period_for_isha(self) -> None:
        now = datetime(2026, 9, 12, 8, 0, tzinfo=PARIS)
        times = compute_mosque_times(cfg=_cfg("bilel.json"), tz=PARIS, now=now)
        maghrib = times.today.prayers["maghrib"].adhan
        isha = times.today.prayers["isha"].adhan
        self.assertEqual(int((isha - maghrib).total_seconds() / 60), 90)


class NextPrayerTests(unittest.TestCase):
    def test_after_isha_returns_tomorrow_fajr(self) -> None:
        now = datetime(2026, 9, 12, 22, 30, tzinfo=PARIS)
        times = compute_mosque_times(
            cfg=_cfg("badr-lille.json"),
            tz=PARIS,
            now=now,
            calendar=_calendar(),
        )
        self.assertEqual(times.next_prayer, "fajr")
        self.assertEqual(times.next_prayer_time.date().isoformat(), "2026-09-13")

    def test_helper_skips_sunrise(self) -> None:
        now = datetime(2026, 9, 12, 6, 30, tzinfo=PARIS)
        times = compute_mosque_times(
            cfg=_cfg("badr-lille.json"),
            tz=PARIS,
            now=now,
            calendar=_calendar(),
        )
        name, when = next_prayer_at(times.today, times.tomorrow, now)
        self.assertEqual(name, "dhuhr")
        self.assertGreater(when, now)


class ScheduleTests(unittest.TestCase):
    def test_before_isha_schedules_after_isha(self) -> None:
        now = datetime(2026, 9, 12, 18, 0, tzinfo=PARIS)
        isha = datetime(2026, 9, 12, 21, 45, tzinfo=PARIS)
        nxt = next_scheduled_refresh(now, isha)
        self.assertEqual(nxt, datetime(2026, 9, 12, 21, 47, tzinfo=PARIS))

    def test_after_isha_schedules_two_am(self) -> None:
        now = datetime(2026, 9, 12, 22, 0, tzinfo=PARIS)
        isha = datetime(2026, 9, 12, 21, 45, tzinfo=PARIS)
        nxt = next_scheduled_refresh(now, isha)
        self.assertEqual(nxt, datetime(2026, 9, 13, 2, 0, tzinfo=PARIS))

    def test_after_two_am_schedules_isha(self) -> None:
        now = datetime(2026, 9, 13, 3, 0, tzinfo=PARIS)
        isha = datetime(2026, 9, 13, 21, 40, tzinfo=PARIS)
        nxt = next_scheduled_refresh(now, isha)
        self.assertEqual(nxt, datetime(2026, 9, 13, 21, 42, tzinfo=PARIS))

    def test_without_isha_uses_two_am(self) -> None:
        now = datetime(2026, 9, 12, 22, 0, tzinfo=PARIS)
        nxt = next_scheduled_refresh(now, None)
        self.assertEqual(nxt, datetime(2026, 9, 13, 2, 0, tzinfo=PARIS))

    def test_retry_delays(self) -> None:
        self.assertEqual(retry_delay(0).total_seconds(), 30)
        self.assertEqual(retry_delay(1).total_seconds(), 60)
        self.assertEqual(retry_delay(2).total_seconds(), 120)
        self.assertEqual(retry_delay(9).total_seconds(), 120)


if __name__ == "__main__":
    unittest.main()
