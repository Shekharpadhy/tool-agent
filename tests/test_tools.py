"""
Tests for individual tools — file_write, search, and calendar_create.
External network calls are mocked so these tests run offline.
"""
import os
from unittest.mock import patch, MagicMock

import pytest

import src.tools.files as files_module
import src.tools.calendar as calendar_module
from src.tools.files import file_write
from src.tools.search import search
from src.tools.calendar import calendar_create


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

MOCK_DDG_RESULTS = [
    {"title": "LangChain Overview", "href": "https://langchain.com", "body": "LangChain is a framework for LLM apps."},
    {"title": "CrewAI Docs",        "href": "https://crewai.com",    "body": "CrewAI enables multi-agent collaboration."},
]

MOCK_TAVILY_RESULTS = [
    {"title": "LangChain Overview", "url": "https://langchain.com", "content": "LangChain is a framework for LLM apps."},
    {"title": "CrewAI Docs",        "url": "https://crewai.com",    "content": "CrewAI enables multi-agent collaboration."},
]


# ── DuckDuckGo backend tests (no TAVILY_API_KEY set) ─────────────────────────

def test_search_returns_formatted_string(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch("ddgs.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = MOCK_DDG_RESULTS
        result = search("AI agent frameworks")

    assert "LangChain Overview" in result
    assert "https://langchain.com" in result
    assert "CrewAI Docs" in result


def test_search_includes_query_in_output(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch("ddgs.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = MOCK_DDG_RESULTS
        result = search("my test query")

    assert "my test query" in result


def test_search_returns_no_results_message_when_empty(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch("ddgs.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = []
        result = search("obscure query")

    assert "No results found" in result


def test_search_respects_max_results(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch("ddgs.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = MOCK_DDG_RESULTS
        search("query", max_results=3)
        MockDDGS.return_value.text.assert_called_once_with("query", max_results=3)


# ── Tavily backend tests (TAVILY_API_KEY set) ─────────────────────────────────

def test_search_uses_tavily_when_api_key_set(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    with patch("src.tools.search._tavily_search", return_value="tavily result") as mock_tavily:
        result = search("AI agent frameworks")
    mock_tavily.assert_called_once_with("AI agent frameworks", 5)
    assert result == "tavily result"


def test_tavily_returns_formatted_string(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    with patch("tavily.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = {"results": MOCK_TAVILY_RESULTS}
        result = search("AI agent frameworks")

    assert "LangChain Overview" in result
    assert "https://langchain.com" in result


def test_tavily_no_results(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    with patch("tavily.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = {"results": []}
        result = search("obscure query")

    assert "No results found" in result


# ── calendar_create ───────────────────────────────────────────────────────────

def test_calendar_create_writes_ics_file(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_module, "OUTPUTS_DIR", str(tmp_path))
    result = calendar_create("2026-04-10", "14:30", "Team Sync")
    ics_files = list(tmp_path.glob("*.ics"))
    assert len(ics_files) == 1
    assert "Team Sync" in result


def test_calendar_create_ics_content_is_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_module, "OUTPUTS_DIR", str(tmp_path))
    calendar_create("2026-04-10", "09:00", "Standup")
    ics_file = list(tmp_path.glob("*.ics"))[0]
    content = ics_file.read_text()
    assert "BEGIN:VCALENDAR" in content
    assert "BEGIN:VEVENT" in content
    assert "SUMMARY:Standup" in content
    assert "DTSTART:20260410T090000" in content


def test_calendar_create_returns_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_module, "OUTPUTS_DIR", str(tmp_path))
    result = calendar_create("2026-05-01", "10:00", "Demo Day")
    assert "Demo Day" in result
    assert "2026-05-01" in result
    assert ".ics" in result


def test_calendar_create_invalid_date_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_module, "OUTPUTS_DIR", str(tmp_path))
    result = calendar_create("not-a-date", "25:99", "Bad Event")
    assert "Invalid" in result
    assert not list(tmp_path.glob("*.ics"))
