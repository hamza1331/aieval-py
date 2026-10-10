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
