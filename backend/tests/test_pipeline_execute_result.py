from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.pipeline.execute_result import ExecutionResult, Failed, NeedsClarification, Success
from skycast.sse.payloads import ErrorKind


def _location(name: str = "Springfield") -> Location:
    return Location(
        id=f"in-memory:{name.lower()}", name=name,
        latitude=39.7817, longitude=-89.6501, timezone="America/Chicago",
    )


def _forecast(name: str = "Hyderabad") -> Forecast:
    return Forecast(
        location=_location(name),
        units=Units(),
        current=HourlyReading(
            timestamp=datetime(2026, 7, 7, 12, tzinfo=timezone.utc),
            temperature=28.0,
            condition_code=ConditionCode.CLEAR,
        ),
    )


# --- Success ---


def test_success_with_one_forecast_is_valid() -> None:
    result = Success(forecasts=[_forecast()])
    assert len(result.forecasts) == 1


def test_success_preserves_chain_order_for_comparisons() -> None:
    miami = _forecast("Miami")
    seattle = _forecast("Seattle")
    result = Success(forecasts=[miami, seattle])
    assert result.forecasts == [miami, seattle]


def test_success_with_empty_forecasts_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Success(forecasts=[])


def test_success_is_frozen() -> None:
    result = Success(forecasts=[_forecast()])
    with pytest.raises(ValidationError):
        result.forecasts = []


def test_success_round_trips_through_json() -> None:
    result = Success(forecasts=[_forecast()])
    assert Success.model_validate_json(result.model_dump_json()) == result


# --- NeedsClarification ---


def test_needs_clarification_with_two_candidates_is_valid() -> None:
    result = NeedsClarification(
        candidates=[_location("Springfield"), _location("Springfield")],
        for_location_name="Springfield",
    )
    assert len(result.candidates) == 2
    assert result.for_location_name == "Springfield"


def test_needs_clarification_with_fewer_than_two_candidates_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NeedsClarification(candidates=[_location()], for_location_name="Springfield")


def test_needs_clarification_with_zero_candidates_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NeedsClarification(candidates=[], for_location_name="Springfield")


def test_needs_clarification_is_frozen() -> None:
    result = NeedsClarification(
        candidates=[_location(), _location()], for_location_name="Springfield"
    )
    with pytest.raises(ValidationError):
        result.for_location_name = "Other"


def test_needs_clarification_round_trips_through_json() -> None:
    result = NeedsClarification(
        candidates=[_location(), _location()], for_location_name="Springfield"
    )
    assert NeedsClarification.model_validate_json(result.model_dump_json()) == result


# --- Failed ---


def test_failed_with_location_name_is_valid() -> None:
    result = Failed(
        kind=ErrorKind.NOT_FOUND, message="no match", for_location_name="Nowhereville"
    )
    assert result.kind == ErrorKind.NOT_FOUND
    assert result.for_location_name == "Nowhereville"


def test_failed_location_name_defaults_to_none() -> None:
    result = Failed(kind=ErrorKind.INTERNAL, message="unknown provider id")
    assert result.for_location_name is None


def test_failed_with_invalid_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Failed(kind="NOT_A_REAL_KIND", message="oops")


def test_failed_is_frozen() -> None:
    result = Failed(kind=ErrorKind.PROVIDER_UNREACHABLE, message="outage")
    with pytest.raises(ValidationError):
        result.message = "different"


def test_failed_round_trips_through_json() -> None:
    result = Failed(
        kind=ErrorKind.PROVIDER_UNREACHABLE, message="outage", for_location_name="Miami"
    )
    assert Failed.model_validate_json(result.model_dump_json()) == result


# --- ExecutionResult union ---


@pytest.mark.parametrize(
    "result",
    [
        Success(forecasts=[_forecast()]),
        NeedsClarification(candidates=[_location(), _location()], for_location_name="Springfield"),
        Failed(kind=ErrorKind.INTERNAL, message="oops"),
    ],
)
def test_each_variant_is_an_execution_result(result) -> None:
    assert isinstance(result, ExecutionResult)


def test_pattern_matching_dispatches_on_variant() -> None:
    def describe(result: ExecutionResult) -> str:
        match result:
            case Success():
                return "success"
            case NeedsClarification():
                return "needs_clarification"
            case Failed():
                return "failed"

    assert describe(Success(forecasts=[_forecast()])) == "success"
    assert describe(
        NeedsClarification(candidates=[_location(), _location()], for_location_name="x")
    ) == "needs_clarification"
    assert describe(Failed(kind=ErrorKind.INTERNAL, message="oops")) == "failed"
