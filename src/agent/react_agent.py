"""
ReAct (Reason + Act) agent.

Unlike the linear Planner → Executor pipeline, this agent runs a loop:

    Thought → Action → Observation → Thought → Action → ... → FINISH

The LLM sees the full conversation history at every step, so each decision
is grounded in what the previous tool actually returned. This is how
production agent systems (LangGraph, AutoGen, CrewAI) work under the hood.
"""

import json
import os
import re
from typing import Any, Dict, List

import requests

from src.agent.error_handler import with_retry
from src.agent.memory import Memory
from src.logger import get_logger

logger = get_logger(__name__)

# LLM context budget for a single observation — long search results are
# truncated here before being appended to the message history.
_MAX_OBSERVATION_CHARS = 2_000

SYSTEM_PROMPT = """You are an autonomous AI agent. You reason step by step and use tools to complete a goal.

Available tools:
- search(query: str) — Search the web for current information
- file_write(filename: str, content: str) — Save text content to a file
- calendar_create(date: str, time: str, title: str) — Schedule a calendar event

At each step, output a single JSON object — nothing else, no markdown.

To call a tool:
{"thought": "<your reasoning>", "action": "<tool_name>", "input": {<tool parameters as key/value pairs>}}

When the goal is fully complete:
{"thought": "<your reasoning>", "action": "FINISH", "input": {"summary": "<what you accomplished>"}}

Rules:
1. Output ONLY valid JSON. No extra text, no code fences.
2. Ground each decision in the observation from the previous step.
3. Never repeat the same action with the same input twice.
4. When writing a file, use actual content from your observations — no placeholders.
5. Complete the goal in as few steps as needed."""


class ReactAgent:
    """
    Iterative ReAct agent that adapts its plan after each tool call.

    Args:
        tools:          Dict mapping tool name → callable.
        memory:         Persistent memory for recording completed steps.
        max_iterations: Safety limit on the number of Thought/Act cycles.
    """

    def __init__(self, tools: dict, memory: Memory, max_iterations: int = 6):
        self.tools = tools
        self.memory = memory
        self.max_iterations = max_iterations
        self.backend = os.getenv("LLM_BACKEND", "ollama").lower()

        if self.backend == "openai":
            self._init_openai()
        else:
            self._init_ollama()

    # ── initialisation ─────────────────────────────────────────────────────────

    def _init_ollama(self) -> None:
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
        logger.info("ReAct backend: Ollama (%s @ %s)", self.model, self.ollama_host)

    def _init_openai(self) -> None:
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        logger.info("ReAct backend: OpenAI (%s)", self.model)

    # ── main loop ──────────────────────────────────────────────────────────────

    def run(self, goal: str) -> List[Dict]:
        """
        Run the ReAct loop until the agent decides the goal is complete
        or max_iterations is reached.

        Returns a list of step dicts compatible with ResponseFormatter.
        """
        logger.info("ReAct loop started — goal: %s", goal)

        messages: List[Dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Goal: {goal}"},
        ]
        results: List[Dict] = []
        step_id = 1

        for iteration in range(1, self.max_iterations + 1):
            logger.info("── Iteration %d/%d ──", iteration, self.max_iterations)

            raw = self._call_llm(messages)

            try:
                step = self._parse_step(raw)
            except ValueError as exc:
                logger.error("Could not parse LLM response: %s", exc)
                break

            thought = step.get("thought", "")
            action  = step.get("action", "")
            inputs  = step.get("input", {})

            logger.info("Thought : %s", thought)
            logger.info("Action  : %s  |  Input: %s", action, inputs)

            # ── FINISH ────────────────────────────────────────────────────────
            if action == "FINISH":
                summary = inputs.get("summary", "Goal completed.")
                logger.info("Agent finished: %s", summary)
                results.append({
                    "step_id": step_id,
                    "action":  "Finished",
                    "tool":    "FINISH",
                    "output":  summary,
                })
                break

            # ── Tool call ─────────────────────────────────────────────────────
            observation = self._execute_tool(action, inputs)
            logger.info("Observation: %s", str(observation)[:200])

            self.memory.save_step(step_id, action, observation)
            results.append({
                "step_id": step_id,
                "action":  thought[:80] if thought else action,
                "tool":    action,
                "output":  observation,
            })

            # Append the exchange to history so the LLM has full context
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role":    "user",
                "content": (
                    f"Observation: {self._truncate(observation)}\n\n"
                    "What is your next step? If the goal is fully complete, respond with FINISH."
                ),
            })

            step_id += 1

        else:
            logger.warning("Max iterations (%d) reached without FINISH.", self.max_iterations)

        logger.info("ReAct loop complete — %d step(s)", len(results))
        return results

    # ── tool execution ─────────────────────────────────────────────────────────

    def _execute_tool(self, action: str, inputs: dict) -> Any:
        if action not in self.tools:
            msg = f"Unknown tool '{action}'. Available: {list(self.tools.keys())}"
            logger.warning(msg)
            return msg

        try:
            return with_retry(self.tools[action], kwargs=inputs)
        except Exception as exc:
            error_msg = f"Tool error ({type(exc).__name__}): {exc}"
            logger.error("Tool '%s' failed: %s", action, exc)
            return error_msg

    # ── LLM backends ──────────────────────────────────────────────────────────

    def _call_llm(self, messages: List[Dict]) -> str:
        if self.backend == "openai":
            return self._call_openai(messages)
        return self._call_ollama(messages)

    def _call_ollama(self, messages: List[Dict]) -> str:
        url = f"{self.ollama_host}/api/chat"
        payload = {"model": self.model, "stream": False, "messages": messages}
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.ollama_host}. Is it running?\n"
                f"Start it with: ollama serve"
            )
        return response.json()["message"]["content"]

    def _call_openai(self, messages: List[Dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
        )
        return response.choices[0].message.content

    # ── parsing & utilities ────────────────────────────────────────────────────

    def _parse_step(self, raw: str) -> Dict:
        """
        Extract the JSON step object from the LLM response.
        Handles markdown code fences and leading/trailing text.
        """
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in LLM response:\n{raw}")
        step = json.loads(match.group())
        if "action" not in step:
            raise ValueError(f"Response missing 'action' field:\n{raw}")
        return step

    def _truncate(self, text: str) -> str:
        """Trim long observations before appending to the message history."""
        if len(text) <= _MAX_OBSERVATION_CHARS:
            return text
        return text[:_MAX_OBSERVATION_CHARS] + f"\n... [truncated — {len(text)} chars total]"
