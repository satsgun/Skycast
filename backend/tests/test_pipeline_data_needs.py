from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.provider import Granularity, TimeWindow, WeatherVariable
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )


def test_query_intent_has_exactly_four_members() -> None:
    assert {member.value for member in QueryIntent} == {
        "DECISION",
        "CONDITIONS",
        "OUTLOOK",
        "COMPARISON",
    }


def test_current_only_spec_without_window_is_valid() -> None:
    spec = DataNeedsSpec(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert spec.window is None


def test_hourly_spec_with_window_is_valid() -> None:
    spec = DataNeedsSpec(
        location_names=["Hyderabad"],
        granularities={Granularity.HOURLY},
        window=_window(),
        variables={WeatherVariable.PRECIP_PROBABILITY},
        intent=QueryIntent.DECISION,
    )
    assert spec.window is not None


def test_empty_granularities_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            location_names=[],
            granularities=set(),
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.CONDITIONS,
        )


def test_empty_variables_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            location_names=[],
            granularities={Granularity.CURRENT},
            variables=set(),
            intent=QueryIntent.CONDITIONS,
        )


@pytest.mark.parametrize("granularity", [Granularity.HOURLY, Granularity.DAILY])
def test_window_required_for_hourly_or_daily(granularity: Granularity) -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            location_names=[],
            granularities={granularity},
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.OUTLOOK,
        )


def test_empty_location_names_is_valid_and_means_use_default_location() -> None:
    spec = DataNeedsSpec(
        location_names=[],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert spec.location_names == []
    assert spec.use_default_location is True


def test_single_location_name_is_valid_and_means_not_use_default_location() -> None:
    spec = DataNeedsSpec(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert spec.use_default_location is False


def test_use_default_location_is_not_included_in_serialization() -> None:
    spec = DataNeedsSpec(
        location_names=[],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert "use_default_location" not in spec.model_dump()
    assert "use_default_location" not in spec.model_dump(mode="json")


def test_comparison_intent_with_two_locations_is_valid() -> None:
    spec = DataNeedsSpec(
        location_names=["Miami", "Seattle"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.COMPARISON,
    )
    assert spec.location_names == ["Miami", "Seattle"]


@pytest.mark.parametrize("location_names", [[], ["Miami"]])
def test_comparison_intent_with_fewer_than_two_locations_is_rejected(
    location_names: list[str],
) -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            location_names=location_names,
            granularities={Granularity.CURRENT},
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.COMPARISON,
        )


def test_non_comparison_intent_with_two_or_more_locations_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            location_names=["Miami", "Seattle"],
            granularities={Granularity.CURRENT},
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.CONDITIONS,
        )


def test_invalid_intent_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            location_names=[],
            granularities={Granularity.CURRENT},
            variables={WeatherVariable.TEMPERATURE},
            intent="NOT_A_REAL_INTENT",
        )


def test_spec_is_frozen() -> None:
    spec = DataNeedsSpec(
        location_names=[],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    with pytest.raises(ValidationError):
        spec.location_names = ["Hyderabad"]


def test_current_only_spec_round_trips_through_json() -> None:
    spec = DataNeedsSpec(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert DataNeedsSpec.model_validate_json(spec.model_dump_json()) == spec


def test_hourly_with_window_spec_round_trips_through_json() -> None:
    spec = DataNeedsSpec(
        location_names=["Springfield"],
        granularities={Granularity.HOURLY, Granularity.DAILY},
        window=_window(),
        variables={WeatherVariable.PRECIP_PROBABILITY, WeatherVariable.WIND_SPEED},
        intent=QueryIntent.OUTLOOK,
    )
    assert DataNeedsSpec.model_validate_json(spec.model_dump_json()) == spec
