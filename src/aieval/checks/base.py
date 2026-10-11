from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure


@dataclass(frozen=True)
class CheckResult:
    """The outcome of an individual check."""

    passed: bool
    failures: tuple[Failure, ...] = field(default_factory=tuple)
    name: str = "check"

    @classmethod
    def ok(cls, name: str = "check") -> "CheckResult":
        return cls(passed=True, failures=(), name=name)

    @classmethod
    def failed(
        cls,
        failures: Sequence[Failure] | Failure,
        name: str = "check",
    ) -> "CheckResult":
        if isinstance(failures, Failure):
            return cls(passed=False, failures=(failures,), name=name)
        return cls(passed=False, failures=tuple(failures), name=name)


@runtime_checkable
class Check(Protocol):
    """Protocol for synchronous validation checks."""

    name: str

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult | Sequence[Failure] | None: ...


@runtime_checkable
class AsyncCheck(Protocol):
    """Protocol for asynchronous validation checks."""

    name: str

    async def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult | Sequence[Failure] | None: ...
