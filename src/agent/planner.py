import json
import os
import re
import requests
from typing import List, Dict

from src.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a task planning AI. Given a user goal, decompose it into a sequence of concrete steps using the available tools.

Available tools:
- search(query: str) — Search the web for information. Use this to look up facts, research topics, or find current information.
- file_write(filename: str, content: str) — Write text content to a file in the outputs directory.
- calendar_create(date: str, time: str, title: str) — Schedule a calendar event.

Rules:
1. Use only the tools listed above.
2. If a step needs the output of a previous step, set that field's value to "$last_output".
3. Keep the plan focused — 1 to 4 steps maximum.
4. Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Each step must follow this exact shape:
{"step_id": <int>, "action": "<short description>", "tool": "<tool_name>", "input": {<tool parameters>}}

Example for "Research Python and save a summary":
[
  {"step_id": 1, "action": "search for Python overview", "tool": "search", "input": {"query": "Python programming language overview 2025"}},
  {"step_id": 2, "action": "save summary to file", "tool": "file_write", "input": {"filename": "python_summary.txt", "content": "$last_output"}}
]"""


class Planner:
    """
    LLM-powered planner. Decomposes a user goal into a structured execution plan.

    Supports two backends (set via LLM_BACKEND env var):
      - "ollama"  → local model via Ollama (default, free)
      - "openai"  → OpenAI API (requires OPENAI_API_KEY)
    """

    def __init__(self):
        self.backend = os.getenv("LLM_BACKEND", "ollama").lower()

        if self.backend == "openai":
            self._init_openai()
        else:
            self._init_ollama()

    def _init_ollama(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
        logger.info("Backend: Ollama (%s @ %s)", self.model, self.ollama_host)

    def _init_openai(self):
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it to your .env file."
            )
        self.client = openai.OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        logger.info("Backend: OpenAI (%s)", self.model)

    def create_plan(self, user_goal: str) -> List[Dict]:
        """Decompose a user goal into an ordered list of tool-calling steps."""
        logger.info("Goal: %s", user_goal)
        logger.info("Generating plan via %s...", self.backend)

        if self.backend == "openai":
            raw = self._call_openai(user_goal)
        else:
            raw = self._call_ollama(user_goal)

        plan = self._parse_plan(raw)
        logger.info("Plan ready — %d step(s)", len(plan))
        return plan

    # ── LLM backends ──────────────────────────────────────────────────────────

    def _call_ollama(self, goal: str) -> str:
        url = f"{self.ollama_host}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"User goal: {goal}"},
            ],
        }
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.ollama_host}.\n"
                "Make sure Ollama is running: https://ollama.com\n"
                f"Then pull your model: ollama pull {self.model}"
            )
        return response.json()["message"]["content"]

    def _call_openai(self, goal: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"User goal: {goal}"},
            ],
            temperature=0,
        )
        return response.choices[0].message.content

    # ── JSON parsing ───────────────────────────────────────────────────────────

    def _parse_plan(self, raw: str) -> List[Dict]:
        """
        Extract and validate the JSON plan from the LLM response.
        LLMs sometimes wrap JSON in markdown fences — this handles that.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()

        # Find the first JSON array in the response
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            raise ValueError(
                f"Planner returned no valid JSON array.\nRaw response:\n{raw}"
            )

        plan = json.loads(match.group())

        if not isinstance(plan, list) or len(plan) == 0:
            raise ValueError("Planner returned an empty plan.")

        for step in plan:
            for field in ("step_id", "action", "tool", "input"):
                if field not in step:
                    raise ValueError(f"Step is missing field '{field}': {step}")

        return plan
