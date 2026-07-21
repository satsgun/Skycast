"""resolve_window: turns a RelativeTimeSpec into a concrete TimeWindow,
using the resolved location's real timezone (Task 21.3, ADR-0006).

Pure, deterministic, no LLM -- the counterpart to decompose emitting a
descriptor instead of resolving one itself (Task 21.2). This is the
first point in the pipeline where the target's real timezone is known
(post-geocode), so it's where absolute bounds actually get computed.
Not yet wired into the pipeline -- that's Task 21.4.
"""

from datetime import date, datetime, time as _time, timedelta, tzinfo as _tzinfo
from zoneinfo import ZoneInfo

from skycast.domain.provider import TimeWindow
from skycast.pipeline.relative_time import RelativeTimeKind, RelativeTimeSpec

# Microsecond precision so a `now` landing late in the local day (e.g.
# 23:59:59.7) never sorts after "end of day" -- TimeWindow requires
# end >= start.
_END_OF_DAY = _time(23, 59, 59, 999999)
_START_OF_DAY = _time(0, 0, 0)
_EVENING_START = _time(17, 0)
_EVENING_END = _time(21, 0)


def resolve_window(time: RelativeTimeSpec, timezone: str | None, now: datetime) -> TimeWindow:
    """Resolves `time` into concrete, tz-aware bounds.

    Uses `timezone` (the resolved location's IANA name) when given;
    falls back to `now`'s own tzinfo when it isn't -- e.g. no
    location-specific timezone applies (current-conditions with a
    carried location).
    """
    tz = ZoneInfo(timezone) if timezone is not None else now.tzinfo
    today = now.astimezone(tz).date()

    if time.kind == RelativeTimeKind.NOW:
        return TimeWindow(start=now, end=now)
    if time.kind == RelativeTimeKind.TODAY:
        return TimeWindow(start=now, end=_at(today, _END_OF_DAY, tz))
    if time.kind == RelativeTimeKind.THIS_EVENING:
        return TimeWindow(
            start=_at(today, _EVENING_START, tz), end=_at(today, _EVENING_END, tz)
        )
    if time.kind == RelativeTimeKind.TOMORROW:
        tomorrow = today + timedelta(days=1)
        return TimeWindow(
            start=_at(tomorrow, _START_OF_DAY, tz), end=_at(tomorrow, _END_OF_DAY, tz)
        )
    if time.kind == RelativeTimeKind.NEXT_N_DAYS:
        assert time.day_count is not None  # guaranteed by RelativeTimeSpec's own validator
        last_day = today + timedelta(days=time.day_count - 1)
        return TimeWindow(start=_at(today, _START_OF_DAY, tz), end=_at(last_day, _END_OF_DAY, tz))

    assert time.kind == RelativeTimeKind.ABSOLUTE
    assert time.clock_time is not None  # guaranteed by RelativeTimeSpec's own validator
    target_day = today + timedelta(days=time.day_offset)
    moment = _at(target_day, time.clock_time, tz)
    return TimeWindow(start=moment, end=moment)


def _at(day: date, clock: _time, tz: _tzinfo) -> datetime:
    return datetime.combine(day, clock, tzinfo=tz)
