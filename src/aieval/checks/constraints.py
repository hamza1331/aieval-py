import re
from collections.abc import Collection
from typing import Any

from aieval.checks.base import CheckResult, resolve_field
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure, FailureCode, Severity


class RegexMatchCheck:
    """Checks that a string (or targeted field) matches a given regular expression."""

    def __init__(
        self,
        pattern: str | re.Pattern[str],
        *,
        field: str | None = None,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern)
            self.pattern_str = pattern
        else:
            self.pattern = pattern
            self.pattern_str = pattern.pattern
        self.field = field
        self.severity = severity
        if name:
            self.name = name
        elif field:
            self.name = f"regex_match({field}={self.pattern_str})"
        else:
            self.name = f"regex_match({self.pattern_str})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if self.field is not None:
            target, exists = resolve_field(output, self.field)
            if not exists:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.MISSING_REQUIRED_FIELD,
                        message=f"Field '{self.field}' is missing for regex match",
                        severity=self.severity,
                        path=self.field,
                    ),
                    name=self.name,
                )
        else:
            target = output

        if not isinstance(target, str):
            return CheckResult.failed(
                Failure(
                    code=FailureCode.REGEX_MISMATCH,
                    message=f"Expected string output for regex match, got {type(target).__name__}",
                    severity=self.severity,
                    path=self.field,
                ),
                name=self.name,
            )

        if not self.pattern.search(target):
            return CheckResult.failed(
                Failure(
                    code=FailureCode.REGEX_MISMATCH,
                    message=f"Output does not match required pattern: '{self.pattern_str}'",
                    severity=self.severity,
                    path=self.field,
                    metadata={"pattern": self.pattern_str, "sample": target[:100]},
                ),
                name=self.name,
            )
        return CheckResult.ok(name=self.name)


class AllowedValuesCheck:
    """Checks that the output value (or targeted field) belongs to a predefined set of allowed values."""

    def __init__(
        self,
        allowed: Collection[Any],
        *,
        field: str | None = None,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.allowed = set(allowed)
        self.field = field
        self.severity = severity
        if name:
            self.name = name
        elif field:
            self.name = f"allowed_values({field} in {sorted(str(x) for x in self.allowed)})"
        else:
            self.name = f"allowed_values({sorted(str(x) for x in self.allowed)})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if self.field is not None:
            target, exists = resolve_field(output, self.field)
            if not exists:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.MISSING_REQUIRED_FIELD,
                        message=f"Field '{self.field}' is missing for allowed_values check",
                        severity=self.severity,
                        path=self.field,
                    ),
                    name=self.name,
                )
        else:
            target = output

        try:
            is_member = target in self.allowed
        except TypeError:
            is_member = False

        if not is_member:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.ENUM_MISMATCH,
                    message=f"Value '{target}' is not one of the allowed values: {sorted(str(x) for x in self.allowed)}",
                    severity=self.severity,
                    path=self.field,
                    metadata={"value": str(target), "allowed": list(self.allowed)},
                ),
                name=self.name,
            )
        return CheckResult.ok(name=self.name)


class NumericRangeCheck:
    """Checks that a numeric value (or targeted field) falls within [min_val, max_val]."""

    def __init__(
        self,
        *,
        min_val: float | None = None,
        max_val: float | None = None,
        field: str | None = None,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.min_val = min_val
        self.max_val = max_val
        self.field = field
        self.severity = severity
        prefix = f"{field}=" if field else ""
        self.name = name or f"numeric_range({prefix}min={min_val}, max={max_val})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if self.field is not None:
            target, exists = resolve_field(output, self.field)
            if not exists:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.MISSING_REQUIRED_FIELD,
                        message=f"Field '{self.field}' is missing for numeric_range check",
                        severity=self.severity,
                        path=self.field,
                    ),
                    name=self.name,
                )
        else:
            target = output

        if not isinstance(target, (int, float)) or isinstance(target, bool):
            return CheckResult.failed(
                Failure(
                    code=FailureCode.VALUE_CONSTRAINT_VIOLATION,
                    message=f"Expected numeric output, got {type(target).__name__}",
                    severity=self.severity,
                    path=self.field,
                ),
                name=self.name,
            )

        if self.min_val is not None and target < self.min_val:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.VALUE_CONSTRAINT_VIOLATION,
                    message=f"Value {target} is less than minimum allowed {self.min_val}",
                    severity=self.severity,
                    path=self.field,
                    metadata={"value": target, "min": self.min_val},
                ),
                name=self.name,
            )

        if self.max_val is not None and target > self.max_val:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.VALUE_CONSTRAINT_VIOLATION,
                    message=f"Value {target} is greater than maximum allowed {self.max_val}",
                    severity=self.severity,
                    path=self.field,
                    metadata={"value": target, "max": self.max_val},
                ),
                name=self.name,
            )

        return CheckResult.ok(name=self.name)


class LengthBoundsCheck:
    """Checks that the length of a string, list, or sequence (or targeted field) falls within [min_len, max_len]."""

    def __init__(
        self,
        *,
        min_len: int | None = None,
        max_len: int | None = None,
        field: str | None = None,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.min_len = min_len
        self.max_len = max_len
        self.field = field
        self.severity = severity
        prefix = f"{field}=" if field else ""
        self.name = name or f"length_bounds({prefix}min={min_len}, max={max_len})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if self.field is not None:
            target, exists = resolve_field(output, self.field)
            if not exists:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.MISSING_REQUIRED_FIELD,
                        message=f"Field '{self.field}' is missing for length_bounds check",
                        severity=self.severity,
                        path=self.field,
                    ),
                    name=self.name,
                )
        else:
            target = output

        try:
            length = len(target)
        except TypeError:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.LENGTH_OUT_OF_BOUNDS,
                    message=f"Output of type {type(target).__name__} does not have a length",
                    severity=self.severity,
                    path=self.field,
                ),
                name=self.name,
            )

        if self.min_len is not None and length < self.min_len:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.LENGTH_OUT_OF_BOUNDS,
                    message=f"Length {length} is less than minimum required {self.min_len}",
                    severity=self.severity,
                    path=self.field,
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
                    path=self.field,
                    metadata={"length": length, "max_len": self.max_len},
                ),
                name=self.name,
            )

        return CheckResult.ok(name=self.name)


def regex_match(
    pattern: str | re.Pattern[str],
    *,
    field: str | None = None,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> RegexMatchCheck:
    return RegexMatchCheck(pattern, field=field, severity=severity, name=name)


def allowed_values(
    allowed: Collection[Any],
    *,
    field: str | None = None,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> AllowedValuesCheck:
    return AllowedValuesCheck(allowed, field=field, severity=severity, name=name)


def numeric_range(
    *,
    min_val: float | None = None,
    max_val: float | None = None,
    field: str | None = None,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> NumericRangeCheck:
    return NumericRangeCheck(
        min_val=min_val, max_val=max_val, field=field, severity=severity, name=name
    )


def length_bounds(
    *,
    min_len: int | None = None,
    max_len: int | None = None,
    field: str | None = None,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> LengthBoundsCheck:
    return LengthBoundsCheck(
        min_len=min_len, max_len=max_len, field=field, severity=severity, name=name
    )
