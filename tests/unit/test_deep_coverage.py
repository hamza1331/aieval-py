import pytest
from pydantic import TypeAdapter

from aieval.checks import (
    schema_check,
    tool_call_check,
)
from aieval.domain import (
    EvaluationContext,
    Failure,
    FailureCode,
    Severity,
)
from aieval.runner import (
    EvaluationConfigError,
    aevaluate,
    evaluate,
    resolve_severity_threshold,
)


def test_severity_all_comparisons():
    s = Severity.WARNING
    assert (s > Severity.INFO) is True
    assert (s > Severity.ERROR) is False
    assert (s > "info") is True
    assert (s > "error") is False

    assert (s < Severity.CRITICAL) is True
    assert (s < Severity.INFO) is False
    assert (s < "critical") is True
    assert (s < "info") is False

    assert (s >= Severity.WARNING) is True
    assert (s >= Severity.ERROR) is False
    assert (s >= "warning") is True
    assert (s >= "invalid_severity") is False

    assert (s <= Severity.WARNING) is True
    assert (s <= Severity.INFO) is False
    assert (s <= "warning") is True
    assert (s <= "invalid_severity") is False

    assert (s == "warning") is True
    assert (s != "error") is True


def test_resolve_severity_threshold_error():
    assert resolve_severity_threshold("ERROR") == Severity.ERROR
    assert resolve_severity_threshold(Severity.CRITICAL) == Severity.CRITICAL
    with pytest.raises(EvaluationConfigError):
        resolve_severity_threshold("non_existent_severity")


def test_schema_check_type_adapter():
    adapter = TypeAdapter(list[int])
    check = schema_check(adapter)
    assert check([1, 2, 3]).passed is True
    res_bad = check(["a", "b"])
    assert res_bad.passed is False
    assert res_bad.failures[0].code == FailureCode.SCHEMA_VALIDATION_ERROR


def test_tool_call_edge_cases():
    check = tool_call_check("calc")

    # String output parsing error
    res_bad_str = check("not json tool call")
    assert res_bad_str.passed is False
    assert res_bad_str.failures[0].code == FailureCode.INVALID_JSON

    # Output not a dict
    res_non_dict = check(12345)
    assert res_non_dict.passed is False
    assert res_non_dict.failures[0].code == FailureCode.TOOL_CALL_UNKNOWN_TOOL

    # Arguments not a dict or string
    res_bad_args = check({"name": "calc", "arguments": 999})
    assert res_bad_args.passed is False
    assert res_bad_args.failures[0].code == FailureCode.TOOL_CALL_ARG_TYPE_MISMATCH

    # Arguments parsed to non-dict
    res_non_dict_args = check({"name": "calc", "arguments": "[1, 2, 3]"})
    assert res_non_dict_args.passed is False
    assert res_non_dict_args.failures[0].code == FailureCode.TOOL_CALL_INVALID_ARGS_JSON


def test_evaluator_edge_cases():
    # Non-callable check
    with pytest.raises(EvaluationConfigError):
        evaluate("test", ["not_a_check"])

    # Output with context
    def check_with_ctx(out, ctx):
        if ctx and ctx.prompt == "test":
            return []
        return [Failure(code="NO_CTX", message="Missing ctx")]

    ctx = EvaluationContext(prompt="test")
    res = evaluate("hello", [check_with_ctx], context=ctx)
    assert res.passed is True


@pytest.mark.asyncio
async def test_aevaluate_edge_cases():
    # Async check with context
    async def async_check(out, ctx=None):
        return []

    # Sync check passed to aevaluate
    def sync_check(out):
        return []

    res = await aevaluate("test", [async_check, sync_check])
    assert res.passed is True

    # Non-callable in aevaluate
    with pytest.raises(EvaluationConfigError):
        await aevaluate("test", ["invalid"])
