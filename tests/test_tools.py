"""
Tests for individual tools — file_write and search.
External network calls are mocked so these tests run offline.
"""
import os
from unittest.mock import patch, MagicMock

import pytest

import src.tools.files as files_module
from src.tools.files import file_write
from src.tools.search import search


# ── file_write ────────────────────────────────────────────────────────────────

def test_file_write_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "OUTPUTS_DIR", str(tmp_path))
    file_write("report.txt", "hello world")
    assert (tmp_path / "report.txt").read_text() == "hello world"


def test_file_write_returns_path_string(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "OUTPUTS_DIR", str(tmp_path))
    result = file_write("out.txt", "content")
    assert "out.txt" in result


def test_file_write_overwrites_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "OUTPUTS_DIR", str(tmp_path))
    file_write("out.txt", "first")
    file_write("out.txt", "second")
    assert (tmp_path / "out.txt").read_text() == "second"


def test_file_write_sanitizes_directory_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "OUTPUTS_DIR", str(tmp_path))
    # Caller tries to escape the outputs directory
    file_write("../../etc/passwd", "malicious")
    # File must land inside tmp_path, not outside
    assert (tmp_path / "passwd").exists()
    assert not os.path.exists("/etc/passwd_test")


def test_file_write_creates_outputs_dir_if_missing(tmp_path, monkeypatch):
    outputs = tmp_path / "new_outputs"
    monkeypatch.setattr(files_module, "OUTPUTS_DIR", str(outputs))
    file_write("file.txt", "data")
    assert (outputs / "file.txt").exists()


# ── search ────────────────────────────────────────────────────────────────────

MOCK_RESULTS = [
    {"title": "LangChain Overview", "href": "https://langchain.com", "body": "LangChain is a framework for LLM apps."},
    {"title": "CrewAI Docs",        "href": "https://crewai.com",    "body": "CrewAI enables multi-agent collaboration."},
]


def test_search_returns_formatted_string():
    with patch("src.tools.search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = MOCK_RESULTS
        result = search("AI agent frameworks")

    assert "LangChain Overview" in result
    assert "https://langchain.com" in result
    assert "CrewAI Docs" in result


def test_search_includes_query_in_output():
    with patch("src.tools.search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = MOCK_RESULTS
        result = search("my test query")

    assert "my test query" in result


def test_search_returns_no_results_message_when_empty():
    with patch("src.tools.search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = []
        result = search("obscure query")

    assert "No results found" in result


def test_search_respects_max_results():
    with patch("src.tools.search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = MOCK_RESULTS
        search("query", max_results=3)
        MockDDGS.return_value.text.assert_called_once_with("query", max_results=3)
