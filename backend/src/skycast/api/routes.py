"""`/query` SSE endpoint (Task 18.5).

No business logic beyond streaming: FastAPI parses the body into
QueryRequest, run_query (Task 18.3) does the actual pipeline work, and
each SSEEvent is serialized via the Task 13.4 wire serializer as one
`data: {...}\n\n` line, written to the stream as it's produced.

get_providers/get_llm_client are FastAPI dependencies, not constructed
inline. In production, app startup wiring (Task 18.6, main.py's
lifespan) stashes the real registry/client on app.state, and these
functions just read it back; in tests, app.dependency_overrides replaces
them outright. Either way, nothing here constructs a provider/client
inline, and the fallback raise means an unconfigured app fails loudly
rather than silently serving something wrong.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from skycast.api.query_request import QueryRequest
from skycast.llm.client import LLMClient
from skycast.orchestrator.run_query import run_query
from skycast.providers.base import WeatherProvider
from skycast.sse.wire import serialize_sse_event

router = APIRouter()


def get_providers(request: Request) -> dict[str, WeatherProvider]:
    providers = getattr(request.app.state, "providers", None)
    if providers is None:
        raise NotImplementedError(
            "no provider registry configured -- app startup wiring "
            "(Task 18.6) didn't run, or override get_providers in tests"
        )
    return providers


def get_llm_client(request: Request) -> LLMClient:
    llm = getattr(request.app.state, "llm_client", None)
    if llm is None:
        raise NotImplementedError(
            "no LLMClient configured -- app startup wiring (Task 18.6) "
            "didn't run, or override get_llm_client in tests"
        )
    return llm


@router.post("/query")
async def query(
    request: QueryRequest,
    providers: dict[str, WeatherProvider] = Depends(get_providers),
    llm: LLMClient = Depends(get_llm_client),
) -> StreamingResponse:
    return StreamingResponse(
        _stream(request, providers, llm),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Stops a fronting reverse proxy (e.g. on Render) from
            # buffering the response and defeating incremental delivery.
            "X-Accel-Buffering": "no",
        },
    )


async def _stream(
    request: QueryRequest, providers: dict[str, WeatherProvider], llm: LLMClient
) -> AsyncIterator[str]:
    async for event in run_query(request, providers, llm):
        yield serialize_sse_event(event)
