"""Wake-up call workflow."""
import asyncio
import re
from app.queue.tasks import EventLogTask


def _extract_time(text: str) -> str | None:
    m = re.search(r"\b(\d{1,2}(?::\d{2})?)\s*(am|pm)?\b", text.lower())
    if m:
        return m.group(0).strip()
    return None


async def handle(
    message: dict, confidence: float, property_cfg: dict, queue: asyncio.Queue
) -> tuple[str, str]:
    wake_time = _extract_time(message["text"]) or "requested time"
    await queue.put(EventLogTask(
        property_id=message["property_id"],
        message_id=message["message_id"],
        event_type="wakeup_scheduled",
        payload={"time": wake_time, "guest_id": message["guest_id"]},
    ))
    reply = (
        f"Wake-up call {wake_time} ke liye schedule kar diya gaya hai. "
        f"(Wake-up call scheduled for {wake_time}.)"
    )
    return ("processed", reply)
