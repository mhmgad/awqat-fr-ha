"""Tests for the Awqat HTTP client helpers."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from awqat.api import AwqatApi, AwqatApiError, _unwrap  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class UnwrapTests(unittest.TestCase):
    def test_error_without_result(self) -> None:
        with self.assertRaises(AwqatApiError):
            _unwrap(
                {
                    "messages": [{"text": "Required request parameter 'type'", "severity": "ERROR"}],
                    "exceptionMessage": "missing type",
                }
            )

    def test_search_payload(self) -> None:
        payload = json.loads((FIXTURES / "search-lille.json").read_text())
        data = _unwrap(payload)
        self.assertGreaterEqual(len(data["result"]), 1)
        self.assertEqual(data["result"][0]["code"], "badr-lille")


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_mosques(self) -> None:
        payload = json.loads((FIXTURES / "search-lille.json").read_text())
        session = MagicMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value=payload)
        session.get.return_value.__aenter__.return_value = response
        api = AwqatApi(session)
        mosques = await api.search_mosques("lille")
        self.assertEqual(mosques[0]["label"], "Mosquée Badr, Lille")

    async def test_fetch_config_parses_string_cfg(self) -> None:
        session = MagicMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(
            return_value={"result": {"code": "badr-lille", "cfg": json.dumps({"timeSetting": {"method": "UOIF"}})}}
        )
        session.post.return_value.__aenter__.return_value = response
        api = AwqatApi(session)
        result = await api.fetch_config("badr-lille")
        self.assertEqual(result["cfg"]["timeSetting"]["method"], "UOIF")

    async def test_http_error(self) -> None:
        session = MagicMock()
        response = AsyncMock()
        response.status = 500
        response.json = AsyncMock(return_value={"error": "nope"})
        session.get.return_value.__aenter__.return_value = response
        api = AwqatApi(session)
        with self.assertRaises(AwqatApiError):
            await api.search_mosques("paris")


if __name__ == "__main__":
    unittest.main()
