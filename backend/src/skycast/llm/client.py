"""Abstract seam for LLM access (Task 14.2).

Stage 1 (decompose), stage 2 (plan), and stage 4 (synthesize) call this
interface for schema-enforced structured output -- never aisuite or a
vendor SDK directly (same seam pattern as WeatherProvider, ADR-0002).
AISuiteLLMClient (Task 14.3) is the only module allowed to import
aisuite; FakeLLMClient (Task 14.4) implements this same interface for
tests.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMClient(ABC):
    """Provider-agnostic contract for schema-enforced structured LLM output.

    Optional usage contract (Task 22, not part of this abstract
    interface): an implementation MAY set `self.last_usage: Usage |
    None` (skycast.llm.usage.Usage) after each `get_structured()` call
    -- the most recent call's token usage, including any repair-retry
    call made to satisfy it -- and MAY accumulate a running
    `self.cumulative_usage: Usage | None` across every call the
    instance has ever made. Neither attribute is required:
    `get_structured()`'s return type stays just the validated model, so
    `FakeLLMClient` and every pipeline caller are unaffected whether or
    not a given implementation tracks usage. A caller reading usage
    (e.g. the eval harness's `InstrumentedLLMClient`) must treat its
    absence (`getattr(client, "last_usage", None) is None`) as
    "unknown," never as an error.
    """

    @abstractmethod
    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        """Return a validated instance of `schema`, obtained via tool calling.

        Raises LLMError on transport failure. Raises StructuredOutputError
        if the model cannot produce schema-valid output after one repair
        retry. Deliberately minimal -- one method for structured output;
        a free-text method can be added later if a stage needs one.
        """
        ...
