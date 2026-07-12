"""SSE contract documentation generator (ADR-0003, Task 13.5).

Renders docs/sse-contract.md: the human-readable half of the FE<->BE SSE
contract (backend/src/skycast/sse/{events,payloads,envelope,wire}.py is
the machine-readable half). The example streams embedded in it are built
from real SSEEvents and run through the real wire serializer -- never
hand-typed -- so they can't silently drift from the actual wire format.
Regenerate after any change to the sse package:
`python -m skycast.sse.contract_doc` from backend/, dev venv active.

Assumes a source checkout layout (this file sits four levels under the
repo root) to locate docs/ -- a dev-time-only tool, like
domain/conditions.py's JSON export.
"""

from datetime import datetime, timezone
from pathlib import Path

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.sse.envelope import SSEEvent
from skycast.sse.payloads import AnswerCard, ForecastBlock, Highlight, PipelineStage, ReadingLocator
from skycast.sse.wire import serialize_sse_event

DEFAULT_DOC_PATH = Path(__file__).parents[4] / "docs" / "sse-contract.md"


def happy_path_events() -> list[SSEEvent]:
    location = Location(
        id="1",
        name="Hyderabad",
        latitude=17.385,
        longitude=78.4867,
        country_code="IN",
        timezone="Asia/Kolkata",
    )
    forecast = Forecast(
        location=location,
        units=Units(),
        current=HourlyReading(
            timestamp=datetime(2024, 6, 1, 18, 0, tzinfo=timezone.utc),
            temperature=27.0,
            precip_probability=80.0,
            condition_code=ConditionCode.RAIN,
        ),
    )
    return [
        SSEEvent.step("Understanding your question...", PipelineStage.DECOMPOSE),
        SSEEvent.step("Working out what to fetch...", PipelineStage.PLAN),
        SSEEvent.step("Looking up Hyderabad...", PipelineStage.EXECUTE_GEOCODE),
        SSEEvent.step("Fetching the forecast...", PipelineStage.EXECUTE_FORECAST),
        SSEEvent.step("Putting together your answer...", PipelineStage.SYNTHESIZE),
        SSEEvent.answer(
            "Yes, bring an umbrella this evening -- rain is likely around 6pm.",
            AnswerCard(
                forecasts=[forecast],
                highlight=Highlight(
                    forecast_index=0, locator=ReadingLocator(block=ForecastBlock.CURRENT)
                ),
            ),
        ),
    ]


def clarify_path_events() -> list[SSEEvent]:
    candidates = [
        Location(
            id="1",
            name="Springfield",
            admin1="Illinois",
            country_code="US",
            latitude=39.7817,
            longitude=-89.6501,
        ),
        Location(
            id="2",
            name="Springfield",
            admin1="Missouri",
            country_code="US",
            latitude=37.2090,
            longitude=-93.2923,
        ),
        Location(
            id="3",
            name="Springfield",
            admin1="Massachusetts",
            country_code="US",
            latitude=42.1015,
            longitude=-72.5898,
        ),
    ]
    # A comparison query ("Compare Springfield and Miami") where Miami
    # already resolved -- demonstrates for_location_name/resolved (fix
    # #90), not just a single-location clarify.
    miami = Location(id="4", name="Miami", country_code="US", latitude=25.7617, longitude=-80.1918)
    return [
        SSEEvent.step("Understanding your question...", PipelineStage.DECOMPOSE),
        SSEEvent.step("Working out what to fetch...", PipelineStage.PLAN),
        SSEEvent.step("Looking up Springfield, Miami...", PipelineStage.EXECUTE_GEOCODE),
        SSEEvent.clarify(candidates, for_location_name="Springfield", resolved={"Miami": miami}),
    ]


def render_example_stream(events: list[SSEEvent]) -> str:
    return "".join(serialize_sse_event(event) for event in events)


