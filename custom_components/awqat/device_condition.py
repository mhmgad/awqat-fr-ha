"""Device conditions for the next Awqat prayer."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN, SALAT_PRAYERS
from .device import async_coordinator_for_device

CONDITION_TYPES = {f"is_next_{name}" for name in SALAT_PRAYERS}

try:
    from homeassistant.components.device_automation import DEVICE_CONDITION_BASE_SCHEMA
except ImportError:  # pragma: no cover
    DEVICE_CONDITION_BASE_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_CONDITION): "device",
            vol.Required(CONF_DOMAIN): str,
            vol.Required(CONF_DEVICE_ID): str,
        }
    )

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES)}
)


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return next-prayer conditions for this mosque."""
    if async_coordinator_for_device(hass, device_id) is None:
        return []
    return [
        {
            CONF_CONDITION: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: condition_type,
        }
        for condition_type in sorted(CONDITION_TYPES)
    ]


@callback
def async_condition_from_config(hass: HomeAssistant, config: ConfigType):
    """Return a checker for the selected next prayer."""
    prayer = str(config[CONF_TYPE]).removeprefix("is_next_")
    device_id = config[CONF_DEVICE_ID]

    @callback
    def test_next_prayer(hass_inner: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        coordinator = async_coordinator_for_device(hass_inner, device_id)
        if coordinator is None or coordinator.data is None:
            return False
        current = coordinator.data.next_prayer
        if current == "jumua":
            current = "dhuhr"
        return current == prayer

    return test_next_prayer
