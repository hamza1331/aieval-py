from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvaluationContext:
    """Metadata and contextual information passed into checks."""

    prompt: str | None = None
    input: Any = None
    model: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

