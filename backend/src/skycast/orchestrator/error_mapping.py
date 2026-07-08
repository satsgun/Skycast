"""map_error: central exception -> ErrorPayload mapping (Task 18.2).

The one place every raised exception from decompose/plan/synthesize
funnels through before reaching the SSE wire (run_query, Task 18.3) --
nothing escapes unmapped, thanks to the catch-all branch. Pure function,
no I/O, unit-testable in isolation.

execute()'s Failed outcome (Task 16) is NOT handled here -- it's an
ExecutionResult variant with an ErrorKind already attached (Failed.kind),
not a raised exception; run_query maps it directly, without calling
map_error.
"""

from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.pipeline.errors import NoCapableProviderError, NoLocationError
from skycast.sse.payloads import ErrorKind, ErrorPayload

_GENERIC_MESSAGE = "An unexpected error occurred."


def map_error(exc: Exception) -> ErrorPayload:
    """Maps a raised pipeline exception to an SSE ErrorPayload.

    NoCapableProviderError maps to `internal`, not `bad_input`: it's a
    capability gap in the configured provider set, not a malformed or
    user-correctable query -- there's no fuzzy-match-style fix, unlike
    NOT_FOUND.

    The four typed errors carry their own human-readable `message` (see
    each class's docstring) -- safe to surface via str(exc). Any other,
    unanticipated exception is not surfaced verbatim -- its message has
    no safety guarantee -- callers get a generic message instead.
    """
    if isinstance(exc, NoLocationError):
        return ErrorPayload(kind=ErrorKind.BAD_INPUT, message=str(exc))
    if isinstance(exc, NoCapableProviderError):
        return ErrorPayload(kind=ErrorKind.INTERNAL, message=str(exc))
    if isinstance(exc, StructuredOutputError):
        return ErrorPayload(kind=ErrorKind.INTERNAL, message=str(exc))
    if isinstance(exc, LLMError):
        return ErrorPayload(kind=ErrorKind.PROVIDER_UNREACHABLE, message=str(exc))
    return ErrorPayload(kind=ErrorKind.INTERNAL, message=_GENERIC_MESSAGE)
