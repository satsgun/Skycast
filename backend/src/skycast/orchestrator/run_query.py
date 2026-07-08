"""run_query: pipeline orchestrator, the /query async generator (Task 18.3).

Runs decompose -> plan -> execute -> synthesize as one streamed sequence,
yielding `step` SSEEvents as each stage starts and exactly one terminal
event (`answer`/`clarify`/`error`) last, then returning. Every raised
exception from decompose/plan/synthesize funnels through map_error (Task
18.2); execute()'s Failed variant already carries its own ErrorKind
(Task 16) and is mapped directly, not through map_error. A top-level
guard maps any other unexpected exception to `internal` too, so the
terminal-event invariant holds even on a bug.

Bridges execute()'s emit callback into yielded step events via
_stream_execute (Task 18.4's callback<->generator impedance match) --
an asyncio.Queue drains in real time while execute() runs as a
background task, so steps reach the stream as the pipeline reaches them
(CLAUDE.md), not batched after execute() finishes.
"""

import asyncio
from collections.abc import AsyncIterator

from skycast.api.query_request import QueryRequest
from skycast.domain.location import Location
from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.orchestrator.error_mapping import map_error
from skycast.pipeline.data_needs import DataNeedsSpec
from skycast.pipeline.decompose import decompose
from skycast.pipeline.errors import NoCapableProviderError, NoLocationError
from skycast.pipeline.execute_result import ExecutionResult, Failed, NeedsClarification, Success
from skycast.pipeline.execute_stage import execute
from skycast.pipeline.plan import ToolPlan
from skycast.pipeline.plan_stage import plan
from skycast.pipeline.synthesize_stage import synthesize
from skycast.providers.base import WeatherProvider
from skycast.sse.envelope import SSEEvent
from skycast.sse.payloads import PipelineStage

_UNDERSTANDING_LABEL = "Understanding your question…"
_PLANNING_LABEL = "Working out what to fetch…"
_SYNTHESIZING_LABEL = "Putting together your answer…"


async def run_query(
    request: QueryRequest, providers: dict[str, WeatherProvider], llm: LLMClient
) -> AsyncIterator[SSEEvent]:
    """Runs decompose -> plan -> execute -> synthesize as one stream.

    Yields zero-or-more `step` events, then exactly one terminal event
    (`answer`/`clarify`/`error`), then returns. The top-level guard here
    maps any exception escaping `_run_query_inner` -- a genuine bug,
    since every anticipated failure is already caught and yielded as an
    `error` event inside it -- to `internal`, so the terminal-event
    invariant holds even then.
    """
    try:
        async for event in _run_query_inner(request, providers, llm):
            yield event
    except Exception as exc:
        payload = map_error(exc)
        yield SSEEvent.error(kind=payload.kind, message=payload.message)


async def _run_query_inner(
    request: QueryRequest, providers: dict[str, WeatherProvider], llm: LLMClient
) -> AsyncIterator[SSEEvent]:
    ctx = request.to_session_context()

    yield SSEEvent.step(_UNDERSTANDING_LABEL, PipelineStage.DECOMPOSE)
    try:
        spec = await decompose(request.query, ctx, llm)
    except (LLMError, StructuredOutputError) as exc:
        payload = map_error(exc)
        yield SSEEvent.error(kind=payload.kind, message=payload.message)
        return

    yield SSEEvent.step(_PLANNING_LABEL, PipelineStage.PLAN)
    plan_spec, default_location = _resolve_plan_inputs(spec, request, ctx.default_location)
    try:
        tool_plan = plan(plan_spec, providers, default_location=default_location)
    except (NoLocationError, NoCapableProviderError) as exc:
        payload = map_error(exc)
        yield SSEEvent.error(kind=payload.kind, message=payload.message)
        return

    result_box: list[ExecutionResult] = []
    async for event in _stream_execute(tool_plan, providers, result_box):
        yield event
    result = result_box[0]

    match result:
        case NeedsClarification():
            yield SSEEvent.clarify(candidates=result.candidates)
            return
        case Failed():
            yield SSEEvent.error(kind=result.kind, message=result.message)
            return
        case Success():
            pass

    yield SSEEvent.step(_SYNTHESIZING_LABEL, PipelineStage.SYNTHESIZE)
    try:
        answer = await synthesize(result.forecasts, spec.intent, llm)
    except (LLMError, StructuredOutputError) as exc:
        payload = map_error(exc)
        yield SSEEvent.error(kind=payload.kind, message=payload.message)
        return
    yield SSEEvent.answer(answer.text, answer.card)


def _resolve_plan_inputs(
    spec: DataNeedsSpec, request: QueryRequest, ctx_default_location: Location | None
) -> tuple[DataNeedsSpec, Location | None]:
    """Disambiguation re-query (resolved_location set): reuses plan()'s
    existing skip-geocode path -- default_location -- rather than adding
    a new plan() parameter. Clears location_names on a *derived copy* of
    spec (DataNeedsSpec is frozen; nothing is mutated) so plan() falls
    through to its default_location branch and treats resolved_location
    as the (only) target, overriding whatever name decompose produced.
    resolved_location wins over the request's own default_location.
    """
    if request.resolved_location is None:
        return spec, ctx_default_location
    return spec.model_copy(update={"location_names": []}), request.resolved_location


async def _stream_execute(
    tool_plan: ToolPlan,
    providers: dict[str, WeatherProvider],
    result_box: list[ExecutionResult],
) -> AsyncIterator[SSEEvent]:
    """Bridges execute()'s emit callback into yielded step events (Task
    18.4's callback<->generator impedance match). Runs execute() as a
    background task while an asyncio.Queue collects step events from its
    emit callback, yielding each as soon as it's queued -- concurrently,
    while execute() is still running -- so steps reach the stream as the
    pipeline reaches them (CLAUDE.md), not batched after execute()
    finishes. Appends the final ExecutionResult to `result_box` once (a
    generator can't yield values and also return one) -- read by the
    caller only after this generator is exhausted. No task is left
    running if the caller stops consuming early (e.g. a client
    disconnect closes the generator): the still-pending queue.get() and,
    if not yet done, the execute task itself are cancelled and awaited.
    """
    queue: asyncio.Queue[SSEEvent] = asyncio.Queue()

    async def emit(label: str, stage: PipelineStage) -> None:
        await queue.put(SSEEvent.step(label, stage))

    execute_task = asyncio.ensure_future(execute(tool_plan, providers, emit=emit))
    get_task: asyncio.Task[SSEEvent] | None = None
    try:
        while not execute_task.done():
            get_task = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait(
                {execute_task, get_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if get_task in done:
                yield get_task.result()
            else:
                await _cancel(get_task)
            get_task = None
    finally:
        if get_task is not None:
            await _cancel(get_task)
        if not execute_task.done():
            await _cancel(execute_task)

    while not queue.empty():  # pragma: no cover
        # Defensive: covers execute_task finishing with items still
        # queued that the loop above hasn't drained yet. Not hit by any
        # current test -- asyncio.Queue.put()/.get() are real checkpoints
        # here, so items are observed to always drain one-by-one through
        # the loop above before execute_task.done() flips -- but nothing
        # guarantees that ordering across asyncio implementations/
        # versions, so this stays as a correctness safeguard.
        yield queue.get_nowait()

    result_box.append(execute_task.result())


async def _cancel(task: "asyncio.Task") -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
