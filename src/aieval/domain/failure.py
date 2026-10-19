from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Failure severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def rank(self) -> int:
        """Returns integer rank for severity comparison."""
        mapping = {
            Severity.INFO: 0,
            Severity.WARNING: 1,
            Severity.ERROR: 2,
            Severity.CRITICAL: 3,
        }
        return mapping[self]

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Severity):
            return self.rank() >= other.rank()
        if isinstance(other, str):
            try:
                return self.rank() >= Severity(other).rank()
            except ValueError:
                return False
        return False

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Severity):
            return self.rank() > other.rank()
        if isinstance(other, str):
            try:
                return self.rank() > Severity(other).rank()
            except ValueError:
                return False
        return False

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Severity):
            return self.rank() <= other.rank()
        if isinstance(other, str):
            try:
                return self.rank() <= Severity(other).rank()
            except ValueError:
                return False
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Severity):
            return self.rank() < other.rank()
        if isinstance(other, str):
            try:
                return self.rank() < Severity(other).rank()
            except ValueError:
                return False
        return False


class FailureCode(str, Enum):
    """Standardized failure taxonomy codes matching TypeScript reference."""

    # JSON / Structure
    INVALID_JSON = "INVALID_JSON"

    # Schema
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"

    # Fields
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    UNEXPECTED_FIELD = "UNEXPECTED_FIELD"

    # Constraints
    REGEX_MISMATCH = "REGEX_MISMATCH"
    ENUM_MISMATCH = "ENUM_MISMATCH"
    VALUE_CONSTRAINT_VIOLATION = "VALUE_CONSTRAINT_VIOLATION"
    LENGTH_OUT_OF_BOUNDS = "LENGTH_OUT_OF_BOUNDS"

    # Tool Calls
    TOOL_CALL_UNKNOWN_TOOL = "TOOL_CALL_UNKNOWN_TOOL"
    TOOL_CALL_INVALID_ARGS_JSON = "TOOL_CALL_INVALID_ARGS_JSON"
    TOOL_CALL_MISSING_REQUIRED_ARG = "TOOL_CALL_MISSING_REQUIRED_ARG"
    TOOL_CALL_ARG_TYPE_MISMATCH = "TOOL_CALL_ARG_TYPE_MISMATCH"
    TOOL_CALL_UNEXPECTED_ARG = "TOOL_CALL_UNEXPECTED_ARG"

    # Policy / Security
    POLICY_VIOLATION = "POLICY_VIOLATION"
    DISALLOWED_FIELD = "DISALLOWED_FIELD"

    # Semantic (Advisory)
    SEMANTIC_JUDGE_SCORE_LOW = "SEMANTIC_JUDGE_SCORE_LOW"
    SEMANTIC_JUDGE_FAILED = "SEMANTIC_JUDGE_FAILED"

    # Generic / Custom
    CUSTOM_CHECK_FAILED = "CUSTOM_CHECK_FAILED"

    @property
    def default_retryability(self) -> "Retryability":
        """Returns default retryability for this failure code."""
        terminal_codes = {
            FailureCode.TOOL_CALL_UNKNOWN_TOOL,
            FailureCode.POLICY_VIOLATION,
            FailureCode.DISALLOWED_FIELD,
        }
        return Retryability.TERMINAL if self in terminal_codes else Retryability.RETRYABLE


class Retryability(str, Enum):
    """Indicates whether an orchestration layer can safely attempt self-correction.

    - RETRYABLE: Minor structural/formatting slip safe for bounded self-correction.
    - TERMINAL: Critical security, policy, or unauthorized tool breach that must fail closed immediately.
    """

    RETRYABLE = "retryable"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class Failure:
    """Represents a discrete validation or evaluation failure."""

    code: str | FailureCode
    message: str
    severity: Severity = Severity.ERROR
    retryability: Retryability | None = None
    path: str | tuple[str | int, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    suggested_repair: str | None = None

    def __post_init__(self) -> None:
        # Resolve retryability from FailureCode if not explicitly passed
        resolved_retry = self.retryability
        if resolved_retry is None:
            if isinstance(self.code, FailureCode):
                resolved_retry = self.code.default_retryability
            elif isinstance(self.code, str):
                try:
                    resolved_retry = FailureCode(self.code).default_retryability
                except ValueError:
                    resolved_retry = Retryability.RETRYABLE
            else:
                resolved_retry = Retryability.RETRYABLE
        object.__setattr__(self, "retryability", resolved_retry)

        # Non-downgrade safety invariant:
        # Terminal policy/tool failures must never carry a suggested_repair
        # to prevent naive self-healing loops from prompting models to bypass guards.
        if resolved_retry == Retryability.TERMINAL and self.suggested_repair is not None:
            object.__setattr__(self, "suggested_repair", None)

    def to_dict(self) -> dict[str, Any]:
        """Serializes failure to a JSON-compatible dictionary."""
        path_str: str | None = None
        if isinstance(self.path, (tuple, list)):
            path_str = ".".join(str(p) for p in self.path)
        elif self.path is not None:
            path_str = str(self.path)

        code_str = self.code.value if hasattr(self.code, "value") else str(self.code)
        sev_str = self.severity.value if hasattr(self.severity, "value") else str(self.severity)
        retry_val = self.retryability or Retryability.RETRYABLE
        retry_str = retry_val.value if hasattr(retry_val, "value") else str(retry_val)

        data: dict[str, Any] = {
            "code": code_str,
            "message": self.message,
            "severity": sev_str,
            "retryability": retry_str,
            "path": path_str,
            "metadata": dict(self.metadata),
        }
        if self.suggested_repair is not None:
            data["suggested_repair"] = self.suggested_repair
        return data
