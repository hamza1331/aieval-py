from dataclasses import dataclass, field
from typing import Any

from aieval.domain.failure import Failure, Retryability


class EvaluationError(Exception):
    """Raised when evaluation fails and raise_for_failures() is called."""

    def __init__(self, message: str, failures: tuple[Failure, ...]) -> None:
        super().__init__(message)
        self.failures = failures


@dataclass(frozen=True)
class EvaluationSummary:
    """Statistical summary of an evaluation run."""

    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings_count: int
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warnings_count": self.warnings_count,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class EvaluationResult:
    """The complete result of an evaluation run."""

    passed: bool
    failures: tuple[Failure, ...] = field(default_factory=tuple)
    warnings: tuple[Failure, ...] = field(default_factory=tuple)
    summary: EvaluationSummary = field(
        default_factory=lambda: EvaluationSummary(
            total_checks=0, passed_checks=0, failed_checks=0, warnings_count=0
        )
    )

    @property
    def is_retryable(self) -> bool:
        """Returns True if the run passed or if ALL failures are retryable.

        If ANY failure is terminal (e.g. policy breach, unknown tool), returns False.
        """
        return self.passed or all(f.retryability == Retryability.RETRYABLE for f in self.failures)

    @property
    def has_terminal_failures(self) -> bool:
        """Returns True if one or more failures require immediate fail-closed termination."""
        return any(f.retryability == Retryability.TERMINAL for f in self.failures)

    @property
    def retryable_failures(self) -> tuple[Failure, ...]:
        """Returns only the failures that can safely enter bounded self-correction loops."""
        return tuple(f for f in self.failures if f.retryability == Retryability.RETRYABLE)

    @property
    def terminal_failures(self) -> tuple[Failure, ...]:
        """Returns the terminal failures requiring immediate fail-closed handling."""
        return tuple(f for f in self.failures if f.retryability == Retryability.TERMINAL)

    def raise_for_failures(self) -> None:
        """Raises EvaluationError if passed is False."""
        if not self.passed:
            count = len(self.failures)
            summary_str = f"Evaluation failed with {count} failure{'s' if count != 1 else ''}:\n"
            details = "\n".join(
                f"  - [{f.code}] {f.message} (path: {f.path or 'root'})" for f in self.failures
            )
            raise EvaluationError(summary_str + details, self.failures)

    def to_dict(self) -> dict[str, Any]:
        """Serializes result to a dictionary."""
        return {
            "passed": self.passed,
            "is_retryable": self.is_retryable,
            "has_terminal_failures": self.has_terminal_failures,
            "failures": [f.to_dict() for f in self.failures],
            "warnings": [w.to_dict() for w in self.warnings],
            "summary": self.summary.to_dict(),
        }
