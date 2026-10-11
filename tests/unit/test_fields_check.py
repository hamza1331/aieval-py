from aieval.checks import allowed_fields, required_fields
from aieval.domain import FailureCode


def test_required_fields_check():
    check = required_fields(["id", "title"])

    # Valid dict
    assert check({"id": 1, "title": "Test", "extra": "ok"}).passed is True

    # Valid JSON string
    assert check('{"id": 2, "title": "JSON"}').passed is True

    # Missing field
    res_missing = check({"id": 1})
    assert res_missing.passed is False
    assert len(res_missing.failures) == 1
    assert res_missing.failures[0].code == FailureCode.MISSING_REQUIRED_FIELD
    assert res_missing.failures[0].path == "title"

    # Non-dict / invalid JSON
    res_bad = check("not-json")
    assert res_bad.passed is False
    assert res_bad.failures[0].code == FailureCode.INVALID_JSON


def test_allowed_fields_check():
    check = allowed_fields(["id", "title"])

    # Valid
    assert check({"id": 1, "title": "Test"}).passed is True

    # Unexpected field
    res_unexp = check({"id": 1, "title": "Test", "admin": True})
    assert res_unexp.passed is False
    assert len(res_unexp.failures) == 1
    assert res_unexp.failures[0].code == FailureCode.UNEXPECTED_FIELD
    assert res_unexp.failures[0].path == "admin"
