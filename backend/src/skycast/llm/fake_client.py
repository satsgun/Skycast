"""FakeLLMClient: deterministic, offline LLMClient test double (Task 14.4).

Mirrors InMemoryProvider's role for WeatherProvider (Task 12) -- lets
stage-1 decompose (Task 14.5) and its tests run without any real LLM
call. `responses` maps the `user` query text to a canned outcome, or is a
callable computing one from the call's arguments; an outcome is either
the BaseModel instance to return, or an LLMError/StructuredOutputError
instance to raise, driving the stage's failure-handling branch on
demand.
"""

from collections.abc import Callable, Mapping
from typing import Union

from pydantic import BaseModel

from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError

Outcome = Union[BaseModel, LLMError, StructuredOutputError]
ResponseSource = Union[Mapping[str, Outcome], Callable[..., Outcome]]


class FakeLLMClient(LLMClient):
    """Deterministic LLMClient test double -- no network I/O."""

    def __init__(self, responses: ResponseSource) -> None:
        self._responses = responses

    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        if callable(self._responses):
            outcome = self._responses(
                system=system, user=user, schema=schema, tool_name=tool_name
            )
        else:
            outcome = self._responses[user]

        if isinstance(outcome, (LLMError, StructuredOutputError)):
            raise outcome
        return outcome
