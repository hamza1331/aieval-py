import pytest

from aieval.domain import (
    EvaluationError,
    EvaluationResult,
    EvaluationSummary,
    Failure,
    FailureCode,
    Severity,
)


def test_severity_ordering():
    assert Severity.INFO < Severity.WARNING
    assert Severity.WARNING < Severity.ERROR
    assert Severity.ERROR < Severity.CRITICAL
    assert Severity.CRITICAL >= Severity.ERROR
    assert Severity.ERROR >= "warning"
    assert Severity.WARNING <= "error"


def test_failure_serialization():
    f = Failure(
        code=FailureCode.MISSING_REQUIRED_FIELD,
        message="Missing required field 'email'",
        severity=Severity.ERROR,
        path=("user", "profile", "email"),
        metadata={"key": "email"},
        suggested_repair="Ensure 'email' is populated",
    )
    d = f.to_dict()
    assert d["code"] == "MISSING_REQUIRED_FIELD"
    assert d["message"] == "Missing required field 'email'"
    assert d["severity"] == "error"
    assert d["path"] == "user.profile.email"
    assert d["metadata"] == {"key": "email"}
    assert d["suggested_repair"] == "Ensure 'email' is populated"


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
    assert len(d["failures"]) == 1
    assert len(d["warnings"]) == 1
    assert d["summary"]["total_checks"] == 2

    with pytest.raises(EvaluationError) as exc_info:
        res.raise_for_failures()

    assert "Evaluation failed with 1 failure" in str(exc_info.value)
    assert exc_info.value.failures == (f,)
