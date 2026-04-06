"""
Retry logic with exponential backoff for transient tool failures.

Usage:
    from .error_handler import with_retry

    output = with_retry(tool_fn, kwargs={"query": "AI trends"})
"""

import time
from typing import Any, Callable

from src.logger import get_logger

logger = get_logger(__name__)

# How many times to attempt a tool call before giving up
DEFAULT_MAX_ATTEMPTS = 3

# Starting delay in seconds; doubles each attempt (1s → 2s → 4s)
DEFAULT_BASE_DELAY = 1.0


def with_retry(
    fn: Callable,
    kwargs: dict = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
) -> Any:
    """
    Call fn(**kwargs) with automatic retry on transient errors.

    - Retries up to max_attempts times.
    - Waits base_delay * 2^(attempt-1) seconds between attempts.
    - Only retries errors that are likely transient (network, TLS, I/O).
    - Raises the last exception if all attempts fail.
    """
    kwargs = kwargs or {}
    last_error: Exception = RuntimeError("No attempts made")

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(**kwargs)
        except Exception as exc:
            last_error = exc

            if not _is_retryable(exc):
                logger.debug("Non-retryable error — raising immediately: %s", exc)
                raise

            if attempt == max_attempts:
                logger.error(
                    "All %d attempts failed. Last error: %s", max_attempts, exc
                )
                raise

            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %d/%d failed (%s: %s). Retrying in %.1fs...",
                attempt,
                max_attempts,
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)

    raise last_error  # unreachable, but satisfies type checkers


def _is_retryable(exc: Exception) -> bool:
    """
    Return True if the exception looks like a transient failure worth retrying.

    Covers:
      - Standard network/IO exceptions
      - TLS/SSL protocol errors (e.g. macOS LibreSSL issues with ddgs)
      - HTTP 429 / 503 style messages
    """
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    msg = str(exc).lower()
    transient_keywords = ("ssl", "tls", "protocol", "timeout", "connection", "network")
    return any(keyword in msg for keyword in transient_keywords)
