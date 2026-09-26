"""Awqat mosque timetable calculator.

Reproduces the widget at https://awqat.fr (PrayTimes + mosque calendar,
offsets, periods, and fixed times).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .const import DEFAULT_ATHAN_URL, DISPLAY_NAMES, NEXT_PRAYER_CANDIDATES, PRAYERS
from .praytimes import PrayTimes

CALENDAR_PRAYERS = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")


@dataclass(frozen=True)
class PrayerTime:
    """One prayer (or sunrise) on a given day."""

    name: str
    adhan: datetime
    iqama: datetime | None
    source: str

    @property
    def display_name(self) -> str:
        return DISPLAY_NAMES.get(self.name, self.name.title())


@dataclass
class DayTimes:
    """Prayer times for a civil date."""

    day: date
    prayers: dict[str, PrayerTime] = field(default_factory=dict)

    def get(self, name: str) -> PrayerTime | None:
        return self.prayers.get(name)


@dataclass
class MosqueTimes:
    """Computed times plus mosque metadata used by Home Assistant sensors."""

    mosque_code: str
    mosque_label: str
    mosque_alias: str | None
    address: str | None
    method: str
    use_calendar: bool
    cfg_updated_on: str | None
    today: DayTimes
    tomorrow: DayTimes
    next_prayer: str
    next_prayer_time: datetime
    timezone: str
    fetch_status: str = "ok"
    last_error: str | None = None
    last_success: datetime | None = None
    next_refresh: datetime | None = None
    attempt: int = 1
    athan_url: str | None = None


def extract_athan_url(cfg: dict[str, Any]) -> str:
    """Prefer the mosque's published adhan audio, else a public fallback."""
    for name in ("fajr", "dhuhr", "maghrib", "isha", "asr"):
        src = (_item_settings(cfg).get(name) or {}).get("athanSoundSrc")
        if isinstance(src, str) and src.startswith("http"):
            return src
    return DEFAULT_ATHAN_URL


def duration_minutes(value: Any) -> float:
    """Convert Awqat duration objects to minutes."""
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value) if value.replace(".", "", 1).isdigit() else 0.0
    hours = value.get("h") or 0
    minutes = value.get("m") or 0
    seconds = value.get("s") or 0
    return hours * 60 + minutes + seconds / 60.0


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def combine_local(day: date, clock: str, tz: ZoneInfo) -> datetime:
    parsed = parse_hhmm(clock)
    return datetime.combine(day, parsed, tzinfo=tz)


def is_dst(moment: datetime) -> bool:
    dst = moment.dst()
    return bool(dst and dst.total_seconds() != 0)


def utc_offset_hours(moment: datetime) -> float:
    offset = moment.utcoffset()
    if offset is None:
        return 0.0
    return offset.total_seconds() / 3600.0


def next_friday(day: date) -> date:
    # Friday is weekday 4.
    delta = (4 - day.weekday()) % 7
    if delta == 0:
        return day
    return day + timedelta(days=delta)


def calendar_key(day: date) -> str:
    return f"{day.day:02d}/{day.month:02d}"


def _truthy(value: Any) -> bool:
    return bool(value) and value != 0


def _item_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    time_setting = cfg.get("timeSetting") or {}
    return time_setting.get("timeItemSettings") or {}


