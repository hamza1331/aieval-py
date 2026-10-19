# Implementation Plan: Retryability Taxonomy & Terminal Safety Boundaries in `aieval-py`

**Document Version:** 1.0  
**Target Package:** `aieval-py` (v0.2.0 milestone)  
**Author:** Hamza Ali <hamxa1331@gmail.com>  
**Status:** Ready for Implementation Review  

---

## 1. Executive Summary & Design Rationale

### 1.1 The Vulnerability: The Naive LLM Self-Healing Loop
In autonomous AI agent and LLM application architectures, deterministic validation is often wired directly to an automated self-healing/retry loop:

```python
result = evaluator.evaluate(model_output)
if not result.passed:
    # NAIVE RETRY LOOP:
    prompt_llm_to_fix(result.failures)
```

While bounded self-correction works well for benign structural slips (such as a missing field in an extraction payload or an unescaped bracket in JSON), it introduces a **severe safety vulnerability** when applied indiscriminately:

1. **Jailbreak and Boundary Probing**: When an agent attempts an unauthorized tool call (e.g., `execute_system_command`, `transfer_funds_unauthorized`) or violates a critical security/compliance policy, prompting the model with *"Your tool call failed because tool 'execute_system_command' is not permitted; please fix your output"* gives the model or an adversarial prompt injection repeated opportunities to circumvent restrictions.
2. **Safety Downgrading**: A model asked to "repair" a policy violation may disguise or obfuscate the malicious action to slip past downstream validation filters.
3. **Latency and Token Exhaustion**: Wasting retry budgets on requests that are fundamentally forbidden degrades performance and increases cost.

### 1.2 The Core Refinement: Decoupling Severity from Retryability
As identified in engineering review:
> *"Keeping severity and retryability separate is essential: severity describes impact, while retryability tells middleware what action is allowed. Terminal policy failures must be impossible to downgrade through model-generated repair output. That gives the retry loop a clear, testable boundary."*

- **Severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`)**: Describes **consequence/impact**. (e.g., Does this invalidate the record? Is it a minor warning or an error?)
- **Retryability (`RETRYABLE`, `TERMINAL`)**: Dictates **orchestration behavior**. (Can calling middleware safely prompt the model for bounded correction, or must it **fail closed** immediately?)

---

## 2. Architectural Specification

### 2.1 Taxonomy & State Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Evaluation Failure Axes                         │
├───────────────────────────────────┬────────────────────────────────────┤
│           Severity                │           Retryability             │
│       (Impact Dimension)          │       (Action Dimension)           │
├───────────────────────────────────┼────────────────────────────────────┤
│ • INFO: Informational advice      │ • RETRYABLE:                       │
│ • WARNING: Non-fatal anomaly      │   Safe for bounded LLM correction  │
│ • ERROR: Contract breach          │   feedback loop.                   │
│ • CRITICAL: Fatal system issue    │ • TERMINAL:                        │
│                                   │   Fail-closed immediately. Never   │
│                                   │   enter a self-healing loop.       │
└───────────────────────────────────┴────────────────────────────────────┘
```

#### Taxonomy Mapping in `FailureCode`:

| Failure Code | Default Severity | Default Retryability | Behavior / Rationale |
| :--- | :--- | :--- | :--- |
| `INVALID_JSON` | `ERROR` | `RETRYABLE` | Syntax error; LLM can repair unescaped quotes or brackets. |
| `MISSING_REQUIRED_FIELD` | `ERROR` | `RETRYABLE` | Missing attribute; LLM can generate the missing key. |
| `VALUE_CONSTRAINT_VIOLATION` | `ERROR` | `RETRYABLE` | Value out of bounds; LLM can clamp/adjust. |
| `REGEX_MISMATCH` | `ERROR` | `RETRYABLE` | Pattern mismatch; LLM can reformat. |
| `ENUM_MISMATCH` | `ERROR` | `RETRYABLE` | Disallowed choice; LLM can pick allowed enum value. |
| `LENGTH_OUT_OF_BOUNDS` | `ERROR` | `RETRYABLE` | String too short/long; LLM can truncate/expand. |
| `TOOL_CALL_INVALID_ARGS_JSON` | `ERROR` | `RETRYABLE` | Tool argument syntax error; LLM can repair JSON. |
| `TOOL_CALL_ARG_TYPE_MISMATCH` | `ERROR` | `RETRYABLE` | Tool argument type error; LLM can cast types. |
| `TOOL_CALL_UNKNOWN_TOOL` | `CRITICAL` | `TERMINAL` | **Disallowed / unlisted tool. Fail closed.** |
| `POLICY_VIOLATION` *(New)* | `CRITICAL` | `TERMINAL` | **Security / compliance policy breach. Zero retry.** |
| `DISALLOWED_FIELD` *(New)* | `ERROR` | `TERMINAL` | **Model emitted restricted/privileged keys.** |
| `CUSTOM_CHECK_FAILED` | `ERROR` | Configurable | Check author declares retryability explicitly. |

