import re
from collections.abc import Collection
from typing import Any

from aieval.checks.base import CheckResult
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure, FailureCode, Severity


class RegexMatchCheck:
    """Checks that a string matches a given regular expression."""

    def __init__(
        self,
        pattern: str | re.Pattern[str],
        *,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern)
            self.pattern_str = pattern
        else:
            self.pattern = pattern
            self.pattern_str = pattern.pattern
        self.severity = severity
        self.name = name or f"regex_match({self.pattern_str})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if not isinstance(output, str):
            return CheckResult.failed(
                Failure(
                    code=FailureCode.REGEX_MISMATCH,
                    message=f"Expected string output for regex match, got {type(output).__name__}",
                    severity=self.severity,
                ),
                name=self.name,
            )

        if not self.pattern.search(output):
            return CheckResult.failed(
                Failure(
                    code=FailureCode.REGEX_MISMATCH,
                    message=f"Output does not match required pattern: '{self.pattern_str}'",
                    severity=self.severity,
                    metadata={"pattern": self.pattern_str, "sample": output[:100]},
                ),
                name=self.name,
            )
        return CheckResult.ok(name=self.name)


class AllowedValuesCheck:
    """Checks that the output value belongs to a predefined set of allowed values."""

    def __init__(
        self,
        allowed: Collection[Any],
        *,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.allowed = set(allowed)
        self.severity = severity
        self.name = name or f"allowed_values({list(allowed)})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        try:
            is_member = output in self.allowed
        except TypeError:
            is_member = False

        if not is_member:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.ENUM_MISMATCH,
                    message=f"Value '{output}' is not one of the allowed values: {sorted(str(x) for x in self.allowed)}",
                    severity=self.severity,
                    metadata={"value": str(output), "allowed": list(self.allowed)},
                ),
                name=self.name,
            )
        return CheckResult.ok(name=self.name)


class NumericRangeCheck:
    """Checks that a numeric value falls within [min_val, max_val]."""

    def __init__(
        self,
        *,
        min_val: float | None = None,
        max_val: float | None = None,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.min_val = min_val
        self.max_val = max_val
        self.severity = severity
        self.name = name or f"numeric_range(min={min_val}, max={max_val})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if not isinstance(output, (int, float)) or isinstance(output, bool):
            return CheckResult.failed(
                Failure(
                    code=FailureCode.VALUE_CONSTRAINT_VIOLATION,
                    message=f"Expected numeric output, got {type(output).__name__}",
                    severity=self.severity,
                ),
                name=self.name,
            )

        if self.min_val is not None and output < self.min_val:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.VALUE_CONSTRAINT_VIOLATION,
                    message=f"Value {output} is less than minimum allowed {self.min_val}",
                    severity=self.severity,
                    metadata={"value": output, "min": self.min_val},
                ),
                name=self.name,
            )

        if self.max_val is not None and output > self.max_val:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.VALUE_CONSTRAINT_VIOLATION,
                    message=f"Value {output} is greater than maximum allowed {self.max_val}",
                    severity=self.severity,
                    metadata={"value": output, "max": self.max_val},
                ),
                name=self.name,
            )

        return CheckResult.ok(name=self.name)


class LengthBoundsCheck:
    """Checks that the length of a string, list, or sequence falls within [min_len, max_len]."""

    def __init__(
        self,
        *,
        min_len: int | None = None,
        max_len: int | None = None,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.min_len = min_len
        self.max_len = max_len
        self.severity = severity
        self.name = name or f"length_bounds(min={min_len}, max={max_len})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        try:
            length = len(output)
        except TypeError:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.LENGTH_OUT_OF_BOUNDS,
                    message=f"Output of type {type(output).__name__} does not have a length",
                    severity=self.severity,
                ),
                name=self.name,
            )

        if self.min_len is not None and length < self.min_len:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.LENGTH_OUT_OF_BOUNDS,
                    message=f"Length {length} is less than minimum required {self.min_len}",
                    severity=self.severity,
                    metadata={"length": length, "min_len": self.min_len},
                ),
                name=self.name,
            )

        if self.max_len is not None and length > self.max_len:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.LENGTH_OUT_OF_BOUNDS,
                    message=f"Length {length} is greater than maximum allowed {self.max_len}",
                    severity=self.severity,
                    metadata={"length": length, "max_len": self.max_len},
                ),
                name=self.name,
            )

        return CheckResult.ok(name=self.name)


def regex_match(
    pattern: str | re.Pattern[str],
    *,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> RegexMatchCheck:
    return RegexMatchCheck(pattern, severity=severity, name=name)


def allowed_values(
    allowed: Collection[Any],
    *,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> AllowedValuesCheck:
    return AllowedValuesCheck(allowed, severity=severity, name=name)


def numeric_range(
    *,
    min_val: float | None = None,
    max_val: float | None = None,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> NumericRangeCheck:
    return NumericRangeCheck(min_val=min_val, max_val=max_val, severity=severity, name=name)


def length_bounds(
    *,
    min_len: int | None = None,
    max_len: int | None = None,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> LengthBoundsCheck:
    return LengthBoundsCheck(min_len=min_len, max_len=max_len, severity=severity, name=name)
