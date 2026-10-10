"""Example 1: Basic LLM Output Validation.

Demonstrates how to validate raw structured text / JSON strings from an LLM
using Pydantic v2 schema checks and field constraints.
"""

from pydantic import BaseModel, Field

from aieval import evaluate, regex_match, required_fields, schema_check


class ExtractionResult(BaseModel):
    company_name: str
    revenue_usd: float = Field(gt=0, description="Revenue in USD")
    fiscal_year: int = Field(ge=2000, le=2050)
    ticker: str


def main() -> None:
    print("--- 1. Valid LLM Output Example ---")
    valid_raw_llm_output = """
    {
        "company_name": "Acme Corp",
        "revenue_usd": 1500000.50,
        "fiscal_year": 2024,
        "ticker": "ACME"
    }
    """

    res = evaluate(
        output=valid_raw_llm_output,
        checks=[
            schema_check(ExtractionResult),
            required_fields(["company_name", "ticker"]),
        ],
    )

    print(f"Passed: {res.passed}")
    print(f"Duration: {res.summary.duration_ms}ms")
    print()

    print("--- 2. Invalid LLM Output Example (Schema Drift & Violation) ---")
    invalid_raw_llm_output = """
    {
        "company_name": "Acme Corp",
        "revenue_usd": -500.0,
        "fiscal_year": 1995,
        "ticker": "invalid_lowercase_ticker"
    }
    """

    res_failed = evaluate(
        output=invalid_raw_llm_output,
        checks=[
            schema_check(ExtractionResult),
        ],
    )

    print(f"Passed: {res_failed.passed}")
    print(f"Total Failures: {len(res_failed.failures)}")
    for f in res_failed.failures:
        print(f"  ✖ [{f.code}] {f.message} (path: {f.path})")
    print()

    print("--- 3. Unstructured Text Format Check ---")
    summary_text = "STATUS: SUCCESS - Processing complete in 142ms."
    res_text = evaluate(
        output=summary_text,
        checks=[
            regex_match(r"^STATUS: SUCCESS"),
        ],
    )
    print(f"Text check passed: {res_text.passed}")


if __name__ == "__main__":
    main()
