from pathlib import Path

from aieval.cli.main import main


def test_cli_human_formatted_output_pass(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "golden_valid_tool_call.json"
    exit_code = main(["run", str(fixture_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "PASSED" in captured.out
    assert "Evaluation Result:" in captured.out


def test_cli_human_formatted_output_fail(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "golden_invalid_tool_call.json"
    exit_code = main(["run", str(fixture_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.out
    assert "Failures:" in captured.out
    assert "TOOL_CALL_UNKNOWN_TOOL" in captured.out


def test_cli_file_not_found(capsys):
    exit_code = main(["run", "non_existent_fixture.json"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Fixture file not found" in captured.err


def test_cli_check_file_not_found(capsys, tmp_path):
    specs_file = tmp_path / "specs.json"
    specs_file.write_text("[]")
    exit_code = main(["check", "non_existent_file.json", "--specs", str(specs_file)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Target file not found" in captured.err


def test_cli_specs_file_not_found(capsys, tmp_path):
    target_file = tmp_path / "target.json"
    target_file.write_text("{}")
    exit_code = main(["check", str(target_file), "--specs", "non_existent_specs.json"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Specs file not found" in captured.err


def test_cli_all_check_specs(tmp_path, capsys):
    specs_file = tmp_path / "specs.json"
    target_file = tmp_path / "target.txt"

    target_file.write_text("hello-world")
    specs_file.write_text(
        """[
            {"type": "regex_match", "pattern": "hello"},
            {"type": "length_bounds", "min_len": 1, "max_len": 50}
        ]"""
    )
    exit_code = main(["check", str(target_file), "--specs", str(specs_file), "--json"])
    assert exit_code == 0
