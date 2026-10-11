from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure


@runtime_checkable
class SemanticJudge(Protocol):
    """Protocol for optional, advisory LLM judges."""

    name: str

    def judge(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> Sequence[Failure] | Failure | None:
        """Evaluates output and returns failure(s) if criteria are not met."""
        ...


@runtime_checkable
class AsyncSemanticJudge(Protocol):
    """Protocol for optional, asynchronous advisory LLM judges."""

    name: str

    async def judge(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> Sequence[Failure] | Failure | None:
        """Asynchronously evaluates output and returns failure(s) if criteria are not met."""
        ...
