import json
import os
from typing import Any

from filelock import FileLock

from src.logger import get_logger

logger = get_logger(__name__)


class Memory:
    """
    Persistent short-term memory for the agent.

    Stores executed steps and their results in a JSON file.
    All reads and writes are protected by a file lock so concurrent
    processes (e.g. multiple agent instances) cannot corrupt the state.
    """

    def __init__(self, memory_path: str = None):
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        default_path = os.path.join(base_dir, "data", "memory.json")
        self.memory_path = memory_path or default_path
        self._lock = FileLock(self.memory_path + ".lock")

        logger.debug("Memory file: %s", self.memory_path)
        self._ensure_memory_file()

    def _ensure_memory_file(self) -> None:
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        with self._lock:
            if not os.path.exists(self.memory_path):
                self._write({"executed_steps": []})
                logger.debug("Created new memory file")

    def load(self) -> dict:
        with self._lock:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def save_step(self, step_id: int, tool: str, output: Any) -> None:
        with self._lock:
            data = self._read()
            data["executed_steps"].append({
                "step_id": step_id,
                "tool": tool,
                "output": output,
            })
            self._write(data)
        logger.debug("Saved step %s (%s) to memory", step_id, tool)

    def has_executed(self, step_id: int) -> bool:
        data = self.load()
        return any(s["step_id"] == step_id for s in data["executed_steps"])

    # ── private helpers ───────────────────────────────────────────────────────

    def _read(self) -> dict:
        """Read without acquiring the lock (caller must hold it)."""
        with open(self.memory_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        """Write without acquiring the lock (caller must hold it)."""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
