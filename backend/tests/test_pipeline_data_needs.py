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
        location_name="Hyderabad",
        use_default_location=False,
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert spec.window is None


def test_hourly_spec_with_window_is_valid() -> None:
    spec = DataNeedsSpec(
        location_name="Hyderabad",
        use_default_location=False,
        granularities={Granularity.HOURLY},
        window=_window(),
        variables={WeatherVariable.PRECIP_PROBABILITY},
        intent=QueryIntent.DECISION,
    )
    assert spec.window is not None


def test_empty_granularities_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            use_default_location=True,
            granularities=set(),
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.CONDITIONS,
        )


def test_empty_variables_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            use_default_location=True,
            granularities={Granularity.CURRENT},
            variables=set(),
            intent=QueryIntent.CONDITIONS,
        )


@pytest.mark.parametrize("granularity", [Granularity.HOURLY, Granularity.DAILY])
def test_window_required_for_hourly_or_daily(granularity: Granularity) -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            use_default_location=True,
            granularities={granularity},
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.OUTLOOK,
        )


def test_use_default_location_true_with_no_location_name_is_valid() -> None:
    spec = DataNeedsSpec(
        location_name=None,
        use_default_location=True,
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert spec.location_name is None
    assert spec.use_default_location is True


def test_invalid_intent_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DataNeedsSpec(
            use_default_location=True,
            granularities={Granularity.CURRENT},
            variables={WeatherVariable.TEMPERATURE},
            intent="NOT_A_REAL_INTENT",
        )


def test_spec_is_frozen() -> None:
    spec = DataNeedsSpec(
        use_default_location=True,
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    with pytest.raises(ValidationError):
        spec.use_default_location = False


def test_current_only_spec_round_trips_through_json() -> None:
    spec = DataNeedsSpec(
        location_name="Hyderabad",
        use_default_location=False,
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    assert DataNeedsSpec.model_validate_json(spec.model_dump_json()) == spec


def test_hourly_with_window_spec_round_trips_through_json() -> None:
    spec = DataNeedsSpec(
        location_name="Springfield",
        use_default_location=False,
        granularities={Granularity.HOURLY, Granularity.DAILY},
        window=_window(),
        variables={WeatherVariable.PRECIP_PROBABILITY, WeatherVariable.WIND_SPEED},
        intent=QueryIntent.COMPARISON,
    )
    assert DataNeedsSpec.model_validate_json(spec.model_dump_json()) == spec
