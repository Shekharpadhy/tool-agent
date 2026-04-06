from src.logger import get_logger
from .error_handler import with_retry
from .memory import Memory

logger = get_logger(__name__)


class Executor:
    """
    Executes a plan step by step, passing results between steps and
    recording everything in persistent memory.

    Variable resolution:
      If a tool input value is the string "$last_output", the executor
      substitutes it with the output of the most recently completed step.
      This lets the planner chain steps without knowing the results upfront.

      Example plan step:
        {"tool": "file_write", "input": {"filename": "out.txt", "content": "$last_output"}}

    Error handling:
      Each tool call is wrapped in with_retry(), which retries transient
      errors (network, TLS) up to 3 times with exponential backoff.
      Non-retryable errors are caught and recorded as the step output so
      the remaining steps can still execute.
    """

    def __init__(self, tools: dict, memory: Memory):
        self.tools = tools
        self.memory = memory

        stored = self.memory.load()
        self.executed_step_ids = {
            step["step_id"] for step in stored.get("executed_steps", [])
        }

    def execute_plan(self, plan: list) -> list:
        results = []
        context: dict = {}

        logger.info("Starting plan execution (%d step(s))", len(plan))

        for step in plan:
            step_id = step.get("step_id")
            tool_name = step.get("tool")
            raw_input = step.get("input", {})
            action = step.get("action", tool_name)

            if step_id in self.executed_step_ids:
                logger.info("Step %s skipped (already in memory)", step_id)
                continue

            if tool_name not in self.tools:
                raise ValueError(
                    f"Unknown tool '{tool_name}'. "
                    f"Available: {list(self.tools.keys())}"
                )

            resolved_input = self._resolve_variables(raw_input, context)
            logger.info("Step %s — %s", step_id, action)
            logger.debug("Input: %s", resolved_input)

            tool_fn = self.tools[tool_name]
            try:
                output = with_retry(tool_fn, kwargs=resolved_input)
            except Exception as exc:
                output = f"[Tool error] {type(exc).__name__}: {exc}"
                logger.error("Step %s failed after all retries: %s", step_id, exc)

            context["last_output"] = output
            context[f"step_{step_id}_output"] = output

            self.memory.save_step(step_id, tool_name, output)
            self.executed_step_ids.add(step_id)

            results.append({
                "step_id": step_id,
                "action": action,
                "tool": tool_name,
                "output": output,
            })

        logger.info("All steps complete")
        return results

    def _resolve_variables(self, input_dict: dict, context: dict) -> dict:
        """Replace placeholder strings (e.g. '$last_output') with real values."""
        resolved = {}
        for key, value in input_dict.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]
                resolved[key] = context.get(var_name, value)
            else:
                resolved[key] = value
        return resolved
