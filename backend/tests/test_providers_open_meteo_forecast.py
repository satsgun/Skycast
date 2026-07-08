import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from skycast.domain.conditions import ConditionCode
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    TimeWindow,
    WeatherVariable,
)
from skycast.providers.errors import ProviderError
from skycast.providers.open_meteo.forecast import _forecast_days, fetch_forecast


def _run(coro):
    return asyncio.run(coro)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json_handler(status_code: int, body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return handler


def _capturing_handler(body: dict):
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=body)

    return handler, captured


def _location(timezone_name: str | None = "Asia/Kolkata") -> Location:
    return Location(
        id="test:hyderabad",
        name="Hyderabad",
        latitude=17.385,
        longitude=78.4867,
        timezone=timezone_name,
    )


def _window(start: str, end: str) -> TimeWindow:
    return TimeWindow(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end))


def _request(**overrides) -> ForecastRequest:
    defaults = dict(
        granularities={Granularity.HOURLY},
        window=_window("2026-07-08T00:00:00+05:30", "2026-07-08T23:00:00+05:30"),
        variables={WeatherVariable.TEMPERATURE},
    )
    defaults.update(overrides)
    return ForecastRequest(**defaults)


_HOURLY_BLOCK = {
    "time": [
        "2026-07-07T23:00",
        "2026-07-08T00:00",
        "2026-07-08T12:00",
        "2026-07-09T01:00",
    ],
    "temperature_2m": [24.0, 24.5, 31.0, 23.0],
    "apparent_temperature": [25.0, 25.5, 33.0, 24.0],
    "precipitation_probability": [10, 12, 40, 8],
    "precipitation": [0.0, 0.0, 1.2, 0.0],
    "wind_speed_10m": [8.0, 8.5, 12.0, 7.0],
    "weather_code": [1, 1, 61, 0],
}

_DAILY_BLOCK = {
    "time": ["2026-07-07", "2026-07-08", "2026-07-09"],
    "temperature_2m_max": [30.0, 32.0, 29.0],
    "temperature_2m_min": [23.0, 24.0, 22.0],
    "precipitation_probability_max": [15, 45, 20],
    "precipitation_sum": [0.0, 3.2, 0.0],
    "wind_speed_10m_max": [14.0, 16.0, 13.0],
    "weather_code": [1, 61, 2],
    "sunrise": ["2026-07-07T05:45", "2026-07-08T05:45", "2026-07-09T05:46"],
    "sunset": ["2026-07-07T19:05", "2026-07-08T19:05", "2026-07-09T19:04"],
}

_CURRENT_BLOCK = {
    "time": "2026-07-08T12:00",
    "temperature_2m": 31.0,
    "apparent_temperature": 33.0,
    "precipitation": 1.2,
    "wind_speed_10m": 12.0,
    "weather_code": 61,
}


def _full_body(**blocks) -> dict:
    body = {"timezone": "Asia/Kolkata"}
    body.update(blocks)
    return body


def test_query_params_for_multi_block_request_are_correct() -> None:
    handler, captured = _capturing_handler(
        _full_body(current=_CURRENT_BLOCK, hourly=_HOURLY_BLOCK, daily=_DAILY_BLOCK)
    )
    client = _client(handler)
    location = _location()
    request = _request(
        granularities={Granularity.CURRENT, Granularity.HOURLY, Granularity.DAILY},
        variables={WeatherVariable.TEMPERATURE, WeatherVariable.WIND_SPEED},
        window=_window("2026-07-08T00:00:00+05:30", "2026-07-10T00:00:00+05:30"),
    )

    _run(fetch_forecast(client, location, request, now=lambda: datetime(2026, 7, 8, tzinfo=timezone.utc)))

    assert len(captured) == 1
    params = captured[0].url.params
    assert params["latitude"] == "17.385"
    assert params["longitude"] == "78.4867"
    assert params["timezone"] == "Asia/Kolkata"
    assert params["current"] == "weather_code,temperature_2m,wind_speed_10m"
    assert params["hourly"] == "weather_code,temperature_2m,wind_speed_10m"
    assert params["daily"] == (
        "weather_code,sunrise,sunset,temperature_2m_max,temperature_2m_min,wind_speed_10m_max"
    )
    assert "forecast_days" in params
    for override_key in ("temperature_unit", "windspeed_unit", "precipitation_unit"):
        assert override_key not in params


def test_timezone_param_falls_back_to_auto_when_location_has_none() -> None:
    handler, captured = _capturing_handler(_full_body(hourly=_HOURLY_BLOCK))
    client = _client(handler)
    location = _location(timezone_name=None)

    _run(fetch_forecast(client, location, _request()))

    assert captured[0].url.params["timezone"] == "auto"


def test_hourly_parse_zips_readings_by_index_and_maps_weather_code() -> None:
    client = _client(_json_handler(200, _full_body(hourly=_HOURLY_BLOCK)))
    location = _location()
    request = _request(
        window=_window("2026-07-07T00:00:00+05:30", "2026-07-09T23:00:00+05:30"),
        variables={
            WeatherVariable.TEMPERATURE,
            WeatherVariable.FEELS_LIKE,
            WeatherVariable.PRECIP_PROBABILITY,
            WeatherVariable.PRECIP_AMOUNT,
            WeatherVariable.WIND_SPEED,
        },
    )

    forecast = _run(fetch_forecast(client, location, request))

    assert forecast.current is None
    assert forecast.daily is None
    assert len(forecast.hourly) == 4
    first = forecast.hourly[0]
    assert first.temperature == 24.0
    assert first.feels_like == 25.0
    assert first.precip_probability == 10
    assert first.precip_amount == 0.0
    assert first.wind_speed == 8.0
    assert first.condition_code is ConditionCode.MAINLY_CLEAR
    assert forecast.hourly[2].condition_code is ConditionCode.RAIN


