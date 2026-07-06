"""SSE event-type enum for the FE<->BE wire contract (ADR-0003, Task 13.1).

The value every SSE envelope's `type` field carries; the frontend
dispatches on it from a single `onmessage` handler (Task 13's uniform-
envelope decision), rather than named SSE `event:` lines. Wire values are
lowercase and are part of the contract -- don't change them without
updating the frontend dispatch table.

Self-contained: imports nothing else from the app.
"""

from enum import StrEnum


class SSEEventType(StrEnum):
    STEP = "step"
    CLARIFY = "clarify"
    ANSWER = "answer"
    ERROR = "error"
