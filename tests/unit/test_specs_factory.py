"""Unit tests for declarative check spec factory and field targeting."""

import pytest

from aieval import build_check_from_spec, evaluate
from aieval.domain.failure import FailureCode, Severity


def test_appendix_a_support_ticket_valid():
    """Verify Appendix A Support Ticket contract passes on valid payload."""
    contract_checks = [
        {
            "type": "required_fields",
            "fields": ["category", "priority", "summary"],
        },
        {
            "type": "enum",
            "field": "category",
            "allowed": ["billing", "technical", "account", "other"],
        },
        {
            "type": "enum",
            "field": "priority",
            "allowed": ["low", "normal", "high", "urgent"],
        },
        {
            "type": "max_length",
            "field": "summary",
            "max": 300,
        },
    ]

    checks = [build_check_from_spec(s) for s in contract_checks]

    valid_output = {
        "category": "billing",
        "priority": "urgent",
        "summary": "Customer unable to update billing card details",
    }

    result = evaluate(valid_output, checks)
    assert result.passed is True
    assert len(result.failures) == 0
    assert result.summary.passed_checks == 4


def test_appendix_a_support_ticket_missing_field():
    """Verify missing required field fails with path."""
    contract_checks = [
        {
            "type": "required_fields",
            "fields": ["category", "priority", "summary"],
        },
        {
            "type": "enum",
            "field": "category",
            "allowed": ["billing", "technical", "account", "other"],
        },
        {
            "type": "max_length",
            "field": "summary",
            "max": 300,
        },
    ]

    checks = [build_check_from_spec(s) for s in contract_checks]

    invalid_output = {
        "category": "billing",
        "priority": "urgent",
        # summary is missing
    }

    result = evaluate(invalid_output, checks)
    assert result.passed is False
    codes = [f.code for f in result.failures]
    paths = [f.path for f in result.failures]

    assert FailureCode.MISSING_REQUIRED_FIELD in codes
    assert "summary" in paths


def test_appendix_a_support_ticket_invalid_enum():
    """Verify invalid enum value fails with ENUM_MISMATCH and accurate path."""
    spec = {
        "type": "enum",
        "field": "priority",
        "allowed": ["low", "normal", "high", "urgent"],
    }
    check = build_check_from_spec(spec)

    output = {"category": "billing", "priority": "urgent_now", "summary": "Urgent ticket"}
    result = evaluate(output, [check])

    assert result.passed is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code == FailureCode.ENUM_MISMATCH
    assert failure.path == "priority"
    assert "urgent_now" in failure.message


def test_appendix_a_support_ticket_max_length_exceeded():
    """Verify max_length constraint check on field fails with LENGTH_OUT_OF_BOUNDS and path."""
    spec = {
        "type": "max_length",
        "field": "summary",
        "max": 10,
    }
    check = build_check_from_spec(spec)

    output = {"summary": "This summary is definitely longer than ten chars"}
    result = evaluate(output, [check])

    assert result.passed is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code == FailureCode.LENGTH_OUT_OF_BOUNDS
    assert failure.path == "summary"


def test_spec_factory_aliases_and_types():
    """Verify all aliases and parameter variants."""
    # min_length / min_len
    c1 = build_check_from_spec({"type": "min_len", "min": 5, "field": "code"})
    assert evaluate({"code": "abc"}, [c1]).passed is False
    assert evaluate({"code": "abcdef"}, [c1]).passed is True

    # length_bounds with length alias
    c2 = build_check_from_spec({"type": "length", "min": 2, "max": 4, "field": "pin"})
    assert evaluate({"pin": "1"}, [c2]).passed is False
    assert evaluate({"pin": "12345"}, [c2]).passed is False
    assert evaluate({"pin": "123"}, [c2]).passed is True

    # numeric_range with range alias
    c3 = build_check_from_spec({"type": "range", "min": 1.0, "max": 10.0, "field": "rating"})
    assert evaluate({"rating": 0.5}, [c3]).passed is False
    assert evaluate({"rating": 5.0}, [c3]).passed is True

    # regex_match with pattern / regex aliases
    c4 = build_check_from_spec({"type": "pattern", "pattern": r"^\d{4}$", "field": "code"})
    assert evaluate({"code": "123"}, [c4]).passed is False
    assert evaluate({"code": "1234"}, [c4]).passed is True

    # allowed_fields with whitelist_fields alias
    c5 = build_check_from_spec({"type": "whitelist_fields", "fields": ["a", "b"]})
    assert evaluate({"a": 1, "b": 2}, [c5]).passed is True
    assert evaluate({"a": 1, "b": 2, "c": 3}, [c5]).passed is False

    # valid_json alias
    c6 = build_check_from_spec({"type": "json"})
    assert evaluate('{"ok": true}', [c6]).passed is True
    assert evaluate("not json", [c6]).passed is False

    # tool_call alias
    c7 = build_check_from_spec({"type": "tool", "name": "search", "required_args": ["q"]})
    assert evaluate({"name": "search", "arguments": {"q": "python"}}, [c7]).passed is True
    assert evaluate({"name": "wrong_tool", "arguments": {"q": "python"}}, [c7]).passed is False


def test_nested_field_path_and_jsonpath():
    """Verify dot notation and leading $. field path resolution."""
    spec_dot = {
        "type": "range",
        "min": 18,
        "max": 120,
        "field": "profile.demographics.age",
    }
    check_dot = build_check_from_spec(spec_dot)

    payload = {"profile": {"demographics": {"age": 25}}}
    assert evaluate(payload, [check_dot]).passed is True

    payload_invalid = {"profile": {"demographics": {"age": 15}}}
    res = evaluate(payload_invalid, [check_dot])
    assert res.passed is False
    assert res.failures[0].path == "profile.demographics.age"

    # JSONPath syntax $.field
    spec_jsonpath = {
        "type": "enum",
        "field": "$.status",
        "allowed": ["active", "pending"],
    }
    check_jsonpath = build_check_from_spec(spec_jsonpath)
    assert evaluate({"status": "active"}, [check_jsonpath]).passed is True
    res2 = evaluate({"status": "suspended"}, [check_jsonpath])
    assert res2.passed is False
    assert res2.failures[0].path == "$.status"


def test_severity_parsing():
    """Verify severity parsing in check spec."""
    spec_warn = {
        "type": "enum",
        "field": "tag",
        "allowed": ["vip"],
        "severity": "warning",
    }
    check = build_check_from_spec(spec_warn)
    result = evaluate({"tag": "standard"}, [check])
    # Under default fail_on="error", warning does not fail the run
    assert result.passed is True
    assert len(result.warnings) == 1
    assert result.warnings[0].severity == Severity.WARNING


def test_spec_factory_invalid_specs():
    """Verify error handling on invalid specifications."""
    with pytest.raises(TypeError, match="Check spec must be a dictionary"):
        build_check_from_spec("not a dict")  # type: ignore

    with pytest.raises(ValueError, match="Check spec must contain a string 'type' field"):
        build_check_from_spec({})

    with pytest.raises(ValueError, match="Unknown or unsupported check type"):
        build_check_from_spec({"type": "nonexistent_check"})

    with pytest.raises(ValueError, match="Invalid severity"):
        build_check_from_spec({"type": "json", "severity": "super_critical"})
