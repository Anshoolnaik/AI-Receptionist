"""Complaint workflow — logs complaint event and escalates to staff."""
import asyncio
from app.queue.tasks import EventLogTask


async def handle(
    message: dict, confidence: float, property_cfg: dict, queue: asyncio.Queue
) -> tuple[str, str]:
    await queue.put(EventLogTask(
        property_id=message["property_id"],
        message_id=message["message_id"],
        event_type="complaint_logged",
        payload={"text": message["text"], "confidence": confidence},
    ))
    reply = (
        "Aapki complaint log kar li gayi hai. "
        "Humara staff jald aapse contact karega. "
        "(Your complaint has been logged. Our staff will contact you shortly.)"
    )
    return ("processed", reply)
