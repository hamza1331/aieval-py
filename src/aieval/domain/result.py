from dataclasses import dataclass, field
from typing import Any

from aieval.domain.failure import Failure


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
            "failures": [f.to_dict() for f in self.failures],
            "warnings": [w.to_dict() for w in self.warnings],
            "summary": self.summary.to_dict(),
        }

