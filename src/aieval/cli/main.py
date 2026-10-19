import argparse
import json
import sys
from pathlib import Path
from typing import Any

from aieval.domain import EvaluationContext
from aieval.runner import evaluate
from aieval.specs.factory import build_check_from_spec

_build_check_from_spec = build_check_from_spec


def _format_terminal_output(result: Any, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(result.to_dict(), indent=2))
        return

    # ANSI Colors
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    status_str = f"{GREEN}PASSED{RESET}" if result.passed else f"{RED}FAILED{RESET}"
    print(f"\n{BOLD}Evaluation Result:{RESET} {status_str}")
    print(
        f"Checks: {result.summary.passed_checks}/{result.summary.total_checks} passed | "
        f"Failures: {result.summary.failed_checks} | "
        f"Warnings: {result.summary.warnings_count} | "
        f"Time: {result.summary.duration_ms:.2f}ms\n"
    )

    if result.failures:
        print(f"{RED}{BOLD}Failures:{RESET}")
        for f in result.failures:
            path_info = f" (at {f.path})" if f.path else ""
            print(f"  {RED}✖ [{f.code}]{RESET} {f.message}{path_info}")

    if result.warnings:
        print(f"\n{YELLOW}{BOLD}Warnings:{RESET}")
        for w in result.warnings:
            path_info = f" (at {w.path})" if w.path else ""
            print(f"  {YELLOW}⚠ [{w.code}]{RESET} {w.message}{path_info}")

    print()


def _validate_fixture_expectation(expected: Any) -> dict[str, Any]:
    if not isinstance(expected, dict) or not isinstance(expected.get("passed"), bool):
        raise ValueError("Fixture 'expected' must be an object with a boolean 'passed' field.")

    failures = expected.get("failures", [])
    if not isinstance(failures, list):
        raise ValueError("Fixture 'expected.failures' must be an array.")
    for index, failure in enumerate(failures):
        if not isinstance(failure, dict) or not isinstance(failure.get("code"), str):
            raise ValueError(f"Fixture 'expected.failures[{index}].code' must be a string.")
        if (
            "path" in failure
            and failure["path"] is not None
            and not isinstance(failure["path"], str)
        ):
            raise ValueError(f"Fixture 'expected.failures[{index}].path' must be a string or null.")
        if "severity" in failure:
            severity = failure["severity"]
            if not isinstance(severity, str) or severity not in {
                "info",
                "warning",
                "error",
                "critical",
            }:
                raise ValueError(
                    f"Fixture 'expected.failures[{index}].severity' must be a supported severity."
                )
    return expected


def _matches_fixture_expectation(result: Any, expected: dict[str, Any]) -> bool:
    if result.passed is not expected["passed"]:
        return False
    if "failures" not in expected:
        return True

    actual_failures = [failure.to_dict() for failure in result.failures]
    expected_failures = expected["failures"]
    matched_expected: dict[int, int] = {}

    def match_expected(expected_index: int, seen_actual: set[int]) -> bool:
        expected_failure = expected_failures[expected_index]
        for actual_index, actual_failure in enumerate(actual_failures):
            if actual_index in seen_actual or not all(
                key not in expected_failure or expected_failure[key] == actual_failure[key]
                for key in ("code", "path", "severity")
            ):
                continue
            seen_actual.add(actual_index)
            if actual_index not in matched_expected or match_expected(
                matched_expected[actual_index], seen_actual
            ):
                matched_expected[actual_index] = expected_index
                return True
        return False

    for index in range(len(expected_failures)):
        if not match_expected(index, set()):
            return False
    return len(matched_expected) == len(actual_failures)


def run_fixture(fixture_path: Path, json_mode: bool = False, fail_on: str = "error") -> int:
    if not fixture_path.exists():
        print(f"Error: Fixture file not found: {fixture_path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        print(f"Error: Invalid JSON in fixture file: {err}", file=sys.stderr)
        return 1

    output = data.get("output")
    checks_specs = data.get("checks", [])
    raw_context = data.get("context", {})
    context = (
        EvaluationContext(
            prompt=raw_context.get("prompt"),
            input=raw_context.get("input"),
            model=raw_context.get("model"),
            metadata=raw_context.get("metadata", {}),
        )
        if raw_context
        else None
    )

    try:
        checks = [_build_check_from_spec(s) for s in checks_specs]
    except ValueError as err:
        print(f"Error configuring checks: {err}", file=sys.stderr)
        return 1

    expected: dict[str, Any] | None = None
    if "expected" in data:
        try:
            expected = _validate_fixture_expectation(data["expected"])
        except ValueError as err:
            print(f"Error validating fixture expectation: {err}", file=sys.stderr)
            return 1

    result = evaluate(output, checks, context=context, fail_on=fail_on)
    _format_terminal_output(result, json_mode)
    if expected is None:
        return 0 if result.passed else 1

    matches_expected = _matches_fixture_expectation(result, expected)
    if not json_mode:
        if matches_expected:
            print("\033[92mFixture expectation matched.\033[0m")
        else:
            print("\033[91mFixture expectation did not match.\033[0m", file=sys.stderr)
    elif not matches_expected:
        print("Fixture expectation did not match.", file=sys.stderr)
    return 0 if matches_expected else 1


def run_check_file(
    file_path: Path,
    specs_path: Path,
    json_mode: bool = False,
    fail_on: str = "error",
) -> int:
    if not file_path.exists():
        print(f"Error: Target file not found: {file_path}", file=sys.stderr)
        return 1
    if not specs_path.exists():
        print(f"Error: Specs file not found: {specs_path}", file=sys.stderr)
        return 1

    try:
        target_content = file_path.read_text(encoding="utf-8")
        try:
            output = json.loads(target_content)
        except json.JSONDecodeError:
            output = target_content

        specs_data = json.loads(specs_path.read_text(encoding="utf-8"))
        specs_list = (
            specs_data if isinstance(specs_data, list) else specs_data.get("checks", [specs_data])
        )
        checks = [_build_check_from_spec(s) for s in specs_list]
    except Exception as err:
        print(f"Error loading inputs: {err}", file=sys.stderr)
        return 1

    result = evaluate(output, checks, fail_on=fail_on)
    _format_terminal_output(result, json_mode)
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aieval",
        description="Deterministic-first runtime validation and reliability toolkit for LLMs and agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # `aieval run <fixture.json>`
    run_parser = subparsers.add_parser(
        "run", help="Run validation against a golden JSON test fixture."
    )
    run_parser.add_argument("fixture", type=Path, help="Path to fixture JSON file")
    run_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    run_parser.add_argument(
        "--fail-on", default="error", help="Severity threshold (default: error, or warning)"
    )

    # `aieval check <file.json> --specs <specs.json>`
    check_parser = subparsers.add_parser(
        "check", help="Check an arbitrary output file against specification checks."
    )
    check_parser.add_argument("file", type=Path, help="Path to file to evaluate")
    check_parser.add_argument(
        "--specs", required=True, type=Path, help="Path to checks specs JSON file"
    )
    check_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    check_parser.add_argument(
        "--fail-on", default="error", help="Severity threshold (default: error, or warning)"
    )

    args = parser.parse_args(argv)

    if args.command == "run":
        return run_fixture(args.fixture, json_mode=args.json, fail_on=args.fail_on)
    elif args.command == "check":
        return run_check_file(args.file, args.specs, json_mode=args.json, fail_on=args.fail_on)

    return 0


if __name__ == "__main__":
    sys.exit(main())
