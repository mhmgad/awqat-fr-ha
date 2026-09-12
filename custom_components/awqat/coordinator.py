"""Data update coordinator for Awqat prayer times."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AwqatApi
from .calculator import MosqueTimes, compute_mosque_times
from .const import (
    CONF_MOSQUE_ALIAS,
    CONF_MOSQUE_CODE,
    CONF_MOSQUE_LABEL,
    EVENT_AWQAT,
    MAX_FETCH_ATTEMPTS,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_RETRYING,
)
from .prayer_events import ScheduledPrayerEvent, iter_upcoming_prayer_events
from .schedule import next_scheduled_refresh, retry_delay

_LOGGER = logging.getLogger(__name__)


class AwqatCoordinator(DataUpdateCoordinator[MosqueTimes]):
    """Fetch mosque config from Awqat on a prayer-day schedule."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_interval=None,
        )
        self.entry = entry
        self.api = AwqatApi(async_get_clientsession(hass))
        self._failures = 0
        self._unsub: Callable[[], None] | None = None
        self._prayer_unsubs: list[Callable[[], None]] = []
        self._next_when: datetime | None = None
        self.device_id: str | None = None

    @property
    def mosque_code(self) -> str:
        return self.entry.data[CONF_MOSQUE_CODE]

    @property
    def mosque_label(self) -> str:
        return self.entry.data.get(CONF_MOSQUE_LABEL) or self.mosque_code

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.hass.config.time_zone or "UTC")

    async def _async_update_data(self) -> MosqueTimes:
        try:
            data = await self._fetch_and_compute()
        except Exception as err:
            return self._handle_failure(err)
        self._failures = 0
        data.fetch_status = STATUS_OK
        data.last_error = None
        data.last_success = dt_util.now(self.timezone)
        data.attempt = 1
        self._schedule_regular(data)
        self._schedule_prayer_events(data)
        return data

    async def _fetch_and_compute(self) -> MosqueTimes:
        code = self.mosque_code
        alias = self.entry.data.get(CONF_MOSQUE_ALIAS)
        result = await self.api.fetch_config(code, alias)
        cfg = result["cfg"]
        calendar = None
        if (cfg.get("timeSetting") or {}).get("useCal"):
            calendar = await self.api.fetch_calendar(code)
        return compute_mosque_times(
            cfg=cfg,
            tz=self.timezone,
            now=dt_util.now(self.timezone),
            calendar=calendar,
            mosque_code=code,
            mosque_label=self.mosque_label,
            mosque_alias=alias,
            cfg_updated_on=result.get("updatedOnCfg"),
        )

    def _handle_failure(self, err: Exception) -> MosqueTimes:
        self._failures += 1
        message = str(err)
        _LOGGER.warning(
            "Awqat fetch failed for %s (attempt %s/%s): %s",
            self.mosque_label,
            self._failures,
            MAX_FETCH_ATTEMPTS,
            message,
        )
        if self._failures < MAX_FETCH_ATTEMPTS:
            delay = retry_delay(self._failures - 1)
            self._schedule_at(dt_util.now(self.timezone) + delay, retrying=True)
            if self.data:
                self.data.fetch_status = STATUS_RETRYING
                self.data.last_error = message
                self.data.attempt = self._failures + 1
                self.data.next_refresh = self._next_when
                return self.data
            raise UpdateFailed(message) from err

        self._failures = 0
        _LOGGER.error(
            "Awqat fetch failed for %s after %s attempts",
            self.mosque_label,
            MAX_FETCH_ATTEMPTS,
        )
        if self.data:
            self.data.fetch_status = STATUS_FAILED
            self.data.last_error = message
            self.data.attempt = MAX_FETCH_ATTEMPTS
            self._schedule_regular(self.data)
            return self.data
        raise UpdateFailed(f"Could not fetch Awqat prayer times: {message}") from err

    def _schedule_regular(self, data: MosqueTimes | None) -> None:
        now = dt_util.now(self.timezone)
        isha = None
        if data and data.today.get("isha"):
            isha = data.today.get("isha").adhan  # type: ignore[union-attr]
            if isha <= now and data.tomorrow.get("isha"):
                isha = data.tomorrow.get("isha").adhan  # type: ignore[union-attr]
        when = next_scheduled_refresh(now, isha)
        if data:
            data.next_refresh = when
        self._schedule_at(when, retrying=False)

    def _schedule_at(self, when: datetime, retrying: bool) -> None:
        self._cancel_fetch_schedule()
        self._next_when = when
        kind = "retry" if retrying else "scheduled"
        _LOGGER.debug("Next Awqat %s fetch for %s at %s", kind, self.mosque_label, when)

        @callback
        def _fire(_now: datetime) -> None:
            self._unsub = None
            self.hass.async_create_task(self.async_request_refresh())

        self._unsub = async_track_point_in_time(self.hass, _fire, when)

    def async_bind_device(self, device_id: str) -> None:
        """Attach the registry device id so prayer events can target automations."""
        self.device_id = device_id
        if self.data:
            self._schedule_prayer_events(self.data)

    def _schedule_prayer_events(self, data: MosqueTimes) -> None:
        self._cancel_prayer_events()
        if not self.device_id:
            return
        now = dt_util.now(self.timezone)
        for event in iter_upcoming_prayer_events(data, now):
            self._prayer_unsubs.append(
                async_track_point_in_time(self.hass, self._prayer_callback(event), event.when)
            )

    def _prayer_callback(self, event: ScheduledPrayerEvent) -> Callable[[datetime], None]:
        @callback
        def _fire(_now: datetime) -> None:
            if not self.device_id:
                return
            self.hass.bus.async_fire(
                EVENT_AWQAT,
                {
                    "device_id": self.device_id,
                    "type": event.trigger_type,
                    "prayer": event.prayer,
                    "kind": event.kind,
                    "prayer_name": event.prayer_name,
                    "kind_name": event.kind_name,
                    "mosque": self.mosque_label,
                    "mosque_code": self.mosque_code,
                    "time": event.when.strftime("%H:%M"),
                },
            )

        return _fire

    def _cancel_prayer_events(self) -> None:
        for unsub in self._prayer_unsubs:
            unsub()
        self._prayer_unsubs = []

    def _cancel_fetch_schedule(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _cancel_schedule(self) -> None:
        self._cancel_fetch_schedule()
        self._cancel_prayer_events()

    @callback
    def async_shutdown(self) -> None:
        self._cancel_schedule()
