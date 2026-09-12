"""Device actions for an Awqat mosque."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN
from .device import async_coordinator_for_device

ACTION_TYPES = {"refresh"}

try:
    from homeassistant.components.device_automation import DEVICE_ACTION_BASE_SCHEMA
except ImportError:  # pragma: no cover
    DEVICE_ACTION_BASE_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): str,
        }
    )

ACTION_SCHEMA = DEVICE_ACTION_BASE_SCHEMA.extend({vol.Required(CONF_TYPE): vol.In(ACTION_TYPES)})


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return actions for this mosque device."""
    if async_coordinator_for_device(hass, device_id) is None:
        return []
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "refresh",
        }
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Refresh the mosque timetable."""
    coordinator = async_coordinator_for_device(hass, config[CONF_DEVICE_ID])
    if coordinator is None:
        return
    await coordinator.async_request_refresh()
