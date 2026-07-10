# SkyCast

![Backend coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/satsgun/Skycast/main/.github/badges/backend-coverage.json)
![Frontend coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/satsgun/Skycast/main/.github/badges/frontend-coverage.json)

Weather application with a TypeScript frontend and a FastAPI backend.

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Frontend

```bash
cd frontend
npm install
npm test
```

## Configuration

The backend selects one LLM vendor per process via environment
variables (no runtime routing between vendors).

| Variable            | Required                        | Default      | Notes                                                    |
| -------------------- | -------------------------------- | ------------- | ---------------------------------------------------------- |
| `LLM_VENDOR`        | No                               | `anthropic`   | `anthropic`, `openai`, or `gemini`. Unknown values fail loudly at startup. |
| `LLM_MODEL`         | No                               | per-vendor    | Model id/name for whichever vendor is selected.           |
| `ANTHROPIC_API_KEY` | Only if `LLM_VENDOR=anthropic` (or unset) | —    | Read ambiently by the Anthropic SDK.                       |
| `OPENAI_API_KEY`    | Only if `LLM_VENDOR=openai`      | —             |                                                            |
| `GEMINI_API_KEY`    | Only if `LLM_VENDOR=gemini`      | —             |                                                            |

Default `LLM_MODEL` per vendor: `anthropic` → `claude-haiku-4-5-20251001`,
`openai` → `gpt-5-mini`, `gemini` → `gemini-2.5-flash`.
