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
