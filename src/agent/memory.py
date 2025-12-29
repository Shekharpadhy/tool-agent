import json
import os


class Memory:
    """
    Persistent short-term memory for the agent.
    Stores executed steps and their results in a JSON file.
    """

    def __init__(self, memory_path: str = None):
        # Resolve project root dynamically
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        default_path = os.path.join(base_dir, "data", "memory.json")

        self.memory_path = memory_path or default_path

        print(f"[Memory] Using memory file at: {self.memory_path}")

        self._ensure_memory_file()


    def _ensure_memory_file(self):
        """
        Create memory file if it does not exist.
        """
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)

        if not os.path.exists(self.memory_path):
            with open(self.memory_path, "w") as f:
                json.dump({"executed_steps": []}, f, indent=2)

    def load(self) -> dict:
        """
        Load memory from disk.
        """
        with open(self.memory_path, "r") as f:
            return json.load(f)

    def save_step(self, step_id: int, tool: str, output):
        """
        Save a completed step to memory.
        """
        memory = self.load()

        memory["executed_steps"].append({
            "step_id": step_id,
            "tool": tool,
            "output": output
        })

        with open(self.memory_path, "w") as f:
            json.dump(memory, f, indent=2)

    def has_executed(self, step_id: int) -> bool:
        """
        Check if a step was already executed.
        """
        memory = self.load()
        return any(step["step_id"] == step_id for step in memory["executed_steps"])

