import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    TimeWindow,
    WeatherVariable,
)
from skycast.providers.base import WeatherProvider
from skycast.providers.errors import ProviderError
from skycast.providers.in_memory import InMemoryProvider


def _hyderabad() -> Location:
    return asyncio.run(InMemoryProvider().geocode("Hyderabad"))[0]


def _window(start: datetime, end: datetime) -> TimeWindow:
    return TimeWindow(start=start, end=end)


def test_in_memory_provider_is_a_weather_provider() -> None:
    provider = InMemoryProvider()
    assert isinstance(provider, WeatherProvider)
    assert issubclass(InMemoryProvider, WeatherProvider)


def test_geocode_hyderabad_returns_exactly_one_location() -> None:
    provider = InMemoryProvider()
    result = asyncio.run(provider.geocode("Hyderabad"))
    assert len(result) == 1
    assert result[0].name == "Hyderabad"
    assert result[0].timezone == "Asia/Kolkata"


def test_geocode_is_case_and_whitespace_normalized() -> None:
    provider = InMemoryProvider()
    exact = asyncio.run(provider.geocode("Hyderabad"))
    normalized = asyncio.run(provider.geocode("  HYDERABAD  "))
    assert normalized == exact


def test_geocode_springfield_returns_three_distinct_admin1_candidates() -> None:
    provider = InMemoryProvider()
    result = asyncio.run(provider.geocode("Springfield"))
    assert len(result) == 3
    assert {location.admin1 for location in result} == {
        "Illinois",
        "Missouri",
        "Massachusetts",
    }


def test_geocode_unknown_name_returns_empty_list() -> None:
    provider = InMemoryProvider()
    result = asyncio.run(provider.geocode("Nowhereville"))
    assert result == []


def test_geocode_raises_provider_error_when_fail_geocode_is_set() -> None:
    provider = InMemoryProvider(fail_geocode=True)
    with pytest.raises(ProviderError):
        asyncio.run(provider.geocode("Hyderabad"))


def test_fetch_forecast_hourly_only_populates_hourly_block_spanning_window() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.HOURLY},
        window=window,
        variables={WeatherVariable.TEMPERATURE},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    assert forecast.current is None
    assert forecast.daily is None
    assert forecast.hourly is not None
    assert [reading.timestamp for reading in forecast.hourly] == [
        window.start + timedelta(hours=offset) for offset in range(4)
    ]


def test_fetch_forecast_current_and_hourly_populates_both_blocks() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.CURRENT, Granularity.HOURLY},
        window=window,
        variables={WeatherVariable.TEMPERATURE},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    assert forecast.current is not None
    assert forecast.hourly is not None
    assert forecast.daily is None
    assert forecast.current.timestamp == window.start


def test_fetch_forecast_daily_only_over_three_day_window_returns_three_readings() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 3, 12, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.DAILY},
        window=window,
        variables={WeatherVariable.TEMPERATURE},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    assert forecast.current is None
    assert forecast.hourly is None
    assert forecast.daily is not None
    assert [reading.date for reading in forecast.daily] == [
        date(2024, 1, 1),
        date(2024, 1, 2),
        date(2024, 1, 3),
    ]


def test_fetch_forecast_raises_provider_error_when_fail_forecast_is_set() -> None:
    provider = InMemoryProvider(fail_forecast=True)
    location = _hyderabad()
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    with pytest.raises(ProviderError):
        asyncio.run(provider.fetch_forecast(location, request))


def test_fetch_forecast_is_deterministic_for_identical_requests() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.HOURLY, Granularity.DAILY},
        window=window,
        variables=set(WeatherVariable),
    )
    first = asyncio.run(provider.fetch_forecast(location, request))
    second = asyncio.run(provider.fetch_forecast(location, request))
    assert first == second


def test_custom_locations_override_replaces_defaults() -> None:
    custom_location = Location(
        id="custom-1", name="Testville", latitude=1.0, longitude=2.0
    )
    provider = InMemoryProvider(locations={"testville": [custom_location]})
    assert asyncio.run(provider.geocode("Testville")) == [custom_location]
    assert asyncio.run(provider.geocode("Hyderabad")) == []


def test_capabilities_returns_declared_static_values() -> None:
    provider = InMemoryProvider()
    capabilities = provider.capabilities()
    assert capabilities.max_forecast_days == 16
    assert capabilities.available_variables == set(WeatherVariable)
    assert capabilities.supports_geocoding is True
    assert capabilities.rate_limit_per_minute is None


def test_fetch_forecast_only_populates_requested_optional_variables() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.HOURLY},
        window=window,
        variables={WeatherVariable.TEMPERATURE},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    reading = forecast.hourly[0]
    assert reading.temperature is not None
    assert reading.condition_code is not None
    assert reading.wind_speed is None
    assert reading.precip_probability is None
    assert reading.precip_amount is None
    assert reading.feels_like is None


def test_fetch_forecast_populates_optional_variable_when_requested() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.HOURLY},
        window=window,
        variables={WeatherVariable.TEMPERATURE, WeatherVariable.WIND_SPEED},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    assert forecast.hourly[0].wind_speed is not None


def test_hourly_temperatures_vary_across_the_window_not_constant() -> None:
    provider = InMemoryProvider()
    location = _hyderabad()
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.HOURLY},
        window=window,
        variables={WeatherVariable.TEMPERATURE},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    temperatures = {reading.temperature for reading in forecast.hourly}
    assert len(temperatures) > 1


def test_fetch_forecast_current_only_without_window_uses_injected_now() -> None:
    fixed_now = datetime(2024, 6, 1, 9, 30, tzinfo=timezone.utc)
    provider = InMemoryProvider(now=lambda: fixed_now)
    location = _hyderabad()
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    assert forecast.current.timestamp == fixed_now


def test_fetch_forecast_daily_uses_utc_when_location_has_no_timezone() -> None:
    provider = InMemoryProvider()
    location = Location(
        id="custom-no-tz", name="Nowhere", latitude=0.0, longitude=0.0
    )
    window = _window(
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    )
    request = ForecastRequest(
        granularities={Granularity.DAILY},
        window=window,
        variables={WeatherVariable.TEMPERATURE},
    )
    forecast = asyncio.run(provider.fetch_forecast(location, request))
    assert [reading.date for reading in forecast.daily] == [date(2024, 1, 1)]


def test_custom_forecasts_override_is_returned_verbatim() -> None:
    location = _hyderabad()
    fixed_forecast = Forecast(
        location=location,
        units=Units(),
        current=HourlyReading(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            temperature=99.0,
            condition_code=ConditionCode.CLEAR,
        ),
    )
    provider = InMemoryProvider(forecasts={location.id: fixed_forecast})
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    result = asyncio.run(provider.fetch_forecast(location, request))
    assert result == fixed_forecast
