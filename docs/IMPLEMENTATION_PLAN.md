# Implementation Plan: `aieval` (Python)

This document tracks the phased implementation plan for the Python counterpart of `aieval` (originally created in TypeScript as `@hamza1331/aieval`).

## Guiding Principles
- **Deterministic-First:** Prioritize zero-cost, sub-millisecond deterministic assertions over expensive, non-deterministic LLM calls.
- **Zero Bloat:** Minimal external dependencies. Python standard library wherever possible (`dataclasses`, `typing`, `enum`, `re`, `json`, `argparse`, `asyncio`), with `pydantic>=2.0.0` as the standard schema engine (equivalent to Zod in TS).
- **TypeScript Parity:** Exact equivalence in domain concepts, failure taxonomy codes, severity routing, and golden test fixture schemas.
- **Idiomatic Python 3.10+:** Dual sync/async execution (`evaluate()` / `aevaluate()`), immutable frozen dataclasses, strict typing (PEP 561 `py.typed`), and modern structural pattern matching/protocols.

---

## Architecture Overview

```text
aieval-py/
├── pyproject.toml               # PEP 621 metadata, Hatchling build backend, dev deps
├── README.md
├── LICENSE
├── IMPLEMENTATION_PLAN.md
├── PROJECT_DISCOVERY.md
├── .gitignore
├── .github/
│   └── workflows/
│       ├── test.yml             # Matrix across Python 3.10, 3.11, 3.12, 3.13, 3.14
│       └── publish.yml          # PyPI Trusted Publishing (OIDC) on release
└── src/
    └── aieval/
        ├── __init__.py          # Clean public exports (evaluate, aevaluate, checks, models)
        ├── py.typed             # PEP 561 marker
        ├── domain/
        │   ├── __init__.py
        │   ├── failure.py       # Failure, Severity, FailureCode
        │   ├── result.py        # EvaluationResult, EvaluationSummary
        │   └── context.py       # EvaluationContext
        ├── checks/
        │   ├── __init__.py      # Check Protocol & standard check exports
        │   ├── base.py          # Protocol Check, CheckResult
        │   ├── schema.py        # schema_check (Pydantic v2)
        │   ├── fields.py        # required_fields, allowed_fields
        │   ├── constraints.py   # regex_match, allowed_values, range_check, length_check
        │   ├── tool_call.py     # tool_call_check, tool_call_check.one_of
        │   └── json_check.py    # valid_json check
        ├── semantic/
        │   ├── __init__.py
        │   └── protocol.py      # SemanticJudge Protocol (zero-dependency, optional)
        ├── runner/
        │   ├── __init__.py
        │   ├── evaluator.py     # evaluate() & aevaluate() execution engines
        │   └── routing.py       # Severity threshold evaluation & summary calculation
        └── cli/
            ├── __init__.py
            └── main.py          # `aieval run <fixture>` and `aieval check` CLI
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_failures.py
    │   ├── test_schema_check.py
    │   ├── test_fields_check.py
    │   ├── test_constraints_check.py
    │   ├── test_tool_call_check.py
    │   ├── test_evaluator_sync.py
    │   ├── test_evaluator_async.py
    │   └── test_severity_routing.py
    ├── fixtures/
    │   ├── golden_valid_schema.json
    │   ├── golden_invalid_tool_call.json
    │   └── golden_mixed_severities.json
    └── test_cli.py
```

---

## Failure Code Taxonomy (Parity with TypeScript)

| Category | Failure Code | Description |
|---|---|---|
| **JSON / Structure** | `INVALID_JSON` | Output is not parseable JSON |
| **Schema** | `SCHEMA_VALIDATION_ERROR` | Failed Pydantic v2 validation |
| **Fields** | `MISSING_REQUIRED_FIELD` | Expected object key is absent |
| **Fields** | `UNEXPECTED_FIELD` | Key present outside allowed whitelist |
| **Constraints** | `REGEX_MISMATCH` | String does not match required regex pattern |
| **Constraints** | `ENUM_MISMATCH` | Value not in permitted set / enum |
| **Constraints** | `VALUE_CONSTRAINT_VIOLATION` | Numeric bounds or custom constraint violated |
| **Constraints** | `LENGTH_OUT_OF_BOUNDS` | String/list length outside min/max range |
| **Tool Calls** | `TOOL_CALL_UNKNOWN_TOOL` | Tool name not found in allowed list |
| **Tool Calls** | `TOOL_CALL_INVALID_ARGS_JSON` | Arguments string could not be parsed as JSON |
| **Tool Calls** | `TOOL_CALL_MISSING_REQUIRED_ARG` | Required argument missing from tool call |
| **Tool Calls** | `TOOL_CALL_ARG_TYPE_MISMATCH` | Tool argument failed type or schema check |
| **Tool Calls** | `TOOL_CALL_UNEXPECTED_ARG` | Tool argument was not in expected schema |
| **Semantic (Advisory)** | `SEMANTIC_JUDGE_SCORE_LOW` | LLM judge score fell below required threshold |
| **Semantic (Advisory)** | `SEMANTIC_JUDGE_FAILED` | LLM judge execution failed or raised an error |

---

## Phased Implementation Roadmap

