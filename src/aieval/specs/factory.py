"""Declarative specification factory for building aieval Check objects from dictionaries."""

from typing import Any

from aieval.checks import (
    Check,
    allowed_fields,
    allowed_values,
    disallowed_fields,
    length_bounds,
    numeric_range,
    regex_match,
    required_fields,
    tool_call_check,
    valid_json,
)
from aieval.domain.failure import Severity


def _parse_severity(raw: Any) -> Severity:
    if isinstance(raw, Severity):
        return raw
    if isinstance(raw, str):
        try:
            return Severity(raw.lower())
        except ValueError as err:
            raise ValueError(
                f"Invalid severity '{raw}'. Allowed values: {[s.value for s in Severity]}"
            ) from err
    return Severity.ERROR


def build_check_from_spec(spec: dict[str, Any]) -> Check:
    """Builds an aieval Check from a declarative specification dictionary.

    Supports canonical types and common aliases:
    - 'required_fields' | 'required': fields, severity
    - 'allowed_fields' | 'whitelist_fields': fields, severity
    - 'enum' | 'allowed_values': allowed (or values), field, severity
    - 'max_length' | 'max_len': max (or max_len), field, severity
    - 'min_length' | 'min_len': min (or min_len), field, severity
    - 'length_bounds' | 'length': min_len/min, max_len/max, field, severity
    - 'numeric_range' | 'range': min_val/min, max_val/max, field, severity
    - 'regex_match' | 'regex' | 'pattern': pattern, field, severity
    - 'valid_json' | 'json': severity
    - 'tool_call' | 'tool': name, required_args, allow_unexpected_args, severity
    """
    if not isinstance(spec, dict):
        raise TypeError(f"Check spec must be a dictionary, got {type(spec).__name__}")

    raw_type = spec.get("type")
    if not raw_type or not isinstance(raw_type, str):
        raise ValueError(f"Check spec must contain a string 'type' field, got: {raw_type}")

    check_type = raw_type.strip().lower()
    severity = _parse_severity(spec.get("severity", Severity.ERROR))
    field = spec.get("field")

    if check_type in ("valid_json", "json"):
        return valid_json(severity=severity)

    elif check_type in ("required_fields", "required"):
        raw_fields = spec.get("fields")
        if raw_fields is None:
            raise ValueError("Check type 'required_fields' requires 'fields' list")
        if isinstance(raw_fields, str):
            fields_list = [raw_fields]
        elif isinstance(raw_fields, (list, tuple)):
            fields_list = list(raw_fields)
        else:
            raise TypeError(f"'fields' must be a list of strings, got {type(raw_fields).__name__}")
        return required_fields(fields_list, severity=severity)

    elif check_type in ("allowed_fields", "whitelist_fields"):
        raw_fields = spec.get("fields")
        if raw_fields is None:
            raise ValueError("Check type 'allowed_fields' requires 'fields' list")
        if isinstance(raw_fields, str):
            fields_list = [raw_fields]
        elif isinstance(raw_fields, (list, tuple)):
            fields_list = list(raw_fields)
        else:
            raise TypeError(f"'fields' must be a list of strings, got {type(raw_fields).__name__}")
        return allowed_fields(fields_list, severity=severity)

    elif check_type in ("disallowed_fields", "forbidden_fields", "forbidden"):
        raw_fields = spec.get("fields")
        if raw_fields is None:
            raise ValueError("Check type 'disallowed_fields' requires 'fields' list")
        if isinstance(raw_fields, str):
            fields_list = [raw_fields]
        elif isinstance(raw_fields, (list, tuple)):
            fields_list = list(raw_fields)
        else:
            raise TypeError(f"'fields' must be a list of strings, got {type(raw_fields).__name__}")
        return disallowed_fields(fields_list, severity=severity)

    elif check_type in ("enum", "allowed_values"):
        allowed = spec.get("allowed") if "allowed" in spec else spec.get("values")
        if allowed is None:
            raise ValueError(
                "Check type 'enum' / 'allowed_values' requires 'allowed' or 'values' list"
            )
        if not isinstance(allowed, (list, tuple, set)):
            raise TypeError(f"'allowed' must be a list or set, got {type(allowed).__name__}")
        return allowed_values(list(allowed), field=field, severity=severity)

    elif check_type in ("max_length", "max_len"):
        max_val = spec.get("max") if "max" in spec else spec.get("max_len")
        if max_val is None:
            raise ValueError("Check type 'max_length' requires 'max' or 'max_len' integer")
        return length_bounds(max_len=int(max_val), field=field, severity=severity)

    elif check_type in ("min_length", "min_len"):
        min_val = spec.get("min") if "min" in spec else spec.get("min_len")
        if min_val is None:
            raise ValueError("Check type 'min_length' requires 'min' or 'min_len' integer")
        return length_bounds(min_len=int(min_val), field=field, severity=severity)

    elif check_type in ("length_bounds", "length"):
        min_val = spec.get("min_len") if "min_len" in spec else spec.get("min")
        max_val = spec.get("max_len") if "max_len" in spec else spec.get("max")
        return length_bounds(
            min_len=int(min_val) if min_val is not None else None,
            max_len=int(max_val) if max_val is not None else None,
            field=field,
            severity=severity,
        )

    elif check_type in ("numeric_range", "range"):
        min_val = spec.get("min_val") if "min_val" in spec else spec.get("min")
        max_val = spec.get("max_val") if "max_val" in spec else spec.get("max")
        return numeric_range(
            min_val=float(min_val) if min_val is not None else None,
            max_val=float(max_val) if max_val is not None else None,
            field=field,
            severity=severity,
        )

    elif check_type in ("regex_match", "regex", "pattern"):
        pattern = spec.get("pattern")
        if pattern is None:
            raise ValueError("Check type 'regex_match' requires 'pattern' string")
        return regex_match(str(pattern), field=field, severity=severity)

    elif check_type in ("tool_call", "tool"):
        name = spec.get("name")
        if not name:
            raise ValueError("Check type 'tool_call' requires 'name' string")
        required_args = spec.get("required_args")
        allow_unexpected = spec.get("allow_unexpected_args", False)
        return tool_call_check(
            name=str(name),
            required_args=list(required_args) if required_args is not None else None,
            allow_unexpected_args=bool(allow_unexpected),
            severity=severity,
        )

    else:
        raise ValueError(f"Unknown or unsupported check type in spec: '{raw_type}'")
