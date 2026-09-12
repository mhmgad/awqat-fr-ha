"""Helpers to resolve an Awqat coordinator from a Home Assistant device."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import AwqatCoordinator


def async_coordinator_for_device(hass: HomeAssistant, device_id: str) -> AwqatCoordinator | None:
    """Return the coordinator that owns this device, if any."""
    device = dr.async_get(hass).async_get(device_id)
    if not device:
        return None
    for identifier in device.identifiers:
        if identifier[0] != DOMAIN:
            continue
        mosque_code = identifier[1]
        for item in hass.data.get(DOMAIN, {}).values():
            if isinstance(item, AwqatCoordinator) and item.mosque_code == mosque_code:
                return item
    return None


def async_device_id_for_coordinator(hass: HomeAssistant, coordinator: AwqatCoordinator) -> str | None:
    """Return the registry id of the mosque device."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, coordinator.mosque_code)})
    return device.id if device else None
