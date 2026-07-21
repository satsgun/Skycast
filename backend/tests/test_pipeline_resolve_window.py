from datetime import datetime, time, timedelta, timezone

import pytest

from skycast.pipeline.relative_time import RelativeTimeKind, RelativeTimeSpec
from skycast.pipeline.resolve_window import implied_horizon_days, resolve_window

_KOLKATA = "Asia/Kolkata"


def _now(*, hour: int = 9, minute: int = 0, day: int = 7, month: int = 7, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_now_resolves_to_a_single_instant_at_now() -> None:
    now = _now()
    window = resolve_window(RelativeTimeSpec(kind=RelativeTimeKind.NOW), _KOLKATA, now)
    assert window.start == now
    assert window.end == now


def test_today_resolves_from_now_to_local_end_of_day() -> None:
    now = _now(hour=9, minute=0)  # 14:30 IST
    window = resolve_window(RelativeTimeSpec(kind=RelativeTimeKind.TODAY), _KOLKATA, now)

    assert window.start == now
    end_local = window.end.astimezone(_offset(_KOLKATA))
    assert (end_local.hour, end_local.minute, end_local.second) == (23, 59, 59)
    assert end_local.date() == now.astimezone(_offset(_KOLKATA)).date()


def test_this_evening_resolves_to_local_17_to_21() -> None:
    now = _now()
    window = resolve_window(RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING), _KOLKATA, now)

    # 17:00-21:00 IST (UTC+5:30) is 11:30-15:30 UTC -- the exact bug from
    # "hourly weather this evening Hyderabad" earlier this session.
    assert window.start == datetime(2026, 7, 7, 11, 30, tzinfo=timezone.utc)
    assert window.end == datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def test_tomorrow_resolves_to_whole_next_local_calendar_day() -> None:
    now = _now()
    window = resolve_window(RelativeTimeSpec(kind=RelativeTimeKind.TOMORROW), _KOLKATA, now)

    start_local = window.start.astimezone(_offset(_KOLKATA))
    end_local = window.end.astimezone(_offset(_KOLKATA))
    assert (start_local.hour, start_local.minute, start_local.second) == (0, 0, 0)
    assert (end_local.hour, end_local.minute, end_local.second) == (23, 59, 59)
    assert start_local.date() == end_local.date() == now.astimezone(_offset(_KOLKATA)).date() + timedelta(days=1)


def test_next_n_days_spans_today_through_n_minus_one_more_days() -> None:
    now = _now()
    window = resolve_window(
        RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=3), _KOLKATA, now
    )

    start_local = window.start.astimezone(_offset(_KOLKATA))
    end_local = window.end.astimezone(_offset(_KOLKATA))
    today_local = now.astimezone(_offset(_KOLKATA)).date()
    assert start_local.date() == today_local
    assert (start_local.hour, start_local.minute, start_local.second) == (0, 0, 0)
    assert end_local.date() == today_local + timedelta(days=2)
    assert (end_local.hour, end_local.minute, end_local.second) == (23, 59, 59)


def test_next_n_days_with_day_count_one_is_just_today() -> None:
    now = _now()
    window = resolve_window(
        RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=1), _KOLKATA, now
    )

    today_local = now.astimezone(_offset(_KOLKATA)).date()
    assert window.start.astimezone(_offset(_KOLKATA)).date() == today_local
    assert window.end.astimezone(_offset(_KOLKATA)).date() == today_local


def test_absolute_resolves_to_named_clock_time_today_by_default() -> None:
    now = _now()
    window = resolve_window(
        RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0)),
        _KOLKATA,
        now,
    )

    # 2 PM IST (UTC+5:30) is 08:30 UTC.
    assert window.start == window.end == datetime(2026, 7, 7, 8, 30, tzinfo=timezone.utc)


def test_absolute_resolves_to_named_clock_time_on_offset_day() -> None:
    now = _now()
    window = resolve_window(
        RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0), day_offset=1),
        _KOLKATA,
        now,
    )

    # "2pm tomorrow" -- 2 PM IST on 2026-07-08 is 08:30 UTC on that date.
    assert window.start == window.end == datetime(2026, 7, 8, 8, 30, tzinfo=timezone.utc)


