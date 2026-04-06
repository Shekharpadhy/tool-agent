"""
Tests for the Executor — variable resolution, step chaining, error handling,
and idempotency (skipping already-executed steps).
"""
import pytest
from unittest.mock import MagicMock, call

from src.agent.executor import Executor


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_executor(tools: dict, executed_step_ids=None):
    memory = MagicMock()
    memory.load.return_value = {
        "executed_steps": [
            {"step_id": sid} for sid in (executed_step_ids or [])
        ]
    }
    return Executor(tools=tools, memory=memory)


SIMPLE_PLAN = [
    {"step_id": 1, "action": "search", "tool": "search", "input": {"query": "AI"}},
    {"step_id": 2, "action": "save", "tool": "file_write", "input": {"filename": "out.txt", "content": "$last_output"}},
]


# ── _resolve_variables ────────────────────────────────────────────────────────

def test_resolve_substitutes_last_output():
    executor = make_executor(tools={})
    context = {"last_output": "real search results"}
    resolved = executor._resolve_variables({"content": "$last_output"}, context)
    assert resolved == {"content": "real search results"}


def test_resolve_substitutes_step_n_output():
    executor = make_executor(tools={})
    context = {"step_1_output": "step one result"}
    resolved = executor._resolve_variables({"data": "$step_1_output"}, context)
    assert resolved == {"data": "step one result"}


def test_resolve_leaves_non_placeholders_unchanged():
    executor = make_executor(tools={})
    resolved = executor._resolve_variables({"filename": "out.txt"}, {})
    assert resolved == {"filename": "out.txt"}


def test_resolve_returns_original_if_variable_not_in_context():
    executor = make_executor(tools={})
    resolved = executor._resolve_variables({"x": "$missing_var"}, {})
    assert resolved == {"x": "$missing_var"}


# ── execute_plan ──────────────────────────────────────────────────────────────

def test_execute_plan_calls_tools_in_order():
    search_fn = MagicMock(return_value="search output")
    write_fn = MagicMock(return_value="file written")
    executor = make_executor(tools={"search": search_fn, "file_write": write_fn})

    results = executor.execute_plan(SIMPLE_PLAN)

    search_fn.assert_called_once_with(query="AI")
    write_fn.assert_called_once_with(filename="out.txt", content="search output")
    assert len(results) == 2


def test_execute_plan_chains_output_via_last_output():
    search_fn = MagicMock(return_value="chained value")
    write_fn = MagicMock(return_value="ok")
    executor = make_executor(tools={"search": search_fn, "file_write": write_fn})

    executor.execute_plan(SIMPLE_PLAN)

    # file_write should receive the search output as content
    write_fn.assert_called_once_with(filename="out.txt", content="chained value")


def test_execute_plan_skips_already_executed_steps():
    search_fn = MagicMock(return_value="result")
    executor = make_executor(
        tools={"search": search_fn},
        executed_step_ids=[1],  # step 1 already done
    )
    plan = [{"step_id": 1, "action": "search", "tool": "search", "input": {"query": "q"}}]

    results = executor.execute_plan(plan)

    search_fn.assert_not_called()
    assert results == []


def test_execute_plan_raises_on_unknown_tool():
    executor = make_executor(tools={})
    plan = [{"step_id": 1, "action": "x", "tool": "nonexistent", "input": {}}]

    with pytest.raises(ValueError, match="Unknown tool 'nonexistent'"):
        executor.execute_plan(plan)


def test_execute_plan_records_tool_error_and_continues():
    broken_fn = MagicMock(side_effect=RuntimeError("tool exploded"))
    next_fn = MagicMock(return_value="next result")
    executor = make_executor(tools={"broken": broken_fn, "next": next_fn})

    plan = [
        {"step_id": 1, "action": "break", "tool": "broken", "input": {}},
        {"step_id": 2, "action": "next", "tool": "next", "input": {}},
    ]
    results = executor.execute_plan(plan)

    assert "Tool error" in results[0]["output"] or "tool exploded" in results[0]["output"]
    assert results[1]["output"] == "next result"


def test_execute_plan_saves_each_step_to_memory():
    tool_fn = MagicMock(return_value="output")
    memory = MagicMock()
    memory.load.return_value = {"executed_steps": []}
    executor = Executor(tools={"search": tool_fn}, memory=memory)

    plan = [{"step_id": 1, "action": "s", "tool": "search", "input": {"query": "q"}}]
    executor.execute_plan(plan)

    memory.save_step.assert_called_once_with(1, "search", "output")
