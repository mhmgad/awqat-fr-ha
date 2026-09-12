"""Tests for Awqat device automations and upcoming prayer events."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from awqat.automations import (  # noqa: E402
    automation_id,
    build_automation_configs,
    slug_mosque_code,
)
from awqat.calculator import compute_mosque_times  # noqa: E402
from awqat.prayer_events import iter_upcoming_prayer_events  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PARIS = ZoneInfo("Europe/Paris")


def _cfg(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())["result"]["cfg"]


def _calendar() -> dict:
    return json.loads((FIXTURES / "badr-lille-cal.json").read_text())["awqat"]


class AutomationBuilderTests(unittest.TestCase):
    def test_ids_are_stable(self) -> None:
        self.assertEqual(automation_id("badr-lille", "adhan"), "awqat_badr_lille_adhan")
        self.assertEqual(slug_mosque_code("awqat_mosquee_villeparisis"), "awqat_mosquee_villeparisis")

    def test_device_automations_cover_adhan_iqama_and_jumua(self) -> None:
        configs = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
        )
        self.assertEqual(len(configs), 3)
        by_id = {item["id"]: item for item in configs}
        self.assertTrue(by_id["awqat_badr_lille_adhan"]["initial_state"])
        self.assertFalse(by_id["awqat_badr_lille_iqama"]["initial_state"])
        adhan_types = {item["type"] for item in by_id["awqat_badr_lille_adhan"]["trigger"]}
        self.assertEqual(adhan_types, {"fajr", "dhuhr", "asr", "maghrib", "isha"})
        for item in configs:
            for trigger in item["trigger"]:
                self.assertEqual(trigger["platform"], "device")
                self.assertEqual(trigger["domain"], "awqat")
                self.assertEqual(trigger["device_id"], "device-123")


class UpcomingEventTests(unittest.TestCase):
    def test_before_fajr_includes_today_adhan_and_iqama(self) -> None:
        now = datetime(2026, 9, 12, 5, 0, tzinfo=PARIS)
        times = compute_mosque_times(
            cfg=_cfg("badr-lille.json"),
            tz=PARIS,
            now=now,
            calendar=_calendar(),
        )
        events = iter_upcoming_prayer_events(times, now)
        types = [item.trigger_type for item in events]
        self.assertIn("fajr", types)
        self.assertIn("iqama_fajr", types)
        self.assertIn("maghrib", types)
        fajr = next(item for item in events if item.trigger_type == "fajr")
        self.assertEqual(fajr.kind, "adhan")
        self.assertGreater(fajr.when, now)

    def test_after_isha_skips_today_isha(self) -> None:
        now = datetime(2026, 9, 12, 22, 30, tzinfo=PARIS)
        times = compute_mosque_times(
            cfg=_cfg("badr-lille.json"),
            tz=PARIS,
            now=now,
            calendar=_calendar(),
        )
        events = iter_upcoming_prayer_events(times, now)
        types = {item.trigger_type for item in events if item.when.date().isoformat() == "2026-09-12"}
        self.assertNotIn("isha", types)
        self.assertTrue(any(item.trigger_type == "fajr" for item in events))


class YamlUpsertTests(unittest.TestCase):
    def test_upsert_appends_missing_automations(self) -> None:
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML is not installed")
        from awqat.automations import _remove_automations, _upsert_automations

        configs = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "automations.yaml"
            written = _upsert_automations(path, configs)
            self.assertEqual(len(written), 3)
            again = _upsert_automations(path, configs)
            self.assertEqual(again, written)
            loaded = yaml.safe_load(path.read_text())
            self.assertEqual(len(loaded), 3)
            self.assertTrue(_remove_automations(path, set(written)))
            self.assertEqual(yaml.safe_load(path.read_text()), [])


if __name__ == "__main__":
    unittest.main()
