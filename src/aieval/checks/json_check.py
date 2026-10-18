import json
from typing import Any

from aieval.checks.base import CheckResult
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure, FailureCode, Severity


class ValidJsonCheck:
    """Checks that output is valid JSON (if string) or a valid JSON-serializable structure."""

    def __init__(
        self,
        *,
        severity: Severity = Severity.ERROR,
        name: str = "valid_json",
    ) -> None:
        self.severity = severity
        self.name = name

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        if isinstance(output, (dict, list)):
            return CheckResult.ok(name=self.name)

        if isinstance(output, str):
            trimmed = output.strip()
            if not trimmed:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.INVALID_JSON,
                        message="Output is an empty string, expected valid JSON.",
                        severity=self.severity,
                    ),
                    name=self.name,
                )
            try:
                json.loads(trimmed)
                return CheckResult.ok(name=self.name)
            except json.JSONDecodeError as err:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.INVALID_JSON,
                        message=f"Output is not valid JSON: {err.msg} at line {err.lineno} col {err.colno}",
                        severity=self.severity,
                        metadata={"error": str(err), "pos": err.pos},
                    ),
                    name=self.name,
                )

        return CheckResult.failed(
            Failure(
                code=FailureCode.INVALID_JSON,
                message=f"Output of type {type(output).__name__} is not a valid JSON string or object.",
                severity=self.severity,
            ),
            name=self.name,
        )


def valid_json(*, severity: Severity = Severity.ERROR, name: str = "valid_json") -> ValidJsonCheck:
    """Returns a check ensuring the output is valid JSON."""
    return ValidJsonCheck(severity=severity, name=name)
