from .memory import Memory


class Executor:
    """
    Executor executes a plan step by step and records results in memory.
    """

    def __init__(self, tools: dict, memory: Memory):
        self.tools = tools
        self.memory = memory

        # Load memory ONCE and cache executed step IDs
        stored_memory = self.memory.load()
        self.executed_step_ids = {
            step["step_id"] for step in stored_memory.get("executed_steps", [])
        }

    def execute_plan(self, plan: list) -> list:
        results = []

        print("\n[Executor] Starting plan execution...\n")

        for step in plan:
            step_id = step.get("step_id")
            tool_name = step.get("tool")
            tool_input = step.get("input", {})

            # Skip already executed steps
            if step_id in self.executed_step_ids:
                print(f"[Executor] Skipping step {step_id} (already executed)")
                continue

            print(f"[Executor] Executing step {step_id} using tool '{tool_name}'")

            if tool_name not in self.tools:
                raise ValueError(f"Tool '{tool_name}' not found")

            tool_function = self.tools[tool_name]

            output = tool_function(**tool_input)

            # Save to memory
            self.memory.save_step(step_id, tool_name, output)
            self.executed_step_ids.add(step_id)

            results.append({
                "step_id": step_id,
                "tool": tool_name,
                "output": output
            })

        print("\n[Executor] Plan execution completed.\n")
        return results

