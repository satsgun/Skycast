# SkyCast

![Backend coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/satsgun/Skycast/main/.github/badges/backend-coverage.json)
![Frontend coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/satsgun/Skycast/main/.github/badges/frontend-coverage.json)

SkyCast is an agentic AI weather app. Ask it a plain-language question —
*"do I need an umbrella this evening?"* — and it answers the question
you actually asked, leading with the decision, then showing the
forecast data behind it as auditable evidence. No dashboard of numbers
to interpret yourself.

<p align="center">
  <img src="https://github.com/user-attachments/assets/3f27717f-a5d9-4e04-99d6-3cbe7ac73ad7" alt="SkyCast answering &quot;do I need an umbrella this evening?&quot; with an answer-first conclusion, forecast card, and the relevant hour highlighted in the hourly strip" width="420" />
</p>

## Demo

**Live app:** [https://skycast-pi-jet.vercel.app](https://skycast-pi-jet.vercel.app)

## How it works

A natural-language query runs through a four-stage agentic pipeline,
streamed to the client over SSE so its progress stays visible:

1. **Decompose** (LLM) — turns the query into a provider-neutral
   data-needs spec: location(s), granularity, time window, the weather
   variables the answer actually depends on, and response intent.
2. **Plan** (deterministic) — turns that spec into an ordered set of
   tool calls. The only real dependency is geocode-before-forecast;
   independent calls (e.g. two cities in a comparison) run in parallel,
   and unnecessary steps are skipped.
3. **Execute** — runs the planned calls against the active weather
   provider. Multiple geocode matches trigger a clarification prompt
   instead of a silent guess; a provider outage or an unresolvable
   location becomes one of the error cases below.
4. **Synthesize** (LLM) — turns the normalized forecast data into an
   answer-first response: a one-to-two-sentence conclusion, plus the
   structured data for the forecast card.

The agent and UI never see provider-specific data. Two generic tools —
`geocode_location` and `get_forecast` — sit behind a `WeatherProvider`
contract; everything Open-Meteo-specific (URLs, variable names, WMO
weather codes) lives inside the one `OpenMeteoProvider` class that
implements it. Swapping or adding a provider means writing one class,
not touching the agent.

<p align="center">
  <img src="https://github.com/user-attachments/assets/4335ed27-e3cb-4471-bbbf-87daf77dde99" alt="SkyCast system architecture: frontend, the four-stage agentic pipeline, and the provider-agnostic tool seam in front of OpenMeteoProvider" width="720" />
</p>

Full design detail — including the per-stage backend and frontend
diagrams, the UX principles, and the ADRs behind each of these
decisions — lives in the [project wiki](https://github.com/satsgun/Skycast/wiki).

## Error handling

Two distinct failure classes, always handled differently, with no dead
ends:

- **User-correctable** — e.g. a location that doesn't resolve. The
  agent admits the miss rather than fabricating an answer.
- **System** — e.g. the weather provider is unreachable. The agent
  stays calm and surfaces the failure as a retryable condition rather
  than a crash.

The `error` terminal SSE event carries a machine-readable `kind` so the
frontend can render each class differently:

| `kind`                  | Class             | Meaning                                   |
| ----------------------- | ------------------ | ------------------------------------------ |
| `not_found`             | User-correctable   | No geocode match for a named location.     |
| `bad_input`             | User-correctable   | The request itself was malformed.          |
| `provider_unreachable`  | System             | The weather provider couldn't be reached.  |
| `internal`              | System             | An unexpected failure inside the pipeline. |

Real wire examples (generated from the actual `SSEEvent`/`ErrorPayload`
models, not hand-typed — see `docs/sse-contract.md` for the full
contract plus the happy-path and clarify-path streams):

<details>
<summary><code>not_found</code> — a location that doesn't geocode</summary>

```text
data: {"type":"step","data":{"label":"Understanding your question...","stage":"decompose"}}

data: {"type":"step","data":{"label":"Working out what to fetch...","stage":"plan"}}

data: {"type":"step","data":{"label":"Looking up Hyderbad...","stage":"execute_geocode"}}

data: {"type":"error","data":{"kind":"not_found","message":"no location matched 'Hyderbad'"}}
```

</details>

<details>
<summary><code>provider_unreachable</code> — the weather provider is down</summary>

```text
data: {"type":"step","data":{"label":"Understanding your question...","stage":"decompose"}}

data: {"type":"step","data":{"label":"Working out what to fetch...","stage":"plan"}}

data: {"type":"step","data":{"label":"Looking up Hyderabad...","stage":"execute_geocode"}}

data: {"type":"step","data":{"label":"Fetching the forecast...","stage":"execute_forecast"}}

data: {"type":"error","data":{"kind":"provider_unreachable","message":"the weather provider is unreachable right now"}}
```

</details>

## Getting started

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Runs at `http://localhost:8000` via `uvicorn skycast.main:app --reload`
once configured (see below) — `GET /health` and `POST /query` (SSE) are
the only two endpoints; the frontend owns all other state client-side.

### Frontend

```bash
cd frontend
npm install
npm test
npm run dev     # http://localhost:5173
npm run build
```

## Configuration

The backend selects one LLM vendor per process via environment
variables (no runtime routing between vendors).

| Variable            | Required                                  | Default                    | Notes                                                       |
| -------------------- | ------------------------------------------ | --------------------------- | ------------------------------------------------------------ |
| `LLM_VENDOR`        | No                                         | `anthropic`                 | `anthropic`, `openai`, or `gemini`. Unknown values fail loudly at startup. |
| `LLM_MODEL`         | No                                         | per-vendor                  | Model id/name for whichever vendor is selected.             |
| `ANTHROPIC_API_KEY` | Only if `LLM_VENDOR=anthropic` (or unset)  | —                           | Read ambiently by the Anthropic SDK.                        |
| `OPENAI_API_KEY`    | Only if `LLM_VENDOR=openai`                | —                           |                                                              |
| `GEMINI_API_KEY`    | Only if `LLM_VENDOR=gemini`                | —                           |                                                              |
| `FRONTEND_ORIGIN`   | No                                         | `http://localhost:5173`     | Sole allowed CORS origin. No trailing slash.                |

Default `LLM_MODEL` per vendor: `anthropic` → `claude-haiku-4-5-20251001`,
`openai` → `gpt-5-mini`, `gemini` → `gemini-2.5-flash`.

The frontend reads one env var, `VITE_API_BASE_URL` (see
`frontend/.env.example`), defaulting to `http://localhost:8000` for
local dev.

## Evaluation harness

`backend/eval/` scores the agent's correctness by importing the real
pipeline stages directly — no deployment needed. Weather is always the
deterministic `InMemoryProvider`; the LLM is real only for the tiers
that need one (decompose/synthesize), gated behind an API key so
ordinary CI stays offline and free:

```bash
cd backend
python -m eval.run_eval                              # deterministic only, every push
python -m eval.run_eval --live --runs 5 --judge --e2e # full eval, needs an API key
```

See `backend/eval/README.md` for the tier breakdown and scoring design.

## Deployment

- **Frontend** → [Vercel](https://vercel.com), zero-config Vite deploy.
- **Backend** → [Render](https://render.com) (`render.yaml`), free tier.
  Expect a ~30–60s cold start after ~15 minutes of inactivity — an
  accepted v1 tradeoff of the free tier, not a bug.

## Documentation

- [SkyCast Intro](https://github.com/satsgun/Skycast/wiki/02-‐-SkyCast)
- [UX Design Principles](https://github.com/satsgun/Skycast/wiki/03-‐-SkyCast-—-UX-Design)
- [Functional Details](https://github.com/satsgun/Skycast/wiki/05-‐-SkyCast-—-Functional-Details)
- [Implementation Notes](https://github.com/satsgun/Skycast/wiki/06-‐-SkyCast-—-Implementation-Notes)
- [System Architecture diagrams](https://github.com/satsgun/Skycast/wiki/Skycast-—-System-Architecture)
- [Roadmap (post-v1)](<https://github.com/satsgun/Skycast/wiki/07-‐-Skycast-—-Roadmap-(post‐v1)>)
- [ADR-0001 through ADR-0006](https://github.com/satsgun/Skycast/wiki/SkyCast-%E2%80%94-The-ADR-Set) — the design decisions behind the pipeline
  split, provider interface, transport, stack/hosting, code-gen
  sandbox, and relative-time resolution.
- [SSE contract](docs/sse-contract.md) — the generated, always-current
  FE↔BE wire contract.
