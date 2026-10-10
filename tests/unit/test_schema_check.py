from pydantic import BaseModel, Field

from aieval.checks import schema_check, valid_json
from aieval.domain import FailureCode


class UserProfile(BaseModel):
    name: str
    age: int = Field(ge=0)
    email: str


def test_valid_json_check():
    check = valid_json()

    # Valid dict / list
    assert check({"a": 1}).passed is True
    assert check([1, 2, 3]).passed is True

    # Valid string
    assert check('{"name": "Alice"}').passed is True

    # Empty string
    res_empty = check("")
    assert res_empty.passed is False
    assert res_empty.failures[0].code == FailureCode.INVALID_JSON

    # Invalid JSON string
    res_bad = check('{"name": "Alice"')
    assert res_bad.passed is False
    assert res_bad.failures[0].code == FailureCode.INVALID_JSON

    # Invalid type
    res_type = check(12345)
    assert res_type.passed is False
    assert res_type.failures[0].code == FailureCode.INVALID_JSON


def test_schema_check_pydantic():
    check = schema_check(UserProfile)

    # Valid dict
    assert check({"name": "Alice", "age": 30, "email": "alice@example.com"}).passed is True

    # Valid stringified JSON
    assert check('{"name": "Bob", "age": 25, "email": "bob@example.com"}').passed is True

    # Invalid JSON string
    res_bad_json = check("{not valid json")
    assert res_bad_json.passed is False
    assert res_bad_json.failures[0].code == FailureCode.INVALID_JSON

    # Schema validation failure (missing field & invalid type)
    res_val = check({"name": "Charlie", "age": -5})
    assert res_val.passed is False
    assert len(res_val.failures) == 2  # age ge 0 + missing email
    assert all(f.code == FailureCode.SCHEMA_VALIDATION_ERROR for f in res_val.failures)
