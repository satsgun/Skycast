"""select_provider: the provider-selection seam for pipeline stage 2,
plan (Task 15.2).

Filters registered providers by capability, then ranks survivors and
picks the top. v1 has one provider, so ranking is a trivial identity
function -- but it's a real, separate step (_rank), so the roadmap's
real multi-provider ranking is a change to that function's body, not to
select_provider's callers or filter logic.

Granularity support is NOT filtered in v1 -- ProviderCapabilities
(Task 11, committed) has no per-granularity field, and every provider
today trivially supports current/hourly/daily. Tracked gap (from 8.2):
a future ProviderCapabilities.supported_granularities would turn this
criterion back on here; do not add that field as part of this task.
"""

from datetime import timedelta

from skycast.domain.provider import (
    Granularity,
    ProviderCapabilities,
    TimeWindow,
    WeatherVariable,
)
from skycast.pipeline.errors import NoCapableProviderError
from skycast.providers.base import WeatherProvider


def select_provider(
    required_variables: set[WeatherVariable],
    granularities: set[Granularity],
    window: TimeWindow | None,
    providers: list[WeatherProvider],
    *,
    needs_geocoding: bool,
    horizon_days: int | None,
) -> WeatherProvider:
    """Raises NoCapableProviderError if no provider satisfies the request.

    `needs_geocoding` must come from the same is-this-a-name check that
    decides whether the caller (plan, Task 15.3) emits a GEOCODE call --
    never evaluated independently here. `granularities` is accepted for
    interface stability (see module docstring) but unused today.

    `horizon_days` (Task 21.5, ADR-0006) is the pre-geocode, descriptor-
    implied alternative to `window` for the forecast-horizon check: plan()
    runs before geocoding and never has a concrete window to check, only
    a RelativeTimeSpec's implied day count (see
    resolve_window.implied_horizon_days). Checked independently of
    `window` -- a caller supplies whichever it actually has.
    """
    capable: list[WeatherProvider] = []
    reasons: list[str] = []

    for provider in providers:
        failure = _first_unmet_requirement(
            provider.capabilities(),
            required_variables=required_variables,
            window=window,
            horizon_days=horizon_days,
            needs_geocoding=needs_geocoding,
        )
        if failure is None:
            capable.append(provider)
        else:
            reasons.append(failure)

    if not capable:
        raise NoCapableProviderError(
            "no registered provider satisfies the request's requirements",
            reason=reasons[0] if reasons else "no_providers_registered",
        )

    return _rank(capable)[0]


def _first_unmet_requirement(
    capabilities: ProviderCapabilities,
    *,
    required_variables: set[WeatherVariable],
    window: TimeWindow | None,
    horizon_days: int | None,
    needs_geocoding: bool,
) -> str | None:
    if not required_variables <= capabilities.available_variables:
        return "missing_variables"
    if needs_geocoding and not capabilities.supports_geocoding:
        return "geocoding_not_supported"
    if window is not None and (
        window.end - window.start
    ) > timedelta(days=capabilities.max_forecast_days):
        return "forecast_horizon_too_short"
    if horizon_days is not None and horizon_days > capabilities.max_forecast_days:
        return "forecast_horizon_too_short"
    return None


def _rank(providers: list[WeatherProvider]) -> list[WeatherProvider]:
    """v1 preference rule: trivial, order-preserving (single provider in
    practice). The ranking hook -- swap this body for a real comparator
    when multi-provider selection lands; no caller changes needed.
    """
    return providers
