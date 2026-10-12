import json
from pathlib import Path

from aieval.cli.main import main


def test_cli_golden_primitive_coercion(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "golden_primitive_coercion.json"
    exit_code = main(["run", str(fixture_path), "--json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["passed"] is False
    assert len(res["failures"]) == 1
    assert res["failures"][0]["code"] == "VALUE_CONSTRAINT_VIOLATION"


def test_cli_golden_null_vs_missing(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "golden_null_vs_missing.json"
    exit_code = main(["run", str(fixture_path), "--json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["passed"] is False
    assert len(res["failures"]) == 1
    assert res["failures"][0]["code"] == "MISSING_REQUIRED_FIELD"
    assert res["failures"][0]["path"] == "completely_missing"

