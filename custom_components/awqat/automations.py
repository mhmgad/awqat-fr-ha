"""Create and remove Home Assistant automations for an Awqat mosque device."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import logging
import re

from .const import (
    CONF_AUTOMATION_IDS,
    CONF_CREATE_AUTOMATIONS,
    CONF_MOSQUE_CODE,
    CONF_MOSQUE_LABEL,
    DEFAULT_ADHAN_TRIGGERS,
    DEFAULT_IQAMA_TRIGGERS,
    DOMAIN,
)

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import HomeAssistantError
except ImportError:  # pragma: no cover - unit tests without Home Assistant
    ConfigEntry = object  # type: ignore[misc, assignment]
    HomeAssistant = object  # type: ignore[misc, assignment]
    HomeAssistantError = Exception  # type: ignore[misc, assignment]

_LOGGER = logging.getLogger(__name__)

AUTOMATION_FILE = "automations.yaml"


def slug_mosque_code(mosque_code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", mosque_code.lower()).strip("_") or "mosque"


def automation_id(mosque_code: str, kind: str) -> str:
    return f"awqat_{slug_mosque_code(mosque_code)}_{kind}"


def _device_trigger(device_id: str, trigger_type: str) -> dict[str, Any]:
    return {
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device_id,
        "type": trigger_type,
    }


def _notification_action() -> dict[str, Any]:
    return {
        "service": "persistent_notification.create",
        "data": {
            "title": "{{ trigger.event.data.prayer_name }} — {{ trigger.event.data.mosque }}",
            "message": "{{ trigger.event.data.kind_name }} at {{ trigger.event.data.time }}",
            "notification_id": "awqat_{{ trigger.event.data.mosque_code }}_{{ trigger.event.data.type }}",
        },
    }


def build_automation_configs(
    *,
    mosque_code: str,
    mosque_label: str,
    device_id: str,
) -> list[dict[str, Any]]:
    """Return the automations attached to a mosque device."""
    return [
        {
            "id": automation_id(mosque_code, "adhan"),
            "alias": f"{mosque_label}: Adhan",
            "description": (
                "Created with this Awqat mosque device. "
                "Sends a Home Assistant notification at each adhan. "
                "You can edit, disable, or delete it."
            ),
            "mode": "queued",
            "initial_state": True,
            "trigger": [_device_trigger(device_id, item) for item in DEFAULT_ADHAN_TRIGGERS],
            "action": [_notification_action()],
        },
        {
            "id": automation_id(mosque_code, "iqama"),
            "alias": f"{mosque_label}: Iqama",
            "description": (
                "Created with this Awqat mosque device. "
                "Sends a notification at iqama. Disabled until you turn it on."
            ),
            "mode": "queued",
            "initial_state": False,
            "trigger": [_device_trigger(device_id, item) for item in DEFAULT_IQAMA_TRIGGERS],
            "action": [_notification_action()],
        },
        {
            "id": automation_id(mosque_code, "jumua"),
            "alias": f"{mosque_label}: Jumua",
            "description": (
                "Created with this Awqat mosque device. "
                "Sends a notification at Jumua (Friday prayer)."
            ),
            "mode": "single",
            "initial_state": True,
            "trigger": [
                _device_trigger(device_id, "jumua"),
                _device_trigger(device_id, "iqama_jumua"),
            ],
            "action": [_notification_action()],
        },
    ]


def _load_yaml_list(path: Path) -> list[Any]:
    import yaml

    if not path.exists() or path.stat().st_size == 0:
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return []
    if not isinstance(loaded, list):
        raise ValueError("automations.yaml is not a list")
    return loaded


def _dump_yaml_list(path: Path, items: list[Any]) -> None:
    import yaml

    path.write_text(
        yaml.safe_dump(
            items,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def _upsert_automations(path: Path, configs: list[dict[str, Any]]) -> list[str]:
    existing = _load_yaml_list(path)
    by_id: dict[str, int] = {}
    for index, item in enumerate(existing):
        if isinstance(item, dict) and item.get("id"):
            by_id[str(item["id"])] = index
    written: list[str] = []
    for config in configs:
        ident = str(config["id"])
        written.append(ident)
        if ident in by_id:
            continue
        existing.append(config)
    _dump_yaml_list(path, existing)
    return written


def _remove_automations(path: Path, identifiers: set[str]) -> bool:
    if not identifiers or not path.exists():
        return False
    existing = _load_yaml_list(path)
    kept = [
        item
        for item in existing
        if not (isinstance(item, dict) and str(item.get("id")) in identifiers)
    ]
    if len(kept) == len(existing):
        return False
    _dump_yaml_list(path, kept)
    return True


async def async_create_device_automations(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_id: str,
) -> None:
    """Add notification automations for this mosque if the user asked for them."""
    if not entry.data.get(CONF_CREATE_AUTOMATIONS, True):
        return
    if entry.data.get(CONF_AUTOMATION_IDS):
        return

    mosque_code = entry.data[CONF_MOSQUE_CODE]
    mosque_label = entry.data.get(CONF_MOSQUE_LABEL) or mosque_code
    configs = build_automation_configs(
        mosque_code=mosque_code,
        mosque_label=mosque_label,
        device_id=device_id,
    )
    path = Path(hass.config.path(AUTOMATION_FILE))

    try:
        written = await hass.async_add_executor_job(_upsert_automations, path, configs)
    except ValueError:
        _LOGGER.warning(
            "Could not add Awqat automations because %s is not a YAML list",
            path,
        )
        return
    except OSError as err:
        _LOGGER.warning("Could not write Awqat automations to %s: %s", path, err)
        return

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_AUTOMATION_IDS: written}
    )
    try:
        await hass.services.async_call("automation", "reload", blocking=True)
    except HomeAssistantError as err:
        _LOGGER.warning("Awqat automations were written but reload failed: %s", err)


async def async_remove_device_automations(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove automations this integration created for the mosque."""
    identifiers = {str(item) for item in entry.data.get(CONF_AUTOMATION_IDS) or []}
    mosque_code = entry.data.get(CONF_MOSQUE_CODE)
    if mosque_code:
        identifiers.update(
            automation_id(mosque_code, kind) for kind in ("adhan", "iqama", "jumua")
        )
    if not identifiers:
        return
    path = Path(hass.config.path(AUTOMATION_FILE))
    try:
        changed = await hass.async_add_executor_job(_remove_automations, path, identifiers)
    except (ValueError, OSError) as err:
        _LOGGER.debug("Could not remove Awqat automations: %s", err)
        return
    if changed:
        try:
            await hass.services.async_call("automation", "reload", blocking=True)
        except HomeAssistantError:
            _LOGGER.debug("Automation reload after Awqat removal failed")
