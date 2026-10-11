# aieval

[![CI](https://github.com/hamza1331/aieval-py/actions/workflows/test.yml/badge.svg)](https://github.com/hamza1331/aieval-py/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/aieval-py.svg)](https://pypi.org/project/aieval-py/)
[![Python versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/aieval-py/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Deterministic-first runtime validation and reliability toolkit for LLM outputs and agent actions.**

Catch predictable failures (schema violations, missing required keys, JSON format errors, invalid tool call args, policy constraints) in sub-millisecond execution **before** spending latency and money on semantic LLM-as-a-judge scoring.

---

## Key Highlights

- ⚡ **Deterministic First:** Cheap, fast assertions run before calling model judges.
- 📦 **Zero Bloat:** Minimal external footprint (`pydantic>=2.0.0` as schema engine, pure Python standard library for the rest).
- 🔄 **Dual Sync & Async:** Native support for synchronous scripts (`evaluate()`) and asynchronous pipelines (`await aevaluate()`).
- 🤖 **Agent Tool Call Pre-flight:** Validates function names, required arguments, type safety, and stringified JSON (OpenAI tool call format).
- 🎚️ **Severity Routing:** Flexible threshold routing (`fail_on="error"` vs strict `fail_on="warning"`).
- 🧪 **CLI & Golden Fixtures:** Run validation from the command line on JSON test fixtures (`aieval run <fixture.json>`).
- 🎯 **Full TypeScript Parity:** Shares the exact failure taxonomy, code conventions, and golden test formats with `@hamza1331/aieval`.

---

## Installation

```bash
pip install aieval-py
```

---

## Quickstart

### 1. Synchronous Output Evaluation

```python
from aieval import evaluate, schema_check, required_fields
from pydantic import BaseModel, Field

class AnalysisReport(BaseModel):
    summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    tags: list[str]

llm_output = '{"summary": "All systems nominal", "confidence_score": 0.95, "tags": ["ops", "prod"]}'

result = evaluate(
    output=llm_output,
    checks=[
        schema_check(AnalysisReport),
        required_fields(["summary", "confidence_score"]),
    ],
)

if result.passed:
    print(f"Passed in {result.summary.duration_ms}ms!")
else:
    for failure in result.failures:
        print(f"[{failure.code}] {failure.message} (path: {failure.path})")
```

### 2. Pre-flight Agent Tool Call Validation

Validate tool calls before execution to avoid runtime exceptions and agent failure loops:

```python
from aieval import evaluate, tool_call_check
from pydantic import BaseModel

class SendEmailArgs(BaseModel):
    recipient: str
    subject: str
    body: str

# Works with both native dicts and OpenAI stringified JSON arguments:
raw_tool_call = {
    "name": "send_email",
    "arguments": '{"recipient": "team@example.com", "subject": "Update"}'
}

result = evaluate(
    output=raw_tool_call,
    checks=[
        tool_call_check("send_email", schema=SendEmailArgs, required_args=["body"]),
    ]
)

print(result.passed) # False - missing required argument 'body'
```

### 3. Asynchronous Pipeline (`aevaluate`)

```python
import asyncio
from aieval import aevaluate, valid_json, regex_match

async def main():
    result = await aevaluate(
        output="Order #12345 confirmed.",
        checks=[
            regex_match(r"Order #\d+"),
        ],
    )
    print("Passed:", result.passed)

asyncio.run(main())
```

---

## CLI Usage

### Run Golden Test Fixtures

```bash
aieval run path/to/fixture.json
```

Or output raw JSON:

```bash
aieval run path/to/fixture.json --json
```

### Check Arbitrary Files

```bash
aieval check output.json --specs checks.json
```

---

## Failure Code Taxonomy

| Code | Category | Description |
|---|---|---|
| `INVALID_JSON` | Syntax | Output string is not parseable JSON |
| `SCHEMA_VALIDATION_ERROR` | Schema | Failed Pydantic v2 schema validation |
| `MISSING_REQUIRED_FIELD` | Fields | Missing expected key |
| `UNEXPECTED_FIELD` | Fields | Extra key outside allowed whitelist |
| `REGEX_MISMATCH` | Constraints | Pattern regex search failed |
| `ENUM_MISMATCH` | Constraints | Value not in permitted set |
| `VALUE_CONSTRAINT_VIOLATION` | Constraints | Range or boundary violation |
| `LENGTH_OUT_OF_BOUNDS` | Constraints | Length outside min/max range |
| `TOOL_CALL_UNKNOWN_TOOL` | Tool Calls | Unknown tool invoked |
| `TOOL_CALL_INVALID_ARGS_JSON`| Tool Calls | Arguments string is invalid JSON |
| `TOOL_CALL_MISSING_REQUIRED_ARG` | Tool Calls | Required argument missing |
| `TOOL_CALL_ARG_TYPE_MISMATCH`| Tool Calls | Argument schema check failed |

---

## Examples

Runnable walkthrough scripts are available in the [`examples/`](examples) directory:

- [`01_basic_llm_output.py`](examples/01_basic_llm_output.py): Schema and field constraint validation on LLM output.
- [`02_agent_tool_guardrail.py`](examples/02_agent_tool_guardrail.py): Agent tool call pre-flight validation (OpenAI stringified arguments & multi-tool selection).
- [`03_async_and_severity_routing.py`](examples/03_async_and_severity_routing.py): Asynchronous concurrent pipeline with severity routing.
- [`04_semantic_judge_adapter.py`](examples/04_semantic_judge_adapter.py): Integrating advisory LLM-as-a-judge checks via `SemanticJudge`.

---

## License

MIT
