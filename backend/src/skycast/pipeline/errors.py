"""Typed errors for pipeline stage 2, plan (Task 15.2/15.3/15.4).

Raised by select_provider() and plan() when stage 2 cannot produce a
ToolPlan. The orchestrator (Phase 5) maps each to an SSE error event.
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


class NoLocationError(Exception):
    """Raised by plan() when a DataNeedsSpec names no location and no
    default location is available to fall back on.

    `message` is a human-readable summary. `reason` is an optional short,
    machine-oriented cause a caller can branch on without parsing the
    message string.
    """

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
