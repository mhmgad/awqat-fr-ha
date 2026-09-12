"""Awqat prayer time sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .calculator import PrayerTime
from .const import ATTRIBUTION, DISPLAY_NAMES, DOMAIN, MANUFACTURER, PRAYERS
from .coordinator import AwqatCoordinator

PRAYER_ICONS = {
    "fajr": "mdi:weather-sunset-up",
    "sunrise": "mdi:weather-sunny",
    "dhuhr": "mdi:weather-sunny",
    "jumua": "mdi:account-group",
    "asr": "mdi:weather-sunset",
    "maghrib": "mdi:weather-sunset-down",
    "isha": "mdi:weather-night",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AwqatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for name in PRAYERS:
        entities.append(AwqatPrayerSensor(coordinator, name, iqama=False))
        if name != "sunrise":
            entities.append(AwqatPrayerSensor(coordinator, name, iqama=True))
    entities.extend(
        [
            AwqatNextPrayerSensor(coordinator),
            AwqatNextPrayerNameSensor(coordinator),
            AwqatStatusSensor(coordinator),
            AwqatLastSuccessSensor(coordinator),
            AwqatNextRefreshSensor(coordinator),
        ]
    )
    async_add_entities(entities)


class AwqatEntity(CoordinatorEntity[AwqatCoordinator], SensorEntity):
    """Base Awqat entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: AwqatCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.mosque_code}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mosque_code)},
            name=coordinator.mosque_label,
            manufacturer=MANUFACTURER,
            model="Mosque timetable",
            configuration_url="https://awqat.fr/",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "mosque": data.mosque_label,
            "mosque_code": data.mosque_code,
            "method": data.method,
        }


class AwqatPrayerSensor(AwqatEntity):
    """Athan or iqama time for one prayer."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: AwqatCoordinator, prayer: str, iqama: bool) -> None:
        key = f"iqama_{prayer}" if iqama else prayer
        super().__init__(coordinator, key)
        self._prayer = prayer
        self._iqama = iqama
        if iqama:
            self._attr_translation_key = f"iqama_{prayer}"
            self._attr_name = f"Iqama {DISPLAY_NAMES[prayer]}"
            self._attr_icon = "mdi:clock-outline"
        else:
            self._attr_translation_key = prayer
            self._attr_name = DISPLAY_NAMES[prayer]
            self._attr_icon = PRAYER_ICONS.get(prayer, "mdi:mosque")

    def _prayer_time(self) -> PrayerTime | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.today.get(self._prayer)

    @property
    def native_value(self) -> datetime | None:
        prayer = self._prayer_time()
        if not prayer:
            return None
        return prayer.iqama if self._iqama else prayer.adhan

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        prayer = self._prayer_time()
        if prayer:
            attrs["source"] = prayer.source
            if prayer.iqama:
                attrs["iqama"] = prayer.iqama.isoformat()
            attrs["adhan"] = prayer.adhan.isoformat()
        return attrs


class AwqatNextPrayerSensor(AwqatEntity):
    """Timestamp of the next salat."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_prayer"
    _attr_name = "Next prayer"
    _attr_icon = "mdi:mosque-outline"

    def __init__(self, coordinator: AwqatCoordinator) -> None:
        super().__init__(coordinator, "next_prayer")

    @property
    def native_value(self) -> datetime | None:
        data = self.coordinator.data
        return data.next_prayer_time if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        data = self.coordinator.data
        if data:
            attrs["prayer"] = data.next_prayer
            attrs["prayer_name"] = DISPLAY_NAMES.get(data.next_prayer, data.next_prayer)
        return attrs


class AwqatNextPrayerNameSensor(AwqatEntity):
    """Name of the next salat."""

    _attr_translation_key = "next_prayer_name"
    _attr_name = "Next prayer name"
    _attr_icon = "mdi:form-textbox"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(DISPLAY_NAMES.values())

    def __init__(self, coordinator: AwqatCoordinator) -> None:
        super().__init__(coordinator, "next_prayer_name")

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data:
            return None
        return DISPLAY_NAMES.get(data.next_prayer, data.next_prayer)


class AwqatStatusSensor(AwqatEntity):
    """Whether the last Awqat pull succeeded."""

    _attr_translation_key = "fetch_status"
    _attr_name = "Fetch status"
    _attr_icon = "mdi:cloud-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "retrying", "failed"]

    def __init__(self, coordinator: AwqatCoordinator) -> None:
        super().__init__(coordinator, "fetch_status")

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        return data.fetch_status if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        data = self.coordinator.data
        if data:
            attrs["last_error"] = data.last_error
            attrs["attempt"] = data.attempt
            attrs["use_calendar"] = data.use_calendar
            attrs["address"] = data.address
        return attrs


class AwqatLastSuccessSensor(AwqatEntity):
    """When the timetable was last pulled successfully."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_success"
    _attr_name = "Last successful fetch"
    _attr_icon = "mdi:check-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AwqatCoordinator) -> None:
        super().__init__(coordinator, "last_success")

    @property
    def native_value(self) -> datetime | None:
        data = self.coordinator.data
        return data.last_success if data else None


class AwqatNextRefreshSensor(AwqatEntity):
    """When the next timetable pull is scheduled."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_refresh"
    _attr_name = "Next fetch"
    _attr_icon = "mdi:timer-refresh-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AwqatCoordinator) -> None:
        super().__init__(coordinator, "next_refresh")

    @property
    def native_value(self) -> datetime | None:
        data = self.coordinator.data
        return data.next_refresh if data else None
