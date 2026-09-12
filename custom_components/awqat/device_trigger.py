"""Device triggers for Awqat mosque prayer times."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_AWQAT, TRIGGER_TYPES
from .device import async_coordinator_for_device

try:
    from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
except ImportError:  # pragma: no cover
    DEVICE_TRIGGER_BASE_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "device",
            vol.Required(CONF_DOMAIN): str,
            vol.Required(CONF_DEVICE_ID): str,
        }
    )

try:
    from homeassistant.components.homeassistant.triggers import event as event_trigger
except ImportError:  # pragma: no cover
    event_trigger = None  # type: ignore[assignment]


TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES)}
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return prayer triggers for this mosque device."""
    if async_coordinator_for_device(hass, device_id) is None:
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPES
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for the matching Awqat prayer event."""
    if event_trigger is None:
        raise RuntimeError("Home Assistant event trigger platform is unavailable")
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_AWQAT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


async def async_validate_trigger_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate a device trigger config."""
    return TRIGGER_SCHEMA(config)
