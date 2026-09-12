"""Awqat HTTP client (widget.fawzone.net, used by awqat.fr)."""

from __future__ import annotations

from typing import Any

from .const import API_BASE, CALENDAR_SINCE, WIDGET_TYPE

try:
    from aiohttp import ClientError, ClientSession, ClientTimeout
except ImportError:  # pragma: no cover - Home Assistant always has aiohttp
    ClientError = Exception  # type: ignore[misc, assignment]
    ClientSession = object  # type: ignore[misc, assignment]
    ClientTimeout = None  # type: ignore[misc, assignment]


class AwqatApiError(Exception):
    """Raised when the Awqat API cannot be reached or returns an error."""


class AwqatApi:
    """Async client for mosque search, config, and calendars."""

    def __init__(self, session: ClientSession, base_url: str = API_BASE) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url, params=params, timeout=_timeout()) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise AwqatApiError(f"HTTP {response.status} for {path}")
        except AwqatApiError:
            raise
        except Exception as err:  # noqa: BLE001 - wrap network stack for HA
            raise AwqatApiError(f"Request failed for {path}: {err}") from err
        return _unwrap(payload)

    async def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.post(url, json=body, timeout=_timeout()) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise AwqatApiError(f"HTTP {response.status} for {path}")
        except AwqatApiError:
            raise
        except Exception as err:  # noqa: BLE001
            raise AwqatApiError(f"Request failed for {path}: {err}") from err
        return _unwrap(payload)

    async def search_mosques(self, query: str) -> list[dict[str, Any]]:
        payload = await self._get_json(
            "/widget/findWidgets",
            {"label": query.strip(), "type": WIDGET_TYPE},
        )
        return list(payload.get("result") or [])

    async def nearby_mosques(self, latitude: float, longitude: float, distance_km: float) -> list[dict[str, Any]]:
        payload = await self._get_json(
            "/widget/findWidgetsWithin",
            {
                "lat": latitude,
                "lng": longitude,
                "distance": distance_km,
                "type": WIDGET_TYPE,
            },
        )
        return list(payload.get("result") or [])

    async def fetch_config(self, mosque_code: str, alias: str | None = None) -> dict[str, Any]:
        payload = await self._post_json(
            "/widget/findCfg",
            {"code": mosque_code, "alias": alias or mosque_code},
        )
        result = payload.get("result")
        if not result or not result.get("cfg"):
            raise AwqatApiError(f"No timetable config for mosque {mosque_code}")
        cfg = result["cfg"]
        if isinstance(cfg, str):
            import json

            cfg = json.loads(cfg)
            result = {**result, "cfg": cfg}
        return result

    async def fetch_calendar(self, mosque_code: str) -> dict[str, list[str]] | None:
        """Return the mosque calendar keyed by DD/MM, or None if none is published."""
        path = f"/awqatCal/byCode/{mosque_code}/{CALENDAR_SINCE}"
        try:
            payload = await self._get_json(path)
        except AwqatApiError:
            return None
        result = payload.get("result")
        if not result or not result.get("value"):
            return None
        value = result["value"]
        if isinstance(value, str):
            import json

            value = json.loads(value)
        awqat = value.get("awqat") if isinstance(value, dict) else None
        if not isinstance(awqat, dict):
            return None
        return {str(key): list(times) for key, times in awqat.items()}


def _timeout() -> Any:
    if ClientTimeout is None:
        return None
    return ClientTimeout(total=30)


def _unwrap(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AwqatApiError("Unexpected Awqat response")
    messages = payload.get("messages") or []
    errors = [item.get("text") for item in messages if item.get("severity") == "ERROR"]
    if errors and "result" not in payload:
        raise AwqatApiError(errors[0])
    if payload.get("exceptionMessage") and payload.get("result") is None and not payload.get("@id"):
        raise AwqatApiError(str(payload["exceptionMessage"]))
    return payload
