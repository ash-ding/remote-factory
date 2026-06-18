"""Tests for factory.sessions — SQLite session persistence layer."""

from __future__ import annotations

from pathlib import Path

from factory.sessions import (
    begin_session,
    complete_session,
    get_children,
    get_session,
    get_sessions,
    init_db,
)


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = init_db(tmp_path)
    assert db_path.exists()
    assert db_path.name == "sessions.db"

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "sessions" in tables
    assert "session_items" in tables


def test_init_db_idempotent(tmp_path: Path) -> None:
    init_db(tmp_path)
    init_db(tmp_path)
    assert (tmp_path / ".factory" / "sessions.db").exists()


def test_begin_session_returns_prefixed_id(tmp_path: Path) -> None:
    sid = begin_session(tmp_path, "builder")
    assert sid.startswith("sess_")
    assert len(sid) == 13  # "sess_" + 8 hex chars


def test_begin_complete_roundtrip(tmp_path: Path) -> None:
    sid = begin_session(tmp_path, "researcher", title="Test session")

    from factory.models import AgentUsage

    usage = AgentUsage(
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=10,
        total_cost_usd=0.05,
        duration_ms=1234.5,
        num_turns=3,
        model="claude-sonnet-4-6",
    )
    metadata = {
        "session_id": "abc123",
        "stop_reason": "end_turn",
        "terminal_reason": "end_turn",
    }
    complete_session(
        tmp_path, sid,
        usage=usage, metadata=metadata, output="I completed the task.",
    )

    session = get_session(tmp_path, sid)
    assert session is not None
    assert session["id"] == sid
    assert session["agent_role"] == "researcher"
    assert session["status"] == "completed"
    assert session["input_tokens"] == 100
    assert session["output_tokens"] == 50
    assert session["cache_read_tokens"] == 10
    assert session["total_cost_usd"] == 0.05
    assert session["duration_ms"] == 1234.5
    assert session["num_turns"] == 3
    assert session["model"] == "claude-sonnet-4-6"
    assert session["stop_reason"] == "end_turn"
    assert session["claude_session_id"] == "abc123"
    assert session["title"] == "Test session"
    assert len(session["items"]) == 1
    assert session["items"][0]["data"] == "I completed the task."
    assert session["items"][0]["type"] == "message"


def test_hierarchical_parent_child(tmp_path: Path) -> None:
    parent_id = begin_session(tmp_path, "ceo")
    child1 = begin_session(tmp_path, "researcher", parent_id=parent_id)
    begin_session(tmp_path, "builder", parent_id=parent_id)

    parent = get_session(tmp_path, parent_id)
    assert parent is not None
    assert parent["kind"] == "default"
    assert parent["root_id"] == parent_id

    c1 = get_session(tmp_path, child1)
    assert c1 is not None
    assert c1["kind"] == "sub_agent"
    assert c1["parent_id"] == parent_id
    assert c1["root_id"] == child1  # root defaults to self when not passed

    children = get_children(tmp_path, parent_id)
    assert len(children) == 2
    roles = {c["agent_role"] for c in children}
    assert roles == {"researcher", "builder"}


def test_hierarchical_with_root_id(tmp_path: Path) -> None:
    root = begin_session(tmp_path, "ceo")
    child = begin_session(tmp_path, "builder", parent_id=root, root_id=root)

    session = get_session(tmp_path, child)
    assert session is not None
    assert session["root_id"] == root
    assert session["parent_id"] == root


def test_get_sessions_filter_by_role(tmp_path: Path) -> None:
    begin_session(tmp_path, "builder")
    begin_session(tmp_path, "researcher")
    begin_session(tmp_path, "builder")

    builders = get_sessions(tmp_path, role="builder")
    assert len(builders) == 2
    assert all(s["agent_role"] == "builder" for s in builders)


def test_get_sessions_filter_by_cycle(tmp_path: Path) -> None:
    root1 = begin_session(tmp_path, "ceo")
    begin_session(tmp_path, "builder", parent_id=root1, root_id=root1)

    root2 = begin_session(tmp_path, "ceo")
    begin_session(tmp_path, "researcher", parent_id=root2, root_id=root2)

    cycle1 = get_sessions(tmp_path, cycle_id=root1)
    assert len(cycle1) == 2
    assert all(s["root_id"] == root1 for s in cycle1)


def test_get_session_not_found(tmp_path: Path) -> None:
    init_db(tmp_path)
    result = get_session(tmp_path, "sess_nonexist")
    assert result is None


def test_get_sessions_no_db(tmp_path: Path) -> None:
    result = get_sessions(tmp_path)
    assert result == []


def test_get_children_no_db(tmp_path: Path) -> None:
    result = get_children(tmp_path, "sess_nonexist")
    assert result == []


def test_complete_session_failed_status(tmp_path: Path) -> None:
    sid = begin_session(tmp_path, "builder")
    complete_session(tmp_path, sid, status="failed")

    session = get_session(tmp_path, sid)
    assert session is not None
    assert session["status"] == "failed"


def test_complete_session_without_output(tmp_path: Path) -> None:
    sid = begin_session(tmp_path, "evaluator")
    complete_session(tmp_path, sid)

    session = get_session(tmp_path, sid)
    assert session is not None
    assert session["status"] == "completed"
    assert session["items"] == []


def test_model_preserved_from_begin(tmp_path: Path) -> None:
    sid = begin_session(tmp_path, "builder", model="claude-opus-4-6")
    complete_session(tmp_path, sid)

    session = get_session(tmp_path, sid)
    assert session is not None
    assert session["model"] == "claude-opus-4-6"
