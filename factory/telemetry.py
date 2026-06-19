"""Langfuse tracing wrapper — graceful no-op when not configured."""

from __future__ import annotations

import json
import os
from pathlib import Path

import structlog

log = structlog.get_logger()

try:
    from langfuse import Langfuse

    _HAS_LANGFUSE = True
except ImportError:
    _HAS_LANGFUSE = False

_client: object | None = None


def is_enabled() -> bool:
    """Check if Langfuse is configured and lazily initialise the client."""
    global _client
    if _client is not None:
        return True
    if not _HAS_LANGFUSE:
        return False
    if not os.environ.get("LANGFUSE_HOST"):
        return False
    try:
        _client = Langfuse()
        log.debug("langfuse_initialized", host=os.environ["LANGFUSE_HOST"])
        return True
    except Exception as exc:
        log.warning("langfuse_init_failed", error=str(exc))
        return False


def _get_client() -> Langfuse:
    if _client is None:
        raise RuntimeError("Langfuse not initialised — call is_enabled() first")
    return _client  # type: ignore[return-value]


def begin_trace(
    project_name: str,
    cycle_id: str,
    model: str | None = None,
) -> str:
    """Create a root trace and return its trace_id."""
    client = _get_client()
    trace = client.trace(
        name=f"factory:{project_name}",
        session_id=cycle_id,
        metadata={"model": model} if model else None,
    )
    log.debug("langfuse_trace_started", trace_id=trace.id, project=project_name)
    return trace.id


def begin_span(
    trace_id: str,
    parent_span_id: str | None,
    role: str,
    model: str | None = None,
) -> str:
    """Create a child span under a trace/parent and return its span_id."""
    client = _get_client()
    span = client.span(
        trace_id=trace_id,
        parent_observation_id=parent_span_id,
        name=f"agent:{role}",
        metadata={"model": model} if model else None,
    )
    log.debug("langfuse_span_started", span_id=span.id, role=role)
    return span.id


def end_span(
    trace_id: str,
    span_id: str,
    *,
    status: str = "completed",
    usage: dict | None = None,
    metadata: dict | None = None,
    output: str | None = None,
) -> None:
    """End a span, recording usage and metadata."""
    client = _get_client()
    u = usage or {}
    m = dict(metadata or {})

    langfuse_usage = {}
    if u.get("input_tokens"):
        langfuse_usage["input"] = u["input_tokens"]
    if u.get("output_tokens"):
        langfuse_usage["output"] = u["output_tokens"]

    for key in ("total_cost_usd", "duration_ms", "num_turns", "model"):
        if u.get(key) is not None:
            m[key] = u[key]

    m["status"] = status

    client.span(
        id=span_id,
        trace_id=trace_id,
        end_time=None,
        metadata=m or None,
        output=output,
        usage=langfuse_usage or None,
    )
    log.debug("langfuse_span_ended", span_id=span_id, status=status)


def end_trace(trace_id: str) -> None:
    """Mark a root trace as finished."""
    client = _get_client()
    client.trace(id=trace_id, metadata={"status": "completed"})
    log.debug("langfuse_trace_ended", trace_id=trace_id)


def flush() -> None:
    """Flush any buffered Langfuse events."""
    if _client is not None:
        _get_client().flush()


# ---------------------------------------------------------------------------
# Transcript ingestion
# ---------------------------------------------------------------------------


def _find_transcript(claude_session_id: str, project_path: Path) -> Path | None:
    """Locate a Claude Code transcript JSONL, trying multiple path patterns."""
    claude_dir = Path.home() / ".claude" / "projects"
    dir_name = str(project_path.resolve()).replace("/", "-").replace(".", "-")
    direct = claude_dir / dir_name / f"{claude_session_id}.jsonl"
    if direct.exists():
        return direct
    if claude_dir.exists():
        for pdir in claude_dir.iterdir():
            if pdir.is_dir():
                candidate = pdir / f"{claude_session_id}.jsonl"
                if candidate.exists():
                    return candidate
    return None


