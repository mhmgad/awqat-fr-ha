"""Awqat prayer times Home Assistant integration."""

from __future__ import annotations

from .const import (
    CONF_CREATE_AUTOMATIONS,
    CONF_CREATE_AZAN,
    CONF_CREATE_IQAMA,
    CONF_CREATE_JUMUA,
    DOMAIN,
    PLATFORMS,
)

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType

    from .automations import async_create_device_automations, async_remove_device_automations
    from .coordinator import AwqatCoordinator
    from .dashboard import async_create_prayer_dashboard, async_setup_frontend
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

    async def async_create_prayer_dashboard(*_args, **_kwargs):  # type: ignore[misc]
        return None

    async def async_setup_frontend(*_args, **_kwargs):  # type: ignore[misc]
        return None

    def async_device_id_for_coordinator(*_args, **_kwargs):  # type: ignore[misc]
        return None

SERVICE_REFRESH = "refresh"


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Awqat domain."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a mosque from a config entry."""
    coordinator = AwqatCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_frontend(hass)
    device_id = async_device_id_for_coordinator(hass, coordinator)
    if device_id:
        coordinator.async_bind_device(device_id)
        await async_create_device_automations(hass, entry, device_id)
    await async_create_prayer_dashboard(hass, entry, coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _refresh(_call: ServiceCall) -> None:
        for item in hass.data.get(DOMAIN, {}).values():
            if isinstance(item, AwqatCoordinator):
                await item.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh)

    entry.async_on_unload(coordinator.async_shutdown)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recreate automations when azan / iqama / media options change."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not isinstance(coordinator, AwqatCoordinator):
        return
    device_id = coordinator.device_id or async_device_id_for_coordinator(hass, coordinator)
    if not device_id:
        return
    coordinator.async_bind_device(device_id)
    await async_create_device_automations(hass, entry, device_id, replace=True)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Split the original combined automation flag into azan / iqama / Jumua."""
    if entry.version == 1:
        data = dict(entry.data)
        create = bool(data.pop(CONF_CREATE_AUTOMATIONS, True))
        data.setdefault(CONF_CREATE_AZAN, create)
        data.setdefault(CONF_CREATE_IQAMA, False)
        data.setdefault(CONF_CREATE_JUMUA, create)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a mosque config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: AwqatCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_shutdown()
        remaining = [item for item in hass.data[DOMAIN].values() if isinstance(item, AwqatCoordinator)]
        if not remaining:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove notification automations created for this mosque."""
    await async_remove_device_automations(hass, entry)
