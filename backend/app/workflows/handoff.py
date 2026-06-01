"""Human-handoff workflow — used when confidence < threshold."""
import asyncio
from app.queue.tasks import EventLogTask


async def handle(message: dict, property_cfg: dict, queue: asyncio.Queue) -> tuple[str, str]:
    await queue.put(EventLogTask(
        property_id=message["property_id"],
        message_id=message["message_id"],
        event_type="handoff_escalated",
        payload={"reason": "low_confidence", "text": message["text"]},
    ))
    reply = (
        "Aapka message humne receive kar liya. "
        "Ek staff member jald aapse connect karega. "
        "(Your message has been received and a staff member will connect with you shortly.)"
    )
    return ("needs_human", reply)
