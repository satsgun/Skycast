import pytest
from pydantic import ValidationError

from skycast.domain.location import Location
from skycast.domain.provider import Granularity, WeatherVariable
from skycast.pipeline.data_needs import QueryIntent
from skycast.pipeline.plan import PlannedCall, PlannedTool, ToolPlan
from skycast.pipeline.relative_time import RelativeTimeKind, RelativeTimeSpec


def _location(name: str = "Hyderabad") -> Location:
    return Location(
        id=f"in-memory:{name.lower()}",
        name=name,
        latitude=17.385,
        longitude=78.4867,
        timezone="Asia/Kolkata",
    )


def _forecast_fields(**overrides) -> dict:
    defaults = dict(
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
    )
    defaults.update(overrides)
    return defaults


def test_planned_tool_has_exactly_two_members() -> None:
    assert {member.value for member in PlannedTool} == {"GEOCODE", "FETCH_FORECAST"}


# --- PlannedCall ---


def test_valid_geocode_call() -> None:
    call = PlannedCall(
        call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Hyderabad",
    )
    assert call.location_name == "Hyderabad"
    assert call.location is None
    assert call.granularities is None
    assert call.variables is None
    assert call.time is None
    assert call.depends_on == []


def test_valid_fetch_forecast_call_with_known_location() -> None:
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), **_forecast_fields(),
    )
    assert call.location is not None
    assert call.depends_on == []


def test_valid_fetch_forecast_call_depending_on_geocode() -> None:
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-1"], **_forecast_fields(),
    )
    assert call.location is None
    assert call.depends_on == ["geocode-1"]


def test_geocode_call_missing_location_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PlannedCall(call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo")


def test_geocode_call_with_location_set_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PlannedCall(
            call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
            location_name="Hyderabad", location=_location(),
        )


def test_geocode_call_with_granularities_set_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PlannedCall(
            call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
            location_name="Hyderabad", **_forecast_fields(),
        )


def test_fetch_forecast_call_with_location_name_set_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PlannedCall(
            call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
            location_name="Hyderabad", **_forecast_fields(),
        )


def test_fetch_forecast_call_with_location_and_location_name_is_valid() -> None:
    """A pre-resolved chain carried forward across a disambiguation round
    keeps its original location_name (Task: fix #90) so a later execute()
    pass can recover which query-named location this chain answers for.
    """
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), location_name="Hyderabad", **_forecast_fields(),
    )
    assert call.location_name == "Hyderabad"
    assert call.location is not None


def test_fetch_forecast_call_missing_granularities_or_variables_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PlannedCall(
            call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
            location=_location(),
        )


def test_fetch_forecast_call_with_hourly_granularity_requires_time() -> None:
    with pytest.raises(ValidationError):
        PlannedCall(
            call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
            location=_location(),
            **_forecast_fields(granularities={Granularity.HOURLY}),
        )


def test_fetch_forecast_call_with_hourly_granularity_and_time_is_valid() -> None:
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(),
        **_forecast_fields(
            granularities={Granularity.HOURLY},
            time=RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING),
        ),
    )
    assert call.time is not None


def test_fetch_forecast_call_with_current_granularity_does_not_require_time() -> None:
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), **_forecast_fields(),
    )
    assert call.time is None


def test_planned_call_is_frozen() -> None:
    call = PlannedCall(
        call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Hyderabad",
    )
    with pytest.raises(ValidationError):
        call.provider = "other"


def test_geocode_call_round_trips_through_json() -> None:
    call = PlannedCall(
        call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Hyderabad",
    )
    assert PlannedCall.model_validate_json(call.model_dump_json()) == call


def test_fetch_forecast_call_round_trips_through_json() -> None:
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), **_forecast_fields(),
    )
    assert PlannedCall.model_validate_json(call.model_dump_json()) == call


def test_fetch_forecast_call_with_location_name_round_trips_through_json() -> None:
    call = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), location_name="Hyderabad", **_forecast_fields(),
    )
    assert PlannedCall.model_validate_json(call.model_dump_json()) == call


# --- ToolPlan ---


