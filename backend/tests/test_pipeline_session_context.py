from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.location import Location
from skycast.domain.provider import TimeWindow
from skycast.pipeline.session_context import SessionContext


def _now() -> datetime:
    return datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc)


def _location() -> Location:
    return Location(
        id="in-memory:hyderabad-in",
        name="Hyderabad",
        latitude=17.385,
        longitude=78.4867,
        country="India",
        country_code="IN",
        timezone="Asia/Kolkata",
    )


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc),
        end=datetime(2026, 7, 7, 22, 0, tzinfo=timezone.utc),
    )


def test_minimal_construction_defaults_optional_fields_to_none() -> None:
    ctx = SessionContext(now=_now())

    assert ctx.now == _now()
    assert ctx.default_location is None
    assert ctx.units_hint is None
    assert ctx.carried_location_name is None
    assert ctx.carried_window is None


def test_full_construction_succeeds() -> None:
    ctx = SessionContext(
        now=_now(),
        default_location=_location(),
        units_hint="celsius",
        carried_location_name="Hyderabad",
        carried_window=_window(),
    )

    assert ctx.default_location == _location()
    assert ctx.units_hint == "celsius"
    assert ctx.carried_location_name == "Hyderabad"
    assert ctx.carried_window == _window()


def test_session_context_is_frozen() -> None:
    ctx = SessionContext(now=_now())

    with pytest.raises(ValidationError):
        ctx.units_hint = "fahrenheit"


def test_minimal_json_round_trip() -> None:
    ctx = SessionContext(now=_now())

    assert SessionContext.model_validate_json(ctx.model_dump_json()) == ctx


def test_full_json_round_trip() -> None:
    ctx = SessionContext(
        now=_now(),
        default_location=_location(),
        units_hint="celsius",
        carried_location_name="Hyderabad",
        carried_window=_window(),
    )

    assert SessionContext.model_validate_json(ctx.model_dump_json()) == ctx
