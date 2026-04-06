import argparse
import os
import sys

from dotenv import load_dotenv

# Load .env before any other imports so env vars are available to all modules
load_dotenv()

from src.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

from src.agent.react_agent import ReactAgent
from src.agent.planner import Planner
from src.agent.executor import Executor
from src.agent.memory import Memory
from src.agent.response_formatter import ResponseFormatter

from src.tools.search import search
from src.tools.files import file_write
from src.tools.calendar import calendar_create

TOOLS = {
    "search": search,
    "file_write": file_write,
    "calendar_create": calendar_create,
}


def _memory_path() -> str:
    return os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        "data",
        "memory.json",
    )


def run_react(goal: str, fresh: bool = False) -> None:
    """Run the ReAct (Reason + Act) agent — adapts plan based on observations."""
    path = _memory_path()
    if fresh and os.path.exists(path):
        os.remove(path)
        logger.info("Memory cleared — starting fresh")

    memory = Memory(memory_path=path)
    agent = ReactAgent(tools=TOOLS, memory=memory)
    results = agent.run(goal)

    response = ResponseFormatter.format(results)
    print("─" * 60)
    print(response)
    print("─" * 60)


def run_pipeline(goal: str, fresh: bool = False) -> None:
    """Run the linear Planner → Executor pipeline."""
    path = _memory_path()
    if fresh and os.path.exists(path):
        os.remove(path)
        logger.info("Memory cleared — starting fresh")

    planner = Planner()
    plan = planner.create_plan(goal)

    logger.info("Generated plan:")
    for step in plan:
        logger.info("  %s. [%s] %s", step["step_id"], step["tool"], step["action"])

    memory = Memory(memory_path=path)
    executor = Executor(tools=TOOLS, memory=memory)
    results = executor.execute_plan(plan)

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
        help="Clear memory before running.",
    )
    parser.add_argument(
        "--mode",
        choices=["react", "pipeline"],
        default="react",
        help="react (default): iterative ReAct loop. pipeline: linear plan+execute.",
    )
    args = parser.parse_args()

    try:
        if args.mode == "pipeline":
            run_pipeline(goal=args.goal, fresh=args.fresh)
        else:
            run_react(goal=args.goal, fresh=args.fresh)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
