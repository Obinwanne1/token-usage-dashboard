"""Parse Claude Code local JSONL files into pandas DataFrames."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pricing import calculate_cost

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def get_claude_base_dir() -> Path:
    override = os.getenv("CLAUDE_DATA_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".claude"


# ---------------------------------------------------------------------------
# Prompt classifier
# ---------------------------------------------------------------------------

_RULES: list[tuple[str, str]] = [
    (r"^/", "skill/command"),
    (r"\b(plan|implement|architecture|phase|roadmap|milestone|design system)\b", "planning"),
    (r"\b(fix|bug|error|traceback|debug|issue|broken|fail|exception)\b", "debugging"),
    (r"\b(write|create|function|class|api|code|script|build|generate|add feature)\b", "coding"),
    (r"\b(design|UI|UX|layout|dashboard|style|color|font|brand|responsive)\b", "design"),
    (r"\b(review|check|audit|test|verify|validate|inspect)\b", "review"),
]


def classify_prompt(text: str) -> str:
    lower = text.lower()
    for pattern, label in _RULES:
        if re.search(pattern, lower if pattern != r"^/" else text, re.IGNORECASE):
            return label
    return "other"


# ---------------------------------------------------------------------------
# Project name extractor
# ---------------------------------------------------------------------------

def _project_name_from_folder(folder_name: str) -> str:
    """Convert encoded folder name back to readable project name.

    e.g. 'C--Users-rigwe-Desktop-CustomCommand' → 'CustomCommand'
    """
    cleaned = re.sub(r"^[A-Za-z]--Users-[^-]+-", "", folder_name)
    for prefix in ("Desktop-", "Documents-", "OneDrive-Desktop-"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return cleaned if cleaned else folder_name


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_sessions() -> list[dict]:
    base = get_claude_base_dir()
    sessions_dir = base / "sessions"
    results: list[dict] = []
    if not sessions_dir.exists():
        return results
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "sessionId": data.get("sessionId", ""),
                "startedAt": data.get("startedAt"),
                "cwd": data.get("cwd", ""),
                "version": data.get("version", ""),
                "entrypoint": data.get("entrypoint", ""),
                "pid": data.get("pid"),
            })
        except Exception:
            continue
    return results


def load_history() -> list[dict]:
    base = get_claude_base_dir()
    history_file = base / "history.jsonl"
    results: list[dict] = []
    if not history_file.exists():
        return results
    with history_file.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                display = entry.get("display", "")
                ts_ms = entry.get("timestamp")
                dt = (
                    datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    if ts_ms
                    else None
                )
                pasted = entry.get("pastedContents", {})
                pasted_chars = sum(
                    len(str(v)) for v in pasted.values()
                ) if isinstance(pasted, dict) else 0

                results.append({
                    "display": display,
                    "timestamp": dt,
                    "timestamp_ms": ts_ms,
                    "sessionId": entry.get("sessionId", ""),
                    "project": entry.get("project", ""),
                    "prompt_type": classify_prompt(display),
                    "has_pasted": pasted_chars > 0,
                    "pasted_chars": pasted_chars,
                })
            except Exception:
                continue
    return results


def load_project_usage() -> list[dict]:
    """Load token usage from all session JSONL files.

    Handles two structures:
    - projects/{PROJECT}/{SESSION_ID}.jsonl  (flat — older sessions)
    - projects/{PROJECT}/{SESSION_ID}/*.jsonl (subfolder — newer sessions)
      └── subagents/agent-*.jsonl            (sub-agent calls)
    """
    base = get_claude_base_dir()
    projects_dir = base / "projects"
    results: list[dict] = []
    if not projects_dir.exists():
        return results

    for project_folder in projects_dir.iterdir():
        if not project_folder.is_dir():
            continue
        project_name = _project_name_from_folder(project_folder.name)

        # Flat: *.jsonl directly in project folder
        for jsonl_file in project_folder.glob("*.jsonl"):
            session_id = jsonl_file.stem
            try:
                _parse_session_jsonl(
                    jsonl_file, session_id, project_name, results, source="main"
                )
            except Exception:
                continue

        # Subfolder: {SESSION_UUID}/*.jsonl + subagents/*.jsonl
        for session_dir in project_folder.iterdir():
            if not session_dir.is_dir():
                continue
            session_id = session_dir.name

            for jsonl_file in session_dir.glob("*.jsonl"):
                try:
                    _parse_session_jsonl(
                        jsonl_file, session_id, project_name, results, source="main"
                    )
                except Exception:
                    continue

            subagents_dir = session_dir / "subagents"
            if subagents_dir.exists():
                for agent_file in subagents_dir.glob("*.jsonl"):
                    try:
                        _parse_session_jsonl(
                            agent_file, session_id, project_name, results,
                            source="subagent"
                        )
                    except Exception:
                        continue

    return results


def _parse_session_jsonl(
    path: Path,
    session_id: str,
    project_name: str,
    results: list[dict],
    source: str = "main",
) -> None:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")

            # Count tool calls in assistant messages
            if entry_type == "assistant":
                message = entry.get("message", {})
                usage = message.get("usage")
                if not usage:
                    continue

                model = message.get("model", "unknown")
                ts_raw = entry.get("timestamp", "")

                content = message.get("content", [])
                tool_use_count = sum(
                    1 for block in content
                    if isinstance(block, dict) and block.get("type") == "tool_use"
                )

                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                cache_create = usage.get("cache_creation_input_tokens", 0)
                cache_read = usage.get("cache_read_input_tokens", 0)
                total_tokens = input_tokens + output_tokens + cache_create + cache_read

                cost = calculate_cost(usage, model)

                results.append({
                    "timestamp": ts_raw,
                    "sessionId": session_id,
                    "project_name": project_name,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_creation_tokens": cache_create,
                    "cache_read_tokens": cache_read,
                    "total_tokens": total_tokens,
                    "cost_usd": cost,
                    "tool_use_count": tool_use_count,
                    "source": source,
                })

            # Count tool results in user messages (context carryover weight)
            elif entry_type == "user":
                message = entry.get("message", {})
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            ts_raw = entry.get("timestamp", "")
                            result_content = block.get("content", "")
                            result_chars = (
                                len(result_content)
                                if isinstance(result_content, str)
                                else sum(
                                    len(str(c.get("text", "")))
                                    for c in result_content
                                    if isinstance(c, dict)
                                )
                            )
                            results.append({
                                "timestamp": ts_raw,
                                "sessionId": session_id,
                                "project_name": project_name,
                                "model": "tool_result",
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "cache_creation_tokens": 0,
                                "cache_read_tokens": 0,
                                "total_tokens": 0,
                                "cost_usd": 0.0,
                                "tool_use_count": 0,
                                "source": "tool_result",
                                "result_chars": result_chars,
                            })


# ---------------------------------------------------------------------------
# DataFrame builder
# ---------------------------------------------------------------------------

def build_dataframes() -> dict[str, pd.DataFrame]:
    usage_records = load_project_usage()
    history_records = load_history()
    session_records = load_sessions()

    # Split usage records from tool_result tracking records
    main_usage = [r for r in usage_records if r.get("source") != "tool_result"]
    tool_result_records = [r for r in usage_records if r.get("source") == "tool_result"]

    df_usage = pd.DataFrame(main_usage) if main_usage else _empty_usage_df()
    df_tool_results = pd.DataFrame(tool_result_records) if tool_result_records else pd.DataFrame()
    df_history = pd.DataFrame(history_records) if history_records else _empty_history_df()
    df_sessions = pd.DataFrame(session_records) if session_records else pd.DataFrame()

    # Normalize timestamps
    for df in (df_usage, df_history):
        if "timestamp" in df.columns and not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            df["date"] = df["timestamp"].dt.date

    # Ensure numeric columns exist
    for col in ("tool_use_count", "source"):
        if col not in df_usage.columns:
            df_usage[col] = 0 if col == "tool_use_count" else "main"

    return {
        "df_usage": df_usage,
        "df_history": df_history,
        "df_sessions": df_sessions,
        "df_tool_results": df_tool_results,
    }


def _empty_usage_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "timestamp", "sessionId", "project_name", "model",
        "input_tokens", "output_tokens", "cache_creation_tokens",
        "cache_read_tokens", "total_tokens", "cost_usd",
        "tool_use_count", "source", "date",
    ])


def _empty_history_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "display", "timestamp", "timestamp_ms", "sessionId",
        "project", "prompt_type", "has_pasted", "pasted_chars", "date",
    ])


# ---------------------------------------------------------------------------
# 30-second mtime cache
# ---------------------------------------------------------------------------

_CACHE: dict[str, Any] = {
    "data": None,
    "loaded_at": 0.0,
    "mtimes": {},
}
_CACHE_TTL = 30  # seconds


def _get_watched_files() -> list[Path]:
    base = get_claude_base_dir()
    files = [base / "history.jsonl"]
    sessions_dir = base / "sessions"
    if sessions_dir.exists():
        files.extend(sessions_dir.glob("*.json"))
    # Watch project subdirectory mtimes so cache invalidates when JSONL data changes.
    # Stat-ing each subdir is cheap; reading 208MB of JSONL is not.
    projects_dir = base / "projects"
    if projects_dir.exists():
        for project_folder in projects_dir.iterdir():
            if project_folder.is_dir():
                files.append(project_folder)
                for session_dir in project_folder.iterdir():
                    if session_dir.is_dir():
                        files.append(session_dir)
    return files


def _current_mtimes() -> dict[str, float]:
    mtimes: dict[str, float] = {}
    for f in _get_watched_files():
        try:
            mtimes[str(f)] = f.stat().st_mtime
        except OSError:
            pass
    return mtimes


def load_data_cached() -> dict[str, pd.DataFrame]:
    """Return dataframes, rebuilding only if files changed or TTL expired."""
    now = time.monotonic()
    cache_stale = (now - _CACHE["loaded_at"]) >= _CACHE_TTL

    if cache_stale:
        current_mtimes = _current_mtimes()
        if current_mtimes != _CACHE["mtimes"] or _CACHE["data"] is None:
            _CACHE["data"] = build_dataframes()
            _CACHE["mtimes"] = current_mtimes
        _CACHE["loaded_at"] = now

    return _CACHE["data"]
