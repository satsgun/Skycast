# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## What SkyCast is

SkyCast is an agentic AI weather app. The input is a natural-language question
("do I need an umbrella this evening?"); the output is an agent-reasoned,
answer-first response backed by glanceable forecast data — not a dashboard of
numbers. The agent interprets intent (current conditions vs. hourly vs.
multi-day), asks for clarification when a location is ambiguous, fails
gracefully when data is unavailable, and tailors the response to the question
actually asked.

Full context lives in the GitHub wiki — read these before making
architectural changes:
- [SkyCast Intro](https://github.com/satsgun/Skycast/wiki/02-‐-SkyCast)
- [UX Design Principles](https://github.com/satsgun/Skycast/wiki/03-‐-SkyCast-—-UX-Design)
- [Functional Details](https://github.com/satsgun/Skycast/wiki/05-‐-SkyCast-—-Functional-Details)
- [Implementation Notes](https://github.com/satsgun/Skycast/wiki/06-‐-SkyCast-—-Implementation-Notes)
- [Roadmap (post-v1)](<https://github.com/satsgun/Skycast/wiki/07-‐-Skycast-—-Roadmap-(post‐v1)>)
- ADR-0001 through ADR-0005 (decompose/plan split, provider interface,
  transport, stack/hosting, code-gen sandbox)
- [System Architecture diagrams](https://github.com/satsgun/Skycast/wiki/Skycast-—-System-Architecture)

## Current repo state

Only the project scaffold exists so far (Task 2). The agentic pipeline,
providers, and UI described below are the **target architecture**, not yet
implemented. Don't assume functionality exists — check `backend/src/skycast/`
and `frontend/src/` before referencing a module.

```
SkyCast/
├── backend/            # FastAPI backend
│   ├── pyproject.toml
│   ├── src/skycast/    # src-layout package (main.py has only /health today)
│   └── tests/          # pytest
└── frontend/            # TypeScript frontend (plain TS, no framework yet)
    ├── package.json
    ├── src/            # index.ts is a placeholder today
    └── tests/          # Vitest
```

## Working method: tests first

Per the project brief, **write the test before the implementation** for
every task. A task isn't done when code exists — it's done when a failing
test was written first and now passes.

## Commands

**Backend** (from `backend/`):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

**Frontend** (from `frontend/`):
```bash
npm install
npm test         # vitest run
npm run build    # tsc -p tsconfig.build.json -> dist/
```

## Target architecture

- **Frontend**: lightweight TypeScript SPA, deployed to **Vercel**. Owns all
  session state client-side.
- **Backend**: FastAPI, deployed to **Render** as a stateless web service —
  no database, no server-side session store. Each request carries its own
  conversation context up from the client.
- **Transport** (ADR-0003): REST for discrete operations
  (`GET/PUT /settings`, geocode-selection, cached-data retrieval); **SSE**
  for the streaming query path (`POST /query` opens a stream emitting
  `step` events, then a terminal `answer` or `error` event). The query
  handler must be a generator that yields progress incrementally, not a
  function that returns once — build it that way from the start.

### The agentic pipeline (backend)

Four stages, run per query:

1. **Decompose** (LLM call) — natural-language query → provider-neutral
   data-needs spec: location(s), forecast granularity, time window,
   required weather variables, response intent.
2. **Plan** (a **separate** LLM call — ADR-0001, not fused with decompose) —
   data-needs spec → ordered tool calls. Ordering is dependency-driven
   (geocode-before-forecast is the only real dependency); independent calls
   (e.g. two cities in a comparison) run in parallel; unnecessary steps are
   skipped.
3. **Execute** — run the planned tool calls against the active provider,
   emitting one SSE step event per stage. Multiple geocode matches trigger
   clarification; zero matches trigger a location-not-found error; provider
   unreachable triggers a service-offline error with cached-data fallback.
4. **Synthesize** (LLM call) — normalized forecast data → answer-first
   response: a 1–2 sentence conclusion leading with the decision or
   exception, plus structured data for the forecast card.

Decompose and plan are kept as two separate LLM calls deliberately (not
fused) so each stage is independently testable and independently routable
to a different model later — do not collapse them into one call without
revisiting ADR-0001.

### Provider-agnostic tool interface (ADR-0002)

The agent and UI **never** see provider-specific data. Two generic tools,
expressed in domain vocabulary, sit behind a `WeatherProvider` contract:

- `geocode_location(name) -> list[Location]`
- `get_forecast(location, granularity, time_window, variables) -> Forecast`
- `capabilities() -> ProviderCapabilities`

All tool outputs use a **canonical schema** (`Location`, `Forecast` /
`WeatherReading` with `timestamp`, `temperature`, `feels_like`,
`precip_probability`, `wind_speed`, `condition_code`) and a canonical
condition enum (`CLEAR`, `CLOUDY`, `RAIN`, `STORM`, …) that drives icon
selection. `OpenMeteoProvider` is the v1 implementation of the contract;
**everything** Open-Meteo-specific (base URLs, `temperature_2m`-style
variable names, WMO weather codes, CC-BY attribution, its error shape,
multi-coordinate batching) lives inside that one class and nowhere else. An
`InMemoryProvider` returning fixed `Forecast` objects should exist for
offline tests of the whole decompose→plan→execute→render path.

**When adding or touching weather-data code: if you're about to reference
an Open-Meteo field name, WMO code, or URL anywhere outside
`OpenMeteoProvider`, stop — that detail belongs behind the seam.**

### Code-gen fallback (ADR-0005 — roadmap, not v1)

For queries the generic tools can't express, the plan is for the LLM to
write Python against the provider-agnostic interface (operating on
normalized `Forecast` objects, never raw provider URLs), executed in an
isolated [e2b](https://e2b.dev/) sandbox — never in-process. Recorded as a
decision; do not build in-process `exec` of generated code.

## Design principles to follow

- **Separation of concerns**, applied at every seam: UI vs. state vs.
  transport (frontend); API surface vs. agentic loop vs. provider adapter
  (backend); provider-neutral vs. provider-specific code.
- **Answer-first responses** — lead with the conclusion/exception, then show
  supporting data as auditable evidence beneath it.
- **Two distinct error classes**, handled differently: user-correctable
  (e.g. location not found → fuzzy-match suggestion chips) vs. system
  (provider unreachable → calm messaging, data freshness, retry + cached
  fallback). Never a dead end.
- **Ask before guessing** on ambiguous input (e.g. multiple geocode
  matches) rather than silently picking — but make resolving the question
  one tap.
- **Make agent progress legible** — the thinking-state UI must reflect real
  backend progress (real SSE step events as the pipeline reaches them), not
  simulated/timed steps.

## Out of scope for v1 (don't build unless asked)

Multi-provider failover/selection/collation, model routing, e2b code-gen
execution, browser geolocation, notifications, configurable session window.
See the [Roadmap](<https://github.com/satsgun/Skycast/wiki/07-‐-Skycast-—-Roadmap-(post‐v1)>)
for the dependency order if/when these are picked up.

## Other project requirements

- Test-coverage badge via `pytest` + `pytest-cov` on the backend.
- Architecture diagram (image) and documented error cases/examples in the
  README.
- Deploy target: frontend → Vercel, backend → Render (free tier; expect
  ~30–60s cold start after ~15 min idle — an accepted v1 tradeoff, not a
  bug to fix).
