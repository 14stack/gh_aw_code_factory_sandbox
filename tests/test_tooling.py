import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_dev_extras_include_linters():
    dev = _pyproject()["project"]["optional-dependencies"]["dev"]
    assert any(entry.startswith("mypy") for entry in dev)
    assert any(entry.startswith("ruff") for entry in dev)


def test_mypy_config_present():
    mypy = _pyproject()["tool"]["mypy"]
    assert mypy["python_version"] == "3.12"
    assert "src" in mypy["files"]
    assert "tests" in mypy["files"]
    assert mypy["warn_unused_configs"] is True
    assert mypy["warn_redundant_casts"] is True
    assert mypy["warn_unused_ignores"] is True
    assert mypy["no_implicit_optional"] is True
    assert mypy["check_untyped_defs"] is True
    assert "strict" not in mypy


def test_makefile_defines_quality_targets():
    makefile = Path(__file__).resolve().parents[1] / "Makefile"
    assert makefile.is_file()
    text = makefile.read_text(encoding="utf-8")

    assert "lint-check:" in text
    assert "test-unit:" in text
    assert ".PHONY: lint-check test-unit" in text

    lint_recipe = text.split("lint-check:", 1)[1].split("test-unit:", 1)[0]
    assert "ruff check" in lint_recipe
    assert "ruff format --check" in lint_recipe
    assert "mypy" in lint_recipe

    test_recipe = text.split("test-unit:", 1)[1]
    assert "pytest" in test_recipe
