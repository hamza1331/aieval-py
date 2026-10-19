import asyncio
import inspect
import time
from collections.abc import Sequence
from typing import Any

from aieval.checks.base import CheckResult
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure
from aieval.domain.result import EvaluationResult
from aieval.runner.routing import (
    EvaluationConfigError,
    build_evaluation_result,
    resolve_severity_threshold,
)
from aieval.semantic.protocol import SemanticJudge


def _extract_failures(res: Any, check_name: str) -> list[Failure]:
    """Helper to normalize check / judge return value into a list of Failures."""
    if res is None:
        return []
    if isinstance(res, CheckResult):
        return list(res.failures)
    if isinstance(res, Failure):
        return [res]
    if isinstance(res, (list, tuple)):
        failures: list[Failure] = []
        for item in res:
            if isinstance(item, Failure):
                failures.append(item)
            elif isinstance(item, CheckResult):
                failures.extend(item.failures)
            else:
                raise EvaluationConfigError(
                    f"Check '{check_name}' returned unsupported result item "
                    f"'{type(item).__name__}'. Expected Failure or CheckResult."
                )
        return failures
    raise EvaluationConfigError(
        f"Check '{check_name}' returned unsupported result '{type(res).__name__}'. "
        "Expected None, Failure, CheckResult, or a sequence of Failure/CheckResult values."
    )


def evaluate(
    output: Any,
    checks: Sequence[Any],
    *,
    context: EvaluationContext | None = None,
    fail_on: str = "error",
) -> EvaluationResult:
    """Evaluates output synchronously against a sequence of checks or judges.

    Args:
        output: The output value, string, or dictionary to validate.
        checks: A list of checks, functions, or SemanticJudge objects.
        context: Optional evaluation context/metadata.
        fail_on: Severity threshold that triggers failure ("error" by default, or "warning").

    Returns:
        EvaluationResult containing pass/fail status, failures, warnings, and summary.

    Raises:
        EvaluationConfigError: If an asynchronous check/coroutine is passed into evaluate().
    """
    threshold = resolve_severity_threshold(fail_on)
    start_time = time.perf_counter()

    all_failures: list[Failure] = []
    failed_checks_count = 0
    total_checks = len(checks)

    for check in checks:
        # Prevent silent failures if user passes an async check to synchronous evaluate
        if inspect.iscoroutinefunction(check) or (
            callable(check) and inspect.iscoroutinefunction(check.__call__)
        ):
            name = getattr(check, "name", str(check))
            raise EvaluationConfigError(
                f"Check '{name}' is asynchronous. Use 'await aevaluate(...)' instead of 'evaluate(...)'."
            )

        if hasattr(check, "judge") and inspect.iscoroutinefunction(check.judge):
            name = getattr(check, "name", str(check))
            raise EvaluationConfigError(
                f"Judge '{name}' is asynchronous. Use 'await aevaluate(...)' instead of 'evaluate(...)'."
            )

        # Run check or judge
        if isinstance(check, SemanticJudge) or hasattr(check, "judge"):
            res = check.judge(output, context)
        elif callable(check):
            # Inspect signature to see if context is accepted
            sig = inspect.signature(check)
            if len(sig.parameters) >= 2 or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                res = check(output, context)
            else:
                res = check(output)
        else:
            raise EvaluationConfigError(f"Check '{check}' is neither callable nor a SemanticJudge.")

        name = getattr(check, "name", type(check).__name__)
        failures = _extract_failures(res, str(name))
        if failures:
            failed_checks_count += 1
            all_failures.extend(failures)

    duration_ms = (time.perf_counter() - start_time) * 1000.0

    return build_evaluation_result(
        all_failures=all_failures,
        total_checks=total_checks,
        failed_checks_count=failed_checks_count,
        duration_ms=duration_ms,
        threshold=threshold,
    )


async def aevaluate(
    output: Any,
    checks: Sequence[Any],
    *,
    context: EvaluationContext | None = None,
    fail_on: str = "error",
) -> EvaluationResult:
    """Evaluates output asynchronously against a sequence of checks or judges.

    Runs checks concurrently where possible.

    Args:
        output: The output value, string, or dictionary to validate.
        checks: A list of synchronous or asynchronous checks/judges.
        context: Optional evaluation context/metadata.
        fail_on: Severity threshold that triggers failure ("error" by default, or "warning").

    Returns:
        EvaluationResult containing pass/fail status, failures, warnings, and summary.
    """
    threshold = resolve_severity_threshold(fail_on)
    start_time = time.perf_counter()

    total_checks = len(checks)

    async def _run_single(check: Any) -> list[Failure]:
        if hasattr(check, "judge") and inspect.iscoroutinefunction(check.judge):
            res = await check.judge(output, context)
        elif hasattr(check, "judge"):
            res = check.judge(output, context)
        elif inspect.iscoroutinefunction(check) or (
            callable(check) and inspect.iscoroutinefunction(check.__call__)
        ):
            sig = inspect.signature(check)
            if len(sig.parameters) >= 2 or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                res = await check(output, context)
            else:
                res = await check(output)
        elif callable(check):
            sig = inspect.signature(check)
            if len(sig.parameters) >= 2 or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                res = check(output, context)
            else:
                res = check(output)
        else:
            raise EvaluationConfigError(f"Check '{check}' is neither callable nor a SemanticJudge.")

        name = getattr(check, "name", type(check).__name__)
        return _extract_failures(res, str(name))

    results = await asyncio.gather(*[_run_single(c) for c in checks])

    all_failures: list[Failure] = []
    failed_checks_count = 0

    for failures in results:
        if failures:
            failed_checks_count += 1
            all_failures.extend(failures)

    duration_ms = (time.perf_counter() - start_time) * 1000.0

    return build_evaluation_result(
        all_failures=all_failures,
        total_checks=total_checks,
        failed_checks_count=failed_checks_count,
        duration_ms=duration_ms,
        threshold=threshold,
    )
