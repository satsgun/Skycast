"""Canonical, provider-agnostic forecast schema (ADR-0002).

Every WeatherProvider normalizes its native response into these types, and
everything above this seam (agent, SSE payload, UI) reasons only in this
vocabulary. Do not introduce provider-specific field names, non-canonical
units, or provider weather codes here or above this module.

Composes ConditionCode (Task 8) and Location (Task 9); imports nothing else
from the app.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from skycast.domain.conditions import ConditionCode
from skycast.domain.location import Location


class HourlyReading(BaseModel):
    """Instantaneous conditions at a point in time; also used for 'current'."""

    model_config = ConfigDict(frozen=True)

    timestamp: AwareDatetime
    temperature: float  # Celsius
    feels_like: float | None = None  # Celsius
    precip_probability: float | None = None  # Percent, 0-100
    precip_amount: float | None = None  # Millimetres, for the hour
    wind_speed: float | None = None  # km/h
    condition_code: ConditionCode


class DailyReading(BaseModel):
    """Aggregated conditions across a calendar date."""

    model_config = ConfigDict(frozen=True)

    date: date  # Local calendar date
    temp_min: float  # Celsius
    temp_max: float  # Celsius
    precip_probability: float | None = None  # Percent, 0-100
    precip_amount: float | None = None  # Millimetres, summed for the day
    wind_speed_max: float | None = None  # km/h
    condition_code: ConditionCode  # Representative for the day
    sunrise: AwareDatetime | None = None
    sunset: AwareDatetime | None = None


class Units(BaseModel):
    """Documents the canonical units used throughout the schema (fixed v1)."""

    model_config = ConfigDict(frozen=True)

    temperature: str = "celsius"
    wind_speed: str = "kmh"
    precip_amount: str = "mm"
    precip_probability: str = "percent"


class Forecast(BaseModel):
    """Top-level object returned by WeatherProvider.fetch_forecast()."""

    model_config = ConfigDict(frozen=True)

    location: Location
    units: Units
    current: HourlyReading | None = None
    hourly: list[HourlyReading] | None = None
    daily: list[DailyReading] | None = None

    @model_validator(mode="after")
    def _require_at_least_one_data_block(self) -> "Forecast":
        if self.current is None and self.hourly is None and self.daily is None:
            raise ValueError(
                "Forecast must populate at least one of current, hourly, or daily"
            )
        return self
