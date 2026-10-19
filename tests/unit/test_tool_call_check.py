from pydantic import BaseModel

from aieval.checks import tool_call_check
from aieval.domain import FailureCode


class SearchArgs(BaseModel):
    query: str
    limit: int = 10


def test_tool_call_check_dict_and_openai_json_string():
    check = tool_call_check("search_database", schema=SearchArgs, required_args=["query"])

    # Standard dictionary
    valid_dict = {"name": "search_database", "arguments": {"query": "python tutorial", "limit": 5}}
    assert check(valid_dict).passed is True

    # OpenAI format: arguments as stringified JSON
    valid_openai = {
        "name": "search_database",
        "arguments": '{"query": "python tutorial", "limit": 5}',
    }
    assert check(valid_openai).passed is True

    # OpenAI function block: { "function": { "name": ..., "arguments": ... } }
    valid_func_block = {
        "function": {
            "name": "search_database",
            "arguments": '{"query": "python tutorial"}',
        }
    }
    assert check(valid_func_block).passed is True


def test_tool_call_check_failures():
    check = tool_call_check("search_database", schema=SearchArgs, required_args=["query"])

    # Wrong tool name
    wrong_tool = {"name": "send_email", "arguments": {"query": "hello"}}
    res_wrong = check(wrong_tool)
    assert res_wrong.passed is False
    assert res_wrong.failures[0].code == FailureCode.TOOL_CALL_UNKNOWN_TOOL

    # Malformed JSON in arguments string
    bad_json_args = {"name": "search_database", "arguments": '{"query": broken'}
    res_bad_json = check(bad_json_args)
    assert res_bad_json.passed is False
    assert res_bad_json.failures[0].code == FailureCode.TOOL_CALL_INVALID_ARGS_JSON

    # Missing required argument
    missing_arg = {"name": "search_database", "arguments": {"limit": 5}}
    res_missing = check(missing_arg)
    assert res_missing.passed is False
    assert any(f.code == FailureCode.TOOL_CALL_MISSING_REQUIRED_ARG for f in res_missing.failures)

    # Argument type mismatch (Pydantic schema failure)
    bad_type = {"name": "search_database", "arguments": {"query": "ok", "limit": "not_an_int"}}
    res_type = check(bad_type)
    assert res_type.passed is False
    assert any(f.code == FailureCode.TOOL_CALL_ARG_TYPE_MISMATCH for f in res_type.failures)

    unexpected_arg = {
        "name": "search_database",
        "arguments": {"query": "python", "limit": 5, "admin": True},
    }
    res_unexpected = check(unexpected_arg)
    assert res_unexpected.passed is False
    assert any(f.code == FailureCode.TOOL_CALL_UNEXPECTED_ARG for f in res_unexpected.failures)


def test_tool_call_check_unexpected_args_follow_configuration():
    call = {"name": "search", "arguments": {"query": "docs", "extra": True}}

    strict_check = tool_call_check("search", required_args=["query"])
    assert any(f.code == FailureCode.TOOL_CALL_UNEXPECTED_ARG for f in strict_check(call).failures)

    permissive_check = tool_call_check(
        "search",
        required_args=["query"],
        allow_unexpected_args=True,
    )
    assert permissive_check(call).passed is True


def test_tool_call_check_schema_allows_declared_optional_fields():
    check = tool_call_check("search_database", schema=SearchArgs)

    assert check({"name": "search_database", "arguments": {"query": "python"}}).passed is True
    result = check({"name": "search_database", "arguments": {"query": "python", "admin": True}})
    assert result.passed is False
    assert any(f.code == FailureCode.TOOL_CALL_UNEXPECTED_ARG for f in result.failures)


def test_tool_call_check_one_of():
    check1 = tool_call_check("search", required_args=["query"])
    check2 = tool_call_check("fetch_url", required_args=["url"])
    multi_check = tool_call_check.one_of([check1, check2])

    assert multi_check({"name": "search", "arguments": {"query": "cats"}}).passed is True
    assert (
        multi_check({"name": "fetch_url", "arguments": {"url": "https://example.com"}}).passed
        is True
    )

    res_unknown = multi_check({"name": "delete_all", "arguments": {}})
    assert res_unknown.passed is False
    assert res_unknown.failures[0].code == FailureCode.TOOL_CALL_UNKNOWN_TOOL
