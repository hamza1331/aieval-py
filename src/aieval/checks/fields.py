import json
from collections.abc import Sequence
from typing import Any

from aieval.checks.base import CheckResult
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure, FailureCode, Severity


def _normalize_dict(output: Any) -> tuple[dict[str, Any] | None, Failure | None]:
    if isinstance(output, dict):
        return output, None
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return parsed, None
            return None, Failure(
                code=FailureCode.INVALID_JSON,
                message=f"Expected JSON object, parsed {type(parsed).__name__}",
                severity=Severity.ERROR,
            )
        except json.JSONDecodeError as err:
            return None, Failure(
                code=FailureCode.INVALID_JSON,
                message=f"Output is not valid JSON: {err.msg}",
                severity=Severity.ERROR,
            )
    return None, Failure(
        code=FailureCode.INVALID_JSON,
        message=f"Output of type {type(output).__name__} is not a dictionary or JSON object",
        severity=Severity.ERROR,
    )


class RequiredFieldsCheck:
    """Checks that all specified fields are present in the output dictionary."""

    def __init__(
        self,
        fields: Sequence[str],
        *,
        severity: Severity = Severity.ERROR,
    ) -> None:
        self.fields = tuple(fields)
        self.severity = severity
        self.name = f"required_fields({list(self.fields)})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        data, err = _normalize_dict(output)
        if err is not None:
            return CheckResult.failed(err, name=self.name)
        assert data is not None

        missing = [f for f in self.fields if f not in data]
        if missing:
            failures = [
                Failure(
                    code=FailureCode.MISSING_REQUIRED_FIELD,
                    message=f"Missing required field: '{field}'",
                    severity=self.severity,
                    path=field,
                )
                for field in missing
            ]
            return CheckResult.failed(failures, name=self.name)
        return CheckResult.ok(name=self.name)


class AllowedFieldsCheck:
    """Checks that no unexpected fields are present beyond the allowed list."""

    def __init__(
        self,
        fields: Sequence[str],
        *,
        severity: Severity = Severity.ERROR,
    ) -> None:
        self.allowed = set(fields)
        self.severity = severity
        self.name = f"allowed_fields({list(fields)})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        data, err = _normalize_dict(output)
        if err is not None:
            return CheckResult.failed(err, name=self.name)
        assert data is not None

        unexpected = [f for f in data if f not in self.allowed]
        if unexpected:
            failures = [
                Failure(
                    code=FailureCode.UNEXPECTED_FIELD,
                    message=f"Unexpected field present: '{field}'",
                    severity=self.severity,
                    path=field,
                )
                for field in unexpected
            ]
            return CheckResult.failed(failures, name=self.name)
        return CheckResult.ok(name=self.name)


def required_fields(
    fields: Sequence[str],
    *,
    severity: Severity = Severity.ERROR,
) -> RequiredFieldsCheck:
    """Returns a check verifying the presence of specified fields."""
    return RequiredFieldsCheck(fields, severity=severity)


def allowed_fields(
    fields: Sequence[str],
    *,
    severity: Severity = Severity.ERROR,
) -> AllowedFieldsCheck:
    """Returns a check verifying that only allowed fields are present."""
    return AllowedFieldsCheck(fields, severity=severity)


class DisallowedFieldsCheck:
    """Checks that specific forbidden or sensitive fields are NOT present in output."""

    def __init__(
        self,
        fields: Sequence[str],
        *,
        severity: Severity = Severity.ERROR,
    ) -> None:
        self.disallowed = set(fields)
        self.severity = severity
        self.name = f"disallowed_fields({list(fields)})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        data, err = _normalize_dict(output)
        if err is not None:
            return CheckResult.failed(err, name=self.name)
        assert data is not None

        present_forbidden = [f for f in data if f in self.disallowed]
        if present_forbidden:
            failures = [
                Failure(
                    code=FailureCode.DISALLOWED_FIELD,
                    message=f"Disallowed field present: '{field}'",
                    severity=self.severity,
                    path=field,
                )
                for field in present_forbidden
            ]
            return CheckResult.failed(failures, name=self.name)
        return CheckResult.ok(name=self.name)


def disallowed_fields(
    fields: Sequence[str],
    *,
    severity: Severity = Severity.ERROR,
) -> DisallowedFieldsCheck:
    """Returns a check verifying that specified forbidden fields are absent."""
    return DisallowedFieldsCheck(fields, severity=severity)
