"""
Tests for the Planner — focuses on plan parsing logic which is pure Python
and does not require a running LLM.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from src.agent.planner import Planner


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_planner() -> Planner:
    """Create a Planner with Ollama backend without actually pinging Ollama."""
    with patch.dict("os.environ", {"LLM_BACKEND": "ollama"}):
        return Planner()


VALID_PLAN = [
    {"step_id": 1, "action": "search", "tool": "search", "input": {"query": "test"}},
    {"step_id": 2, "action": "save", "tool": "file_write", "input": {"filename": "out.txt", "content": "$last_output"}},
]


# ── _parse_plan ────────────────────────────────────────────────────────────────

def test_parse_plan_returns_list_of_steps():
    planner = make_planner()
    result = planner._parse_plan(json.dumps(VALID_PLAN))
    assert len(result) == 2
    assert result[0]["step_id"] == 1
    assert result[1]["tool"] == "file_write"


def test_parse_plan_strips_markdown_json_fence():
    planner = make_planner()
    raw = f"```json\n{json.dumps(VALID_PLAN)}\n```"
    result = planner._parse_plan(raw)
    assert len(result) == 2


def test_parse_plan_strips_plain_code_fence():
    planner = make_planner()
    raw = f"```\n{json.dumps(VALID_PLAN)}\n```"
    result = planner._parse_plan(raw)
    assert len(result) == 2


def test_parse_plan_tolerates_leading_explanation():
    planner = make_planner()
    raw = f"Sure! Here is the plan:\n{json.dumps(VALID_PLAN)}"
    result = planner._parse_plan(raw)
    assert len(result) == 2


def test_parse_plan_raises_when_no_json_array():
    planner = make_planner()
    with pytest.raises(ValueError, match="no valid JSON array"):
        planner._parse_plan("This is a response with no JSON at all.")


def test_parse_plan_raises_when_plan_is_empty():
    planner = make_planner()
    with pytest.raises(ValueError, match="empty plan"):
        planner._parse_plan("[]")


def test_parse_plan_raises_when_step_missing_field():
    planner = make_planner()
    bad_plan = [{"step_id": 1, "action": "x", "tool": "search"}]  # missing "input"
    with pytest.raises(ValueError, match="missing field 'input'"):
        planner._parse_plan(json.dumps(bad_plan))


# ── create_plan (mocked LLM call) ─────────────────────────────────────────────

def test_create_plan_calls_ollama_and_returns_plan():
    planner = make_planner()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": json.dumps(VALID_PLAN)}
    }

    with patch("src.agent.planner.requests.post", return_value=mock_response):
        plan = planner.create_plan("research AI and save a file")

    assert len(plan) == 2
    assert plan[0]["tool"] == "search"


def test_create_plan_raises_on_ollama_connection_error():
    import requests as req

    planner = make_planner()
    with patch("src.agent.planner.requests.post", side_effect=req.exceptions.ConnectionError):
        with pytest.raises(ConnectionError):
            planner.create_plan("some goal")
