"""Config flow for Awqat prayer times."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .api import AwqatApi, AwqatApiError
from .const import (
    CONF_CREATE_AUTOMATIONS,
    CONF_MOSQUE,
    CONF_MOSQUE_ALIAS,
    CONF_MOSQUE_CODE,
    CONF_MOSQUE_LABEL,
    CONF_NEARBY,
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

    VERSION = 1

    def __init__(self) -> None:
        self._mosques: list[dict[str, Any]] = []

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
                return self.async_create_entry(
                    title=selected.get("label") or code,
                    data={
                        CONF_MOSQUE_CODE: code,
                        CONF_MOSQUE_LABEL: selected.get("label") or code,
                        CONF_MOSQUE_ALIAS: selected.get("alias") or code,
                        CONF_CREATE_AUTOMATIONS: bool(
                            user_input.get(CONF_CREATE_AUTOMATIONS, True)
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MOSQUE): SelectSelector(
                    SelectSelectorConfig(options=options, sort=True)
                ),
                vol.Optional(CONF_CREATE_AUTOMATIONS, default=True): bool,
            }
        )
        return self.async_show_form(step_id="mosque", data_schema=schema, errors=errors)


def _mosque_label(item: dict[str, Any]) -> str:
    label = item.get("label") or item.get("code") or ""
    distance = item.get("distance")
    if isinstance(distance, (int, float)):
        return f"{label} ({distance:.1f} km)"
    return str(label)
