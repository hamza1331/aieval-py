import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from aieval.checks.base import CheckResult
from aieval.domain.context import EvaluationContext
from aieval.domain.failure import Failure, FailureCode, Severity


class ToolCallCheck:
    """Pre-flight validator for agent tool call invocations."""

    def __init__(
        self,
        name: str,
        *,
        schema: type[BaseModel] | TypeAdapter[Any] | None = None,
        required_args: Sequence[str] | None = None,
        allow_unexpected_args: bool = False,
        severity: Severity = Severity.ERROR,
    ) -> None:
        self.tool_name = name
        self.schema = schema
        self.required_args = tuple(required_args) if required_args else ()
        self.allow_unexpected_args = allow_unexpected_args
        self.severity = severity
        self.name = f"tool_call_check({name})"

    def _normalize_call(
        self, output: Any
    ) -> tuple[str | None, dict[str, Any] | None, Failure | None]:
        if not isinstance(output, dict):
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except json.JSONDecodeError as err:
                    return (
                        None,
                        None,
                        Failure(
                            code=FailureCode.INVALID_JSON,
                            message=f"Tool call is not valid JSON: {err.msg}",
                            severity=self.severity,
                        ),
                    )
            if not isinstance(output, dict):
                return (
                    None,
                    None,
                    Failure(
                        code=FailureCode.TOOL_CALL_UNKNOWN_TOOL,
                        message=f"Tool call must be a dictionary or JSON object, got {type(output).__name__}",
                        severity=self.severity,
                    ),
                )

        # Support OpenAI function format: { "function": { "name": ..., "arguments": ... } }
        call_dict: dict[str, Any] = output
        if "function" in call_dict and isinstance(call_dict["function"], dict):
            call_dict = call_dict["function"]

        tool_name = call_dict.get("name")
        raw_args = call_dict.get("arguments", call_dict.get("args", {}))

        # Check if arguments are stringified JSON (OpenAI standard)
        args_dict: dict[str, Any]
        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args)
                if not isinstance(parsed_args, dict):
                    return (
                        tool_name,
                        None,
                        Failure(
                            code=FailureCode.TOOL_CALL_INVALID_ARGS_JSON,
                            message=f"Tool call arguments parsed to {type(parsed_args).__name__}, expected object",
                            severity=self.severity,
                            metadata={"raw_args": raw_args},
                        ),
                    )
                args_dict = parsed_args
            except json.JSONDecodeError as err:
                return (
                    tool_name,
                    None,
                    Failure(
                        code=FailureCode.TOOL_CALL_INVALID_ARGS_JSON,
                        message=f"Tool call arguments could not be parsed as JSON: {err.msg}",
                        severity=self.severity,
                        metadata={"raw_args": raw_args},
                    ),
                )
        elif isinstance(raw_args, dict):
            args_dict = raw_args
        else:
            return (
                tool_name,
                None,
                Failure(
                    code=FailureCode.TOOL_CALL_ARG_TYPE_MISMATCH,
                    message=f"Tool arguments must be a dict or stringified JSON, got {type(raw_args).__name__}",
                    severity=self.severity,
                ),
            )

        return tool_name, args_dict, None

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        actual_name, args_dict, failure = self._normalize_call(output)
        if failure is not None:
            return CheckResult.failed(failure, name=self.name)

        if actual_name != self.tool_name:
            return CheckResult.failed(
                Failure(
                    code=FailureCode.TOOL_CALL_UNKNOWN_TOOL,
                    message=f"Expected tool '{self.tool_name}', got '{actual_name}'",
                    severity=self.severity,
                    metadata={"expected": self.tool_name, "actual": actual_name},
                ),
                name=self.name,
            )

        assert args_dict is not None
        failures: list[Failure] = []

        # Check required args
        for req in self.required_args:
            if req not in args_dict:
                failures.append(
                    Failure(
                        code=FailureCode.TOOL_CALL_MISSING_REQUIRED_ARG,
                        message=f"Tool '{self.tool_name}' missing required argument: '{req}'",
                        severity=self.severity,
                        path=req,
                    )
                )

        # Check schema if provided
        if self.schema is not None:
            try:
                if isinstance(self.schema, type) and issubclass(self.schema, BaseModel):
                    self.schema.model_validate(args_dict)
                elif isinstance(self.schema, TypeAdapter):
                    self.schema.validate_python(args_dict)
            except ValidationError as val_err:
                for err in val_err.errors():
                    loc = err.get("loc", ())
                    path_str = ".".join(str(item) for item in loc) if loc else None
                    failures.append(
                        Failure(
                            code=FailureCode.TOOL_CALL_ARG_TYPE_MISMATCH,
                            message=f"Argument validation failed: {err.get('msg')}",
                            severity=self.severity,
                            path=path_str,
                            metadata={"type": err.get("type")},
                        )
                    )

        if failures:
            return CheckResult.failed(failures, name=self.name)
        return CheckResult.ok(name=self.name)


class MultiToolCallCheck:
    """Validates that a tool call matches one of multiple permitted tool call checks."""

    def __init__(
        self,
        checks: Sequence[ToolCallCheck],
        *,
        severity: Severity = Severity.ERROR,
    ) -> None:
        self.checks = tuple(checks)
        self.severity = severity
        tool_names = [c.tool_name for c in self.checks]
        self.name = f"tool_call_check.one_of({tool_names})"

    def __call__(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> CheckResult:
        # Determine actual tool name
        sample_check = self.checks[0]
        actual_name, _, failure = sample_check._normalize_call(output)
        if failure is not None:
            return CheckResult.failed(failure, name=self.name)

        matching_checks = [c for c in self.checks if c.tool_name == actual_name]
        if not matching_checks:
            allowed_names = [c.tool_name for c in self.checks]
            return CheckResult.failed(
                Failure(
                    code=FailureCode.TOOL_CALL_UNKNOWN_TOOL,
                    message=f"Tool '{actual_name}' is not in allowed tools: {allowed_names}",
                    severity=self.severity,
                    metadata={"actual": actual_name, "allowed": allowed_names},
                ),
                name=self.name,
            )

        # Run matching check
        return matching_checks[0](output, context)


def tool_call_check(
    name: str,
    *,
    schema: type[BaseModel] | TypeAdapter[Any] | None = None,
    required_args: Sequence[str] | None = None,
    allow_unexpected_args: bool = False,
    severity: Severity = Severity.ERROR,
) -> ToolCallCheck:
    """Returns a check validating agent tool calls."""
    return ToolCallCheck(
        name=name,
        schema=schema,
        required_args=required_args,
        allow_unexpected_args=allow_unexpected_args,
        severity=severity,
    )


def tool_call_one_of(
    checks: Sequence[ToolCallCheck],
    *,
    severity: Severity = Severity.ERROR,
) -> MultiToolCallCheck:
    """Validates that a tool call matches one of multiple specified ToolCallCheck instances."""
    return MultiToolCallCheck(checks, severity=severity)


# Attach one_of as a namespace method
tool_call_check.one_of = tool_call_one_of  # type: ignore[attr-defined]
