import os

from src.logger import get_logger

logger = get_logger(__name__)


# All output files are written here, keeping them out of the project root.
OUTPUTS_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "data",
    "outputs",
)


def file_write(filename: str, content: str) -> str:
    """
    Write content to a file inside data/outputs/.

    Returns the absolute path of the file that was written.
    """
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    # Sanitize filename — strip any path separators so callers can't escape the
    # outputs directory.
    safe_name = os.path.basename(filename)
    filepath = os.path.join(OUTPUTS_DIR, safe_name)

    logger.info("Writing to: %s", filepath)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Done — %d characters written", len(content))
    return f"File saved to: {filepath}"
