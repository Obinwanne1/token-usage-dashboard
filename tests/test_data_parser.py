"""Unit tests for data_parser and pricing modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_parser import classify_prompt, _project_name_from_folder
from pricing import calculate_cost, format_cost, PRICING


# ---------------------------------------------------------------------------
# classify_prompt
# ---------------------------------------------------------------------------

class TestClassifyPrompt:
    def test_skill_command(self):
        assert classify_prompt("/statusline") == "skill/command"
        assert classify_prompt("/commit") == "skill/command"

    def test_planning(self):
        assert classify_prompt("Create a plan for the new auth phase") == "planning"
        assert classify_prompt("Implement this architecture") == "planning"

    def test_debugging(self):
        assert classify_prompt("Fix the bug in login") == "debugging"
        assert classify_prompt("There is an error in the traceback") == "debugging"

    def test_coding(self):
        assert classify_prompt("Write a function to parse JSON") == "coding"
        assert classify_prompt("Create a new class for the API") == "coding"

    def test_design(self):
        assert classify_prompt("Design the dashboard layout") == "design"
        assert classify_prompt("Update the UI color scheme") == "design"

    def test_review(self):
        assert classify_prompt("Review this pull request") == "review"
        assert classify_prompt("Audit the security checks") == "review"

    def test_other(self):
        assert classify_prompt("Hello, what is the weather?") == "other"
        assert classify_prompt("") == "other"


# ---------------------------------------------------------------------------
# _project_name_from_folder
# ---------------------------------------------------------------------------

class TestProjectNameFromFolder:
    def test_desktop_project(self):
        result = _project_name_from_folder("C--Users-rigwe-Desktop-CustomCommand")
        assert result == "CustomCommand"

    def test_nested_project(self):
        result = _project_name_from_folder("C--Users-rigwe-Desktop-LearningClaudeCode")
        assert result == "LearningClaudeCode"

    def test_unknown_format(self):
        result = _project_name_from_folder("SomeRandomFolder")
        assert result == "SomeRandomFolder"


# ---------------------------------------------------------------------------
# calculate_cost
# ---------------------------------------------------------------------------

class TestCalculateCost:
    def test_sonnet_input_only(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0}
        cost = calculate_cost(usage, "claude-sonnet-4-6")
        assert abs(cost - 3.00) < 0.0001

    def test_sonnet_output_only(self):
        usage = {"input_tokens": 0, "output_tokens": 1_000_000}
        cost = calculate_cost(usage, "claude-sonnet-4-6")
        assert abs(cost - 15.00) < 0.0001

    def test_opus_mixed(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
        cost = calculate_cost(usage, "claude-opus-4-6")
        assert abs(cost - 90.00) < 0.0001

    def test_haiku(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0}
        cost = calculate_cost(usage, "claude-haiku-4-5")
        assert abs(cost - 0.25) < 0.0001

    def test_cache_read(self):
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 1_000_000,
        }
        cost = calculate_cost(usage, "claude-sonnet-4-6")
        assert abs(cost - 0.30) < 0.0001

    def test_cache_create(self):
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 1_000_000,
        }
        cost = calculate_cost(usage, "claude-sonnet-4-6")
        assert abs(cost - 3.75) < 0.0001

    def test_unknown_model_fallback(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0}
        cost = calculate_cost(usage, "claude-unknown-model")
        # Falls back to sonnet pricing
        assert abs(cost - 3.00) < 0.0001

    def test_zero_tokens(self):
        usage = {"input_tokens": 0, "output_tokens": 0}
        assert calculate_cost(usage, "claude-sonnet-4-6") == 0.0


# ---------------------------------------------------------------------------
# format_cost
# ---------------------------------------------------------------------------

class TestFormatCost:
    def test_large_amount(self):
        assert format_cost(14.23) == "$14.23"

    def test_zero(self):
        assert format_cost(0.0) == "$0.0000"

    def test_tiny_amount(self):
        result = format_cost(0.001)
        assert result.startswith("$0.00")

    def test_thousands(self):
        assert format_cost(1234.56) == "$1,234.56"


# ---------------------------------------------------------------------------
# load_sessions (mocked file system)
# ---------------------------------------------------------------------------

class TestLoadSessions:
    def test_returns_list(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        session_data = {
            "pid": 1234,
            "sessionId": "abc-123",
            "cwd": "C:\\Users\\rigwe\\Desktop\\TestProject",
            "startedAt": 1778746933833,
            "version": "2.1.140",
            "entrypoint": "cli",
        }
        (sessions_dir / "1234.json").write_text(json.dumps(session_data), encoding="utf-8")

        with patch("data_parser.get_claude_base_dir", return_value=tmp_path):
            from data_parser import load_sessions
            result = load_sessions()

        assert len(result) == 1
        assert result[0]["sessionId"] == "abc-123"
        assert result[0]["entrypoint"] == "cli"

    def test_empty_dir(self, tmp_path):
        (tmp_path / "sessions").mkdir()
        with patch("data_parser.get_claude_base_dir", return_value=tmp_path):
            from data_parser import load_sessions
            result = load_sessions()
        assert result == []

    def test_missing_sessions_dir(self, tmp_path):
        with patch("data_parser.get_claude_base_dir", return_value=tmp_path):
            from data_parser import load_sessions
            result = load_sessions()
        assert result == []
