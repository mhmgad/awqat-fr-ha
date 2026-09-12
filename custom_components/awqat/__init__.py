"""Awqat prayer times Home Assistant integration."""

from __future__ import annotations

from .const import DOMAIN, PLATFORMS

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType

    from .automations import async_create_device_automations, async_remove_device_automations
    from .coordinator import AwqatCoordinator
    from .device import async_device_id_for_coordinator
except ImportError:  # pragma: no cover - calculator tests without Home Assistant
    ConfigEntry = object  # type: ignore[misc, assignment]
    HomeAssistant = object  # type: ignore[misc, assignment]
    ServiceCall = object  # type: ignore[misc, assignment]
    ConfigType = dict  # type: ignore[misc, assignment]
    AwqatCoordinator = object  # type: ignore[misc, assignment]

    async def async_create_device_automations(*_args, **_kwargs):  # type: ignore[misc]
        return None

    async def async_remove_device_automations(*_args, **_kwargs):  # type: ignore[misc]
        return None

    def async_device_id_for_coordinator(*_args, **_kwargs):  # type: ignore[misc]
        return None

SERVICE_REFRESH = "refresh"


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Awqat domain."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a mosque from a config entry."""
    coordinator = AwqatCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    device_id = async_device_id_for_coordinator(hass, coordinator)
    if device_id:
        coordinator.async_bind_device(device_id)
        await async_create_device_automations(hass, entry, device_id)

    async def _refresh(_call: ServiceCall) -> None:
        for item in hass.data.get(DOMAIN, {}).values():
            if isinstance(item, AwqatCoordinator):
                await item.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh)

    entry.async_on_unload(coordinator.async_shutdown)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a mosque config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: AwqatCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_shutdown()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove notification automations created for this mosque."""
    await async_remove_device_automations(hass, entry)
