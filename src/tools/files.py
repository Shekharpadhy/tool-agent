def file_write(filename: str, content: str = "AI trends summary") -> str:
    """
    Mock file writing tool.
    """
    print(f"[File Tool] Writing to file: {filename}")

    with open(filename, "w") as f:
        f.write(content)

    return f"File '{filename}' written successfully."

