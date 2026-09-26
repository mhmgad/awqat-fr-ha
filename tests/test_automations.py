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
from awqat.calculator import compute_mosque_times, extract_athan_url  # noqa: E402
from awqat.const import DEFAULT_ATHAN_URL  # noqa: E402
from awqat.dashboard import build_dashboard_config  # noqa: E402
from awqat.prayer_events import iter_upcoming_prayer_events  # noqa: E402
from awqat.settings import azan_player, create_azan, create_iqama, create_jumua, pause_players  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PARIS = ZoneInfo("Europe/Paris")


class _Entry:
    def __init__(self, data: dict, options: dict | None = None) -> None:
        self.data = data
        self.options = options or {}


def _cfg(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())["result"]["cfg"]


def _calendar() -> dict:
    return json.loads((FIXTURES / "badr-lille-cal.json").read_text())["awqat"]


def _services(config: dict) -> set[str]:
    return {item["service"] for item in config["action"] if "service" in item}


class AutomationBuilderTests(unittest.TestCase):
    def test_ids_are_stable(self) -> None:
        self.assertEqual(automation_id("badr-lille", "adhan"), "awqat_badr_lille_adhan")
        self.assertEqual(slug_mosque_code("awqat_mosquee_villeparisis"), "awqat_mosquee_villeparisis")

    def test_default_creates_azan_and_jumua_only(self) -> None:
        configs = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
        )
        self.assertEqual([item["id"] for item in configs], ["awqat_badr_lille_adhan", "awqat_badr_lille_jumua"])
        adhan_types = {item["type"] for item in configs[0]["trigger"]}
        self.assertEqual(adhan_types, {"fajr", "dhuhr", "asr", "maghrib", "isha"})
        self.assertEqual(configs[1]["trigger"][0]["type"], "jumua")

    def test_each_kind_can_be_skipped(self) -> None:
        configs = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
            create_azan_automation=False,
            create_iqama_automation=True,
            create_jumua_automation=False,
        )
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["id"], "awqat_badr_lille_iqama")
        self.assertEqual(_services(configs[0]), {"persistent_notification.create"})

    def test_media_actions_pause_tvs_and_play_azan(self) -> None:
        configs = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
            create_azan_automation=True,
            create_iqama_automation=True,
            create_jumua_automation=True,
            azan_media_player="media_player.kitchen",
            pause_media_players=["media_player.tv", "media_player.kitchen"],
        )
        by_id = {item["id"]: item for item in configs}
        azan_services = _services(by_id["awqat_badr_lille_adhan"])
        self.assertIn("media_player.media_pause", azan_services)
        self.assertIn("media_player.play_media", azan_services)
        play = next(
            item
            for item in by_id["awqat_badr_lille_adhan"]["action"]
            if item.get("service") == "media_player.play_media"
        )
        self.assertEqual(play["target"]["entity_id"], "media_player.kitchen")
        pause = next(
            item
            for item in by_id["awqat_badr_lille_adhan"]["action"]
            if item.get("service") == "media_player.media_pause"
        )
        self.assertEqual(pause["target"]["entity_id"], ["media_player.tv"])
        iqama_services = _services(by_id["awqat_badr_lille_iqama"])
        self.assertIn("media_player.media_pause", iqama_services)
        self.assertNotIn("media_player.play_media", iqama_services)
        jumua_services = _services(by_id["awqat_badr_lille_jumua"])
        self.assertIn("media_player.play_media", jumua_services)


class SettingsTests(unittest.TestCase):
    def test_legacy_combined_flag_maps_to_azan_and_jumua(self) -> None:
        entry = _Entry({"create_automations": True})
        self.assertTrue(create_azan(entry))
        self.assertFalse(create_iqama(entry))
        self.assertTrue(create_jumua(entry))

    def test_options_override_data(self) -> None:
        entry = _Entry(
            {"create_azan": True, "create_iqama": False, "azan_player": "media_player.old"},
            {
                "create_azan": False,
                "create_iqama": True,
                "azan_player": "media_player.kitchen",
                "pause_players": ["media_player.tv", "media_player.kitchen"],
            },
        )
        self.assertFalse(create_azan(entry))
        self.assertTrue(create_iqama(entry))
        self.assertEqual(azan_player(entry), "media_player.kitchen")
        self.assertEqual(pause_players(entry), ["media_player.tv"])


class DashboardTests(unittest.TestCase):
    def test_card_includes_five_prayers_jumua_sunrise_and_next(self) -> None:
        entities = {
            "fajr": "sensor.fajr",
            "dhuhr": "sensor.dhuhr",
            "asr": "sensor.asr",
            "maghrib": "sensor.maghrib",
            "isha": "sensor.isha",
            "jumua": "sensor.jumua",
            "sunrise": "sensor.sunrise",
            "next_prayer": "sensor.next_prayer",
            "next_prayer_name": "sensor.next_prayer_name",
        }
        config = build_dashboard_config("Mosquée Badr, Lille", entities)
        card = config["views"][0]["cards"][0]
        self.assertEqual(card["type"], "custom:awqat-prayer-card")
        self.assertEqual(card["entities"]["jumua"], "sensor.jumua")
        self.assertEqual(card["entities"]["sunrise"], "sensor.sunrise")
        self.assertEqual(card["entities"]["next_prayer"], "sensor.next_prayer")


class AthanUrlTests(unittest.TestCase):
    def test_fallback_when_mosque_has_no_audio(self) -> None:
        self.assertEqual(extract_athan_url(_cfg("badr-lille.json")), DEFAULT_ATHAN_URL)

    def test_uses_published_audio(self) -> None:
        cfg = {
            "timeSetting": {
                "timeItemSettings": {
                    "dhuhr": {"athanSoundSrc": "https://example.test/adhan.mp3"},
                }
            }
        }
        self.assertEqual(extract_athan_url(cfg), "https://example.test/adhan.mp3")


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
            create_iqama_automation=True,
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

    def test_replace_drops_disabled_kinds(self) -> None:
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML is not installed")
        from awqat.automations import _upsert_automations

        all_three = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
            create_iqama_automation=True,
        )
        azan_only = build_automation_configs(
            mosque_code="badr-lille",
            mosque_label="Mosquée Badr, Lille",
            device_id="device-123",
            create_azan_automation=True,
            create_iqama_automation=False,
            create_jumua_automation=False,
            azan_media_player="media_player.kitchen",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "automations.yaml"
            _upsert_automations(path, all_three)
            written = _upsert_automations(
                path,
                azan_only,
                replace=True,
                drop_ids={"awqat_badr_lille_iqama", "awqat_badr_lille_jumua"},
            )
            loaded = yaml.safe_load(path.read_text())
            self.assertEqual(written, ["awqat_badr_lille_adhan"])
            self.assertEqual(len(loaded), 1)
            self.assertIn("media_player.play_media", {item["service"] for item in loaded[0]["action"]})


if __name__ == "__main__":
    unittest.main()
