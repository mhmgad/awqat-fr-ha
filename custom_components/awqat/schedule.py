"""Schedule the next Awqat timetable pull.

Times are fetched once after Isha (last prayer) and again after 02:00.
Failures retry a few times, then the integration declares failure until
the next scheduled pull.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .const import AFTER_ISHA_DELAY, AFTER_TWO_AM, RETRY_DELAYS


def retry_delay(attempt_index: int) -> timedelta:
    """Delay after a failed attempt. attempt_index is 0-based for the failure just seen."""
    if attempt_index < 0:
        attempt_index = 0
    if attempt_index >= len(RETRY_DELAYS):
        return RETRY_DELAYS[-1]
    return RETRY_DELAYS[attempt_index]


def next_scheduled_refresh(now: datetime, isha: datetime | None) -> datetime:
    """Return the next regular pull: after Isha, or after 02:00."""
    two_am_today = datetime.combine(now.date(), AFTER_TWO_AM, tzinfo=now.tzinfo)
    two_am_tomorrow = two_am_today + timedelta(days=1)

    candidates: list[datetime] = []
    if isha is not None:
        after_isha = isha + AFTER_ISHA_DELAY
        if after_isha > now:
            candidates.append(after_isha)
        else:
            # Isha has passed; the next post-Isha pull is tomorrow.
            candidates.append(after_isha + timedelta(days=1))

    if two_am_today > now:
        candidates.append(two_am_today)
    else:
        candidates.append(two_am_tomorrow)

    return min(candidates)
