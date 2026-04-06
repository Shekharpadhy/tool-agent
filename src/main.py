import argparse
import os
import sys

from dotenv import load_dotenv

# Load .env before any other imports so env vars are available to all modules
load_dotenv()

from src.logger import setup_logging, get_logger

# Configure logging before importing anything else that uses loggers
setup_logging()
logger = get_logger(__name__)

from src.agent.planner import Planner
from src.agent.executor import Executor
from src.agent.memory import Memory
from src.agent.response_formatter import ResponseFormatter

from src.tools.search import search
from src.tools.files import file_write
from src.tools.calendar import calendar_create


def run(goal: str, fresh: bool = False) -> None:
    memory_path = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        "data",
        "memory.json",
    )

    if fresh and os.path.exists(memory_path):
        os.remove(memory_path)
        logger.info("Memory cleared — starting fresh")

    # ── Plan ──────────────────────────────────────────────────────────────────
    planner = Planner()
    plan = planner.create_plan(goal)

    logger.info("Generated plan:")
    for step in plan:
        logger.info("  %s. [%s] %s", step["step_id"], step["tool"], step["action"])

    # ── Execute ───────────────────────────────────────────────────────────────
    memory = Memory(memory_path=memory_path)

    tools = {
        "search": search,
        "file_write": file_write,
        "calendar_create": calendar_create,
    }

    executor = Executor(tools=tools, memory=memory)
    results = executor.execute_plan(plan)

    # ── Respond ───────────────────────────────────────────────────────────────
    response = ResponseFormatter.format(results)
    print("─" * 60)
    print(response)
    print("─" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tool Agent — an autonomous AI agent that plans and executes tasks."
    )
    parser.add_argument(
        "goal",
        nargs="?",
        default="Research the latest AI agent frameworks and save a summary",
        help="The goal you want the agent to accomplish.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear memory before running (re-executes all steps).",
    )
    args = parser.parse_args()

    try:
        run(goal=args.goal, fresh=args.fresh)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