def ingest_transcript_to_span(
    trace_id: str,
    span_id: str,
    claude_session_id: str,
    project_path: Path,
) -> bool:
    """Parse a Claude Code JSONL transcript into Langfuse observations.

    Tool calls and their results are paired by tool_use_id into single
    span observations.  Returns True if any observations were created.
    """
    transcript_file = _find_transcript(claude_session_id, project_path)
    if transcript_file is None:
        log.debug("langfuse_transcript_not_found", claude_session_id=claude_session_id)
        return False

    client = _get_client()
    pending_tools: dict[str, str] = {}
    count = 0

    with open(transcript_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            item_type = item.get("type", "")

            if item_type == "user":
                msg = item.get("message", {})
                content_parts = msg.get("content", [])

                tool_results: list[dict] = []
                text_parts: list[str] = []

                for part in content_parts:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict):
                        if part.get("type") == "tool_result":
                            tool_use_id = part.get("tool_use_id", "")
                            raw = part.get("content", [])
                            text = "".join(str(c) for c in raw) if isinstance(raw, list) else str(raw)
                            tool_results.append({
                                "tool_use_id": tool_use_id,
                                "content": text,
                                "is_error": part.get("is_error", False),
                            })
                        elif part.get("type") == "text":
                            text_parts.append(part.get("text", ""))

                for tr in tool_results:
                    tool_use_id = tr["tool_use_id"]
                    if tool_use_id in pending_tools:
                        obs_id = pending_tools.pop(tool_use_id)
                        client.span(
                            id=obs_id,
                            trace_id=trace_id,
                            output=tr["content"][:4000],
                            metadata={"is_error": tr["is_error"]},
                        )
                        count += 1
                    else:
                        client.event(
                            trace_id=trace_id,
                            parent_observation_id=span_id,
                            name="tool_output",
                            output=tr["content"][:4000],
                            metadata={"tool_use_id": tool_use_id, "is_error": tr["is_error"]},
                        )
                        count += 1

                if not tool_results and text_parts:
                    text = "".join(text_parts)
                    if text.strip():
                        client.event(
                            trace_id=trace_id,
                            parent_observation_id=span_id,
                            name="user_message",
                            input=text[:4000],
                        )
                        count += 1

            elif item_type == "assistant":
                msg = item.get("message", {})
                content = msg.get("content", [])
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type", "")
                    if ptype == "text":
                        text = part.get("text", "")
                        if text.strip():
                            client.event(
                                trace_id=trace_id,
                                parent_observation_id=span_id,
                                name="assistant_message",
                                output=text[:4000],
                            )
                            count += 1
                    elif ptype == "tool_use":
                        tool_name = part.get("name", "unknown")
                        tool_input = part.get("input", {})
                        tool_use_id = part.get("id", "")
                        obs = client.span(
                            trace_id=trace_id,
                            parent_observation_id=span_id,
                            name=f"tool:{tool_name}",
                            input=tool_input,
                        )
                        if tool_use_id:
                            pending_tools[tool_use_id] = obs.id
                        count += 1
                    elif ptype == "thinking":
                        text = part.get("thinking", "")
                        if text.strip():
                            client.event(
                                trace_id=trace_id,
                                parent_observation_id=span_id,
                                name="thinking",
                                metadata={"thinking": text[:4000]},
                            )
                            count += 1

            elif item_type == "tool_result":
                content = item.get("content", [])
                tool_use_id = item.get("tool_use_id", "")
                text = ""
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text += part.get("text", "")
                    elif isinstance(part, str):
                        text += part
                if text.strip():
                    if tool_use_id and tool_use_id in pending_tools:
                        obs_id = pending_tools.pop(tool_use_id)
                        client.span(
                            id=obs_id,
                            trace_id=trace_id,
                            output=text[:4000],
                        )
                    else:
                        client.event(
                            trace_id=trace_id,
                            parent_observation_id=span_id,
                            name="tool_output",
                            output=text[:4000],
                        )
                    count += 1

    for orphan_id in pending_tools.values():
        client.span(
            id=orphan_id,
            trace_id=trace_id,
            metadata={"status": "no_result"},
        )

    log.debug("langfuse_transcript_ingested", count=count, session=claude_session_id)
    return count > 0
