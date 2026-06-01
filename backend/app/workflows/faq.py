"""FAQ workflow — answers from property_config custom_faqs."""
import asyncio
from app.queue.tasks import EventLogTask


async def handle(
    message: dict, confidence: float, property_cfg: dict, queue: asyncio.Queue
) -> tuple[str, str]:
    text_lower = message["text"].lower()
    custom_faqs = property_cfg.get("custom_faqs", [])

    reply = None
    for faq in custom_faqs:
        if any(word in text_lower for word in faq["q"].lower().split()):
            reply = faq["a"]
            break

    if reply is None:
        reply = "Yeh information abhi available nahi hai. Staff se contact karein. (Please contact staff for this information.)"

    await queue.put(EventLogTask(
        property_id=message["property_id"],
        message_id=message["message_id"],
        event_type="faq_answered",
        payload={"text": message["text"], "reply": reply},
    ))
    return ("processed", reply)
