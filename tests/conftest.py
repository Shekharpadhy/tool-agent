"""
Shared pytest configuration and fixtures.
"""
import logging

import pytest

# Suppress log output during tests for cleaner pytest output.
# Individual tests can re-enable logging if they want to assert on it.
logging.disable(logging.CRITICAL)


@pytest.fixture
def mock_memory():
    """A Memory object whose file operations are fully mocked out."""
    from unittest.mock import MagicMock

    memory = MagicMock()
    memory.load.return_value = {"executed_steps": []}
    return memory
