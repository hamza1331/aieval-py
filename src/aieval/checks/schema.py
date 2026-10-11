import json
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from aieval.checks.base import CheckResult
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure, FailureCode, Severity


class SchemaCheck:
    """Validates output against a Pydantic v2 BaseModel or TypeAdapter."""

    def __init__(
        self,
        schema: type[BaseModel] | TypeAdapter[Any],
        *,
        severity: Severity = Severity.ERROR,
        name: str | None = None,
    ) -> None:
        self.schema = schema
        self.severity = severity
        if name is not None:
            self.name = name
        elif isinstance(schema, type) and issubclass(schema, BaseModel):
            self.name = f"schema_check({schema.__name__})"
        else:
            self.name = "schema_check"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        data = output

        # Auto-parse JSON string if input is string
        if isinstance(output, str):
            trimmed = output.strip()
            try:
                data = json.loads(trimmed)
            except json.JSONDecodeError as err:
                return CheckResult.failed(
                    Failure(
                        code=FailureCode.INVALID_JSON,
                        message=f"Failed to parse JSON string for schema validation: {err.msg}",
                        severity=self.severity,
                        metadata={"raw": output},
                    ),
                    name=self.name,
                )

        try:
            if isinstance(self.schema, type) and issubclass(self.schema, BaseModel):
                self.schema.model_validate(data)
            elif isinstance(self.schema, TypeAdapter):
                self.schema.validate_python(data)
            return CheckResult.ok(name=self.name)
        except ValidationError as err:
            failures: list[Failure] = []
            for e in err.errors():
                loc = e.get("loc", ())
                path_str = ".".join(str(item) for item in loc) if loc else None
                failures.append(
                    Failure(
                        code=FailureCode.SCHEMA_VALIDATION_ERROR,
                        message=e.get("msg", "Schema validation error"),
                        severity=self.severity,
                        path=path_str,
                        metadata={
                            "type": e.get("type"),
                            "input": e.get("input"),
                        },
                    )
                )
            return CheckResult.failed(failures, name=self.name)


def schema_check(
    schema: type[BaseModel] | TypeAdapter[Any],
    *,
    severity: Severity = Severity.ERROR,
    name: str | None = None,
) -> SchemaCheck:
    """Returns a check validating output against a Pydantic v2 BaseModel or TypeAdapter."""
    return SchemaCheck(schema, severity=severity, name=name)