---

### 2.2 Safety Invariants & Non-Downgrade Guarantees

1. **Terminal Non-Downgrade Rule**:
   - If a failure has `retryability == Retryability.TERMINAL`, `suggested_repair` MUST be forced to `None`.
   - Middleware is strictly prohibited from generating a "repair hint" for a terminal failure.
2. **Fail-Closed Aggregate Evaluation**:
   - On `EvaluationResult`:
     - `is_retryable`: Returns `True` **only if** all failures are `RETRYABLE`. If any single failure is `TERMINAL`, `is_retryable` is `False`.
     - `has_terminal_failures`: Returns `True` if one or more failures are `TERMINAL`.
     - `terminal_failures`: Returns tuple of only the terminal failures requiring immediate abort/alerting.
     - `retryable_failures`: Returns tuple of failures that can be safely passed to self-correction prompts.

---

## 3. Implementation Steps in `aieval-py`

### Step 1: Domain Types in `src/aieval/domain/failure.py`
1. Define `Retryability(str, Enum)`:
   ```python
   class Retryability(str, Enum):
       """Indicates whether an orchestration layer can safely attempt self-correction."""
       RETRYABLE = "retryable"
       TERMINAL = "terminal"
   ```
2. Add new safety failure codes to `FailureCode`:
   - `POLICY_VIOLATION = "POLICY_VIOLATION"`
   - `DISALLOWED_FIELD = "DISALLOWED_FIELD"`
3. Add `default_retryability` property to `FailureCode`:
   - Maps `TOOL_CALL_UNKNOWN_TOOL`, `POLICY_VIOLATION`, and `DISALLOWED_FIELD` to `Retryability.TERMINAL`.
   - Defaults all other codes to `Retryability.RETRYABLE`.
4. Update `Failure` dataclass:
   - Add field `retryability: Retryability | None = None`.
   - In `__post_init__`, resolve retryability from `self.code` if omitted.
   - Enforce invariant: if `retryability == Retryability.TERMINAL`, clear `suggested_repair = None`.
   - Include `"retryability": self.retryability.value` in `Failure.to_dict()`.

### Step 2: Aggregate Evaluation State in `src/aieval/domain/result.py`
1. Add aggregate properties to `EvaluationResult`:
   - `is_retryable -> bool`
   - `has_terminal_failures -> bool`
   - `retryable_failures -> tuple[Failure, ...]`
   - `terminal_failures -> tuple[Failure, ...]`
2. Update `EvaluationResult.to_dict()` to serialize `is_retryable` and `has_terminal_failures`.

### Step 3: Update Check Implementations & Factory
1. **`ToolCallCheck` (`src/aieval/checks/tool_call.py`)**:
   - Ensure `TOOL_CALL_UNKNOWN_TOOL` produces `Severity.CRITICAL` and `Retryability.TERMINAL`.
2. **`ForbiddenFieldsCheck` / Spec Factory (`src/aieval/specs/factory.py`)**:
   - Support `disallowed_fields` check emitting `DISALLOWED_FIELD` with `Retryability.TERMINAL`.

### Step 4: Public Exports in `src/aieval/__init__.py`
- Export `Retryability` alongside `Severity`, `Failure`, `FailureCode`, `EvaluationResult`.

### Step 5: Unit & Conformance Testing
1. Unit tests in `tests/unit/test_failure.py`:
   - Test `Retryability` enum values and default assignment.
   - Verify terminal failures force `suggested_repair = None`.
2. Unit tests in `tests/unit/test_result.py`:
   - Test `is_retryable` returns `False` when even a single failure is `TERMINAL`.
   - Test separation of `retryable_failures` vs `terminal_failures`.
3. Unit tests in `tests/unit/test_tool_call.py`:
   - Verify unknown tool calls fail closed with `Retryability.TERMINAL`.

---

## 4. Acceptance Criteria & Definition of Done

- [x] `aieval-py` defines `Retryability(RETRYABLE, TERMINAL)` without breaking existing API contracts.
- [x] `FailureCode` defaults match the security taxonomy (e.g., `TOOL_CALL_UNKNOWN_TOOL` and `POLICY_VIOLATION` are `TERMINAL`).
- [x] Non-downgrade invariant strictly enforced: `suggested_repair` is nullified for any terminal failure.
- [x] `EvaluationResult.is_retryable` returns `False` if any failure is terminal.
- [x] `EvaluationResult.terminal_failures` and `EvaluationResult.retryable_failures` isolate fatal triggers from repairable items.
- [x] 100% of `aieval-py` tests pass (`pytest tests/`), with 0 ruff errors and 0 mypy errors.
- [x] Downstream consumers (like `aieval-console`) receive `retryability` transparently via `to_dict()`.

