"""E2E tests for runner implementations — real API calls, no mocks, no dry-run.

These tests invoke actual CLI binaries and make real API calls.
Mark with @pytest.mark.slow so they can be skipped in fast CI runs.

Cost control:
- Tiny greeter project (2 files, <20 lines)
- Short prompts, trivial tasks
- 60s timeouts
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from factory.models import AgentRunRequest, AgentRunResult
from factory.runners import get_available_runners

pytestmark = pytest.mark.slow


# ── fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def greeter_project(tmp_path: Path) -> Path:
    """Create a tiny Python project for agents to work with."""
    main = tmp_path / "greeter.py"
    main.write_text(
        'def greet(name: str) -> str:\n'
        '    return f"Hello, {name}!"\n'
        '\n'
        'if __name__ == "__main__":\n'
        '    print(greet("World"))\n'
    )
    readme = tmp_path / "README.md"
    readme.write_text("# Greeter\n\nA tiny greeter.\n")
    return tmp_path


def _runner_available(name: str) -> bool:
    """Check if a runner binary is on PATH and auth is configured."""
    runners = get_available_runners()
    if name not in runners:
        return False
    cls = runners[name]
    try:
        meta = cls.metadata()  # type: ignore[union-attr]
        if not meta.is_available():
            return False
        return True
    except (AttributeError, TypeError):
        return shutil.which(name) is not None


def _runner_has_auth(name: str) -> bool:
    """Check if a runner's auth requirements are met."""
    if name == "codex":
        return bool(os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if name == "bob":
        return bool(os.environ.get("BOBSHELL_API_KEY"))
    if name == "opencode":
        return bool(os.environ.get("OPENAI_API_KEY"))
    return True


# ── parametrized runner IDs ──────────────────────────────────────


def _collect_runner_ids() -> list[str]:
    """Collect runner names that are installed and authenticated on this machine."""
    ids = []
    for name in get_available_runners():
        if _runner_available(name) and _runner_has_auth(name):
            ids.append(name)
    return ids


AVAILABLE_RUNNERS = _collect_runner_ids()


def _make_request(
    project: Path,
    *,
    task: str = "Read greeter.py and tell me what the greet function returns. Reply in one sentence.",
    role: str = "researcher",
    timeout: float = 60.0,
    model: str | None = None,
) -> AgentRunRequest:
    """Build a minimal AgentRunRequest for testing."""
    return AgentRunRequest(
        prompt="You are a code assistant. Be concise.",
        task=task,
        cwd=project,
        timeout=timeout,
        skip_permissions=True,
        role=role,
        model=model,
    )


# ── tests ────────────────────────────────────────────────────────


@pytest.mark.parametrize("runner_name", AVAILABLE_RUNNERS)
async def test_headless_produces_output(
    runner_name: str, greeter_project: Path
) -> None:
    """Every runner can do a headless invocation and return non-empty stdout."""
    from factory.runners import get_runner

    runner = get_runner(runner_name)
    request = _make_request(greeter_project)
    result = await runner.headless(request)

    assert isinstance(result, AgentRunResult)
    assert result.return_code == 0, f"{runner_name} failed: {result.stdout[:300]}"
    assert len(result.stdout.strip()) > 0, f"{runner_name} returned empty output"


@pytest.mark.parametrize("runner_name", AVAILABLE_RUNNERS)
async def test_timeout_handling(
    runner_name: str, greeter_project: Path
) -> None:
    """Runners handle very short timeouts gracefully (return code 1, no crash)."""
    from factory.runners import get_runner

    runner = get_runner(runner_name)
    request = _make_request(
        greeter_project,
        task="Write a 1000-line essay about software engineering.",
        timeout=3.0,
    )
    result = await runner.headless(request)

    assert isinstance(result, AgentRunResult)
    assert result.return_code != 0 or "timed out" in result.stdout.lower()


@pytest.mark.skipif("claude" not in AVAILABLE_RUNNERS, reason="claude not available")
async def test_claude_usage_telemetry(greeter_project: Path) -> None:
    """Claude runner returns usage telemetry (input/output tokens, cost)."""
    from factory.runners import get_runner

    runner = get_runner("claude")
    request = _make_request(greeter_project)
    result = await runner.headless(request)

    assert result.return_code == 0
    assert result.usage is not None, "Claude should return usage telemetry"
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


@pytest.mark.skipif("claude" not in AVAILABLE_RUNNERS, reason="claude not available")
async def test_claude_model_override(greeter_project: Path) -> None:
    """Claude respects model override."""
    from factory.runners import get_runner

    runner = get_runner("claude")
    request = _make_request(greeter_project, model="claude-sonnet-4-6")
    result = await runner.headless(request)

    assert result.return_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.skipif("opencode" not in AVAILABLE_RUNNERS, reason="opencode not available")
async def test_opencode_headless(greeter_project: Path) -> None:
    """OpenCode runner can do a headless invocation."""
    from factory.runners import get_runner

    runner = get_runner("opencode")
    request = _make_request(greeter_project)
    result = await runner.headless(request)

    assert isinstance(result, AgentRunResult)
    assert result.return_code == 0, f"opencode failed: {result.stdout[:300]}"
    assert len(result.stdout.strip()) > 0


def test_runners_list_command() -> None:
    """factory runners list returns 0 and shows all runners."""
    from factory.cli import build_parser, cmd_runners_list

    parser = build_parser()
    args = parser.parse_args(["runners", "list"])
    code = cmd_runners_list(args)
    assert code == 0


def test_runners_list_json() -> None:
    """factory runners list --json returns valid JSON with all runners."""
    import json
    from io import StringIO
    from unittest.mock import patch

    from factory.cli import build_parser, cmd_runners_list

    parser = build_parser()
    args = parser.parse_args(["runners", "list", "--json"])

    buf = StringIO()
    with patch("sys.stdout", buf):
        code = cmd_runners_list(args)

    assert code == 0
    data = json.loads(buf.getvalue())
    assert isinstance(data, list)
    assert len(data) >= 4
    names = {r["name"] for r in data}
    assert "claude" in names
    assert "bob" in names
    assert "codex" in names
    assert "opencode" in names


def test_get_available_runners_includes_all_builtins() -> None:
    """get_available_runners includes all 4 built-in runners."""
    runners = get_available_runners()
    assert "claude" in runners
    assert "bob" in runners
    assert "codex" in runners
    assert "opencode" in runners


def test_runner_metadata_consistency() -> None:
    """All runners have consistent metadata."""
    from factory.runners import get_all_runner_meta

    meta_list = get_all_runner_meta()
    assert len(meta_list) >= 4

    names = set()
    for m in meta_list:
        assert m.name, "name must not be empty"
        assert m.display_name, "display_name must not be empty"
        assert m.binary, "binary must not be empty"
        assert m.install_hint, "install_hint must not be empty"
        assert m.name not in names, f"duplicate runner name: {m.name}"
        names.add(m.name)


def test_entry_point_discovery_does_not_crash() -> None:
    """Entry point discovery runs without error even if no plugins are installed."""
    import factory.runners as runners_mod

    runners_mod._entrypoints_loaded = False
    runners_mod._load_entrypoint_runners()
    assert runners_mod._entrypoints_loaded is True


@pytest.mark.parametrize("runner_name", AVAILABLE_RUNNERS)
async def test_cross_runner_parity(
    runner_name: str, greeter_project: Path
) -> None:
    """All runners produce a valid AgentRunResult with the same task."""
    from factory.runners import get_runner

    runner = get_runner(runner_name)
    request = _make_request(
        greeter_project,
        task="What does greeter.py do? Answer in one sentence.",
    )
    result = await runner.headless(request)

    assert isinstance(result, AgentRunResult)
    assert isinstance(result.stdout, str)
    assert isinstance(result.return_code, int)
