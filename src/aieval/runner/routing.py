from collections.abc import Sequence

from aieval.domain.failure import Failure, Severity
from aieval.domain.result import EvaluationResult, EvaluationSummary


class EvaluationConfigError(ValueError):
    """Raised when an invalid configuration is passed to evaluate()."""

    pass


def resolve_severity_threshold(fail_on: str | Severity) -> Severity:
    """Parses fail_on into a Severity enum instance."""
    if isinstance(fail_on, Severity):
        return fail_on
    try:
        return Severity(fail_on.lower())
    except (ValueError, AttributeError):
        valid = [s.value for s in Severity]
        raise EvaluationConfigError(
            f"Invalid fail_on value '{fail_on}'. Expected one of {valid}"
        ) from None


def partition_failures_by_severity(
    failures: Sequence[Failure],
    threshold: Severity,
) -> tuple[tuple[Failure, ...], tuple[Failure, ...]]:
    """Splits failures into blocking failures and non-blocking warnings based on threshold.

    Returns:
        (blocking_failures, non_blocking_warnings)
    """
    blocking: list[Failure] = []
    warnings: list[Failure] = []

    for f in failures:
        # If severity is >= threshold, it blocks pass
        if f.severity >= threshold:
            blocking.append(f)
        else:
            warnings.append(f)

    return tuple(blocking), tuple(warnings)


def build_evaluation_result(
    all_failures: Sequence[Failure],
    total_checks: int,
    failed_checks_count: int,
    duration_ms: float,
    threshold: Severity,
) -> EvaluationResult:
    """Constructs the final EvaluationResult based on severity threshold."""
    blocking, warnings = partition_failures_by_severity(all_failures, threshold)
    passed = len(blocking) == 0

    summary = EvaluationSummary(
        total_checks=total_checks,
        passed_checks=total_checks - failed_checks_count,
        failed_checks=failed_checks_count,
        warnings_count=len(warnings),
        duration_ms=round(duration_ms, 3),
    )

    return EvaluationResult(
        passed=passed,
        failures=blocking,
        warnings=warnings,
        summary=summary,
    )
