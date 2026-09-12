"""Upcoming adhan and iqama events used by triggers and automations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .calculator import MosqueTimes
from .const import DISPLAY_NAMES


@dataclass(frozen=True)
class ScheduledPrayerEvent:
    """One future adhan or iqama occurrence."""

    when: datetime
    trigger_type: str
    prayer: str
    kind: str
    prayer_name: str
    kind_name: str


def iter_upcoming_prayer_events(data: MosqueTimes, now: datetime) -> list[ScheduledPrayerEvent]:
    """Return future prayer events for today and tomorrow, de-duplicated."""
    found: dict[tuple[str, str], ScheduledPrayerEvent] = {}
    for day_times in (data.today, data.tomorrow):
        for prayer in day_times.prayers.values():
            prayer_name = DISPLAY_NAMES.get(prayer.name, prayer.name.title())
            if prayer.adhan > now:
                trigger = prayer.name
                found[(trigger, prayer.adhan.isoformat())] = ScheduledPrayerEvent(
                    when=prayer.adhan,
                    trigger_type=trigger,
                    prayer=prayer.name,
                    kind="adhan",
                    prayer_name=prayer_name,
                    kind_name="Adhan",
                )
            if prayer.iqama and prayer.iqama > now:
                trigger = f"iqama_{prayer.name}"
                found[(trigger, prayer.iqama.isoformat())] = ScheduledPrayerEvent(
                    when=prayer.iqama,
                    trigger_type=trigger,
                    prayer=prayer.name,
                    kind="iqama",
                    prayer_name=prayer_name,
                    kind_name="Iqama",
                )
    return sorted(found.values(), key=lambda item: item.when)
