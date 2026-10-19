import pytest

from aieval.domain import (
    EvaluationError,
    EvaluationResult,
    EvaluationSummary,
    Failure,
    FailureCode,
    Retryability,
    Severity,
)


def test_severity_ordering():
    assert Severity.INFO < Severity.WARNING
    assert Severity.WARNING < Severity.ERROR
    assert Severity.ERROR < Severity.CRITICAL
    assert Severity.CRITICAL >= Severity.ERROR
    assert Severity.ERROR >= "warning"
    assert Severity.WARNING <= "error"


def test_retryability_defaults_and_serialization():
    # Retryable failure
    f_retry = Failure(
        code=FailureCode.MISSING_REQUIRED_FIELD,
        message="Missing required field 'email'",
        severity=Severity.ERROR,
        path=("user", "profile", "email"),
        metadata={"key": "email"},
        suggested_repair="Ensure 'email' is populated",
    )
    assert f_retry.retryability == Retryability.RETRYABLE
    d_retry = f_retry.to_dict()
    assert d_retry["code"] == "MISSING_REQUIRED_FIELD"
    assert d_retry["retryability"] == "retryable"
    assert d_retry["suggested_repair"] == "Ensure 'email' is populated"

    # Terminal failure (unknown tool)
    f_terminal = Failure(
        code=FailureCode.TOOL_CALL_UNKNOWN_TOOL,
        message="Disallowed tool called",
        severity=Severity.CRITICAL,
        suggested_repair="Try another tool",  # Should be suppressed by non-downgrade invariant!
    )
    assert f_terminal.retryability == Retryability.TERMINAL
    assert f_terminal.suggested_repair is None  # Non-downgrade invariant enforced!
    d_terminal = f_terminal.to_dict()
    assert d_terminal["retryability"] == "terminal"
    assert "suggested_repair" not in d_terminal

    # Policy violation
    f_policy = Failure(
        code=FailureCode.POLICY_VIOLATION,
        message="Safety policy breach",
    )
    assert f_policy.retryability == Retryability.TERMINAL
    assert f_policy.to_dict()["retryability"] == "terminal"

    # Disallowed field
    f_field = Failure(
        code=FailureCode.DISALLOWED_FIELD,
        message="Disallowed field __internal_token present",
    )
    assert f_field.retryability == Retryability.TERMINAL


def test_evaluation_result_retryability_properties():
    f_repairable = Failure(
        code=FailureCode.MISSING_REQUIRED_FIELD,
        message="Missing required field 'name'",
    )
    f_terminal = Failure(
        code=FailureCode.POLICY_VIOLATION,
        message="Prohibited operation attempted",
    )

    # 1. Passing run is always retryable / has no terminal failures
    res_pass = EvaluationResult(passed=True)
    assert res_pass.is_retryable is True
    assert res_pass.has_terminal_failures is False
    assert res_pass.terminal_failures == ()
    assert res_pass.retryable_failures == ()

    # 2. Failing run with only retryable failures
    res_retryable = EvaluationResult(
        passed=False,
        failures=(f_repairable,),
    )
    assert res_retryable.is_retryable is True
    assert res_retryable.has_terminal_failures is False
    assert res_retryable.retryable_failures == (f_repairable,)
    assert res_retryable.terminal_failures == ()

    # 3. Failing run with terminal failure -> fails closed (is_retryable is False)
    res_terminal = EvaluationResult(
        passed=False,
        failures=(f_repairable, f_terminal),
    )
    assert res_terminal.is_retryable is False
    assert res_terminal.has_terminal_failures is True
    assert res_terminal.retryable_failures == (f_repairable,)
    assert res_terminal.terminal_failures == (f_terminal,)

    d = res_terminal.to_dict()
    assert d["is_retryable"] is False
    assert d["has_terminal_failures"] is True


def test_evaluation_result_serialization_and_exception():
    f = Failure(
        code=FailureCode.INVALID_JSON,
        message="Invalid JSON payload",
        severity=Severity.ERROR,
        path="root",
    )
    w = Failure(
        code="MINOR_WARN",
        message="Minor warning",
        severity=Severity.WARNING,
    )
    summary = EvaluationSummary(
        total_checks=2,
        passed_checks=1,
        failed_checks=1,
        warnings_count=1,
        duration_ms=1.23,
    )
    res = EvaluationResult(
        passed=False,
        failures=(f,),
        warnings=(w,),
        summary=summary,
    )
    d = res.to_dict()
    assert d["passed"] is False
    assert d["is_retryable"] is True
    assert d["has_terminal_failures"] is False
    assert len(d["failures"]) == 1
    assert len(d["warnings"]) == 1
    assert d["summary"]["total_checks"] == 2

    with pytest.raises(EvaluationError) as exc_info:
        res.raise_for_failures()

    assert "Evaluation failed with 1 failure" in str(exc_info.value)
    assert exc_info.value.failures == (f,)
