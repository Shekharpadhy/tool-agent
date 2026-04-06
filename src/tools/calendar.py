from src.logger import get_logger

logger = get_logger(__name__)


def calendar_create(date: str, time: str, title: str = "Meeting") -> str:
    """
    Simulates scheduling a calendar event.
    (Replace with a real calendar API integration in a future phase.)
    """
    logger.info("Scheduling '%s' on %s at %s", title, date, time)
    return f"Event '{title}' scheduled on {date} at {time}."