def _geo(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("geoPlace") or {}


def apply_fixed_time(
    current: str,
    setting: dict[str, Any],
    day: date,
    tz: ZoneInfo,
) -> tuple[str, str]:
    """Apply Awqat fixedTimes overrides. Returns (hh:mm, source)."""
    fixed_times = setting.get("fixedTimes") or []
    if not fixed_times:
        return current, "calculated"
    noon = datetime.combine(day, time(12, 0), tzinfo=tz)
    dst = is_dst(noon)
    current_dt = combine_local(day, current, tz)
    for item in fixed_times:
        if not item or not item.get("time"):
            continue
        kind = item.get("type")
        clock = f"{item['time'][0:2]}:{item['time'][2:4]}"
        period = item.get("period")
        if kind in ("dst_yes", "dst_no", "interval", None, ""):
            if kind == "dst_yes" and not dst:
                continue
            if kind == "dst_no" and dst:
                continue
            if (not kind or kind == "interval") and item.get("start") and item.get("end"):
                if not _in_range(day, item["start"], item["end"]):
                    continue
            return clock, "fixed"
        if kind in ("min", "max"):
            if period and not (
                (period == "dst_no" and not dst) or (period == "dst_yes" and dst)
            ):
                continue
            bound = combine_local(day, clock, tz)
            if kind == "min" and bound > current_dt:
                return clock, "fixed"
            if kind == "max" and bound < current_dt:
                return clock, "fixed"
    return current, "calculated"


def _in_range(day: date, start: str, end: str) -> bool:
    """Awqat stores ranges as DDMM and compares as MMDD, wrapping the year."""
    start_key = start[2:4] + start[0:2]
    end_key = end[2:4] + end[0:2]
    current = f"{day.month:02d}{day.day:02d}"
    if start_key <= end_key:
        return start_key <= current <= end_key
    return current >= start_key or current <= end_key


def _praytimes_for_cfg(cfg: dict[str, Any]) -> PrayTimes:
    time_setting = cfg.get("timeSetting") or {}
    method = time_setting.get("method") or "UOIF"
    calculator = PrayTimes("MWL")
    calculator.set_method(method)
    adjust: dict[str, Any] = {}
    tune: dict[str, float] = {}
    for name, setting in _item_settings(cfg).items():
        if not isinstance(setting, dict):
            continue
        if setting.get("angle") and method == "CUSTOM":
            adjust[name] = setting["angle"]
        if _truthy(setting.get("period")):
            adjust[name] = f"{setting['period']}min"
        if _truthy(setting.get("offset")):
            tune[name] = float(setting["offset"])
    if adjust:
        calculator.adjust(adjust)
    if tune:
        calculator.tune(tune)
    return calculator


def _offset_clock(clock: str, minutes: float, day: date, tz: ZoneInfo) -> str:
    moment = combine_local(day, clock, tz) + timedelta(minutes=minutes)
    return moment.strftime("%H:%M")


def compute_day_clocks(
    cfg: dict[str, Any],
    day: date,
    tz: ZoneInfo,
    calendar: dict[str, list[str]] | None = None,
) -> dict[str, tuple[str, str]]:
    """Return {prayer: (HH:MM, source)} for one civil date."""
    geo = _geo(cfg)
    lat = float(geo.get("lat") or 0)
    lng = float(geo.get("long") or geo.get("lng") or 0)
    noon = datetime.combine(day, time(12, 0), tzinfo=tz)
    calculator = _praytimes_for_cfg(cfg)
    raw = calculator.get_times((day.year, day.month, day.day), (lat, lng), utc_offset_hours(noon), 0)

    clocks: dict[str, str] = {
        "fajr": raw["fajr"],
        "sunrise": raw["sunrise"],
        "dhuhr": raw["dhuhr"],
        "asr": raw["asr"],
        "maghrib": raw["maghrib"],
        "isha": raw["isha"],
    }
    sources = {name: "calculated" for name in clocks}

    time_setting = cfg.get("timeSetting") or {}
    use_cal = bool(time_setting.get("useCal"))
    if use_cal and calendar:
        row = calendar.get(calendar_key(day))
        if row and len(row) >= 6:
            for index, name in enumerate(CALENDAR_PRAYERS):
                clocks[name] = row[index]
                sources[name] = "calendar"
            isha_setting = _item_settings(cfg).get("isha") or {}
            if _truthy(isha_setting.get("period")):
                clocks["isha"] = _offset_clock(clocks["maghrib"], float(isha_setting["period"]), day, tz)
                sources["isha"] = "calendar"
            for name in list(clocks):
                setting = _item_settings(cfg).get(name) or {}
                if _truthy(setting.get("offset")):
                    clocks[name] = _offset_clock(clocks[name], float(setting["offset"]), day, tz)

    jumua_setting = _item_settings(cfg).get("jumua") or {}
    jumua_clock = clocks["dhuhr"]
    if _truthy(jumua_setting.get("offset")):
        jumua_clock = _offset_clock(jumua_clock, float(jumua_setting["offset"]), day, tz)
    clocks["jumua"] = jumua_clock
    sources["jumua"] = sources["dhuhr"]

    result: dict[str, tuple[str, str]] = {}
    for name in PRAYERS:
        setting = _item_settings(cfg).get(name) or {}
        clock = clocks[name]
        source = sources[name]
        if name != "sunrise":
            clock, fixed_source = apply_fixed_time(clock, setting, day, tz)
            if fixed_source == "fixed":
                source = "fixed"
        result[name] = (clock, source)
    return result


def _iqama_for(name: str, adhan: datetime, setting: dict[str, Any]) -> datetime | None:
    if name == "sunrise":
        return None
    minutes = duration_minutes(setting.get("durationBeforeIqama"))
    if minutes <= 0:
        return None
    return adhan + timedelta(minutes=minutes)


def build_day(
    cfg: dict[str, Any],
    day: date,
    tz: ZoneInfo,
    calendar: dict[str, list[str]] | None = None,
    jumua_clocks: dict[str, tuple[str, str]] | None = None,
    jumua_day: date | None = None,
) -> DayTimes:
    clocks = compute_day_clocks(cfg, day, tz, calendar)
    if jumua_clocks and day.weekday() != 4:
        clocks["jumua"] = jumua_clocks["jumua"]
    settings = _item_settings(cfg)
    prayers: dict[str, PrayerTime] = {}
    for name in PRAYERS:
        clock, source = clocks[name]
        adhan = combine_local(day, clock, tz)
        if name == "jumua" and jumua_day and day.weekday() != 4:
            adhan = combine_local(jumua_day, clock, tz)
        prayers[name] = PrayerTime(
            name=name,
            adhan=adhan,
            iqama=_iqama_for(name, adhan, settings.get(name) or {}),
            source=source,
        )
    return DayTimes(day=day, prayers=prayers)


def next_prayer_at(today: DayTimes, tomorrow: DayTimes, now: datetime) -> tuple[str, datetime]:
    """Return the next salat after now, skipping sunrise and using Jumua on Friday."""
    is_friday = now.date() == today.day and now.weekday() == 4

    def candidates(day_times: DayTimes, friday: bool) -> list[tuple[str, datetime]]:
        names = list(NEXT_PRAYER_CANDIDATES)
        if friday and day_times.get("jumua"):
            names = ["fajr", "jumua", "asr", "maghrib", "isha"]
        result = []
        for name in names:
            prayer = day_times.get(name)
            if prayer:
                result.append((name, prayer.adhan))
        return result

    for name, moment in candidates(today, is_friday):
        if moment > now:
            return name, moment
    tomorrow_friday = tomorrow.day.weekday() == 4
    name, moment = candidates(tomorrow, tomorrow_friday)[0]
    return name, moment


def compute_mosque_times(
    *,
    cfg: dict[str, Any],
    tz: ZoneInfo,
    now: datetime,
    calendar: dict[str, list[str]] | None = None,
    mosque_code: str | None = None,
    mosque_label: str | None = None,
    mosque_alias: str | None = None,
    cfg_updated_on: str | None = None,
) -> MosqueTimes:
    """Compute today and tomorrow using a mosque config payload."""
    target = cfg.get("targetWidget") or {}
    geo = _geo(cfg)
    time_setting = cfg.get("timeSetting") or {}
    today = now.astimezone(tz).date()
    tomorrow = today + timedelta(days=1)
    friday = next_friday(today)
    friday_clocks = compute_day_clocks(cfg, friday, tz, calendar) if friday != today else None

    today_times = build_day(cfg, today, tz, calendar, friday_clocks, friday)
    tomorrow_friday = next_friday(tomorrow)
    tomorrow_friday_clocks = (
        compute_day_clocks(cfg, tomorrow_friday, tz, calendar) if tomorrow_friday != tomorrow else None
    )
    tomorrow_times = build_day(
        cfg, tomorrow, tz, calendar, tomorrow_friday_clocks, tomorrow_friday
    )

    next_name, next_time = next_prayer_at(today_times, tomorrow_times, now.astimezone(tz))
    return MosqueTimes(
        mosque_code=mosque_code or target.get("code") or "",
        mosque_label=mosque_label or target.get("label") or mosque_code or "",
        mosque_alias=mosque_alias or target.get("alias"),
        address=geo.get("name"),
        method=time_setting.get("method") or "UOIF",
        use_calendar=bool(time_setting.get("useCal")),
        cfg_updated_on=cfg_updated_on,
        today=today_times,
        tomorrow=tomorrow_times,
        next_prayer=next_name,
        next_prayer_time=next_time,
        timezone=str(tz),
        athan_url=extract_athan_url(cfg),
    )
