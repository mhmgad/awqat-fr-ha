"""Prayer Times Calculator (ver 2.3), adapted for Awqat / Home Assistant.

Copyright (C) 2007-2011 PrayTimes.org
Python Code: Saleem Shafi, Hamid Zarrabi-Zadeh
Original JS Code: Hamid Zarrabi-Zadeh

License: GNU LGPL v3.0

Permission is granted to use this code, with or without modification,
provided that credit is given to the original work with a link back
to PrayTimes.org.
"""

from __future__ import annotations

import math
import re
from typing import Any

TimeDict = dict[str, Any]


class PrayTimes:
    """Compute Islamic prayer times for a date and coordinates."""

    time_names = {
        "imsak": "Imsak",
        "fajr": "Fajr",
        "sunrise": "Sunrise",
        "dhuhr": "Dhuhr",
        "asr": "Asr",
        "sunset": "Sunset",
        "maghrib": "Maghrib",
        "isha": "Isha",
        "midnight": "Midnight",
    }

    methods = {
        "MWL": {
            "name": "Muslim World League",
            "params": {"fajr": 18, "isha": 17},
        },
        "ISNA": {
            "name": "Islamic Society of North America (ISNA)",
            "params": {"fajr": 15, "isha": 15},
        },
        "Egypt": {
            "name": "Egyptian General Authority of Survey",
            "params": {"fajr": 19.5, "isha": 17.5},
        },
        "Makkah": {
            "name": "Umm Al-Qura University, Makkah",
            "params": {"fajr": 18.5, "isha": "90 min"},
        },
        "Karachi": {
            "name": "University of Islamic Sciences, Karachi",
            "params": {"fajr": 18, "isha": 18},
        },
        "Tehran": {
            "name": "Institute of Geophysics, University of Tehran",
            "params": {"fajr": 17.7, "isha": 14, "maghrib": 4.5, "midnight": "Jafari"},
        },
        "Jafari": {
            "name": "Shia Ithna-Ashari, Leva Institute, Qum",
            "params": {"fajr": 16, "isha": 14, "maghrib": 4, "midnight": "Jafari"},
        },
        "UOIF": {
            "name": "Union des Organisations Islamiques de France",
            "params": {"fajr": 12, "isha": 12},
        },
    }

    default_params = {"maghrib": "0 min", "midnight": "Standard"}

    def __init__(self, method: str = "MWL") -> None:
        for config in self.methods.values():
            for name, value in self.default_params.items():
                config["params"].setdefault(name, value)

        self.settings: dict[str, Any] = {
            "imsak": "10 min",
            "dhuhr": "0 min",
            "asr": "Standard",
            "highLats": "NightMiddle",
            "maghrib": "0 min",
            "midnight": "Standard",
        }
        self.offset = {name: 0.0 for name in self.time_names}
        self.time_format = "24h"
        self.invalid_time = "-----"
        self.num_iterations = 1
        self.calc_method = "MWL"
        self.lat = 0.0
        self.lng = 0.0
        self.elv = 0.0
        self.time_zone = 0.0
        self.j_date = 0.0
        self.set_method(method)

    def set_method(self, method: str) -> None:
        if method in self.methods:
            self.adjust(self.methods[method]["params"])
            self.calc_method = method

    def adjust(self, params: dict[str, Any]) -> None:
        self.settings.update(params)

    def tune(self, time_offsets: dict[str, float]) -> None:
        self.offset.update(time_offsets)

    def get_times(
        self,
        date: tuple[int, int, int],
        coords: tuple[float, float] | tuple[float, float, float],
        timezone: float,
        dst: float = 0,
        time_format: str | None = None,
    ) -> dict[str, str]:
        self.lat = coords[0]
        self.lng = coords[1]
        self.elv = coords[2] if len(coords) > 2 else 0
        if time_format is not None:
            self.time_format = time_format
        self.time_zone = timezone + dst
        self.j_date = self._julian(date[0], date[1], date[2]) - self.lng / (15 * 24.0)
        return self._compute_times()

    def _formatted_time(self, time_value: float, fmt: str) -> str:
        if math.isnan(time_value):
            return self.invalid_time
        if fmt == "Float":
            return time_value  # type: ignore[return-value]
        time_value = self._fix_hour(time_value + 0.5 / 60)
        hours = math.floor(time_value)
        minutes = math.floor((time_value - hours) * 60)
        return f"{int(hours):02d}:{int(minutes):02d}"

    def _mid_day(self, time_value: float) -> float:
        eqt = self._sun_position(self.j_date + time_value)[1]
        return self._fix_hour(12 - eqt)

    def _sun_angle_time(self, angle: float, time_value: float, direction: str | None = None) -> float:
        try:
            decl = self._sun_position(self.j_date + time_value)[0]
            noon = self._mid_day(time_value)
            t = (1 / 15.0) * self._arccos(
                (-self._sin(angle) - self._sin(decl) * self._sin(self.lat))
                / (self._cos(decl) * self._cos(self.lat))
            )
            return noon + (-t if direction == "ccw" else t)
        except ValueError:
            return float("nan")

    def _asr_time(self, factor: float, time_value: float) -> float:
        decl = self._sun_position(self.j_date + time_value)[0]
        angle = -self._arccot(factor + self._tan(abs(self.lat - decl)))
        return self._sun_angle_time(angle, time_value)

    def _sun_position(self, jd: float) -> tuple[float, float]:
        d = jd - 2451545.0
        g = self._fix_angle(357.529 + 0.98560028 * d)
        q = self._fix_angle(280.459 + 0.98564736 * d)
        l = self._fix_angle(q + 1.915 * self._sin(g) + 0.020 * self._sin(2 * g))
        e = 23.439 - 0.00000036 * d
        ra = self._arctan2(self._cos(e) * self._sin(l), self._cos(l)) / 15.0
        eqt = q / 15.0 - self._fix_hour(ra)
        decl = self._arcsin(self._sin(e) * self._sin(l))
        return decl, eqt

    def _julian(self, year: int, month: int, day: int) -> float:
        if month <= 2:
            year -= 1
            month += 12
        a = math.floor(year / 100)
        b = 2 - a + math.floor(a / 4)
        return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5

    def _compute_prayer_times(self, times: dict[str, float]) -> dict[str, float]:
        times = {name: value / 24.0 for name, value in times.items()}
        params = self.settings
        imsak = self._sun_angle_time(self._eval(params["imsak"]), times["imsak"], "ccw")
        fajr = self._sun_angle_time(self._eval(params["fajr"]), times["fajr"], "ccw")
        sunrise = self._sun_angle_time(self._rise_set_angle(), times["sunrise"], "ccw")
        dhuhr = self._mid_day(times["dhuhr"])
        asr = self._asr_time(self._asr_factor(params["asr"]), times["asr"])
        sunset = self._sun_angle_time(self._rise_set_angle(), times["sunset"])
        maghrib = self._sun_angle_time(self._eval(params["maghrib"]), times["maghrib"])
        isha = self._sun_angle_time(self._eval(params["isha"]), times["isha"])
        return {
            "imsak": imsak,
            "fajr": fajr,
            "sunrise": sunrise,
            "dhuhr": dhuhr,
            "asr": asr,
            "sunset": sunset,
            "maghrib": maghrib,
            "isha": isha,
        }

    def _compute_times(self) -> dict[str, str]:
        times = {
            "imsak": 5.0,
            "fajr": 5.0,
            "sunrise": 6.0,
            "dhuhr": 12.0,
            "asr": 13.0,
            "sunset": 18.0,
            "maghrib": 18.0,
            "isha": 18.0,
        }
        for _ in range(self.num_iterations):
            times = self._compute_prayer_times(times)
        times = self._adjust_times(times)
        if self.settings.get("midnight") == "Jafari":
            times["midnight"] = times["sunset"] + self._time_diff(times["sunset"], times["fajr"]) / 2
        else:
            times["midnight"] = times["sunset"] + self._time_diff(times["sunset"], times["sunrise"]) / 2
        times = self._tune_times(times)
        return {name: self._formatted_time(value, self.time_format) for name, value in times.items()}

    def _adjust_times(self, times: dict[str, float]) -> dict[str, float]:
        params = self.settings
        tz_adjust = self.time_zone - self.lng / 15.0
        times = {name: value + tz_adjust for name, value in times.items()}
        if params.get("highLats") != "None":
            times = self._adjust_high_lats(times)
        if self._is_min(params.get("imsak")):
            times["imsak"] = times["fajr"] - self._eval(params["imsak"]) / 60.0
        if self._is_min(params.get("maghrib")):
            times["maghrib"] = times["sunset"] + self._eval(params["maghrib"]) / 60.0
        if self._is_min(params.get("isha")):
            times["isha"] = times["maghrib"] + self._eval(params["isha"]) / 60.0
        times["dhuhr"] += self._eval(params.get("dhuhr", 0)) / 60.0
        return times

    def _asr_factor(self, asr_param: Any) -> float:
        methods = {"Standard": 1, "Hanafi": 2}
        return methods.get(asr_param, self._eval(asr_param))

    def _rise_set_angle(self) -> float:
        return 0.833 + 0.0347 * math.sqrt(self.elv or 0)

    def _tune_times(self, times: dict[str, float]) -> dict[str, float]:
        for name in list(times):
            times[name] += self.offset.get(name, 0) / 60.0
        return times

    def _adjust_high_lats(self, times: dict[str, float]) -> dict[str, float]:
        params = self.settings
        night = self._time_diff(times["sunset"], times["sunrise"])
        times["imsak"] = self._adjust_hl_time(
            times["imsak"], times["sunrise"], self._eval(params["imsak"]), night, "ccw"
        )
        times["fajr"] = self._adjust_hl_time(
            times["fajr"], times["sunrise"], self._eval(params["fajr"]), night, "ccw"
        )
        times["isha"] = self._adjust_hl_time(
            times["isha"], times["sunset"], self._eval(params["isha"]), night
        )
        times["maghrib"] = self._adjust_hl_time(
            times["maghrib"], times["sunset"], self._eval(params["maghrib"]), night
        )
        return times

    def _adjust_hl_time(
        self,
        time_value: float,
        base: float,
        angle: float,
        night: float,
        direction: str | None = None,
    ) -> float:
        portion = self._night_portion(angle, night)
        diff = self._time_diff(time_value, base) if direction == "ccw" else self._time_diff(base, time_value)
        if math.isnan(time_value) or diff > portion:
            time_value = base + (-portion if direction == "ccw" else portion)
        return time_value

    def _night_portion(self, angle: float, night: float) -> float:
        method = self.settings.get("highLats")
        portion = 1 / 2.0
        if method == "AngleBased":
            portion = 1 / 60.0 * angle
        elif method == "OneSeventh":
            portion = 1 / 7.0
        return portion * night

    def _time_diff(self, time1: float, time2: float) -> float:
        return self._fix_hour(time2 - time1)

    def _eval(self, value: Any) -> float:
        match = re.split(r"[^0-9.+-]", str(value), maxsplit=1)[0]
        return float(match) if match else 0.0

    def _is_min(self, value: Any) -> bool:
        return isinstance(value, str) and "min" in value

    def _sin(self, degrees: float) -> float:
        return math.sin(math.radians(degrees))

    def _cos(self, degrees: float) -> float:
        return math.cos(math.radians(degrees))

    def _tan(self, degrees: float) -> float:
        return math.tan(math.radians(degrees))

    def _arcsin(self, value: float) -> float:
        return math.degrees(math.asin(value))

    def _arccos(self, value: float) -> float:
        return math.degrees(math.acos(value))

    def _arccot(self, value: float) -> float:
        return math.degrees(math.atan(1.0 / value))

    def _arctan2(self, y: float, x: float) -> float:
        return math.degrees(math.atan2(y, x))

    def _fix_angle(self, angle: float) -> float:
        return self._fix(angle, 360.0)

    def _fix_hour(self, hour: float) -> float:
        return self._fix(hour, 24.0)

    def _fix(self, value: float, mode: float) -> float:
        if math.isnan(value):
            return value
        value = value - mode * math.floor(value / mode)
        return value + mode if value < 0 else value
