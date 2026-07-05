import json
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import DailyReading, Forecast, HourlyReading, Units
from skycast.domain.location import Location


def _location() -> Location:
    return Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6)


def _hourly_reading() -> HourlyReading:
    return HourlyReading(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        temperature=20.0,
        condition_code=ConditionCode.CLEAR,
    )


def _daily_reading() -> DailyReading:
    return DailyReading(
        date=date(2024, 1, 1),
        temp_min=10.0,
        temp_max=22.0,
        condition_code=ConditionCode.PARTLY_CLOUDY,
    )


def test_hourly_reading_can_be_constructed_with_only_required_fields() -> None:
    reading = _hourly_reading()
    assert reading.feels_like is None
    assert reading.precip_probability is None
    assert reading.precip_amount is None
    assert reading.wind_speed is None


def test_hourly_reading_missing_temperature_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        HourlyReading(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            condition_code=ConditionCode.CLEAR,
        )


def test_hourly_reading_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HourlyReading(
            timestamp=datetime(2024, 1, 1, 12, 0),  # no tzinfo
            temperature=20.0,
            condition_code=ConditionCode.CLEAR,
        )


def test_hourly_reading_is_frozen() -> None:
    reading = _hourly_reading()
    with pytest.raises(ValidationError):
        reading.temperature = 25.0


def test_daily_reading_can_be_constructed_with_only_required_fields() -> None:
    reading = _daily_reading()
    assert reading.precip_probability is None
    assert reading.precip_amount is None
    assert reading.wind_speed_max is None
    assert reading.sunrise is None
    assert reading.sunset is None


def test_daily_reading_missing_temp_min_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        DailyReading(date=date(2024, 1, 1), temp_max=22.0, condition_code=ConditionCode.CLOUDY)


def test_daily_reading_missing_temp_max_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        DailyReading(date=date(2024, 1, 1), temp_min=10.0, condition_code=ConditionCode.CLOUDY)


def test_daily_reading_naive_sunrise_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DailyReading(
            date=date(2024, 1, 1),
            temp_min=10.0,
            temp_max=22.0,
            condition_code=ConditionCode.CLOUDY,
            sunrise=datetime(2024, 1, 1, 6, 0),  # naive
        )


def test_daily_reading_naive_sunset_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DailyReading(
            date=date(2024, 1, 1),
            temp_min=10.0,
            temp_max=22.0,
            condition_code=ConditionCode.CLOUDY,
            sunset=datetime(2024, 1, 1, 18, 0),  # naive
        )


def test_daily_reading_is_frozen() -> None:
    reading = _daily_reading()
    with pytest.raises(ValidationError):
        reading.temp_min = 5.0


def test_units_default_values_match_canonical_v1_constants() -> None:
    units = Units()
    assert units.temperature == "celsius"
    assert units.wind_speed == "kmh"
    assert units.precip_amount == "mm"
    assert units.precip_probability == "percent"


def test_units_serializes_with_fixed_canonical_values() -> None:
    assert Units().model_dump() == {
        "temperature": "celsius",
        "wind_speed": "kmh",
        "precip_amount": "mm",
        "precip_probability": "percent",
    }


def test_units_is_frozen() -> None:
    units = Units()
    with pytest.raises(ValidationError):
        units.temperature = "fahrenheit"


def test_forecast_with_only_hourly_populated_is_valid() -> None:
    forecast = Forecast(location=_location(), units=Units(), hourly=[_hourly_reading()])
    assert forecast.current is None
    assert forecast.daily is None
    assert forecast.hourly == [_hourly_reading()]


def test_forecast_with_only_daily_populated_is_valid() -> None:
    forecast = Forecast(location=_location(), units=Units(), daily=[_daily_reading()])
    assert forecast.current is None
    assert forecast.hourly is None


def test_forecast_with_only_current_populated_is_valid() -> None:
    forecast = Forecast(location=_location(), units=Units(), current=_hourly_reading())
    assert forecast.hourly is None
    assert forecast.daily is None


def test_forecast_with_all_blocks_none_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        Forecast(location=_location(), units=Units())


def test_condition_code_round_trips_as_string_value_through_json() -> None:
    reading = _hourly_reading()
    payload = json.loads(reading.model_dump_json())
    assert payload["condition_code"] == "CLEAR"
    restored = HourlyReading.model_validate_json(reading.model_dump_json())
    assert restored.condition_code is ConditionCode.CLEAR


def test_hourly_only_forecast_round_trips_through_json() -> None:
    forecast = Forecast(location=_location(), units=Units(), hourly=[_hourly_reading()])
    restored = Forecast.model_validate_json(forecast.model_dump_json())
    assert restored == forecast


def test_daily_only_forecast_round_trips_through_json() -> None:
    forecast = Forecast(location=_location(), units=Units(), daily=[_daily_reading()])
    restored = Forecast.model_validate_json(forecast.model_dump_json())
    assert restored == forecast


def test_all_blocks_forecast_round_trips_through_json() -> None:
    forecast = Forecast(
        location=_location(),
        units=Units(),
        current=_hourly_reading(),
        hourly=[_hourly_reading()],
        daily=[_daily_reading()],
    )
    restored = Forecast.model_validate_json(forecast.model_dump_json())
    assert restored == forecast


def test_forecast_is_frozen() -> None:
    forecast = Forecast(location=_location(), units=Units(), hourly=[_hourly_reading()])
    with pytest.raises(ValidationError):
        forecast.hourly = None
