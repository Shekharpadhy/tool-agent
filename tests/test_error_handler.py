"""
Tests for the ErrorHandler — retry logic, backoff behaviour, and error
classification (retryable vs non-retryable).
"""
from unittest.mock import MagicMock, patch

import pytest

from src.agent.error_handler import with_retry, _is_retryable


# ── _is_retryable ─────────────────────────────────────────────────────────────

def test_connection_error_is_retryable():
    assert _is_retryable(ConnectionError("refused")) is True


def test_timeout_error_is_retryable():
    assert _is_retryable(TimeoutError("timed out")) is True


def test_os_error_is_retryable():
    assert _is_retryable(OSError("io error")) is True


def test_ssl_message_is_retryable():
    assert _is_retryable(Exception("SSL handshake failed")) is True


def test_tls_protocol_message_is_retryable():
    assert _is_retryable(Exception("Unsupported protocol version 0x304")) is True


def test_value_error_is_not_retryable():
    assert _is_retryable(ValueError("bad input")) is False


def test_key_error_is_not_retryable():
    assert _is_retryable(KeyError("missing key")) is False


# ── with_retry — success paths ────────────────────────────────────────────────

def test_returns_result_on_first_success():
    fn = MagicMock(return_value="ok")
    result = with_retry(fn, kwargs={"x": 1})
    assert result == "ok"
    fn.assert_called_once_with(x=1)


def test_succeeds_on_second_attempt_after_transient_error():
    fn = MagicMock(side_effect=[ConnectionError("down"), "recovered"])

    with patch("src.agent.error_handler.time.sleep"):
        result = with_retry(fn, max_attempts=3, base_delay=0)

    assert result == "recovered"
    assert fn.call_count == 2


def test_succeeds_on_third_attempt():
    fn = MagicMock(side_effect=[ConnectionError(), ConnectionError(), "final"])

    with patch("src.agent.error_handler.time.sleep"):
        result = with_retry(fn, max_attempts=3, base_delay=0)

    assert result == "final"
    assert fn.call_count == 3


# ── with_retry — failure paths ────────────────────────────────────────────────

def test_raises_immediately_on_non_retryable_error():
    fn = MagicMock(side_effect=ValueError("permanent"))

    with pytest.raises(ValueError, match="permanent"):
        with_retry(fn, max_attempts=3)

    fn.assert_called_once()  # did not retry


def test_raises_after_all_attempts_exhausted():
    fn = MagicMock(side_effect=ConnectionError("always down"))

    with patch("src.agent.error_handler.time.sleep"):
        with pytest.raises(ConnectionError):
            with_retry(fn, max_attempts=3, base_delay=0)

    assert fn.call_count == 3


# ── backoff timing ────────────────────────────────────────────────────────────

def test_sleep_called_with_exponential_backoff():
    fn = MagicMock(side_effect=[ConnectionError(), ConnectionError(), "ok"])
    sleep_calls = []

    with patch("src.agent.error_handler.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        with_retry(fn, max_attempts=3, base_delay=1.0)

    # attempt 1 fails → sleep 1.0s, attempt 2 fails → sleep 2.0s
    assert sleep_calls == [1.0, 2.0]


def test_no_sleep_on_first_attempt_success():
    fn = MagicMock(return_value="immediate")

    with patch("src.agent.error_handler.time.sleep") as mock_sleep:
        with_retry(fn)

    mock_sleep.assert_not_called()
