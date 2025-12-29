class ResponseFormatter:
    """
    Converts raw execution results into human-friendly responses.
    """

    @staticmethod
    def format(results: list) -> str:
        if not results:
            return "I didn’t need to do anything because everything was already completed earlier."

        lines = ["Here’s what I did for you:"]

        for result in results:
            tool = result.get("tool")
            output = result.get("output")

            if tool == "search":
                lines.append("• I researched the latest AI trends.")
            elif tool == "file_write":
                lines.append("• I saved a summary to a file for you.")
            elif tool == "calendar_create":
                lines.append("• I scheduled your meeting as requested.")
            else:
                lines.append(f"• I completed an action using {tool}.")

        return "\n".join(lines)

