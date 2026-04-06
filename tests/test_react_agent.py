"""
Tests for the ReactAgent — loop control, tool dispatch, JSON parsing,
and error recovery. All LLM and tool calls are mocked.
"""
import json
from unittest.mock import MagicMock, patch, call

import pytest

from src.agent.react_agent import ReactAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_agent(tools=None):
    memory = MagicMock()
    memory.load.return_value = {"executed_steps": []}
    return ReactAgent(
        tools=tools or {},
        memory=memory,
        max_iterations=5,
    )


def llm_response(thought: str, action: str, inputs: dict) -> str:
    """Build a fake LLM JSON response."""
    return json.dumps({"thought": thought, "action": action, "input": inputs})


# ── _parse_step ───────────────────────────────────────────────────────────────

def test_parse_step_valid_json():
    agent = make_agent()
    raw = json.dumps({"thought": "search now", "action": "search", "input": {"query": "AI"}})
    step = agent._parse_step(raw)
    assert step["action"] == "search"
    assert step["input"]["query"] == "AI"


def test_parse_step_strips_markdown_fence():
    agent = make_agent()
    raw = '```json\n{"thought": "ok", "action": "FINISH", "input": {"summary": "done"}}\n```'
    step = agent._parse_step(raw)
    assert step["action"] == "FINISH"


def test_parse_step_raises_when_no_json():
    agent = make_agent()
    with pytest.raises(ValueError, match="No JSON object found"):
        agent._parse_step("Here is my answer: I will search for things.")


def test_parse_step_raises_when_action_missing():
    agent = make_agent()
    with pytest.raises(ValueError, match="missing 'action'"):
        agent._parse_step(json.dumps({"thought": "hmm", "input": {}}))


# ── _truncate ─────────────────────────────────────────────────────────────────

def test_truncate_short_text_unchanged():
    agent = make_agent()
    assert agent._truncate("short text") == "short text"


def test_truncate_long_text_is_cut():
    agent = make_agent()
    long = "x" * 5_000
    result = agent._truncate(long)
    assert len(result) < len(long)
    assert "truncated" in result


# ── run — happy path ──────────────────────────────────────────────────────────

def test_run_executes_tool_and_finishes():
    search_fn = MagicMock(return_value="search results")
    agent = make_agent(tools={"search": search_fn})

    responses = [
        llm_response("I should search", "search", {"query": "AI trends"}),
        llm_response("Done", "FINISH", {"summary": "Found AI trends"}),
    ]

    with patch.object(agent, "_call_llm", side_effect=responses):
        results = agent.run("Research AI trends")

    search_fn.assert_called_once_with(query="AI trends")
    assert results[-1]["tool"] == "FINISH"
    assert "Found AI trends" in results[-1]["output"]


def test_run_chains_observation_into_next_llm_call():
    search_fn = MagicMock(return_value="actual results")
    write_fn = MagicMock(return_value="file written")
    agent = make_agent(tools={"search": search_fn, "file_write": write_fn})

    responses = [
        llm_response("search first", "search", {"query": "AI"}),
        llm_response("now save", "file_write", {"filename": "out.txt", "content": "actual results"}),
        llm_response("done", "FINISH", {"summary": "saved"}),
    ]

    with patch.object(agent, "_call_llm", side_effect=responses):
        results = agent.run("Research AI and save")

    # Both tools were called and the final message history (shared reference)
    # contains observations from both steps
    search_fn.assert_called_once_with(query="AI")
    write_fn.assert_called_once_with(filename="out.txt", content="actual results")
    assert results[-1]["tool"] == "FINISH"


def test_run_returns_results_for_each_step():
    agent = make_agent(tools={"search": MagicMock(return_value="results")})
    responses = [
        llm_response("search", "search", {"query": "q"}),
        llm_response("done", "FINISH", {"summary": "complete"}),
    ]

    with patch.object(agent, "_call_llm", side_effect=responses):
        results = agent.run("goal")

    assert len(results) == 2
    assert results[0]["tool"] == "search"
    assert results[1]["tool"] == "FINISH"


# ── run — error handling ──────────────────────────────────────────────────────

def test_run_handles_unknown_tool_gracefully():
    agent = make_agent(tools={})
    responses = [
        llm_response("try nonexistent", "nonexistent_tool", {}),
        llm_response("ok done", "FINISH", {"summary": "gave up"}),
    ]

    with patch.object(agent, "_call_llm", side_effect=responses):
        results = agent.run("do something")

    assert "Unknown tool" in results[0]["output"]
    assert results[1]["tool"] == "FINISH"


def test_run_handles_tool_exception_and_continues():
    broken = MagicMock(side_effect=RuntimeError("exploded"))
    agent = make_agent(tools={"search": broken})
    responses = [
        llm_response("search", "search", {"query": "q"}),
        llm_response("done", "FINISH", {"summary": "finished despite error"}),
    ]

    with patch.object(agent, "_call_llm", side_effect=responses):
        results = agent.run("goal")

    assert "Tool error" in results[0]["output"] or "exploded" in results[0]["output"]
    assert results[-1]["tool"] == "FINISH"


def test_run_stops_at_max_iterations_without_finish():
    agent = make_agent(tools={"search": MagicMock(return_value="ok")}, )
    agent.max_iterations = 3

    never_finish = llm_response("keep searching", "search", {"query": "q"})

    with patch.object(agent, "_call_llm", return_value=never_finish):
        results = agent.run("goal that never finishes")

    assert len(results) == 3
    assert all(r["tool"] == "search" for r in results)


def test_run_saves_each_step_to_memory():
    memory = MagicMock()
    memory.load.return_value = {"executed_steps": []}
    agent = ReactAgent(tools={"search": MagicMock(return_value="r")}, memory=memory, max_iterations=5)

    responses = [
        llm_response("search", "search", {"query": "q"}),
        llm_response("done", "FINISH", {"summary": "x"}),
    ]

    with patch.object(agent, "_call_llm", side_effect=responses):
        agent.run("goal")

    memory.save_step.assert_called_once_with(1, "search", "r")
