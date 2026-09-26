"""Config flow for Awqat prayer times."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api import AwqatApi, AwqatApiError
from .const import (
    CONF_AZAN_PLAYER,
    CONF_CREATE_AZAN,
    CONF_CREATE_IQAMA,
    CONF_CREATE_JUMUA,
    CONF_MOSQUE,
    CONF_MOSQUE_ALIAS,
    CONF_MOSQUE_CODE,
    CONF_MOSQUE_LABEL,
    CONF_NEARBY,
    CONF_PAUSE_PLAYERS,
    CONF_QUERY,
    DOMAIN,
    NEARBY_DISTANCE_KM,
)

STEP_USER = vol.Schema(
    {
        vol.Optional(CONF_QUERY, default=""): str,
        vol.Optional(CONF_NEARBY, default=False): bool,
    }
)

MEDIA_PLAYER_SELECTOR = EntitySelector(EntitySelectorConfig(domain="media_player", multiple=False))
PAUSE_PLAYERS_SELECTOR = EntitySelector(EntitySelectorConfig(domain="media_player", multiple=True))


async def _search(hass: HomeAssistant, query: str, nearby: bool) -> list[dict[str, Any]]:
    api = AwqatApi(async_get_clientsession(hass))
    mosques: list[dict[str, Any]] = []
    if nearby:
        mosques.extend(
            await api.nearby_mosques(
                hass.config.latitude,
                hass.config.longitude,
                NEARBY_DISTANCE_KM,
            )
        )
    if query.strip():
        found = await api.search_mosques(query.strip())
        seen = {item.get("code") for item in mosques}
        for item in found:
            if item.get("code") not in seen:
                mosques.append(item)
    return mosques


class AwqatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Search awqat.fr mosques and store the selected one."""

    VERSION = 2

    def __init__(self) -> None:
        self._mosques: list[dict[str, Any]] = []
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            query = (user_input.get(CONF_QUERY) or "").strip()
            nearby = bool(user_input.get(CONF_NEARBY))
            if not query and not nearby:
                errors["base"] = "search_required"
            else:
                try:
                    self._mosques = await _search(self.hass, query, nearby)
                except AwqatApiError:
                    errors["base"] = "cannot_connect"
                else:
                    if not self._mosques:
                        errors["base"] = "no_mosques"
                    else:
                        return await self.async_step_mosque()

        return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

    async def async_step_mosque(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        options = [
            SelectOptionDict(
                value=item["code"],
                label=_mosque_label(item),
            )
            for item in self._mosques
            if item.get("code")
        ]
        if user_input is not None:
            code = user_input[CONF_MOSQUE]
            selected = next((item for item in self._mosques if item.get("code") == code), None)
            if not selected:
                errors["base"] = "no_mosques"
            else:
                await self.async_set_unique_id(code)
                self._abort_if_unique_id_configured()
                self._data = {
                    CONF_MOSQUE_CODE: code,
                    CONF_MOSQUE_LABEL: selected.get("label") or code,
                    CONF_MOSQUE_ALIAS: selected.get("alias") or code,
                }
                return await self.async_step_azan()

        schema = vol.Schema(
            {
                vol.Required(CONF_MOSQUE): SelectSelector(
                    SelectSelectorConfig(options=options, sort=True)
                ),
            }
        )
        return self.async_show_form(step_id="mosque", data_schema=schema, errors=errors)

    async def async_step_azan(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_CREATE_AZAN] = bool(user_input.get(CONF_CREATE_AZAN, True))
            return await self.async_step_iqama()
        return self.async_show_form(
            step_id="azan",
            data_schema=vol.Schema({vol.Required(CONF_CREATE_AZAN, default=True): bool}),
        )

    async def async_step_iqama(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_CREATE_IQAMA] = bool(user_input.get(CONF_CREATE_IQAMA, False))
            return await self.async_step_jumua()
        return self.async_show_form(
            step_id="iqama",
            data_schema=vol.Schema({vol.Required(CONF_CREATE_IQAMA, default=False): bool}),
        )

    async def async_step_jumua(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_CREATE_JUMUA] = bool(user_input.get(CONF_CREATE_JUMUA, True))
            if self._needs_media():
                return await self.async_step_media()
            return self.async_create_entry(title=self._data[CONF_MOSQUE_LABEL], data=self._data)
        return self.async_show_form(
            step_id="jumua",
            data_schema=vol.Schema({vol.Required(CONF_CREATE_JUMUA, default=True): bool}),
        )

    async def async_step_media(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_AZAN_PLAYER] = user_input.get(CONF_AZAN_PLAYER)
            self._data[CONF_PAUSE_PLAYERS] = user_input.get(CONF_PAUSE_PLAYERS) or []
            return self.async_create_entry(title=self._data[CONF_MOSQUE_LABEL], data=self._data)
        return self.async_show_form(
            step_id="media",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_AZAN_PLAYER): MEDIA_PLAYER_SELECTOR,
                    vol.Optional(CONF_PAUSE_PLAYERS): PAUSE_PLAYERS_SELECTOR,
                }
            ),
        )

    def _needs_media(self) -> bool:
        return bool(
            self._data.get(CONF_CREATE_AZAN)
            or self._data.get(CONF_CREATE_IQAMA)
            or self._data.get(CONF_CREATE_JUMUA)
        )

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: config_entries.ConfigEntry):
        return AwqatOptionsFlow()


class AwqatOptionsFlow(config_entries.OptionsFlow):
    """Change which automations to keep and which media to control."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        data = {**self.config_entry.data, **self.config_entry.options}
        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_CREATE_AZAN, default=bool(data.get(CONF_CREATE_AZAN, True))): bool,
            vol.Required(CONF_CREATE_IQAMA, default=bool(data.get(CONF_CREATE_IQAMA, False))): bool,
            vol.Required(CONF_CREATE_JUMUA, default=bool(data.get(CONF_CREATE_JUMUA, True))): bool,
        }
        player = data.get(CONF_AZAN_PLAYER)
        if player:
            schema_dict[vol.Optional(CONF_AZAN_PLAYER, default=player)] = MEDIA_PLAYER_SELECTOR
        else:
            schema_dict[vol.Optional(CONF_AZAN_PLAYER)] = MEDIA_PLAYER_SELECTOR
        paused = data.get(CONF_PAUSE_PLAYERS) or []
        if paused:
            schema_dict[vol.Optional(CONF_PAUSE_PLAYERS, default=paused)] = PAUSE_PLAYERS_SELECTOR
        else:
            schema_dict[vol.Optional(CONF_PAUSE_PLAYERS)] = PAUSE_PLAYERS_SELECTOR
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict))


def _mosque_label(item: dict[str, Any]) -> str:
    label = item.get("label") or item.get("code") or ""
    distance = item.get("distance")
    if isinstance(distance, (int, float)):
        return f"{label} ({distance:.1f} km)"
    return str(label)
