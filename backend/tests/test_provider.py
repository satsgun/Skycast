from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    ProviderCapabilities,
    TimeWindow,
    WeatherVariable,
)


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )


def test_granularity_members_are_exactly_current_hourly_daily() -> None:
    assert [member.value for member in Granularity] == ["CURRENT", "HOURLY", "DAILY"]


def test_weather_variable_values_equal_their_names() -> None:
    for member in WeatherVariable:
        assert member.value == member.name


def test_time_window_can_be_constructed_with_end_after_start() -> None:
    window = _window()
    assert window.end > window.start


def test_time_window_allows_end_equal_to_start() -> None:
    same = datetime(2024, 1, 1, tzinfo=timezone.utc)
    window = TimeWindow(start=same, end=same)
    assert window.start == window.end


def test_time_window_end_before_start_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        TimeWindow(
            start=datetime(2024, 1, 2, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


def test_time_window_naive_start_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        TimeWindow(start=datetime(2024, 1, 1), end=datetime(2024, 1, 2, tzinfo=timezone.utc))


def test_time_window_naive_end_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        TimeWindow(start=datetime(2024, 1, 1, tzinfo=timezone.utc), end=datetime(2024, 1, 2))


def test_time_window_is_frozen() -> None:
    window = _window()
    with pytest.raises(ValidationError):
        window.start = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_time_window_round_trips_through_json() -> None:
    window = _window()
    restored = TimeWindow.model_validate_json(window.model_dump_json())
    assert restored == window


def test_forecast_request_empty_granularities_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ForecastRequest(granularities=set(), variables={WeatherVariable.TEMPERATURE})


def test_forecast_request_empty_variables_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ForecastRequest(granularities={Granularity.CURRENT}, variables=set())


def test_forecast_request_hourly_without_window_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ForecastRequest(
            granularities={Granularity.HOURLY}, variables={WeatherVariable.TEMPERATURE}
        )


def test_forecast_request_daily_without_window_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ForecastRequest(
            granularities={Granularity.DAILY}, variables={WeatherVariable.TEMPERATURE}
        )


def test_forecast_request_current_only_without_window_is_valid() -> None:
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    assert request.window is None


def test_forecast_request_hourly_with_window_is_valid() -> None:
    request = ForecastRequest(
        granularities={Granularity.HOURLY},
        window=_window(),
        variables={WeatherVariable.TEMPERATURE},
    )
    assert request.window is not None


def test_forecast_request_is_frozen() -> None:
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    with pytest.raises(ValidationError):
        request.variables = {WeatherVariable.WIND_SPEED}


def test_forecast_request_round_trips_through_json() -> None:
    request = ForecastRequest(
        granularities={Granularity.CURRENT, Granularity.HOURLY},
        window=_window(),
        variables={WeatherVariable.TEMPERATURE, WeatherVariable.WIND_SPEED},
    )
    restored = ForecastRequest.model_validate_json(request.model_dump_json())
    assert restored == request


def test_provider_capabilities_round_trips_through_json() -> None:
    capabilities = ProviderCapabilities(
        max_forecast_days=16,
        available_variables={WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION},
        supports_geocoding=True,
        rate_limit_per_minute=600,
    )
    restored = ProviderCapabilities.model_validate_json(capabilities.model_dump_json())
    assert restored == capabilities


def test_provider_capabilities_rate_limit_defaults_to_none() -> None:
    capabilities = ProviderCapabilities(
        max_forecast_days=16,
        available_variables={WeatherVariable.TEMPERATURE},
        supports_geocoding=False,
    )
    assert capabilities.rate_limit_per_minute is None


def test_provider_capabilities_is_frozen() -> None:
    capabilities = ProviderCapabilities(
        max_forecast_days=16,
        available_variables={WeatherVariable.TEMPERATURE},
        supports_geocoding=False,
    )
    with pytest.raises(ValidationError):
        capabilities.supports_geocoding = True
