import json
from pathlib import Path

from aieval.cli.main import main


def test_cli_run_golden_fixture_pass(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "golden_valid_tool_call.json"
    exit_code = main(["run", str(fixture_path), "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["passed"] is True
    assert res["summary"]["total_checks"] == 2
    assert res["summary"]["passed_checks"] == 2


def test_cli_run_golden_fixture_fail(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "golden_invalid_tool_call.json"
    exit_code = main(["run", str(fixture_path), "--json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["passed"] is False
    assert len(res["failures"]) == 1
    assert res["failures"][0]["code"] == "TOOL_CALL_UNKNOWN_TOOL"


def test_cli_run_expected_failure_fixture_passes_when_expectation_matches(tmp_path, capsys):
    fixture_path = tmp_path / "expected_failure.json"
    fixture_path.write_text(
        json.dumps(
            {
                "output": {},
                "checks": [{"type": "required_fields", "fields": ["name"]}],
                "expected": {
                    "passed": False,
                    "failures": [
                        {
                            "code": "MISSING_REQUIRED_FIELD",
                            "path": "name",
                            "severity": "error",
                        }
                    ],
                },
            }
        )
    )

    exit_code = main(["run", str(fixture_path), "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_cli_run_expected_pass_flag_without_failure_details(tmp_path, capsys):
    fixture_path = tmp_path / "expected_failure_without_details.json"
    fixture_path.write_text(
        json.dumps(
            {
                "output": {},
                "checks": [{"type": "required_fields", "fields": ["name"]}],
                "expected": {"passed": False},
            }
        )
    )

    assert main(["run", str(fixture_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_cli_run_matches_partial_failure_expectations_without_order_dependence(tmp_path, capsys):
    fixture_path = tmp_path / "partial_expectations.json"
    fixture_path.write_text(
        json.dumps(
            {
                "output": {"category": "invalid", "priority": "invalid"},
                "checks": [
                    {"type": "enum", "field": "category", "allowed": ["valid"]},
                    {"type": "enum", "field": "priority", "allowed": ["valid"]},
                ],
                "expected": {
                    "passed": False,
                    "failures": [
                        {"code": "ENUM_MISMATCH"},
                        {"code": "ENUM_MISMATCH", "path": "category"},
                    ],
                },
            }
        )
    )

    assert main(["run", str(fixture_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_cli_run_fixture_fails_when_expected_failures_diverge(tmp_path, capsys):
    fixture_path = tmp_path / "mismatched_expectation.json"
    fixture_path.write_text(
        json.dumps(
            {
                "output": {},
                "checks": [{"type": "required_fields", "fields": ["name"]}],
                "expected": {
                    "passed": False,
                    "failures": [{"code": "MISSING_REQUIRED_FIELD", "path": "other"}],
                },
            }
        )
    )

    exit_code = main(["run", str(fixture_path), "--json"])

    assert exit_code == 1
    assert "expectation did not match" in capsys.readouterr().err


def test_cli_run_rejects_malformed_fixture_expectation(tmp_path, capsys):
    fixture_path = tmp_path / "malformed_expectation.json"
    fixture_path.write_text(
        json.dumps(
            {
                "output": {},
                "checks": [{"type": "valid_json"}],
                "expected": {"passed": "false"},
            }
        )
    )

    assert main(["run", str(fixture_path), "--json"]) == 1
    assert "boolean 'passed'" in capsys.readouterr().err


def test_cli_check_file(tmp_path, capsys):
    output_file = tmp_path / "output.json"
    specs_file = tmp_path / "specs.json"

    output_file.write_text(json.dumps({"username": "hamza", "status": "active"}))
    specs_file.write_text(
        json.dumps(
            [
                {"type": "required_fields", "fields": ["username", "status"]},
                {"type": "allowed_fields", "fields": ["username", "status"]},
            ]
        )
    )

    exit_code = main(["check", str(output_file), "--specs", str(specs_file), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["passed"] is True
