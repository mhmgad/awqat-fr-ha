"""Lovelace card and dashboard for Awqat prayer times."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
import logging

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
except ImportError:  # pragma: no cover - unit tests without Home Assistant
    ConfigEntry = object  # type: ignore[misc, assignment]
    HomeAssistant = object  # type: ignore[misc, assignment]
    er = None  # type: ignore[assignment]

from .const import CONF_MOSQUE_CODE, DOMAIN, LOVELACE_CARD_URL, PRAYERS

if TYPE_CHECKING:
    from .coordinator import AwqatCoordinator

_LOGGER = logging.getLogger(__name__)

WWW_DIR = Path(__file__).resolve().parent / "www"
CARD_FILENAME = "awqat-prayer-card.js"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve the prayer card and register it as a Lovelace resource."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("frontend_setup"):
        try:
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [StaticPathConfig("/awqat-local", str(WWW_DIR), False)]
            )
        except (ImportError, AttributeError, ValueError, RuntimeError) as err:
            try:
                hass.http.register_static_path("/awqat-local", str(WWW_DIR), False)
            except Exception:  # noqa: BLE001 - older HA fallback
                _LOGGER.debug("Could not register Awqat static path: %s", err)
        domain_data["frontend_setup"] = True
    await _async_register_lovelace_resource(hass)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    try:
        resources = hass.data["lovelace"].resources
        await resources.async_load()
        for item in resources.async_items():
            if str(item.get("url", "")).startswith("/awqat-local/"):
                return
        await resources.async_create_item({"res_type": "module", "url": LOVELACE_CARD_URL})
    except Exception as err:  # noqa: BLE001 - Lovelace YAML mode has no storage API
        _LOGGER.debug("Could not auto-register Awqat Lovelace card: %s", err)


def prayer_entity_map(hass: HomeAssistant, mosque_code: str) -> dict[str, str]:
    """Map prayer keys to current sensor entity ids."""
    if er is None:
        return {}
    registry = er.async_get(hass)
    mapping: dict[str, str] = {}
    for key in (*PRAYERS, "next_prayer", "next_prayer_name"):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{mosque_code}_{key}")
        if entity_id:
            mapping[key] = entity_id
    return mapping


def build_dashboard_config(mosque_label: str, entities: dict[str, str]) -> dict[str, Any]:
    """Return a Lovelace dashboard config for this mosque."""
    return {
        "title": mosque_label,
        "views": [
            {
                "title": "Prayer times",
                "path": "prayers",
                "icon": "mdi:mosque",
                "cards": [
                    {
                        "type": "custom:awqat-prayer-card",
                        "title": mosque_label,
                        "entities": entities,
                    }
                ],
            }
        ],
    }


async def async_create_prayer_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: AwqatCoordinator,
) -> None:
    """Add a sidebar dashboard with the prayer card when Lovelace allows it."""
    mosque_code = entry.data[CONF_MOSQUE_CODE]
    entities = prayer_entity_map(hass, mosque_code)
    if "fajr" not in entities or "next_prayer" not in entities:
        return
    config = build_dashboard_config(coordinator.mosque_label, entities)
    url_path = f"awqat-{mosque_code}".lower().replace("_", "-")[:40]
    try:
        collection = hass.data["lovelace"].dashboards
        await collection.async_load()
        existing = {
            item.get("url_path") or item.get("id")
            for item in collection.async_items()
        }
        if url_path not in existing:
            await collection.async_create_item(
                {
                    "url_path": url_path,
                    "title": coordinator.mosque_label,
                    "icon": "mdi:mosque",
                    "require_admin": False,
                    "show_in_sidebar": True,
                }
            )
        dashboard = collection.dashboards.get(url_path) if hasattr(collection, "dashboards") else None
        if dashboard is not None and hasattr(dashboard, "async_save"):
            await dashboard.async_save(config)
            return
        # Some HA versions expose dashboards as a dict on hass.data["lovelace"]
        dashboards = getattr(hass.data["lovelace"], "dashboards", None)
        if isinstance(dashboards, dict) and url_path in dashboards:
            board = dashboards[url_path]
            if hasattr(board, "async_save"):
                await board.async_save(config)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not create Awqat dashboard (add the card manually): %s", err)
