"""Provider-neutral error type for the WeatherProvider seam (ADR-0002,
Task 11).

Raised by WeatherProvider.geocode()/fetch_forecast() when the underlying
provider is unreachable or returns a malformed response. Stage 3 maps
this to the `provider_unreachable` SSE error event; must never leak
provider-specific detail — that translation happens in the concrete
provider before it escapes the seam.
"""


class ProviderError(Exception):
    """Raised when a WeatherProvider cannot fulfill a request.

    `message` is a human-readable summary. `reason` is an optional short,
    machine-oriented cause (e.g. "timeout", "http_5xx") a caller can
    branch on without parsing the message string.
    """

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
