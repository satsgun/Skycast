"""Provider-agnostic request/capability vocabulary for the WeatherProvider
seam (ADR-0002, Task 11).

These are the small value types WeatherProvider.fetch_forecast() and
capabilities() speak in: what a caller asks for (ForecastRequest, built
from Granularity / WeatherVariable / TimeWindow) and what a provider
declares it can do (ProviderCapabilities). Every concrete provider
translates its own request/response shape to and from these types;
nothing provider-specific belongs here.

Self-contained: imports nothing else from the app.
"""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Granularity(StrEnum):
    CURRENT = "CURRENT"
    HOURLY = "HOURLY"
    DAILY = "DAILY"


class WeatherVariable(StrEnum):
    TEMPERATURE = "TEMPERATURE"
    FEELS_LIKE = "FEELS_LIKE"
    PRECIP_PROBABILITY = "PRECIP_PROBABILITY"
    PRECIP_AMOUNT = "PRECIP_AMOUNT"
    WIND_SPEED = "WIND_SPEED"
    CONDITION = "CONDITION"


class TimeWindow(BaseModel):
    """An inclusive [start, end] span.

    Covers both hourly bounds (used directly) and daily bounds (the
    provider derives spanned calendar dates from them); which
    interpretation applies is carried by the request's granularities.
    """

    model_config = ConfigDict(frozen=True)

    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _require_end_not_before_start(self) -> "TimeWindow":
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


class ForecastRequest(BaseModel):
    """What fetch_forecast() is asked for. window is required whenever
    granularities includes HOURLY or DAILY; may be omitted for CURRENT-only.
    """

    model_config = ConfigDict(frozen=True)

    granularities: set[Granularity] = Field(min_length=1)
    window: TimeWindow | None = None
    variables: set[WeatherVariable] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_window_for_hourly_or_daily(self) -> "ForecastRequest":
        needs_window = {Granularity.HOURLY, Granularity.DAILY} & self.granularities
        if needs_window and self.window is None:
            raise ValueError(
                "window is required when granularities includes HOURLY or DAILY"
            )
        return self


class ProviderCapabilities(BaseModel):
    """Static (v1) declaration of what a provider can do."""

    model_config = ConfigDict(frozen=True)

    max_forecast_days: int
    available_variables: set[WeatherVariable]
    supports_geocoding: bool
    rate_limit_per_minute: int | None = None
