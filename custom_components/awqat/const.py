"""Constants for the Awqat prayer times integration."""

from __future__ import annotations

from datetime import time, timedelta
from typing import Final

DOMAIN: Final = "awqat"
PLATFORMS: Final = ["sensor"]
EVENT_AWQAT: Final = "awqat_event"

ATTRIBUTION: Final = "Prayer times from Awqat (awqat.fr)"
MANUFACTURER: Final = "Awqat"

API_BASE: Final = "https://widget.fawzone.net"
WIDGET_TYPE: Final = "salat-widget"
CALENDAR_SINCE: Final = "2001-06-30T23:38:13.754Z"

CONF_MOSQUE_CODE: Final = "mosque_code"
CONF_MOSQUE_LABEL: Final = "mosque_label"
CONF_MOSQUE_ALIAS: Final = "mosque_alias"
CONF_QUERY: Final = "query"
CONF_NEARBY: Final = "nearby"
CONF_MOSQUE: Final = "mosque"
CONF_CREATE_AUTOMATIONS: Final = "create_automations"
CONF_CREATE_AZAN: Final = "create_azan"
CONF_CREATE_IQAMA: Final = "create_iqama"
CONF_CREATE_JUMUA: Final = "create_jumua"
CONF_AZAN_PLAYER: Final = "azan_player"
CONF_PAUSE_PLAYERS: Final = "pause_players"
CONF_AUTOMATION_IDS: Final = "automation_ids"

DEFAULT_ATHAN_URL: Final = "https://media.sd.ma/assabile/adhan_3435370/8c052a5edec1.mp3"
LOVELACE_CARD_URL: Final = "/awqat-local/awqat-prayer-card.js"

NEARBY_DISTANCE_KM: Final = 40

# Fetch after Isha, then again after 02:00. Retry a few times on failure.
AFTER_ISHA_DELAY: Final = timedelta(minutes=2)
AFTER_TWO_AM: Final = time(2, 0)
MAX_FETCH_ATTEMPTS: Final = 4
RETRY_DELAYS: Final = (timedelta(seconds=30), timedelta(minutes=1), timedelta(minutes=2))

STATUS_OK: Final = "ok"
STATUS_RETRYING: Final = "retrying"
STATUS_FAILED: Final = "failed"

PRAYERS: Final = ("fajr", "sunrise", "dhuhr", "jumua", "asr", "maghrib", "isha")
SALAT_PRAYERS: Final = ("fajr", "dhuhr", "asr", "maghrib", "isha")
NEXT_PRAYER_CANDIDATES: Final = ("fajr", "dhuhr", "asr", "maghrib", "isha")

DISPLAY_NAMES: Final = {
    "fajr": "Fajr",
    "sunrise": "Sunrise",
    "dhuhr": "Dhuhr",
    "jumua": "Jumua",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
}

ADHAN_TRIGGER_TYPES: Final = ("fajr", "dhuhr", "asr", "maghrib", "isha", "jumua", "sunrise")
IQAMA_TRIGGER_TYPES: Final = ("iqama_fajr", "iqama_dhuhr", "iqama_asr", "iqama_maghrib", "iqama_isha", "iqama_jumua")
TRIGGER_TYPES: Final = ADHAN_TRIGGER_TYPES + IQAMA_TRIGGER_TYPES
DEFAULT_ADHAN_TRIGGERS: Final = ("fajr", "dhuhr", "asr", "maghrib", "isha")
DEFAULT_IQAMA_TRIGGERS: Final = ("iqama_fajr", "iqama_dhuhr", "iqama_asr", "iqama_maghrib", "iqama_isha")
