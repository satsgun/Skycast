import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skycast.api.routes import router

app = FastAPI(title="SkyCast API")

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
