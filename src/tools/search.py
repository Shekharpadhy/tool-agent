import time

from ddgs import DDGS

from src.logger import get_logger

logger = get_logger(__name__)

# Small delay between searches to avoid TLS connection-reuse issues on macOS
_SEARCH_DELAY = 1.5


def search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo (no API key required).

    Returns a formatted string of the top results including
    title, URL, and a short snippet for each result.
    """
    logger.info("Querying DuckDuckGo: '%s'", query)
    time.sleep(_SEARCH_DELAY)

    results = list(DDGS().text(query, max_results=max_results))

    if not results:
        logger.warning("No results found for: %s", query)
        return f"No results found for: {query}"

    lines = [f"Search results for '{query}':\n"]
    for i, result in enumerate(results, start=1):
        title = result.get("title", "No title")
        url = result.get("href", "")
        snippet = result.get("body", "")
        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        lines.append(f"   {snippet}\n")

    output = "\n".join(lines)
    logger.info("Found %d result(s)", len(results))
    return output
