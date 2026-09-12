"""Diagnostics for Awqat prayer times."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AwqatCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: AwqatCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data
    if not data:
        return {"configured": entry.data, "times": None}

    def _day(day) -> dict[str, Any]:
        return {
            "date": day.day.isoformat(),
            "prayers": {
                name: {
                    "adhan": prayer.adhan.isoformat(),
                    "iqama": prayer.iqama.isoformat() if prayer.iqama else None,
                    "source": prayer.source,
                }
                for name, prayer in day.prayers.items()
            },
        }

    return {
        "mosque_code": data.mosque_code,
        "mosque_label": data.mosque_label,
        "method": data.method,
        "use_calendar": data.use_calendar,
        "fetch_status": data.fetch_status,
        "last_error": data.last_error,
        "last_success": data.last_success.isoformat() if data.last_success else None,
        "next_refresh": data.next_refresh.isoformat() if data.next_refresh else None,
        "next_prayer": data.next_prayer,
        "next_prayer_time": data.next_prayer_time.isoformat(),
        "automation_ids": list(entry.data.get("automation_ids") or []),
        "today": _day(data.today),
        "tomorrow": _day(data.tomorrow),
    }
