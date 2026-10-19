import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure


def resolve_field(output: Any, field_path: str | None) -> tuple[Any, bool]:
    """Resolves a field from an output dictionary, list or object.

    Supports:
    - None or empty string: returns (output, True)
    - Simple keys: 'category' -> output['category']
    - JSONPath style leading '$.': '$.category' -> output['category']
    - Dot notation: 'customer.tier' -> output['customer']['tier']

    Returns:
        (resolved_value, exists_flag)
    """
    if field_path is None or field_path == "":
        return output, True

    current = output
    if isinstance(current, str):
        try:
            parsed = json.loads(current)
            if isinstance(parsed, (dict, list)):
                current = parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    normalized_path = field_path[2:] if field_path.startswith("$.") else field_path
    if not normalized_path:
        return current, True

    parts = normalized_path.split(".")
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None, False
    return current, True


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
