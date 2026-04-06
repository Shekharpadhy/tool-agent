"""
FastAPI web server for Tool Agent.

Endpoints:
  GET  /              → single-page UI
  GET  /run           → SSE stream: runs the agent and streams logs + results
  GET  /download/{f}  → download a file from data/outputs/
"""

import asyncio
import json
import logging
import os
import queue
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from src.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

from src.agent.react_agent import ReactAgent
from src.agent.memory import Memory
from src.agent.response_formatter import ResponseFormatter
from src.tools.search import search
from src.tools.files import file_write
from src.tools.calendar import calendar_create

# ── paths ──────────────────────────────────────────────────────────────────────

_ROOT       = Path(__file__).parent.parent.parent
STATIC_DIR  = Path(__file__).parent / "static"
OUTPUTS_DIR = _ROOT / "data" / "outputs"
MEMORY_PATH = _ROOT / "data" / "memory.json"

TOOLS = {
    "search":          search,
    "file_write":      file_write,
    "calendar_create": calendar_create,
}

# ── app ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Tool Agent", docs_url=None, redoc_url=None)


# ── log capture ────────────────────────────────────────────────────────────────

class _QueueHandler(logging.Handler):
    """
    Captures log records from src.* loggers and puts them into a Queue
    so the SSE stream can forward them to the browser in real time.
    """

    def __init__(self, q: queue.Queue) -> None:
        super().__init__()
        self.q = q
        self.addFilter(logging.Filter("src"))          # src.* only
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put({
                "type":    "log",
                "level":   record.levelname,
                "message": self.format(record),
            })
        except Exception:
            self.handleError(record)


# ── routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/run")
async def run_agent(goal: str, fresh: bool = False) -> EventSourceResponse:
    """
    Runs the ReAct agent in a background thread and streams every log line
    to the browser via Server-Sent Events.  Final event is type='done' and
    carries the formatted response + list of output files.
    """
    log_queue: queue.Queue = queue.Queue()
    outcome: dict = {"results": None, "error": None}

    handler = _QueueHandler(log_queue)
    logging.getLogger().addHandler(handler)

    def _run() -> None:
        try:
            if fresh and MEMORY_PATH.exists():
                MEMORY_PATH.unlink()

            memory = Memory(memory_path=str(MEMORY_PATH))
            agent  = ReactAgent(tools=TOOLS, memory=memory)
            outcome["results"] = agent.run(goal)
        except Exception as exc:
            logger.error("Agent run failed: %s", exc, exc_info=True)
            outcome["error"] = str(exc)
        finally:
            logging.getLogger().removeHandler(handler)
            log_queue.put(None)   # sentinel → stream is done

    threading.Thread(target=_run, daemon=True).start()

    async def _stream():
        while True:
            try:
                item = log_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue

            if item is None:                          # sentinel
                if outcome["error"]:
                    yield {"data": json.dumps({"type": "error", "message": outcome["error"]})}
                else:
                    results  = outcome["results"] or []
                    response = ResponseFormatter.format(results)

                    files = []
                    if OUTPUTS_DIR.exists():
                        files = [
                            {"name": f.name, "size": _human_size(f.stat().st_size)}
                            for f in sorted(OUTPUTS_DIR.iterdir(),
                                            key=lambda x: x.stat().st_mtime,
                                            reverse=True)[:10]
                            if f.is_file()
                        ]

                    yield {"data": json.dumps({"type": "done", "response": response, "files": files})}
                break

            yield {"data": json.dumps(item)}

    return EventSourceResponse(_stream())


@app.get("/download/{filename}")
async def download_file(filename: str) -> FileResponse:
    safe = Path(filename).name          # strip any directory traversal
    path = OUTPUTS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(path), filename=safe)


# ── helpers ────────────────────────────────────────────────────────────────────

def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} MB"
