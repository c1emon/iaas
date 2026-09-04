"""Focused tests for shared primitive helpers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from iaas_automation.common.cli import run_validation_cli
from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import check_outputs, check_text_file, load_json, load_yaml, write_text
from iaas_automation.common.markdown import escape_table_cell
from iaas_automation.common.validation import as_list, as_mapping, require_bool, require_non_empty_string, require_positive_int, require_unknown_keys, require_url_like


ROOT = Path(__file__).resolve().parents[2]


def test_common_validation_helpers_raise_expected_errors() -> None:
    with pytest.raises(ValidationError, match="expected mapping"):
        as_mapping([], "item")
    with pytest.raises(ValidationError, match="expected list"):
        as_list({}, "item")
    with pytest.raises(ValidationError, match="must be a positive integer"):
        require_positive_int(0, "item")
    with pytest.raises(ValidationError, match="must be a boolean"):
        require_bool("true", "item")
    with pytest.raises(ValidationError, match="must be a non-empty string"):
        require_non_empty_string("", "item")
    with pytest.raises(ValidationError, match="unknown keys extra"):
        require_unknown_keys({"extra": True}, set(), "item")
    with pytest.raises(ValidationError, match="must look like a URL"):
        require_url_like("ftp://example.invalid", "item")
    with pytest.raises(ValidationError, match="boom"):
        require(False, "boom")


def test_common_io_helpers_cover_yaml_json_text_and_stale_checks(tmp_path: Path) -> None:
    yaml_path = tmp_path / "sample.yml"
    yaml_path.write_text("name: demo\n", encoding="utf-8")
    json_path = tmp_path / "sample.json"
    json_path.write_text('{"name": "demo"}\n', encoding="utf-8")
    text_path = tmp_path / "sample.txt"
    write_text(text_path, "hello\n")
    secure_path = tmp_path / "secure.txt"
    write_text(secure_path, "secret\n", secure=True)

    assert load_yaml(yaml_path) == {"name": "demo"}
    assert load_json(json_path) == {"name": "demo"}
    assert check_text_file(text_path, "hello\n") is True
    assert check_text_file(text_path, "nope\n") is False
    assert secure_path.read_text(encoding="utf-8") == "secret\n"

    expected = {"first": "ok\n", "second": "fresh\n"}
    paths = {"first": text_path, "second": tmp_path / "missing.txt"}
    write_text(paths["first"], "stale\n")
    assert check_outputs(expected, paths) == [f"stale: {paths['first']}", f"missing: {paths['second']}"]


def test_markdown_cell_escape_matches_service_documentation_behavior() -> None:
    assert escape_table_cell(None) == "-"
    assert escape_table_cell("") == "-"
    assert escape_table_cell("a|b\nline\r\nnext") == "a\\|b<br>line<br>next"


def test_validation_cli_boundary_preserves_failure_format(capsys: pytest.CaptureFixture[str]) -> None:
    def main(_argv: list[str] | None) -> int:
        raise ValidationError("bad input")

    assert run_validation_cli(main, []) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "FAIL validation: bad input\n"


def test_services_inventory_does_not_import_pve_shared_primitives() -> None:
    forbidden = {
        "iaas_automation.pve_inventory.errors",
        "iaas_automation.pve_inventory.io",
        "iaas_automation.pve_inventory.validation_common",
    }
    for path in (ROOT / "automation" / "src" / "iaas_automation" / "services_inventory").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    assert module not in forbidden
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                module = node.module
                assert module not in forbidden
