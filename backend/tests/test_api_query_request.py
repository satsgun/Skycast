from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.api.query_request import QueryRequest
from skycast.domain.location import Location


def _now() -> datetime:
    return datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc)


def _location(name: str = "Hyderabad") -> Location:
    return Location(
        id=f"in-memory:{name.lower()}", name=name,
        latitude=17.385, longitude=78.4867, country="India",
        country_code="IN", timezone="Asia/Kolkata",
    )


def test_constructs_with_only_required_fields() -> None:
    request = QueryRequest(query="Do I need an umbrella?", now=_now())

    assert request.query == "Do I need an umbrella?"
    assert request.now == _now()
    assert request.default_location is None
    assert request.resolved_location is None
    assert request.units is None


def test_constructs_with_all_fields() -> None:
    request = QueryRequest(
        query="Is it warmer in Miami or Seattle?",
        now=_now(),
        default_location=_location("Hyderabad"),
        resolved_location=_location("Springfield"),
        units="celsius",
    )

    assert request.default_location == _location("Hyderabad")
    assert request.resolved_location == _location("Springfield")
    assert request.units == "celsius"


def test_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(query="", now=_now())


def test_rejects_timezone_naive_now() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(query="Will it rain today?", now=datetime(2026, 7, 7, 18, 0))


def test_is_frozen() -> None:
    request = QueryRequest(query="Will it rain today?", now=_now())

    with pytest.raises(ValidationError):
        request.query = "Changed"


def test_round_trips_through_json() -> None:
    request = QueryRequest(
        query="Is it warmer in Miami or Seattle?",
        now=_now(),
        default_location=_location("Hyderabad"),
        resolved_location=_location("Springfield"),
        units="celsius",
    )

    restored = QueryRequest.model_validate_json(request.model_dump_json())

    assert restored == request


def test_to_session_context_maps_fields() -> None:
    request = QueryRequest(
        query="Will it rain today?",
        now=_now(),
        default_location=_location("Hyderabad"),
        units="celsius",
    )

    ctx = request.to_session_context()

    assert ctx.now == request.now
    assert ctx.default_location == request.default_location
    assert ctx.units_hint == "celsius"


def test_to_session_context_defaults_carried_fields_to_none() -> None:
    request = QueryRequest(
        query="Will it rain today?", now=_now(), default_location=_location(), units="celsius"
    )

    ctx = request.to_session_context()

    assert ctx.carried_location_name is None
    assert ctx.carried_window is None


def test_to_session_context_drops_resolved_location() -> None:
    without = QueryRequest(query="Will it rain today?", now=_now())
    with_resolved = QueryRequest(
        query="Will it rain today?", now=_now(), resolved_location=_location("Springfield")
    )

    assert without.to_session_context() == with_resolved.to_session_context()