### Phase 1: Repository Setup & Packaging Baseline
- [x] Configure `pyproject.toml` (PEP 621, Hatchling build backend, Python `>=3.10`).
- [x] Declare runtime dependencies (`pydantic>=2.0.0`) and dev dependencies (`pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`).
- [x] Set up package directory structure under `src/aieval`.
- [x] Add `py.typed` marker (PEP 561).
- [x] Add `.gitignore` for Python artifacts (`.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `dist/`).
- [x] Configure `ruff` and `mypy` strict type checking rules.

### Phase 2: Core Domain Model & Failure Classification
- [x] Implement `Severity` enum (`INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- [x] Implement `FailureCode` enum for all taxonomy codes.
- [x] Implement frozen dataclass `Failure`:
  - `code: str | FailureCode`
  - `message: str`
  - `severity: Severity = Severity.ERROR`
  - `path: str | tuple[str | int, ...] | None = None`
  - `metadata: dict[str, Any] = field(default_factory=dict)`
  - `suggested_repair: str | None = None`
- [x] Implement frozen dataclass `EvaluationSummary`:
  - `total_checks: int`
  - `passed_checks: int`
  - `failed_checks: int`
  - `warnings_count: int`
  - `duration_ms: float`
- [x] Implement frozen dataclass `EvaluationResult`:
  - `passed: bool`
  - `failures: tuple[Failure, ...]`
  - `warnings: tuple[Failure, ...]`
  - `summary: EvaluationSummary`
  - `to_dict()` and `raise_for_failures()` helper methods.
- [x] Implement `CheckResult` and `Check` Protocol (callable supporting `(output, context) -> CheckResult | Sequence[Failure]`).
- [x] Write unit tests for domain classes and serialization.

### Phase 3: Built-in Deterministic Checks
- [x] Implement `valid_json()` check (handles raw string and decodes safely).
- [x] Implement `schema_check(model: type[BaseModel] | TypeAdapter[T])`:
  - Auto-parses JSON string if needed.
  - Converts Pydantic `ValidationError.errors()` to clean `Failure` objects with dot-notation path strings.
- [x] Implement field checks:
  - `required_fields(fields: Sequence[str])`
  - `allowed_fields(fields: Sequence[str])`
- [x] Implement value constraint checks:
  - `regex_match(pattern: str | re.Pattern)`
  - `allowed_values(allowed: Collection[Any])`
  - `numeric_range(min_val: float | None = None, max_val: float | None = None)`
  - `length_bounds(min_len: int | None = None, max_len: int | None = None)`
- [x] Implement agent tool-call checks:
  - Normalize `{name, arguments}` (OpenAI stringified or dict) and `{name, args}`.
  - Check tool name against allowed list.
  - Parse stringified JSON arguments safely.
  - Validate tool argument presence, unexpected arguments, and Pydantic argument schemas.
  - Support `tool_call_check.one_of([...])` for multi-tool options.
- [x] Write thorough unit tests for each check across valid and invalid inputs.

### Phase 4: Sync & Async Dual Evaluator Engine & Severity Routing
- [x] Implement severity routing logic:
  - Default: `fail_on="error"` (only `ERROR` and `CRITICAL` cause `passed=False`).
  - Strict mode: `fail_on="warning"` (`WARNING` also causes `passed=False`).
- [x] Implement synchronous evaluator:
  - `evaluate(output: Any, checks: Sequence[Check], *, context: EvaluationContext | None = None, fail_on: str = "error") -> EvaluationResult`
  - Guard: raise informative `EvaluationConfigError` if an asynchronous check is passed to synchronous `evaluate()`.
- [x] Implement asynchronous evaluator:
  - `aevaluate(output: Any, checks: Sequence[Check | AsyncCheck], *, context: EvaluationContext | None = None, fail_on: str = "error") -> EvaluationResult`
  - Concurrently runs checks using `asyncio.gather()`.
- [x] Implement optional, zero-dependency `SemanticJudge` Protocol:
  - Allows injecting user-defined LLM evaluators.
  - Produces advisory results (`SEMANTIC_JUDGE_SCORE_LOW` or `SEMANTIC_JUDGE_FAILED`).
- [x] Write unit and integration tests for sync/async evaluation and routing behavior.

### Phase 5: CLI & Golden Test Fixtures Parity
- [x] Implement CLI in `aieval.cli.main`:
  - `aieval run <fixture.json>`: Runs validation on a test fixture.
  - `aieval check <file.json> --specs <specs.json>`: Evaluates an arbitrary output against a check specification.
  - Format human-friendly colored terminal output and support `--json` output flag.
  - Return exit code `0` on pass, `1` on failure.
- [x] Create golden test fixtures in `tests/fixtures/` matching TypeScript fixture schemas.
- [x] Write CLI execution tests verifying stdout/stderr and exit codes.

### Phase 6: Documentation, CI/CD & PyPI Release Setup
- [x] Write comprehensive `README.md` with:
  - Quickstart guide (sync and async).
  - Pydantic v2 schema validation examples.
  - Agent tool call validation examples.
  - Custom check implementation guide.
  - Comparison table / philosophy (deterministic vs semantic).
- [x] Set up GitHub Actions CI workflow (`.github/workflows/test.yml`):
  - Matrix across Python 3.10, 3.11, 3.12, 3.13, 3.14.
  - Enforce `ruff check`, `ruff format --check`, `mypy`, and `pytest --cov=aieval --cov-fail-under=90`.
- [x] Set up PyPI Trusted Publishing GitHub Actions workflow (`.github/workflows/publish.yml`).
- [x] Add `LICENSE` (MIT) and ensure package build verification (`hatch build` / `pip install -e .`).
