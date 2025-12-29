import os

from .agent.planner import Planner
from .agent.executor import Executor
from .agent.memory import Memory
from .agent.response_formatter import ResponseFormatter

from .tools.search import search
from .tools.files import file_write
from .tools.calendar import calendar_create

if __name__ == "__main__":
    # 1. Create planner
    planner = Planner()

    # 2. User goal
    goal = "Research AI trends and schedule a meeting tomorrow at 5pm"

    # 3. Create plan
    plan = planner.create_plan(goal)

    print("\nGenerated Plan:")
    for step in plan:
        print(step)

    # 4. Define memory path (IMPORTANT)
    memory_path = os.path.join(os.getcwd(), "data", "memory.json")

    # 5. Initialize memory (⬅️ THIS LINE GOES HERE)
    memory = Memory(memory_path=memory_path)

    # 6. Register tools
    tools = {
        "search": search,
        "file_write": file_write,
        "calendar_create": calendar_create
    }

    # 7. Create executor (pass memory)
    executor = Executor(tools=tools, memory=memory)

    # 8. Execute plan
    results = executor.execute_plan(plan)

    response = ResponseFormatter.format(results)

    print("\nAssistant Response:\n")
    print(response)

