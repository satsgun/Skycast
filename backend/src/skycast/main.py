import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skycast.api.routes import router
from skycast.api.wiring import build_llm_client, build_provider_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.providers = build_provider_registry()
    app.state.llm_client = build_llm_client()
    yield


app = FastAPI(title="SkyCast API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
