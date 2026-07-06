"""DataNeedsSpec: the provider-neutral output of pipeline stage 1,
decompose (Task 14.1).

The structured artifact carried through the rest of the pipeline: stage
2 (plan) turns it into executable ForecastRequest(s); stage 4
(synthesize) reads `intent` from it. Distinct from ForecastRequest even
though several fields mirror it one-for-one -- this type is
provider-neutral *intent about data*, not a request a WeatherProvider
can execute directly (e.g. `location_name` is a string the query named,
not a resolved Location).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from skycast.domain.provider import Granularity, TimeWindow, WeatherVariable


class QueryIntent(StrEnum):
    DECISION = "DECISION"
    CONDITIONS = "CONDITIONS"
    OUTLOOK = "OUTLOOK"
    COMPARISON = "COMPARISON"


class DataNeedsSpec(BaseModel):
    """Provider-neutral data needs extracted from a natural-language query.

    window is required whenever granularities includes HOURLY or DAILY;
    may be omitted for CURRENT-only, mirroring ForecastRequest.
    """

    model_config = ConfigDict(frozen=True)

    location_name: str | None = None
    use_default_location: bool
    granularities: set[Granularity] = Field(min_length=1)
    window: TimeWindow | None = None
    variables: set[WeatherVariable] = Field(min_length=1)
    intent: QueryIntent

    @model_validator(mode="after")
    def _require_window_for_hourly_or_daily(self) -> "DataNeedsSpec":
        needs_window = {Granularity.HOURLY, Granularity.DAILY} & self.granularities
        if needs_window and self.window is None:
            raise ValueError(
                "window is required when granularities includes HOURLY or DAILY"
            )
        return self
