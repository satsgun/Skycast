"""Unit tests for eval/harness/grounding.py's derive_facts (Task E4.1)."""

from datetime import date, datetime, timezone

import pytest

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import DailyReading, Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.sse.payloads import ForecastBlock, ReadingLocator

from eval.harness.grounding import derive_facts

_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def _location() -> Location:
    return Location(id="test:x", name="X", latitude=0.0, longitude=0.0)


def _hourly(
    *,
    temperature: float = 20.0,
    precip_probability: float | None = 10.0,
    wind_speed: float | None = 5.0,
    condition_code: ConditionCode = ConditionCode.CLEAR,
    timestamp: datetime = _NOW,
) -> HourlyReading:
    return HourlyReading(
        timestamp=timestamp,
        temperature=temperature,
        precip_probability=precip_probability,
        wind_speed=wind_speed,
        condition_code=condition_code,
    )


def _daily(
    *,
    temp_max: float = 20.0,
    temp_min: float = 10.0,
    precip_probability: float | None = 10.0,
    wind_speed_max: float | None = 5.0,
    condition_code: ConditionCode = ConditionCode.CLEAR,
    day: date = date(2026, 7, 18),
) -> DailyReading:
    return DailyReading(
        date=day,
        temp_min=temp_min,
        temp_max=temp_max,
        precip_probability=precip_probability,
        wind_speed_max=wind_speed_max,
        condition_code=condition_code,
    )


def _forecast(*, current=None, hourly=None, daily=None) -> Forecast:
    return Forecast(location=_location(), units=Units(), current=current, hourly=hourly, daily=daily)


# --- reading selection ---


def test_no_locator_uses_current_when_present() -> None:
    forecast = _forecast(
        current=_hourly(temperature=5.0), hourly=[_hourly(temperature=99.0)]
    )
    facts = derive_facts(forecast)
    assert facts.temperature_band == "cold"


def test_no_locator_falls_back_to_first_hourly_when_no_current() -> None:
    forecast = _forecast(hourly=[_hourly(temperature=5.0), _hourly(temperature=99.0)])
    facts = derive_facts(forecast)
    assert facts.temperature_band == "cold"


def test_no_locator_falls_back_to_first_daily_when_no_current_or_hourly() -> None:
    forecast = _forecast(daily=[_daily(temp_max=5.0), _daily(temp_max=99.0)])
    facts = derive_facts(forecast)
    assert facts.temperature_band == "cold"


def test_locator_current_is_honored() -> None:
    forecast = _forecast(
        current=_hourly(temperature=5.0), hourly=[_hourly(temperature=99.0)]
    )
    locator = ReadingLocator(block=ForecastBlock.CURRENT)
    facts = derive_facts(forecast, locator)
    assert facts.temperature_band == "cold"


def test_locator_hourly_nonzero_index_is_honored() -> None:
    forecast = _forecast(
        hourly=[_hourly(temperature=99.0), _hourly(temperature=5.0)]
    )
    locator = ReadingLocator(block=ForecastBlock.HOURLY, index=1)
    facts = derive_facts(forecast, locator)
    assert facts.temperature_band == "cold"


def test_locator_daily_nonzero_index_is_honored() -> None:
    forecast = _forecast(daily=[_daily(temp_max=99.0), _daily(temp_max=5.0)])
    locator = ReadingLocator(block=ForecastBlock.DAILY, index=1)
    facts = derive_facts(forecast, locator)
    assert facts.temperature_band == "cold"


# --- rain_likely ---


def test_rain_likely_true_at_80_percent() -> None:
    forecast = _forecast(current=_hourly(precip_probability=80.0))
    assert derive_facts(forecast).rain_likely is True


def test_rain_likely_false_below_threshold() -> None:
    forecast = _forecast(current=_hourly(precip_probability=20.0))
    assert derive_facts(forecast).rain_likely is False


def test_rain_likely_true_at_exact_threshold() -> None:
    forecast = _forecast(current=_hourly(precip_probability=50.0))
    assert derive_facts(forecast).rain_likely is True


def test_rain_likely_none_when_precip_probability_missing() -> None:
    forecast = _forecast(current=_hourly(precip_probability=None))
    assert derive_facts(forecast).rain_likely is None


# --- temperature_band ---


def test_temperature_band_cold_at_5_degrees() -> None:
    forecast = _forecast(current=_hourly(temperature=5.0))
    assert derive_facts(forecast).temperature_band == "cold"


@pytest.mark.parametrize(
    "temperature,expected",
    [
        (9.9, "cold"),
        (10.0, "mild"),
        (19.9, "mild"),
        (20.0, "warm"),
        (27.9, "warm"),
        (28.0, "hot"),
        (35.0, "hot"),
    ],
)
def test_temperature_band_boundaries(temperature: float, expected: str) -> None:
    forecast = _forecast(current=_hourly(temperature=temperature))
    assert derive_facts(forecast).temperature_band == expected


def test_temperature_band_uses_temp_max_for_daily_reading() -> None:
    forecast = _forecast(daily=[_daily(temp_min=-5.0, temp_max=30.0)])
    assert derive_facts(forecast).temperature_band == "hot"


# --- condition_family ---


def test_condition_family_rain_for_rain_code() -> None:
    forecast = _forecast(current=_hourly(condition_code=ConditionCode.RAIN))
    assert derive_facts(forecast).condition_family == "rain"


@pytest.mark.parametrize("code", list(ConditionCode))
def test_condition_family_is_total_over_every_condition_code(code: ConditionCode) -> None:
    forecast = _forecast(current=_hourly(condition_code=code))
    family = derive_facts(forecast).condition_family
    assert family in {"clear", "cloud", "rain", "snow", "storm", "unknown"}


# --- windy ---


def test_windy_true_above_threshold() -> None:
    forecast = _forecast(current=_hourly(wind_speed=40.0))
    assert derive_facts(forecast).windy is True


def test_windy_false_below_threshold() -> None:
    forecast = _forecast(current=_hourly(wind_speed=5.0))
    assert derive_facts(forecast).windy is False


def test_windy_none_when_wind_speed_missing() -> None:
    forecast = _forecast(current=_hourly(wind_speed=None))
    assert derive_facts(forecast).windy is None


def test_windy_uses_wind_speed_max_for_daily_reading() -> None:
    forecast = _forecast(daily=[_daily(wind_speed_max=40.0)])
    assert derive_facts(forecast).windy is True
