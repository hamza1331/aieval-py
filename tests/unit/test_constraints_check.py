from aieval.checks import (
    allowed_values,
    length_bounds,
    numeric_range,
    regex_match,
)
from aieval.domain import FailureCode


def test_regex_match():
    check = regex_match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    assert check("test@example.com").passed is True

    res = check("invalid-email")
    assert res.passed is False
    assert res.failures[0].code == FailureCode.REGEX_MISMATCH

    res_type = check(123)
    assert res_type.passed is False
    assert res_type.failures[0].code == FailureCode.REGEX_MISMATCH


def test_allowed_values():
    check = allowed_values(["pending", "approved", "rejected"])
    assert check("approved").passed is True

    res = check("unknown_status")
    assert res.passed is False
    assert res.failures[0].code == FailureCode.ENUM_MISMATCH


def test_numeric_range():
    check = numeric_range(min_val=0.0, max_val=1.0)
    assert check(0.5).passed is True
    assert check(0).passed is True
    assert check(1.0).passed is True

    res_low = check(-0.1)
    assert res_low.passed is False
    assert res_low.failures[0].code == FailureCode.VALUE_CONSTRAINT_VIOLATION

    res_high = check(1.5)
    assert res_high.passed is False
    assert res_high.failures[0].code == FailureCode.VALUE_CONSTRAINT_VIOLATION

    res_bool = check(True)  # booleans should be rejected
    assert res_bool.passed is False


def test_length_bounds():
    check = length_bounds(min_len=2, max_len=5)
    assert check("abc").passed is True
    assert check([1, 2, 3, 4]).passed is True

    res_short = check("a")
    assert res_short.passed is False
    assert res_short.failures[0].code == FailureCode.LENGTH_OUT_OF_BOUNDS

    res_long = check("123456")
    assert res_long.passed is False
    assert res_long.failures[0].code == FailureCode.LENGTH_OUT_OF_BOUNDS

