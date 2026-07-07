"""Shared test utilities (Task 16.3).

RecordingEmitter is a tiny stand-in for the `emit` callback pipeline
stage 3's execute() (Task 16.2) takes -- records every (label, stage)
call in order, so tests can assert emission order and that a phase
emits before its calls run, without wiring a real SSE stream.
"""

from skycast.sse.payloads import PipelineStage


class RecordingEmitter:
    """Async callable recording every (label, stage) call, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, PipelineStage]] = []

    async def __call__(self, label: str, stage: PipelineStage) -> None:
        self.calls.append((label, stage))
