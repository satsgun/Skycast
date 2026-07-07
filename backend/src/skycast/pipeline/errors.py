"""Typed errors for pipeline stage 2, plan (Task 15.2/15.4).

Raised by select_provider() when no registered provider can satisfy a
request's requirements. The orchestrator (Phase 5) maps this to an SSE
error event.
"""


class NoCapableProviderError(Exception):
    """Raised when no registered WeatherProvider's capabilities() satisfy
    a request's requirements.

    `message` is a human-readable summary. `reason` is an optional short,
    machine-oriented cause identifying which requirement failed (e.g.
    "missing_variables", "geocoding_not_supported",
    "forecast_horizon_too_short", "no_providers_registered") -- cheap to
    compute since it's already known from the filter step that produced
    this error, not separately investigated.
    """

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
