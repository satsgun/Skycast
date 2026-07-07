"""execute: pipeline stage 3 (Task 16.2).

Runs a ToolPlan against registered providers: geocode-then-forecast per
chain, independent chains concurrent within each phase, every branch
(0/1/2+ geocode matches, provider failure, unknown provider id) folded
into one ExecutionResult. No exception escapes except a genuine
programming bug -- ProviderError is always caught and mapped here.
"""

import asyncio
from collections.abc import Awaitable, Callable

from skycast.domain.location import Location
from skycast.pipeline.execute_result import ExecutionResult, Failed, NeedsClarification, Success
from skycast.pipeline.plan import PlannedCall, PlannedTool, ToolPlan
from skycast.providers.base import WeatherProvider
from skycast.providers.errors import ProviderError
from skycast.sse.payloads import ErrorKind, PipelineStage

Emit = Callable[[str, PipelineStage], Awaitable[None]]


async def execute(
    plan: ToolPlan, providers: dict[str, WeatherProvider], *, emit: Emit
) -> ExecutionResult:
    forecast_calls = [c for c in plan.calls if c.tool == PlannedTool.FETCH_FORECAST]
    calls_by_id = {c.call_id: c for c in plan.calls}
    geocode_calls: list[PlannedCall | None] = [
        calls_by_id[c.depends_on[0]] if c.depends_on else None for c in forecast_calls
    ]

    needing_geocode = [g for g in geocode_calls if g is not None]
    if needing_geocode:
        await emit(_geocode_label(needing_geocode), PipelineStage.EXECUTE_GEOCODE)
        geocode_results = await _run_with_fail_fast(
            [_run_geocode(g, providers) for g in needing_geocode]
        )
        decisive = _prioritize(geocode_results)
        if decisive is not None:
            return decisive
    else:
        geocode_results = []

    locations: list[Location] = []
    remaining = iter(geocode_results)
    for call, geocode_call in zip(forecast_calls, geocode_calls):
        locations.append(call.location if geocode_call is None else next(remaining))

    await emit(_forecast_label(forecast_calls), PipelineStage.EXECUTE_FORECAST)
    forecast_results = await _run_with_fail_fast(
        [
            _run_forecast(call, location, providers)
            for call, location in zip(forecast_calls, locations)
        ]
    )
    decisive = _prioritize(forecast_results)
    if decisive is not None:
        return decisive

    return Success(forecasts=[r.forecasts[0] for r in forecast_results])


async def _run_geocode(
    geocode_call: PlannedCall, providers: dict[str, WeatherProvider]
) -> Location | Failed | NeedsClarification:
    provider = providers.get(geocode_call.provider)
    if provider is None:
        return Failed(
            kind=ErrorKind.INTERNAL,
            message=f"unknown provider id {geocode_call.provider!r}",
            for_location_name=geocode_call.location_name,
        )
    try:
        matches = await provider.geocode(geocode_call.location_name)
    except ProviderError as exc:
        return Failed(
            kind=ErrorKind.PROVIDER_UNREACHABLE,
            message=str(exc),
            for_location_name=geocode_call.location_name,
        )
    if not matches:
        return Failed(
            kind=ErrorKind.NOT_FOUND,
            message=f"no location matched {geocode_call.location_name!r}",
            for_location_name=geocode_call.location_name,
        )
    if len(matches) > 1:
        return NeedsClarification(
            candidates=matches, for_location_name=geocode_call.location_name
        )
    return matches[0]


async def _run_forecast(
    forecast_call: PlannedCall, location: Location, providers: dict[str, WeatherProvider]
) -> Success | Failed:
    provider = providers.get(forecast_call.provider)
    if provider is None:
        return Failed(
            kind=ErrorKind.INTERNAL,
            message=f"unknown provider id {forecast_call.provider!r}",
            for_location_name=location.name,
        )
    try:
        forecast = await provider.fetch_forecast(location, forecast_call.request)
    except ProviderError as exc:
        return Failed(
            kind=ErrorKind.PROVIDER_UNREACHABLE, message=str(exc), for_location_name=location.name
        )
    return Success(forecasts=[forecast])


async def _run_with_fail_fast(coros: list[Awaitable]) -> list:
    """Runs `coros` concurrently. If any completed result is a
    Failed(kind=PROVIDER_UNREACHABLE), cancels the rest immediately --
    nothing can outrank that outcome (see _prioritize), so waiting for
    slower siblings would be wasted work. No task is left pending or
    unawaited when this returns, even if a task raises unexpectedly.
    """
    tasks = [asyncio.ensure_future(c) for c in coros]
    pending = set(tasks)
    results: dict[asyncio.Task, object] = {}

    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                results[task] = task.result()
            if any(
                isinstance(r, Failed) and r.kind == ErrorKind.PROVIDER_UNREACHABLE
                for r in results.values()
            ):
                break
    finally:
        for task in pending:
            task.cancel()
        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass

    return [results[t] for t in tasks if t in results]


def _prioritize(outcomes: list) -> Failed | NeedsClarification | None:
    """Deterministic priority across a batch of per-chain outcomes:
    provider_unreachable Failed > NeedsClarification > any other Failed.
    Ignores anything else in `outcomes` (e.g. resolved Location values
    from a geocode-phase batch) and returns None when nothing decisive
    is present -- callers decide what "all clear" means for their phase.
    """
    provider_unreachable = [
        o for o in outcomes if isinstance(o, Failed) and o.kind == ErrorKind.PROVIDER_UNREACHABLE
    ]
    if provider_unreachable:
        return provider_unreachable[0]
    clarifications = [o for o in outcomes if isinstance(o, NeedsClarification)]
    if clarifications:
        return clarifications[0]
    other_failures = [o for o in outcomes if isinstance(o, Failed)]
    if other_failures:
        return other_failures[0]
    return None


def _geocode_label(geocode_calls: list[PlannedCall]) -> str:
    names = [c.location_name for c in geocode_calls]
    if len(names) == 1:
        return f"Resolving location {names[0]}…"
    return f"Resolving locations: {', '.join(names)}…"


def _forecast_label(forecast_calls: list[PlannedCall]) -> str:
    return "Fetching forecast…" if len(forecast_calls) == 1 else "Fetching forecasts…"
