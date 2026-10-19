# Cross-Language Fixture Specification

This document defines the golden fixture contract shared between TypeScript (`@hamza1331/aieval`) and Python (`aieval-py`).

## 1. Design Goal
A single JSON fixture file can be executed identically by both the TypeScript CLI (`aieval run fixture.json`) and the Python CLI (`aieval run fixture.json`), producing:
1. Identical pass/fail determination under matching `fail_on` severity thresholds.
2. Identical failure codes (`code`).
3. Identical dot-delimited field paths (`path`).
4. Consistent coercion rules without silent acceptance divergence.

---

## 2. Fixture Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AIEvalFixture",
  "type": "object",
  "required": ["output", "checks"],
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string" },
    "context": {
      "type": "object",
      "properties": {
        "prompt": { "type": "string" },
        "input": {},
        "model": { "type": "string" },
        "metadata": { "type": "object" }
      }
    },
    "output": {},
    "checks": {
      "type": "array",
      "items": { "$ref": "#/$defs/CheckSpec" }
    },
    "expected": {
      "type": "object",
      "required": ["passed"],
      "properties": {
        "passed": { "type": "boolean" },
        "failures": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["code"],
            "properties": {
              "code": { "type": "string" },
              "path": { "type": ["string", "null"] },
              "severity": { "type": "string", "enum": ["info", "warning", "error", "critical"] }
            }
          }
        }
      }
    }
  }
}
```

For the Python CLI and Aieval Console replay, `expected.passed` is always
compared. If `expected.failures` is omitted, failure details are not asserted.
When it is present, entries match the actual blocking failures without depending
on list order; duplicate entries are significant. `code` is always compared,
while optional `path` and `severity` are compared only when supplied. An
explicit `"path": null` asserts that the failure has no path.

---

## 3. Coercion & Edge Case Contract Rules

| Scenario | Input | Expected Outcome | Failure Code | Rationale |
|---|---|---|---|---|
| **String vs Number (`"3"` vs `3`)** | `{"age": "3"}` evaluated against `numeric_range(min_val=1, max_val=10)` | Fail | `VALUE_CONSTRAINT_VIOLATION` | Strict typing: primitives do not silently coerce string numbers. |
| **`null` vs Missing Key** | `{"name": null}` evaluated against `required_fields(["name"])` | Pass for existence check; fails downstream if non-null required | N/A (Key exists) | Key presence is distinct from value type validation. |
| **Missing Key** | `{}` evaluated against `required_fields(["name"])` | Fail | `MISSING_REQUIRED_FIELD` | Key does not exist in payload. Path is `"name"`. |
| **Unexpected Field** | `{"name": "Alice", "role": "admin"}` with `allowed_fields(["name"])` | Fail | `UNEXPECTED_FIELD` | Field `"role"` not in whitelist. Path is `"role"`. |
| **OpenAI Stringified Arguments** | `{"name": "search", "arguments": "{\"query\": 123}"}` | Fail | `TOOL_CALL_ARG_TYPE_MISMATCH` | Normalized parsing; argument type checks apply after JSON decode. |
| **Severity Threshold Routing** | Failure with severity `warning` evaluated under `fail_on="error"` (default) | Pass (`passed=true`, `warnings` array contains issue) | N/A | Warnings do not fail runs unless strict mode (`fail_on="warning"`) is set. |
| **Strict Severity Mode** | Failure with severity `warning` evaluated under `fail_on="warning"` | Fail (`passed=false`, `failures` contains issue) | Matches issue code | Strict mode treats warnings as blocking errors. |

---

## 4. Canonical Golden Fixtures

### Fixture A: Primitive Coercion (`"3"` vs `3`)
File: `tests/fixtures/golden_primitive_coercion.json`

```json
{
  "name": "strict_primitive_coercion",
  "description": "Ensures string numbers are not coerced into numeric types",
  "output": {
    "count": "3"
  },
  "checks": [
    {
      "type": "numeric_range",
      "min_val": 1,
      "max_val": 10
    }
  ],
  "expected": {
    "passed": false,
    "failures": [
      {
        "code": "VALUE_CONSTRAINT_VIOLATION",
        "path": null,
        "severity": "error"
      }
    ]
  }
}
```

### Fixture B: `null` vs Missing Field
File: `tests/fixtures/golden_null_vs_missing.json`

```json
{
  "name": "null_vs_missing_field",
  "description": "Distinguishes between missing key and null key",
  "output": {
    "present_null": null
  },
  "checks": [
    {
      "type": "required_fields",
      "fields": ["present_null", "completely_missing"]
    }
  ],
  "expected": {
    "passed": false,
    "failures": [
      {
        "code": "MISSING_REQUIRED_FIELD",
        "path": "completely_missing",
        "severity": "error"
      }
    ]
  }
}
```

### Fixture C: Unexpected Argument in Agent Tool Call
File: `tests/fixtures/golden_unexpected_argument.json`

```json
{
  "name": "tool_call_unexpected_arg",
  "description": "Detects extra unexpected fields in agent tool calls",
  "output": {
    "name": "search",
    "arguments": {
      "query": "documentation",
      "unauthorized_override": true
    }
  },
  "checks": [
    {
      "type": "tool_call",
      "name": "search",
      "required_args": ["query"],
      "allow_unexpected_args": false
    }
  ],
  "expected": {
    "passed": false,
    "failures": [
      {
        "code": "TOOL_CALL_UNEXPECTED_ARG",
        "path": "unauthorized_override",
        "severity": "error"
      }
    ]
  }
}
```
