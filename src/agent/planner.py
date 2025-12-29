import json
from typing import List, Dict


class Planner:
    """
    Mock Planner

    This planner does NOT call OpenAI.
    It returns a hardcoded plan so the rest of the agent
    (executor, tools, memory) can be built without billing.
    """

    def __init__(self):
        pass

    def create_plan(self, user_goal: str) -> List[Dict]:
        """
        Takes a user goal and returns a fixed structured plan.
        """
        print(f"[MockPlanner] Received goal: {user_goal}")

        plan = [
            {
                "step_id": 1,
                "action": "search_information",
                "tool": "search",
                "input": {
                    "query": "AI trends 2025"
                }
            },
            {
                "step_id": 2,
                "action": "write_summary",
                "tool": "file_write",
                "input": {
                    "filename": "ai_trends.txt"
                }
            },
            {
                "step_id": 3,
                "action": "create_meeting",
                "tool": "calendar_create",
                "input": {
                    "date": "tomorrow",
                    "time": "5pm"
                }
            }
        ]

        # Return as Python object (executor expects this)
        return plan

