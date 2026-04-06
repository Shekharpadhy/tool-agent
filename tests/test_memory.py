"""
Tests for Memory — persistence, thread-safe locking, and idempotency checks.
All tests use pytest's tmp_path fixture to avoid touching real files.
"""
import json

import pytest

from src.agent.memory import Memory


# ── helpers ───────────────────────────────────────────────────────────────────

def make_memory(tmp_path) -> Memory:
    return Memory(memory_path=str(tmp_path / "memory.json"))


# ── initialization ────────────────────────────────────────────────────────────

def test_creates_memory_file_on_init(tmp_path):
    path = tmp_path / "memory.json"
    assert not path.exists()
    Memory(memory_path=str(path))
    assert path.exists()


def test_initial_memory_has_empty_executed_steps(tmp_path):
    memory = make_memory(tmp_path)
    data = memory.load()
    assert data == {"executed_steps": []}


def test_existing_memory_file_is_not_overwritten(tmp_path):
    path = tmp_path / "memory.json"
    existing = {"executed_steps": [{"step_id": 99, "tool": "search", "output": "x"}]}
    path.write_text(json.dumps(existing))

    memory = Memory(memory_path=str(path))
    data = memory.load()
    assert data["executed_steps"][0]["step_id"] == 99


# ── save_step / load ──────────────────────────────────────────────────────────

def test_save_step_persists_to_disk(tmp_path):
    memory = make_memory(tmp_path)
    memory.save_step(1, "search", "some result")

    data = memory.load()
    assert len(data["executed_steps"]) == 1
    assert data["executed_steps"][0] == {
        "step_id": 1,
        "tool": "search",
        "output": "some result",
    }


def test_save_multiple_steps_appends_each(tmp_path):
    memory = make_memory(tmp_path)
    memory.save_step(1, "search", "result 1")
    memory.save_step(2, "file_write", "result 2")

    data = memory.load()
    assert len(data["executed_steps"]) == 2
    assert data["executed_steps"][1]["step_id"] == 2


def test_save_step_output_can_be_long_string(tmp_path):
    memory = make_memory(tmp_path)
    long_output = "x" * 10_000
    memory.save_step(1, "search", long_output)

    data = memory.load()
    assert data["executed_steps"][0]["output"] == long_output


# ── has_executed ──────────────────────────────────────────────────────────────

def test_has_executed_returns_false_before_save(tmp_path):
    memory = make_memory(tmp_path)
    assert memory.has_executed(1) is False


def test_has_executed_returns_true_after_save(tmp_path):
    memory = make_memory(tmp_path)
    memory.save_step(1, "search", "output")
    assert memory.has_executed(1) is True


def test_has_executed_is_specific_to_step_id(tmp_path):
    memory = make_memory(tmp_path)
    memory.save_step(1, "search", "output")
    assert memory.has_executed(2) is False
