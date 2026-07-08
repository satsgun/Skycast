"""Open-Meteo forecast fetch + parse (Task 19.4).

Standalone async function, not yet a WeatherProvider method -- see
geocode.py's docstring for why (OpenMeteoProvider needs capabilities()
(19.5) too before it can be instantiated as an ABC subclass).
"""

from collections.abc import Callable
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from skycast.domain.forecast import DailyReading, Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    TimeWindow,
    WeatherVariable,
)
from skycast.providers.errors import ProviderError
from skycast.providers.open_meteo._http import get_json
from skycast.providers.open_meteo.conditions import map_condition_code
from skycast.providers.open_meteo.variables import (
    current_params,
    daily_params,
    hourly_params,
)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_MAX_FORECAST_DAYS = 16


async def fetch_forecast(
    client: httpx.AsyncClient,
    location: Location,
    request: ForecastRequest,
    *,
    now: Callable[[], datetime] | None = None,
) -> Forecast:
    now = now if now is not None else (lambda: datetime.now(timezone.utc))
    params = _build_params(location, request, now)
    body = await get_json(client, _FORECAST_URL, params=params)

    try:
        tz = ZoneInfo(body["timezone"])
        current = hourly = daily = None
        if Granularity.CURRENT in request.granularities:
            current = _parse_current(body["current"], request.variables, tz)
        if Granularity.HOURLY in request.granularities:
            assert request.window is not None  # ForecastRequest guarantees this
            hourly = _parse_hourly(
                body["hourly"], request.variables, tz, request.window
            )
        if Granularity.DAILY in request.granularities:
            assert request.window is not None
            daily = _parse_daily(body["daily"], request.variables, tz, request.window)
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ProviderError(
            "Open-Meteo forecast response did not match the expected shape",
            reason="malformed_response",
        ) from exc

    return Forecast(
        location=location, units=Units(), current=current, hourly=hourly, daily=daily
    )


def _build_params(
    location: Location, request: ForecastRequest, now: Callable[[], datetime]
) -> dict:
    params: dict = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "timezone": location.timezone if location.timezone is not None else "auto",
    }
    if Granularity.CURRENT in request.granularities:
        params["current"] = ",".join(current_params(request.variables))
    if Granularity.HOURLY in request.granularities:
        params["hourly"] = ",".join(hourly_params(request.variables))
    if Granularity.DAILY in request.granularities:
        params["daily"] = ",".join(daily_params(request.variables))
    if request.window is not None:
        params["forecast_days"] = _forecast_days(request.window, now, location)
    return params


def _forecast_days(
    window: TimeWindow, now: Callable[[], datetime], location: Location
) -> int:
    tz = ZoneInfo(location.timezone) if location.timezone is not None else timezone.utc
    today = now().astimezone(tz).date()
    end_date = window.end.astimezone(tz).date()
    return max(1, min((end_date - today).days + 1, _MAX_FORECAST_DAYS))


def _parse_local_dt(value: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=tz)


def _parse_current(
    current: dict, variables: set[WeatherVariable], tz: ZoneInfo
) -> HourlyReading:
    return HourlyReading(
        timestamp=_parse_local_dt(current["time"], tz),
        temperature=current["temperature_2m"],
        feels_like=(
            current.get("apparent_temperature")
            if WeatherVariable.FEELS_LIKE in variables
            else None
        ),
        precip_amount=(
            current.get("precipitation")
            if WeatherVariable.PRECIP_AMOUNT in variables
            else None
        ),
        wind_speed=(
            current.get("wind_speed_10m")
            if WeatherVariable.WIND_SPEED in variables
            else None
        ),
        condition_code=map_condition_code(current["weather_code"]),
    )


def _parse_hourly(
    hourly: dict, variables: set[WeatherVariable], tz: ZoneInfo, window: TimeWindow
) -> list[HourlyReading]:
    readings = []
    for i, time_str in enumerate(hourly["time"]):
        timestamp = _parse_local_dt(time_str, tz)
        if not (window.start <= timestamp <= window.end):
            continue
        readings.append(
            HourlyReading(
                timestamp=timestamp,
                temperature=hourly["temperature_2m"][i],
                feels_like=(
                    hourly["apparent_temperature"][i]
                    if WeatherVariable.FEELS_LIKE in variables
                    else None
                ),
                precip_probability=(
                    hourly["precipitation_probability"][i]
                    if WeatherVariable.PRECIP_PROBABILITY in variables
                    else None
                ),
                precip_amount=(
                    hourly["precipitation"][i]
                    if WeatherVariable.PRECIP_AMOUNT in variables
                    else None
                ),
                wind_speed=(
                    hourly["wind_speed_10m"][i]
                    if WeatherVariable.WIND_SPEED in variables
                    else None
                ),
                condition_code=map_condition_code(hourly["weather_code"][i]),
            )
        )
    return readings


def _parse_daily(
    daily: dict, variables: set[WeatherVariable], tz: ZoneInfo, window: TimeWindow
) -> list[DailyReading]:
    start_date = window.start.astimezone(tz).date()
    end_date = window.end.astimezone(tz).date()
    readings = []
    for i, date_str in enumerate(daily["time"]):
        day = date.fromisoformat(date_str)
        if not (start_date <= day <= end_date):
            continue
        readings.append(
            DailyReading(
                date=day,
                temp_min=daily["temperature_2m_min"][i],
                temp_max=daily["temperature_2m_max"][i],
                precip_probability=(
                    daily["precipitation_probability_max"][i]
                    if WeatherVariable.PRECIP_PROBABILITY in variables
                    else None
                ),
                precip_amount=(
                    daily["precipitation_sum"][i]
                    if WeatherVariable.PRECIP_AMOUNT in variables
                    else None
                ),
                wind_speed_max=(
                    daily["wind_speed_10m_max"][i]
                    if WeatherVariable.WIND_SPEED in variables
                    else None
                ),
                condition_code=map_condition_code(daily["weather_code"][i]),
                sunrise=_parse_local_dt(daily["sunrise"][i], tz),
                sunset=_parse_local_dt(daily["sunset"][i], tz),
            )
        )
    return readings