def test_this_evening_differs_by_timezone_for_the_same_now() -> None:
    now = _now()
    spec = RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING)

    tokyo = resolve_window(spec, "Asia/Tokyo", now)
    la = resolve_window(spec, "America/Los_Angeles", now)

    assert tokyo != la
    assert tokyo.start != la.start


def test_this_evening_uses_the_correct_offset_before_us_dst_transition() -> None:
    # 2026-10-25 is before that year's US fall-back (2026-11-01), so
    # America/New_York is still on daylight time (UTC-4).
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    window = resolve_window(
        RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING), "America/New_York", now
    )
    assert window.start.utcoffset() == timedelta(hours=-4)


def test_this_evening_uses_the_correct_offset_after_us_dst_transition() -> None:
    # 2026-11-01 is the actual US fall-back date that year; by 17:00
    # local, the transition (2am local) has already happened, so this is
    # standard time (UTC-5) -- proof the offset is computed per-date, not
    # cached from whatever offset `now` itself carries.
    now = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    window = resolve_window(
        RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING), "America/New_York", now
    )
    assert window.start.utcoffset() == timedelta(hours=-5)


def test_falls_back_to_now_tzinfo_when_no_timezone_is_given() -> None:
    now = _now()
    window = resolve_window(RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING), None, now)

    # now is UTC, so "local" evening with no location timezone is UTC
    # evening -- 17:00-21:00 UTC, not defaulted to some other zone.
    assert window.start == datetime(2026, 7, 7, 17, 0, tzinfo=timezone.utc)
    assert window.end == datetime(2026, 7, 7, 21, 0, tzinfo=timezone.utc)


def test_same_inputs_produce_an_identical_window() -> None:
    now = _now()
    spec = RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=4)

    first = resolve_window(spec, _KOLKATA, now)
    second = resolve_window(spec, _KOLKATA, now)

    assert first == second


@pytest.mark.parametrize(
    "spec",
    [
        RelativeTimeSpec(kind=RelativeTimeKind.NOW),
        RelativeTimeSpec(kind=RelativeTimeKind.TODAY),
        RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING),
        RelativeTimeSpec(kind=RelativeTimeKind.TOMORROW),
        RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=2),
        RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE, clock_time=time(9, 30)),
    ],
)
def test_every_kind_resolves_to_a_tz_aware_valid_window(spec: RelativeTimeSpec) -> None:
    window = resolve_window(spec, _KOLKATA, _now())
    assert window.start.tzinfo is not None
    assert window.end.tzinfo is not None
    assert window.end >= window.start


def test_today_end_of_day_never_sorts_before_a_now_late_in_the_local_day() -> None:
    # now lands at 23:59:59.7 local (IST) -- the microsecond-precision
    # end-of-day boundary must still be >= this, or TimeWindow's own
    # end-must-be->=-start validator would reject the result.
    now = datetime(2026, 7, 7, 18, 29, 59, 700000, tzinfo=timezone.utc)  # 23:59:59.7 IST
    window = resolve_window(RelativeTimeSpec(kind=RelativeTimeKind.TODAY), _KOLKATA, now)
    assert window.end >= window.start


def _offset(tz_name: str):
    from zoneinfo import ZoneInfo

    return ZoneInfo(tz_name)


# --- implied_horizon_days (Task 21.5) ---


@pytest.mark.parametrize(
    "spec",
    [
        RelativeTimeSpec(kind=RelativeTimeKind.NOW),
        RelativeTimeSpec(kind=RelativeTimeKind.TODAY),
        RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING),
        RelativeTimeSpec(kind=RelativeTimeKind.TOMORROW),
        RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0)),
        RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0), day_offset=3),
    ],
)
def test_implied_horizon_days_is_one_for_every_kind_but_next_n_days(spec: RelativeTimeSpec) -> None:
    assert implied_horizon_days(spec) == 1


@pytest.mark.parametrize("day_count", [1, 3, 16, 20])
def test_implied_horizon_days_matches_day_count_for_next_n_days(day_count: int) -> None:
    spec = RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=day_count)
    assert implied_horizon_days(spec) == day_count