def test_single_location_by_name_chain_is_valid() -> None:
    geocode = PlannedCall(
        call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Hyderabad",
    )
    forecast = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-1"], **_forecast_fields(),
    )
    plan = ToolPlan(calls=[geocode, forecast], intent=QueryIntent.CONDITIONS)
    assert plan.calls[1].depends_on == [plan.calls[0].call_id]


def test_single_location_known_coords_skips_geocode() -> None:
    forecast = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), **_forecast_fields(),
    )
    plan = ToolPlan(calls=[forecast], intent=QueryIntent.CONDITIONS)
    assert plan.calls[0].depends_on == []


def test_comparison_produces_independent_parallel_chains() -> None:
    geocode_a = PlannedCall(
        call_id="geocode-a", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Miami",
    )
    forecast_a = PlannedCall(
        call_id="forecast-a", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-a"], **_forecast_fields(),
    )
    geocode_b = PlannedCall(
        call_id="geocode-b", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Seattle",
    )
    forecast_b = PlannedCall(
        call_id="forecast-b", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-b"], **_forecast_fields(),
    )
    plan = ToolPlan(
        calls=[geocode_a, forecast_a, geocode_b, forecast_b], intent=QueryIntent.COMPARISON
    )
    assert len(plan.calls) == 4
    assert forecast_a.depends_on == ["geocode-a"]
    assert forecast_b.depends_on == ["geocode-b"]


def test_dangling_depends_on_is_rejected() -> None:
    forecast = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["does-not-exist"], **_forecast_fields(),
    )
    with pytest.raises(ValidationError):
        ToolPlan(calls=[forecast], intent=QueryIntent.CONDITIONS)


def test_two_call_cycle_is_rejected() -> None:
    call_a = PlannedCall(
        call_id="a", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["b"], **_forecast_fields(),
    )
    call_b = PlannedCall(
        call_id="b", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["a"], **_forecast_fields(),
    )
    with pytest.raises(ValidationError):
        ToolPlan(calls=[call_a, call_b], intent=QueryIntent.CONDITIONS)


def test_self_referencing_call_is_rejected() -> None:
    call = PlannedCall(
        call_id="a", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["a"], **_forecast_fields(),
    )
    with pytest.raises(ValidationError):
        ToolPlan(calls=[call], intent=QueryIntent.CONDITIONS)


def test_fetch_forecast_with_both_location_and_geocode_dependency_is_rejected() -> None:
    geocode = PlannedCall(
        call_id="geocode-1", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Hyderabad",
    )
    forecast = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-1"], location=_location(), **_forecast_fields(),
    )
    with pytest.raises(ValidationError):
        ToolPlan(calls=[geocode, forecast], intent=QueryIntent.CONDITIONS)


def test_fetch_forecast_with_neither_location_nor_geocode_dependency_is_rejected() -> None:
    forecast = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        **_forecast_fields(),
    )
    with pytest.raises(ValidationError):
        ToolPlan(calls=[forecast], intent=QueryIntent.CONDITIONS)


def test_tool_plan_is_frozen() -> None:
    forecast = PlannedCall(
        call_id="forecast-1", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        location=_location(), **_forecast_fields(),
    )
    plan = ToolPlan(calls=[forecast], intent=QueryIntent.CONDITIONS)
    with pytest.raises(ValidationError):
        plan.intent = QueryIntent.OUTLOOK


def test_comparison_plan_round_trips_through_json() -> None:
    geocode_a = PlannedCall(
        call_id="geocode-a", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Miami",
    )
    forecast_a = PlannedCall(
        call_id="forecast-a", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-a"], **_forecast_fields(),
    )
    geocode_b = PlannedCall(
        call_id="geocode-b", tool=PlannedTool.GEOCODE, provider="open-meteo",
        location_name="Seattle",
    )
    forecast_b = PlannedCall(
        call_id="forecast-b", tool=PlannedTool.FETCH_FORECAST, provider="open-meteo",
        depends_on=["geocode-b"], **_forecast_fields(),
    )
    plan = ToolPlan(
        calls=[geocode_a, forecast_a, geocode_b, forecast_b], intent=QueryIntent.COMPARISON
    )
    assert ToolPlan.model_validate_json(plan.model_dump_json()) == plan
