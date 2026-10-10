"""Example 4: Optional Semantic Judge with Advisory LLM Evaluation.

Demonstrates how to implement the zero-dependency `SemanticJudge` or
`AsyncSemanticJudge` protocol to incorporate an LLM-as-a-judge check after
deterministic checks have already passed.
"""

from typing import Any

from aieval import (
    EvaluationContext,
    Failure,
    FailureCode,
    Severity,
    evaluate,
    regex_match,
    required_fields,
)


class MockLLMSemanticJudge:
    """Implements SemanticJudge protocol without external SDK dependencies."""

    name: str = "conciseness_semantic_judge"

    def __init__(self, max_allowed_words: int = 20) -> None:
        self.max_allowed_words = max_allowed_words

    def judge(
        self,
        output: Any,
        context: EvaluationContext | None = None,
    ) -> Failure | None:
        # In a production app, here you would invoke OpenAI / Anthropic / Gemini:
        # client.chat.completions.create(...)
        # For demonstration, we inspect semantic word count:
        words = str(output).split()
        if len(words) > self.max_allowed_words:
            return Failure(
                code=FailureCode.SEMANTIC_JUDGE_SCORE_LOW,
                message=f"Semantic judge evaluated output as too verbose ({len(words)} words, max {self.max_allowed_words})",
                severity=Severity.WARNING,  # Advisory by default
                metadata={"word_count": len(words), "max_allowed": self.max_allowed_words},
            )
        return None


def main() -> None:
    judge = MockLLMSemanticJudge(max_allowed_words=10)

    # Output that passes deterministic checks but fails semantic judge conciseness
    output = {
        "status": "success",
        "explanation": "This is an extremely long response that rambles on and on far past the ten word limit set by the judge.",
    }

    res = evaluate(
        output=output,
        checks=[
            required_fields(["status", "explanation"]),
            lambda out: regex_match("success").__call__(out["status"]),
            judge,
        ],
        fail_on="error",
    )

    print("--- Deterministic + Semantic Judge Evaluation ---")
    print(f"Passed: {res.passed}")  # True because judge failure is WARNING
    print(f"Total checks: {res.summary.total_checks}")
    print(f"Warnings recorded: {len(res.warnings)}")
    for w in res.warnings:
        print(f"  ⚠ [{w.code}] {w.message}")


if __name__ == "__main__":
    main()

