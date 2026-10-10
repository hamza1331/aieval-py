"""Example 3: Asynchronous Evaluation Pipeline with Severity Routing.

Demonstrates how to evaluate concurrent checks in async pipelines (FastAPI, asyncio,
LangGraph) while separating hard errors from non-blocking warnings.
"""

import asyncio

from aieval import EvaluationContext, Failure, Severity, aevaluate, regex_match


# 1. Custom Async Safety Check (e.g. simulating a check or DB lookup)
async def check_pii_async(text: str, context: EvaluationContext | None = None) -> list[Failure]:
    await asyncio.sleep(0.01)  # Simulate non-blocking async inspection
    failures: list[Failure] = []
    if "SSN:" in text or "PASSWORD=" in text:
        failures.append(
            Failure(
                code="PII_LEAK_DETECTED",
                message="Sensitive PII credential pattern detected in output",
                severity=Severity.CRITICAL,
            )
        )
    return failures


# 2. Advisory Warning Check (Tone / Length guidance)
def check_tone_warning(text: str) -> Failure | None:
    if len(text) > 200:
        return Failure(
            code="RESPONSE_TOO_VERBOSE",
            message="Response exceeds 200 characters; advisory warning only.",
            severity=Severity.WARNING,
        )
    return None


async def main() -> None:
    print("--- 1. Evaluating with Warnings (fail_on='error', Default Mode) ---")
    long_response = (
        "Thank you for contacting customer support. We are very pleased to assist you today. "
        "Your ticket ID is #987654 and our engineering team will address this as soon as possible. "
        "Please feel free to reply with additional details."
    )

    result_default = await aevaluate(
        output=long_response,
        checks=[
            regex_match(r"#\d{6}"),
            check_pii_async,
            check_tone_warning,
        ],
        fail_on="error",  # Warnings will NOT block pass
    )

    print(f"Passed: {result_default.passed}")  # True
    print(f"Blocking failures: {len(result_default.failures)}")  # 0
    print(f"Advisory warnings: {len(result_default.warnings)}")  # 1
    for w in result_default.warnings:
        print(f"  ⚠ [{w.code}] {w.message}")
    print()

    print("--- 2. Evaluating in Strict Mode (fail_on='warning') ---")
    result_strict = await aevaluate(
        output=long_response,
        checks=[
            check_tone_warning,
        ],
        fail_on="warning",  # Warnings DO block pass in strict mode
    )

    print(f"Passed (Strict Mode): {result_strict.passed}")  # False
    for f in result_strict.failures:
        print(f"  ✖ [{f.code}] {f.message}")


if __name__ == "__main__":
    asyncio.run(main())
