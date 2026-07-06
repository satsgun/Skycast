# SSE Contract (FE<->BE)

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
{"type": "<step|clarify|answer|error>", "data": { ... }}
```

The frontend dispatches on the `type` field from one `onmessage` handler
-- it never relies on SSE's own named-event mechanism.

## Event types and payloads

### `step` -- non-terminal progress update

| Field   | Type   | Notes |
|---------|--------|-------|
| `label` | string | Human-readable thinking-state line for the UI. |
| `stage` | `decompose \| plan \| execute_geocode \| execute_forecast \| synthesize` | Machine-readable pipeline stage marker. |

### `clarify` -- terminal: ambiguous location

| Field        | Type         | Notes |
|--------------|--------------|-------|
| `candidates` | `Location[]` | 2 or more ambiguous geocode matches. The FE renders these as one-tap options. |

### `answer` -- terminal: resolved answer

| Field  | Type         | Notes |
|--------|--------------|-------|
| `text` | string       | The answer-first conclusion -- leads with the decision/exception. |
| `card` | `AnswerCard` | `{"forecast": Forecast, "highlight": <timestamp \| date \| null>}` -- the full resolved `Forecast`, sent as-is, plus which reading the answer is about. |

### `error` -- terminal: something went wrong

| Field     | Type | Notes |
|-----------|------|-------|
| `kind`    | `not_found \| provider_unreachable \| bad_input \| internal` | Machine-readable error kind. |
| `message` | string | Human-readable message for display. |

## Ordering invariant

Every stream is zero or more `step` events, followed by exactly one terminal event -- `answer`, `clarify`, or `error` -- which is always last. After the terminal event, the stream closes.

## Example streams

These are not hand-written -- they are produced by constructing real
`SSEEvent`s and running them through `serialize_sse_event()`
(`backend/src/skycast/sse/wire.py`). See "Regenerating this document".

### Happy path

```text
data: {"type":"step","data":{"label":"Understanding your question...","stage":"decompose"}}

data: {"type":"step","data":{"label":"Working out what to fetch...","stage":"plan"}}

data: {"type":"step","data":{"label":"Looking up Hyderabad...","stage":"execute_geocode"}}

data: {"type":"step","data":{"label":"Fetching the forecast...","stage":"execute_forecast"}}

data: {"type":"step","data":{"label":"Putting together your answer...","stage":"synthesize"}}

data: {"type":"answer","data":{"text":"Yes, bring an umbrella this evening -- rain is likely around 6pm.","card":{"forecast":{"location":{"id":"1","name":"Hyderabad","latitude":17.385,"longitude":78.4867,"country":null,"country_code":"IN","admin1":null,"admin2":null,"population":null,"timezone":"Asia/Kolkata"},"units":{"temperature":"celsius","wind_speed":"kmh","precip_amount":"mm","precip_probability":"percent"},"current":{"timestamp":"2024-06-01T18:00:00Z","temperature":27.0,"feels_like":null,"precip_probability":80.0,"precip_amount":null,"wind_speed":null,"condition_code":"RAIN"},"hourly":null,"daily":null},"highlight":"2024-06-01T18:00:00Z"}}}

```

### Clarify path

```text
data: {"type":"step","data":{"label":"Understanding your question...","stage":"decompose"}}

data: {"type":"step","data":{"label":"Working out what to fetch...","stage":"plan"}}

data: {"type":"step","data":{"label":"Looking up Springfield...","stage":"execute_geocode"}}

data: {"type":"clarify","data":{"candidates":[{"id":"1","name":"Springfield","latitude":39.7817,"longitude":-89.6501,"country":null,"country_code":"US","admin1":"Illinois","admin2":null,"population":null,"timezone":null},{"id":"2","name":"Springfield","latitude":37.209,"longitude":-93.2923,"country":null,"country_code":"US","admin1":"Missouri","admin2":null,"population":null,"timezone":null},{"id":"3","name":"Springfield","latitude":42.1015,"longitude":-72.5898,"country":null,"country_code":"US","admin1":"Massachusetts","admin2":null,"population":null,"timezone":null}]}}

```

## Regenerating this document

The example streams above (and this whole file) are generated, not
hand-maintained. After changing anything in `backend/src/skycast/sse/`,
regenerate it from `backend/`, with the dev virtualenv active:

```bash
python -m skycast.sse.contract_doc
```

Commit the regenerated `docs/sse-contract.md` alongside the code change.
