import asyncio

import pytest

from aieval.checks import regex_match, required_fields
from aieval.domain import Failure, FailureCode, Severity
from aieval.runner import EvaluationConfigError, aevaluate, evaluate


def test_sync_evaluate_all_passed():
    output = {"id": 1, "email": "test@example.com"}
    res = evaluate(
        output,
        [
            required_fields(["id", "email"]),
            lambda out: regex_match(r"@").__call__(out["email"]),
        ],
    )
    assert res.passed is True
    assert res.summary.total_checks == 2
    assert res.summary.passed_checks == 2
    assert len(res.failures) == 0


def test_sync_evaluate_with_failures():
    output = {"id": 1}
    res = evaluate(
        output,
        [
            required_fields(["id", "email"]),
        ],
    )
    assert res.passed is False
    assert len(res.failures) == 1
    assert res.failures[0].code == FailureCode.MISSING_REQUIRED_FIELD


def test_sync_evaluate_severity_routing_warning_vs_error():
    # Warning severity failure
    check_warn = required_fields(["optional_field"], severity=Severity.WARNING)

    # By default fail_on="error", so warning should NOT fail evaluation
    res_default = evaluate({}, [check_warn], fail_on="error")
    assert res_default.passed is True
    assert len(res_default.failures) == 0
    assert len(res_default.warnings) == 1

    # In strict mode fail_on="warning", warning DOES fail evaluation
    res_strict = evaluate({}, [check_warn], fail_on="warning")
    assert res_strict.passed is False
    assert len(res_strict.failures) == 1


def test_sync_evaluate_rejects_async_check():
    async def async_checker(output):
        return []

    with pytest.raises(EvaluationConfigError) as exc_info:
        evaluate("test", [async_checker])
    assert "is asynchronous. Use 'await aevaluate(...)'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_evaluate_concurrent_checks():
    async def async_check_1(out, ctx=None):
        await asyncio.sleep(0.01)
        return []

    async def async_check_2(out, ctx=None):
        await asyncio.sleep(0.01)
        if "forbidden" in out:
            return Failure(code="POLICY_VIOLATION", message="Forbidden word detected")
        return []

    res_pass = await aevaluate("clean text", [async_check_1, async_check_2])
    assert res_pass.passed is True
    assert res_pass.summary.total_checks == 2

    res_fail = await aevaluate("forbidden content", [async_check_1, async_check_2])
    assert res_fail.passed is False
    assert len(res_fail.failures) == 1
    assert res_fail.failures[0].code == "POLICY_VIOLATION"


class CustomSemanticJudge:
    name = "custom_judge"

    def judge(self, output, context=None):
        if len(output) < 5:
            return Failure(
                code=FailureCode.SEMANTIC_JUDGE_SCORE_LOW,
                message="Output too short",
                severity=Severity.WARNING,
            )
        return None


def test_semantic_judge_support():
    judge = CustomSemanticJudge()
    res = evaluate("hi", [judge], fail_on="error")
    # Warning shouldn't fail default evaluation
    assert res.passed is True
    assert len(res.warnings) == 1
    assert res.warnings[0].code == FailureCode.SEMANTIC_JUDGE_SCORE_LOW
