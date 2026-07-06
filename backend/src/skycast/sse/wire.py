"""SSE wire serialization for the FE<->BE contract (ADR-0003, Task 13.4).

Turns an SSEEvent into the bytes actually sent over the wire: a single
`data:` line carrying the envelope's JSON, terminated by a blank line --
the SSE spec's default (unnamed) event format. Task 13's dispatch
decision is to switch on the JSON `type` field, not SSE's own `event:`
field, so that field is never emitted here. Pure function, no FastAPI
import, so it's testable independent of the actual `/query` endpoint
(Phase 5).
"""

from skycast.sse.envelope import SSEEvent


def serialize_sse_event(event: SSEEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"
