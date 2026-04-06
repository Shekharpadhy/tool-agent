class ResponseFormatter:
    """
    Converts raw execution results into a human-readable response.
    Output is driven by actual tool results, not hardcoded strings.
    """

    @staticmethod
    def format(results: list) -> str:
        if not results:
            return (
                "Everything was already completed in a previous run.\n"
                "Delete data/memory.json to start fresh."
            )

        lines = ["Here's what I did:\n"]

        for result in results:
            action = result.get("action") or result.get("tool")
            output = result.get("output", "")

            lines.append(f"  [{action}]")

            # Indent the output so it reads as a sub-section
            for line in str(output).splitlines():
                lines.append(f"    {line}")

            lines.append("")  # blank line between steps

        return "\n".join(lines)
