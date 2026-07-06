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
    """Provider-agnostic contract for schema-enforced structured LLM output."""

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
