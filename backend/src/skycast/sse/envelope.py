"""SSE envelope model for the FE<->BE wire contract (ADR-0003, Task 13.3).

Every SSE event is one SSEEvent: {type, data} -- the uniform shape Task 13
specifies so the frontend's single onmessage handler can dispatch on
`type` alone. The typed constructors (step/clarify/answer/error) are the
sanctioned way to build one; they guarantee `type` and `data` agree, an
invariant a directly-constructed mismatch would otherwise violate
silently. Task 13.4 turns one of these into the actual `data: ...\n\n`
wire bytes.
"""

from pydantic import BaseModel, ConfigDict, model_validator

from skycast.domain.location import Location
from skycast.sse.events import SSEEventType
from skycast.sse.payloads import (
    AnswerCard,
    AnswerPayload,
    ClarifyPayload,
    ErrorKind,
    ErrorPayload,
    PipelineStage,
    StepPayload,
)

_PAYLOAD_TYPE_BY_EVENT_TYPE: dict[SSEEventType, type] = {
    SSEEventType.STEP: StepPayload,
    SSEEventType.CLARIFY: ClarifyPayload,
    SSEEventType.ANSWER: AnswerPayload,
    SSEEventType.ERROR: ErrorPayload,
}


class SSEEvent(BaseModel):
    """The uniform {type, data} envelope every SSE event is sent as."""

    model_config = ConfigDict(frozen=True)

    type: SSEEventType
    data: StepPayload | ClarifyPayload | AnswerPayload | ErrorPayload

    @model_validator(mode="after")
    def _require_data_matches_type(self) -> "SSEEvent":
        expected = _PAYLOAD_TYPE_BY_EVENT_TYPE[self.type]
        if not isinstance(self.data, expected):
            raise ValueError(
                f"type={self.type.value!r} requires data to be "
                f"{expected.__name__}, got {type(self.data).__name__}"
            )
        return self

    @classmethod
    def step(cls, label: str, stage: PipelineStage) -> "SSEEvent":
        return cls(type=SSEEventType.STEP, data=StepPayload(label=label, stage=stage))

    @classmethod
    def clarify(
        cls,
        candidates: list[Location],
        *,
        for_location_name: str,
        resolved: dict[str, Location] | None = None,
    ) -> "SSEEvent":
        return cls(
            type=SSEEventType.CLARIFY,
            data=ClarifyPayload(
                candidates=candidates,
                for_location_name=for_location_name,
                resolved=resolved or {},
            ),
        )

    @classmethod
    def answer(cls, text: str, card: AnswerCard) -> "SSEEvent":
        return cls(type=SSEEventType.ANSWER, data=AnswerPayload(text=text, card=card))

    @classmethod
    def error(cls, kind: ErrorKind, message: str) -> "SSEEvent":
        return cls(
            type=SSEEventType.ERROR, data=ErrorPayload(kind=kind, message=message)
        )
