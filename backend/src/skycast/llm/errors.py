"""Typed errors for the LLMClient seam (Task 14.2).

Raised by LLMClient.get_structured() implementations. Kept as two
separate, non-overlapping exception types (neither subclasses the
other) so a caller -- e.g. the stage-1 decompose orchestrator -- can
catch and map each to a distinct SSE error kind without accidentally
catching one while meaning to catch only the other.
"""


class LLMError(Exception):
    """Raised on transport failure (the call to the model itself failed).

    `message` is a human-readable summary. `reason` is an optional short,
    machine-oriented cause (e.g. "timeout", "http_5xx") a caller can
    branch on without parsing the message string.
    """

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class StructuredOutputError(Exception):
    """Raised when the model cannot produce schema-valid output after the
    one allowed repair retry (transport itself succeeded).

    `message` is a human-readable summary. `reason` is an optional short,
    machine-oriented cause a caller can branch on without parsing the
    message string.
    """

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