def render_sse_contract_doc() -> str:
    happy_path = render_example_stream(happy_path_events())
    clarify_path = render_example_stream(clarify_path_events())
    return f'''# SSE Contract (FE<->BE)

This document is the human-readable half of the SSE `/query` contract
(ADR-0003, Task 13). The machine-readable half is the Pydantic v2 models
in `backend/src/skycast/sse/` (`events.py`, `payloads.py`, `envelope.py`,
`wire.py`) -- this file is generated from those models and their real
serializer, not hand-written, so it can't drift from the actual wire
format. See "Regenerating this document" below.

The `/query` endpoint itself and the orchestrator that emits these events
in sequence are Phase 5 (not yet built); this contract is what they will
produce and what the frontend's `EventSource` handler will consume.

## Envelope shape

Every SSE event is sent as a single, unnamed `data:` line (no SSE
`event:` field) whose JSON is a uniform envelope:

```json
{{"type": "<step|clarify|answer|error>", "data": {{ ... }}}}
```

The frontend dispatches on the `type` field from one `onmessage` handler
-- it never relies on SSE's own named-event mechanism.

## Event types and payloads

### `step` -- non-terminal progress update

| Field   | Type   | Notes |
|---------|--------|-------|
| `label` | string | Human-readable thinking-state line for the UI. |
| `stage` | `decompose \\| plan \\| execute_geocode \\| execute_forecast \\| synthesize` | Machine-readable pipeline stage marker. |

### `clarify` -- terminal: ambiguous location

| Field               | Type                   | Notes |
|---------------------|------------------------|-------|
| `candidates`        | `Location[]`           | 2 or more ambiguous geocode matches. The FE renders these as one-tap options. |
| `for_location_name` | string                 | Which query-named location `candidates` is for. A multi-location plan (e.g. a comparison) may have other, still-unresolved names -- this says which one the user is being asked about. |
| `resolved`          | `{{[name: string]: Location}}` | Every other location already known this round, keyed by its original query name. The re-query (`POST /query`) must send these back via `resolved_locations` alongside the newly-picked candidate, or they're lost. |

### `answer` -- terminal: resolved answer

| Field  | Type         | Notes |
|--------|--------------|-------|
| `text` | string       | The answer-first conclusion -- leads with the decision/exception. |
| `card` | `AnswerCard` | `{{"forecasts": Forecast[], "highlight": Highlight \\| null}}` -- the resolved `Forecast`(s), sent as-is (one per compared location), plus which reading the answer is about. `Highlight` is `{{"forecast_index": int, "locator": ReadingLocator}}`; `ReadingLocator` is `{{"block": "current" \\| "hourly" \\| "daily", "index": int \\| null}}` (`null` index only for `current`). |

### `error` -- terminal: something went wrong

| Field     | Type | Notes |
|-----------|------|-------|
| `kind`    | `not_found \\| provider_unreachable \\| bad_input \\| internal` | Machine-readable error kind. |
| `message` | string | Human-readable message for display. |

## Ordering invariant

Every stream is zero or more `step` events, followed by exactly one terminal event -- `answer`, `clarify`, or `error` -- which is always last. After the terminal event, the stream closes.

## Example streams

These are not hand-written -- they are produced by constructing real
`SSEEvent`s and running them through `serialize_sse_event()`
(`backend/src/skycast/sse/wire.py`). See "Regenerating this document".

### Happy path

```text
{happy_path}```

### Clarify path

```text
{clarify_path}```

## Regenerating this document

The example streams above (and this whole file) are generated, not
hand-maintained. After changing anything in `backend/src/skycast/sse/`,
regenerate it from `backend/`, with the dev virtualenv active:

```bash
python -m skycast.sse.contract_doc
```

Commit the regenerated `docs/sse-contract.md` alongside the code change.
'''


def write_sse_contract_doc(path: Path = DEFAULT_DOC_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sse_contract_doc(), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    write_sse_contract_doc()
