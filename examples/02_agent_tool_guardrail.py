"""Example 2: Agent Tool-Call Pre-Flight Guardrails.

Demonstrates how to validate agent tool calls before executing them, preventing
invalid database mutations, API crashes, or agent infinite retry loops.
"""

from typing import Literal

from pydantic import BaseModel, Field

from aieval import evaluate, tool_call_check


# Tool 1 Argument Schema
class SendNotificationArgs(BaseModel):
    recipient_email: str
    channel: Literal["email", "sms", "slack"]
    priority: int = Field(ge=1, le=5)
    body: str


# Tool 2 Argument Schema
class SearchDocsArgs(BaseModel):
    query: str
    max_results: int = Field(default=5, le=50)


def main() -> None:
    # Set up multi-tool validator: agent may call either tool
    allowed_tools = tool_call_check.one_of(
        [
            tool_call_check("send_notification", schema=SendNotificationArgs),
            tool_call_check("search_docs", schema=SearchDocsArgs),
        ]
    )

    print("--- 1. Valid OpenAI-Formatted Tool Call (Stringified JSON args) ---")
    openai_tool_call = {
        "name": "send_notification",
        "arguments": '{"recipient_email": "alice@example.com", "channel": "email", "priority": 1, "body": "Server down!"}',
    }

    res_valid = evaluate(output=openai_tool_call, checks=[allowed_tools])
    print(f"Passed: {res_valid.passed}")
    print(f"Checks passed: {res_valid.summary.passed_checks}/{res_valid.summary.total_checks}\n")

    print("--- 2. Invalid Tool Call: Unknown Tool Invocation ---")
    unknown_tool_call = {
        "name": "drop_production_database",
        "arguments": "{}",
    }
    res_unknown = evaluate(output=unknown_tool_call, checks=[allowed_tools])
    print(f"Passed: {res_unknown.passed}")
    for f in res_unknown.failures:
        print(f"  ✖ [{f.code}] {f.message}\n")

    print("--- 3. Invalid Tool Call: Schema Validation Failure in Args ---")
    bad_args_tool_call = {
        "name": "send_notification",
        "arguments": {
            "recipient_email": "not-an-email",
            "channel": "carrier_pigeon",  # Not in allowed channels
            "priority": 10,  # Max allowed is 5
            "body": "Hello",
        },
    }
    res_bad_args = evaluate(output=bad_args_tool_call, checks=[allowed_tools])
    print(f"Passed: {res_bad_args.passed}")
    for f in res_bad_args.failures:
        print(f"  ✖ [{f.code}] {f.message} (path: {f.path})")


if __name__ == "__main__":
    main()
