"""
Search tool with two backends:

  Tavily  (preferred) — set TAVILY_API_KEY. Built for AI agents; returns
                        clean, relevant excerpts. 1,000 free/month.
  DuckDuckGo (fallback) — no API key needed, but results can be noisy.
"""

import os
import time

from src.logger import get_logger

logger = get_logger(__name__)


def search(query: str, max_results: int = 5) -> str:
    """
    Search the web. Uses Tavily if TAVILY_API_KEY is set, otherwise DuckDuckGo.
    """
    if os.getenv("TAVILY_API_KEY"):
        return _tavily_search(query, max_results)
    return _ddgs_search(query, max_results)


# ── Tavily ─────────────────────────────────────────────────────────────────────

def _tavily_search(query: str, max_results: int) -> str:
    from tavily import TavilyClient

    logger.info("Querying Tavily: '%s'", query)
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    response = client.search(query, max_results=max_results)

    results = response.get("results", [])
    if not results:
        logger.warning("No Tavily results for: %s", query)
        return f"No results found for: {query}"

    lines = [f"Search results for '{query}':\n"]
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   {r.get('url', '')}")
        lines.append(f"   {r.get('content', '')}\n")

    logger.info("Tavily returned %d result(s)", len(results))
    return "\n".join(lines)


# ── DuckDuckGo fallback ────────────────────────────────────────────────────────

_DDGS_DELAY = 1.5   # avoid TLS connection-reuse issues on macOS


def _ddgs_search(query: str, max_results: int) -> str:
    from ddgs import DDGS

    logger.info("Querying DuckDuckGo: '%s'", query)
    time.sleep(_DDGS_DELAY)

    results = list(DDGS().text(query, max_results=max_results))
    if not results:
        logger.warning("No DuckDuckGo results for: %s", query)
        return f"No results found for: {query}"

    lines = [f"Search results for '{query}':\n"]
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   {r.get('href', '')}")
        lines.append(f"   {r.get('body', '')}\n")

    logger.info("DuckDuckGo returned %d result(s)", len(results))
    return "\n".join(lines)
