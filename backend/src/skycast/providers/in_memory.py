"""In-memory WeatherProvider fake for offline, deterministic testing
(ADR-0002, Task 12).

Returns fixed-shape, realistic-ish Forecast data with no network I/O, so
the decompose -> plan -> execute -> synthesize pipeline and the SSE
orchestrator can run entirely offline and reproducibly -- the basis of the
evaluation harness. Ships a small built-in dataset (single-match
"hyderabad", multi-match "springfield") and accepts constructor-injected
locations/forecasts for exact test scenarios, or can be made to raise
ProviderError on demand to drive the provider-failure branch. Never
imports OpenMeteoProvider or performs HTTP I/O.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
import math
import zlib
from zoneinfo import ZoneInfo

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import DailyReading, Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    ProviderCapabilities,
    TimeWindow,
    WeatherVariable,
)
from skycast.providers.base import WeatherProvider
from skycast.providers.errors import ProviderError

_CONDITION_ROTATION: tuple[ConditionCode, ...] = (
    ConditionCode.CLEAR,
    ConditionCode.PARTLY_CLOUDY,
    ConditionCode.RAIN,
)

_DIURNAL_AMPLITUDE_C = 6.0
_DIURNAL_PEAK_HOUR = 15.0  # local hour of day with the warmest temperature

_DAY_DRIFT_AMPLITUDE_C = 3.0
_DAY_DRIFT_PERIOD_DAYS = 5.0

# Only the three ConditionCode members in _CONDITION_ROTATION ever reach
# these lookups, so they don't need to cover all ConditionCode members.
_CONDITION_PRECIP_PROBABILITY_BASE: dict[ConditionCode, float] = {
    ConditionCode.CLEAR: 5.0,
    ConditionCode.PARTLY_CLOUDY: 20.0,
    ConditionCode.RAIN: 70.0,
}

_CONDITION_PRECIP_AMOUNT_BASE: dict[ConditionCode, float] = {
    ConditionCode.CLEAR: 0.0,
    ConditionCode.PARTLY_CLOUDY: 0.0,
    ConditionCode.RAIN: 2.0,
}


def _default_locations() -> dict[str, list[Location]]:
    return {
        "hyderabad": [
            Location(
                id="in-memory:hyderabad-in",
                name="Hyderabad",
                latitude=17.385,
                longitude=78.4867,
                country="India",
                country_code="IN",
                admin1="Telangana",
                population=6809970,
                timezone="Asia/Kolkata",
            ),
        ],
        "springfield": [
            Location(
                id="in-memory:springfield-il-us",
                name="Springfield",
                latitude=39.7817,
                longitude=-89.6501,
                country="United States",
                country_code="US",
                admin1="Illinois",
                population=114230,
                timezone="America/Chicago",
            ),
            Location(
                id="in-memory:springfield-mo-us",
                name="Springfield",
                latitude=37.2090,
                longitude=-93.2923,
                country="United States",
                country_code="US",
                admin1="Missouri",
                population=169176,
                timezone="America/Chicago",
            ),
            Location(
                id="in-memory:springfield-ma-us",
                name="Springfield",
                latitude=42.1015,
                longitude=-72.5898,
                country="United States",
                country_code="US",
                admin1="Massachusetts",
                population=155929,
                timezone="America/New_York",
            ),
        ],
    }


def _stable_fraction(seed: str) -> float:
    """Deterministic value in [0, 1) derived from `seed` via CRC32 -- stable
    across processes and Python versions, unlike str hash() (randomized
    per-process for security). Not for security use; only for spreading
    generated values.
    """
    return zlib.crc32(seed.encode("utf-8")) / 2**32


def _local_time(timestamp: datetime, location: Location) -> datetime:
    if location.timezone is None:
        return timestamp.astimezone(timezone.utc)
    return timestamp.astimezone(ZoneInfo(location.timezone))


def _base_temperature(location: Location) -> float:
    return 28.0 - 0.35 * abs(location.latitude)


def _day_drift(location: Location, day: date) -> float:
    phase_seed = _stable_fraction(f"{location.id}:day-phase")
    phase = 2 * math.pi * (day.toordinal() / _DAY_DRIFT_PERIOD_DAYS + phase_seed)
    return _DAY_DRIFT_AMPLITUDE_C * math.sin(phase)


def _temperature_at(location: Location, timestamp: datetime) -> float:
    local_time = _local_time(timestamp, location)
    day_base = _base_temperature(location) + _day_drift(location, local_time.date())
    hour_fraction = local_time.hour + local_time.minute / 60.0
    phase = 2 * math.pi * (hour_fraction - _DIURNAL_PEAK_HOUR) / 24.0
    return round(day_base + _DIURNAL_AMPLITUDE_C * math.cos(phase), 1)


def _daily_temperature_range(location: Location, day: date) -> tuple[float, float]:
    day_base = _base_temperature(location) + _day_drift(location, day)
    return (
        round(day_base - _DIURNAL_AMPLITUDE_C, 1),
        round(day_base + _DIURNAL_AMPLITUDE_C, 1),
    )


def _condition_at(location: Location, moment: str) -> ConditionCode:
    seed = f"{location.id}:{moment}:condition"
    index = int(_stable_fraction(seed) * len(_CONDITION_ROTATION))
    return _CONDITION_ROTATION[index]


def _feels_like_at(temperature: float, seed: str) -> float:
    return round(temperature - _stable_fraction(f"{seed}:feels_like") * 2.0, 1)


def _precip_probability_at(condition: ConditionCode, seed: str) -> float:
    base = _CONDITION_PRECIP_PROBABILITY_BASE[condition]
    jitter = _stable_fraction(f"{seed}:precip_probability") * 20.0
    return round(min(base + jitter, 100.0), 1)


def _precip_amount_at(condition: ConditionCode, seed: str) -> float:
    base = _CONDITION_PRECIP_AMOUNT_BASE[condition]
    if base == 0.0:
        return 0.0
    jitter = _stable_fraction(f"{seed}:precip_amount") * 3.0
    return round(base + jitter, 1)


def _wind_speed_at(seed: str) -> float:
    return round(6.0 + _stable_fraction(f"{seed}:wind_speed") * 14.0, 1)


def _hourly_timestamps(window: TimeWindow) -> list[datetime]:
    timestamps = []
    current = window.start
    while current <= window.end:
        timestamps.append(current)
        current += timedelta(hours=1)
    return timestamps


def _spanned_dates(window: TimeWindow, location: Location) -> list[date]:
    start_date = _local_time(window.start, location).date()
    end_date = _local_time(window.end, location).date()
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _generate_hourly_reading(
    location: Location, timestamp: datetime, variables: set[WeatherVariable]
) -> HourlyReading:
    condition = _condition_at(location, timestamp.isoformat())
    temperature = _temperature_at(location, timestamp)
    seed = f"{location.id}:{timestamp.isoformat()}"
    return HourlyReading(
        timestamp=timestamp,
        temperature=temperature,
        condition_code=condition,
        feels_like=(
            _feels_like_at(temperature, seed)
            if WeatherVariable.FEELS_LIKE in variables
            else None
        ),
        precip_probability=(
            _precip_probability_at(condition, seed)
            if WeatherVariable.PRECIP_PROBABILITY in variables
            else None
        ),
        precip_amount=(
            _precip_amount_at(condition, seed)
            if WeatherVariable.PRECIP_AMOUNT in variables
            else None
        ),
        wind_speed=(
            _wind_speed_at(seed) if WeatherVariable.WIND_SPEED in variables else None
        ),
    )


def _generate_daily_reading(
    location: Location, day: date, variables: set[WeatherVariable]
) -> DailyReading:
    condition = _condition_at(location, day.isoformat())
    temp_min, temp_max = _daily_temperature_range(location, day)
    seed = f"{location.id}:{day.isoformat()}"
    return DailyReading(
        date=day,
        temp_min=temp_min,
        temp_max=temp_max,
        condition_code=condition,
        precip_probability=(
            _precip_probability_at(condition, seed)
            if WeatherVariable.PRECIP_PROBABILITY in variables
            else None
        ),
        precip_amount=(
            _precip_amount_at(condition, seed)
            if WeatherVariable.PRECIP_AMOUNT in variables
            else None
        ),
        wind_speed_max=(
            _wind_speed_at(seed) if WeatherVariable.WIND_SPEED in variables else None
        ),
    )


class InMemoryProvider(WeatherProvider):
    """Deterministic WeatherProvider fake -- no network I/O.

    `locations` maps a lowercased query name to its candidate Locations
    (defaults to a small built-in dataset covering a single-match and a
    multi-match case). `forecasts` optionally maps a Location id to a
    fixed Forecast to return verbatim; any location not present there
    gets a realistic-ish Forecast generated on demand. `fail_geocode` /
    `fail_forecast` make the corresponding method raise ProviderError,
    for exercising the provider-failure branch. `now` is consulted only
    for a window-less CURRENT-only request, so tests can pin "now".
    """

    def __init__(
        self,
        locations: dict[str, list[Location]] | None = None,
        forecasts: dict[str, Forecast] | None = None,
        fail_forecast: bool = False,
        fail_geocode: bool = False,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._locations = locations if locations is not None else _default_locations()
        self._forecasts = forecasts if forecasts is not None else {}
        self._fail_forecast = fail_forecast
        self._fail_geocode = fail_geocode
        self._now = now if now is not None else lambda: datetime.now(timezone.utc)

    async def geocode(self, name: str) -> list[Location]:
        if self._fail_geocode:
            raise ProviderError(
                "in-memory provider configured to fail geocode",
                reason="simulated geocode failure",
            )
        key = name.strip().lower()
        return list(self._locations.get(key, []))

    async def fetch_forecast(
        self, location: Location, request: ForecastRequest
    ) -> Forecast:
        if self._fail_forecast:
            raise ProviderError(
                "in-memory provider configured to fail fetch_forecast",
                reason="simulated provider outage",
            )

        fixed = self._forecasts.get(location.id)
        if fixed is not None:
            return fixed

        current = None
        hourly = None
        daily = None

        if Granularity.CURRENT in request.granularities:
            timestamp = (
                request.window.start if request.window is not None else self._now()
            )
            current = _generate_hourly_reading(location, timestamp, request.variables)

        if Granularity.HOURLY in request.granularities:
            window = request.window
            assert window is not None  # guaranteed by ForecastRequest validation
            hourly = [
                _generate_hourly_reading(location, timestamp, request.variables)
                for timestamp in _hourly_timestamps(window)
            ]

        if Granularity.DAILY in request.granularities:
            window = request.window
            assert window is not None  # guaranteed by ForecastRequest validation
            daily = [
                _generate_daily_reading(location, day, request.variables)
                for day in _spanned_dates(window, location)
            ]

        return Forecast(
            location=location,
            units=Units(),
            current=current,
            hourly=hourly,
            daily=daily,
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            max_forecast_days=16,
            available_variables=set(WeatherVariable),
            supports_geocoding=True,
        )
