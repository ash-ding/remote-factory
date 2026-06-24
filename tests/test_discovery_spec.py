"""Tests for factory.discovery.spec — SPEC.md resolution and generation."""

from __future__ import annotations

from pathlib import Path

from factory.discovery.spec import generate_spec, resolve_spec
from factory.models import ProjectProfile


def _make_profile(**overrides) -> ProjectProfile:
    defaults = {
        "name": "test-project",
        "language": "python",
        "project_type": "cli_tool",
        "has_tests": True,
        "has_linter": True,
        "has_type_checker": True,
        "has_ci": False,
        "test_command": "pytest -v",
        "lint_command": "ruff check .",
        "type_check_command": "mypy .",
        "package_manager": "uv",
    }
    defaults.update(overrides)
    return ProjectProfile(**defaults)


def test_resolve_spec_committed(tmp_path: Path):
    (tmp_path / "SPEC.md").write_text("# Spec")
    path, source = resolve_spec(tmp_path)
    assert source == "committed"
    assert path == tmp_path / "SPEC.md"


def test_resolve_spec_generated(tmp_path: Path):
    factory_dir = tmp_path / ".factory"
    factory_dir.mkdir()
    (factory_dir / "SPEC.md").write_text("# Generated Spec")
    path, source = resolve_spec(tmp_path)
    assert source == "generated"
    assert path == factory_dir / "SPEC.md"


def test_resolve_spec_committed_takes_priority(tmp_path: Path):
    (tmp_path / "SPEC.md").write_text("# Committed")
    factory_dir = tmp_path / ".factory"
    factory_dir.mkdir()
    (factory_dir / "SPEC.md").write_text("# Generated")
    path, source = resolve_spec(tmp_path)
    assert source == "committed"
    assert path == tmp_path / "SPEC.md"


def test_resolve_spec_absent(tmp_path: Path):
    path, source = resolve_spec(tmp_path)
    assert source == "absent"
    assert path is None


def test_generate_spec_format(tmp_path: Path):
    profile = _make_profile(name="my-app")
    output = generate_spec(tmp_path, profile)
    assert output.startswith("# my-app Specification")
    assert "## 1. Project Identity" in output
    assert "## 2. Goals" in output
    assert "## 3. Technical Stack" in output
    assert "## 4. Architecture" in output
    assert "## 5. Eval Dimensions" in output
    assert "## 6. Known Issues" in output
    assert "## 7. Backlog" in output
    assert "RFC 2119" in output


def test_generate_spec_captures_profile_data(tmp_path: Path):
    profile = _make_profile(
        language="python",
        framework="fastapi",
        test_command="pytest -v",
    )
    output = generate_spec(tmp_path, profile)
    assert "python" in output
    assert "fastapi" in output
    assert "pytest -v" in output


def test_generate_spec_reads_readme(tmp_path: Path):
    (tmp_path / "README.md").write_text("# My Project\n\nThis is a great tool for testing.\n")
    profile = _make_profile()
    output = generate_spec(tmp_path, profile)
    assert "This is a great tool for testing." in output


def test_generate_spec_no_readme(tmp_path: Path):
    profile = _make_profile()
    output = generate_spec(tmp_path, profile)
    assert "Goals not yet documented." in output


def test_generate_spec_detects_source_dirs(tmp_path: Path):
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    profile = _make_profile()
    output = generate_spec(tmp_path, profile)
    assert "mypackage" in output
