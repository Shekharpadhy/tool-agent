"""
Calendar tool — writes a valid .ics file to data/outputs/.

The .ics format is understood by Apple Calendar, Google Calendar,
Outlook, and any other RFC 5545-compliant calendar app.
"""

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from src.logger import get_logger

logger = get_logger(__name__)

OUTPUTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "outputs"
)


def calendar_create(date: str, time: str, title: str = "Meeting") -> str:
    """
    Create a calendar event and save it as a .ics file.

    Args:
        date:  Event date in YYYY-MM-DD format  (e.g. "2026-04-10")
        time:  Event time in HH:MM  24-hour format (e.g. "14:30")
        title: Event title / summary

    Returns:
        A confirmation string with the path to the saved .ics file.
    """
    logger.info("Creating calendar event '%s' on %s at %s", title, date, time)

    # Parse and validate date/time
    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        msg = (
            f"Invalid date/time format. Expected date='YYYY-MM-DD' and "
            f"time='HH:MM', got date='{date}' time='{time}'."
        )
        logger.error(msg)
        return msg

    end_dt = start_dt + timedelta(hours=1)

    # Format timestamps for iCal (UTC-style local stamp)
    fmt = "%Y%m%dT%H%M%S"
    now_stamp = datetime.utcnow().strftime(fmt) + "Z"
    start_stamp = start_dt.strftime(fmt)
    end_stamp = end_dt.strftime(fmt)

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Tool Agent//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uuid.uuid4()}@tool-agent\r\n"
        f"DTSTAMP:{now_stamp}\r\n"
        f"DTSTART:{start_stamp}\r\n"
        f"DTEND:{end_stamp}\r\n"
        f"SUMMARY:{title}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    # Write to outputs directory
    outputs_path = Path(OUTPUTS_DIR)
    outputs_path.mkdir(parents=True, exist_ok=True)

    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"{date}_{safe_title.replace(' ', '_')}.ics"
    file_path = outputs_path / filename

    file_path.write_text(ics_content, encoding="utf-8")
    logger.info("Calendar event saved to %s", file_path)

    return (
        f"Event '{title}' scheduled on {date} at {time}. "
        f"Saved as '{filename}' — open it to import into any calendar app."
    )