def test_hourly_unrequested_optional_fields_are_none() -> None:
    client = _client(_json_handler(200, _full_body(hourly=_HOURLY_BLOCK)))
    location = _location()
    request = _request(variables={WeatherVariable.TEMPERATURE})

    forecast = _run(fetch_forecast(client, location, request))

    reading = forecast.hourly[0]
    assert reading.feels_like is None
    assert reading.precip_probability is None
    assert reading.precip_amount is None
    assert reading.wind_speed is None


def test_window_filtering_excludes_out_of_bounds_hourly_readings() -> None:
    client = _client(_json_handler(200, _full_body(hourly=_HOURLY_BLOCK)))
    location = _location()
    # Window covers only 2026-07-08 00:00 through 12:00 IST -- excludes
    # the 07-07 23:00 and 07-09 01:00 canned timestamps.
    request = _request(
        window=_window("2026-07-08T00:00:00+05:30", "2026-07-08T12:00:00+05:30")
    )

    forecast = _run(fetch_forecast(client, location, request))

    assert len(forecast.hourly) == 2
    assert forecast.hourly[0].temperature == 24.5
    assert forecast.hourly[1].temperature == 31.0


def test_multi_block_request_populates_all_three_blocks() -> None:
    body = _full_body(current=_CURRENT_BLOCK, hourly=_HOURLY_BLOCK, daily=_DAILY_BLOCK)
    client = _client(_json_handler(200, body))
    location = _location()
    request = _request(
        granularities={Granularity.CURRENT, Granularity.HOURLY, Granularity.DAILY},
        window=_window("2026-07-07T00:00:00+05:30", "2026-07-09T23:00:00+05:30"),
    )

    forecast = _run(fetch_forecast(client, location, request))

    assert forecast.current is not None
    assert forecast.hourly is not None
    assert forecast.daily is not None
    assert forecast.current.temperature == 31.0


def test_daily_and_hourly_and_current_always_include_temperature_gap1() -> None:
    body = _full_body(current=_CURRENT_BLOCK, hourly=_HOURLY_BLOCK, daily=_DAILY_BLOCK)
    client = _client(_json_handler(200, body))
    location = _location()
    request = _request(
        granularities={Granularity.CURRENT, Granularity.HOURLY, Granularity.DAILY},
        window=_window("2026-07-07T00:00:00+05:30", "2026-07-09T23:00:00+05:30"),
        # Deliberately doesn't request TEMPERATURE.
        variables={WeatherVariable.WIND_SPEED},
    )

    forecast = _run(fetch_forecast(client, location, request))

    assert forecast.current.temperature == 31.0
    assert forecast.hourly[0].temperature == 24.0
    assert forecast.daily[0].temp_min == 23.0
    assert forecast.daily[0].temp_max == 30.0


def test_current_request_never_sends_precipitation_probability_gap2() -> None:
    handler, captured = _capturing_handler(_full_body(current=_CURRENT_BLOCK))
    client = _client(handler)
    location = _location()
    request = _request(
        granularities={Granularity.CURRENT},
        window=None,
        variables={WeatherVariable.PRECIP_PROBABILITY},
    )

    _run(fetch_forecast(client, location, request))

    assert "precipitation_probability" not in captured[0].url.params["current"]


def test_daily_drops_feels_like_but_hourly_still_populates_it() -> None:
    handler, captured = _capturing_handler(
        _full_body(hourly=_HOURLY_BLOCK, daily=_DAILY_BLOCK)
    )
    client = _client(handler)
    location = _location()
    request = _request(
        granularities={Granularity.HOURLY, Granularity.DAILY},
        window=_window("2026-07-07T00:00:00+05:30", "2026-07-09T23:00:00+05:30"),
        variables={WeatherVariable.FEELS_LIKE},
    )

    forecast = _run(fetch_forecast(client, location, request))

    daily_params_sent = captured[0].url.params["daily"]
    assert "apparent_temperature_max" not in daily_params_sent
    assert "apparent_temperature_min" not in daily_params_sent
    assert forecast.hourly[0].feels_like == 25.0


def test_documented_error_body_raises_provider_error() -> None:
    client = _client(_json_handler(400, {"error": True, "reason": "Invalid latitude"}))
    location = _location()

    with pytest.raises(ProviderError) as exc_info:
        _run(fetch_forecast(client, location, _request(granularities={Granularity.CURRENT}, window=None)))

    assert "Invalid latitude" in str(exc_info.value)


def test_transport_failure_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = _client(handler)
    location = _location()

    with pytest.raises(ProviderError):
        _run(fetch_forecast(client, location, _request(granularities={Granularity.CURRENT}, window=None)))


def test_malformed_response_missing_requested_block_raises_provider_error() -> None:
    # hourly requested but the response body has no "hourly" key.
    client = _client(_json_handler(200, {"timezone": "Asia/Kolkata"}))
    location = _location()

    with pytest.raises(ProviderError):
        _run(fetch_forecast(client, location, _request()))


def test_forecast_days_is_clamped_between_1_and_16() -> None:
    location = _location()
    now = lambda: datetime(2026, 7, 8, tzinfo=timezone.utc)

    short_window = _window("2026-07-08T00:00:00+05:30", "2026-07-08T10:00:00+05:30")
    assert _forecast_days(short_window, now, location) >= 1

    long_window = _window("2026-07-08T00:00:00+05:30", "2026-09-08T00:00:00+05:30")
    assert _forecast_days(long_window, now, location) == 16
