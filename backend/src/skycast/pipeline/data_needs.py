"""DataNeedsSpec: the provider-neutral output of pipeline stage 1,
decompose (Task 14.1, revised by Task 14.8 for multi-location support).

The structured artifact carried through the rest of the pipeline: stage
2 (plan) turns it into executable ForecastRequest(s) -- reading
`location_names` to decide fan-out, one geocode->forecast chain per
named location, run in parallel for a comparison; stage 4 (synthesize)
reads `intent` from it. Distinct from ForecastRequest even though
several fields mirror it one-for-one -- this type is provider-neutral
*intent about data*, not a request a WeatherProvider can execute
directly (e.g. entries in `location_names` are strings the query named,
not resolved Locations).
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

    `location_names` cardinality is the single source of truth for
    location resolution: empty means no location was named (use the
    default location); one entry is the normal case; two or more means a
    comparison, and must pair with intent=COMPARISON (enforced below).
    window is required whenever granularities includes HOURLY or DAILY;
    may be omitted for CURRENT-only, mirroring ForecastRequest.
    """

    model_config = ConfigDict(frozen=True)

    location_names: list[str]
    granularities: set[Granularity] = Field(min_length=1)
    window: TimeWindow | None = None
    variables: set[WeatherVariable] = Field(min_length=1)
    intent: QueryIntent

    @property
    def use_default_location(self) -> bool:
        """Derived, not stored -- true iff no location was named."""
        return len(self.location_names) == 0

    @model_validator(mode="after")
    def _require_window_for_hourly_or_daily(self) -> "DataNeedsSpec":
        needs_window = {Granularity.HOURLY, Granularity.DAILY} & self.granularities
        if needs_window and self.window is None:
            raise ValueError(
                "window is required when granularities includes HOURLY or DAILY"
            )
        return self

    @model_validator(mode="after")
    def _require_location_count_consistent_with_intent(self) -> "DataNeedsSpec":
        if self.intent == QueryIntent.COMPARISON and len(self.location_names) < 2:
            raise ValueError(
                "intent=COMPARISON requires at least two location_names"
            )
        if self.intent != QueryIntent.COMPARISON and len(self.location_names) > 1:
            raise ValueError(
                "location_names may hold at most one entry unless intent=COMPARISON"
            )
        return self
