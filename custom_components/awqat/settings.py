"""Helpers for reading Awqat config-entry settings."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_AZAN_PLAYER,
    CONF_CREATE_AUTOMATIONS,
    CONF_CREATE_AZAN,
    CONF_CREATE_IQAMA,
    CONF_CREATE_JUMUA,
    CONF_PAUSE_PLAYERS,
    DEFAULT_ATHAN_URL,
)


def entry_value(entry: Any, key: str, default: Any = None) -> Any:
    """Prefer options, then data."""
    if key in getattr(entry, "options", {}):
        return entry.options[key]
    return entry.data.get(key, default)


def as_entity_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if item]


def create_azan(entry: Any) -> bool:
    if CONF_CREATE_AZAN in getattr(entry, "options", {}) or CONF_CREATE_AZAN in entry.data:
        return bool(entry_value(entry, CONF_CREATE_AZAN, False))
    return bool(entry_value(entry, CONF_CREATE_AUTOMATIONS, True))


def create_iqama(entry: Any) -> bool:
    if CONF_CREATE_IQAMA in getattr(entry, "options", {}) or CONF_CREATE_IQAMA in entry.data:
        return bool(entry_value(entry, CONF_CREATE_IQAMA, False))
    return False


def create_jumua(entry: Any) -> bool:
    if CONF_CREATE_JUMUA in getattr(entry, "options", {}) or CONF_CREATE_JUMUA in entry.data:
        return bool(entry_value(entry, CONF_CREATE_JUMUA, False))
    return bool(entry_value(entry, CONF_CREATE_AUTOMATIONS, True))


def azan_player(entry: Any) -> str | None:
    value = entry_value(entry, CONF_AZAN_PLAYER)
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def pause_players(entry: Any) -> list[str]:
    player = azan_player(entry)
    paused = as_entity_list(entry_value(entry, CONF_PAUSE_PLAYERS))
    return [item for item in paused if item != player]


def athan_url_from_entry(entry: Any, fallback: str | None = None) -> str:
    return fallback or DEFAULT_ATHAN_URL
