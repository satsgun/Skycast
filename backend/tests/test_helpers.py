import asyncio

from skycast.sse.payloads import PipelineStage
from tests.helpers import RecordingEmitter


def test_starts_with_empty_calls() -> None:
    emitter = RecordingEmitter()
    assert emitter.calls == []


def test_records_calls_in_order() -> None:
    emitter = RecordingEmitter()

    async def run() -> None:
        await emitter("Resolving location…", PipelineStage.EXECUTE_GEOCODE)
        await emitter("Fetching forecast…", PipelineStage.EXECUTE_FORECAST)

    asyncio.run(run())

    assert emitter.calls == [
        ("Resolving location…", PipelineStage.EXECUTE_GEOCODE),
        ("Fetching forecast…", PipelineStage.EXECUTE_FORECAST),
    ]
