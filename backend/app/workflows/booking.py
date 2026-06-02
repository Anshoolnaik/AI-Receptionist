"""Booking workflow — enqueues BookingCreateTask (side-effect not inline)."""
import asyncio
from app.queue.tasks import BookingCreateTask, EventLogTask
from app.config import CONFIDENCE_THRESHOLD


async def handle(
    message: dict, confidence: float, property_cfg: dict, queue: asyncio.Queue
) -> tuple[str, str]:
    if confidence < CONFIDENCE_THRESHOLD:
        # Handoff — not confident enough to act
        await queue.put(EventLogTask(
            property_id=message["property_id"],
            message_id=message["message_id"],
            event_type="handoff_escalated",
            payload={"reason": "low_confidence_booking", "text": message["text"]},
        ))
        return ("needs_human", "Ek staff member aapko booking mein help karega. / A staff member will assist you with booking.")

    # Enqueue booking creation (processed async by worker)
    await queue.put(BookingCreateTask(
        property_id=message["property_id"],
        message_id=message["message_id"],
        booking_data={
            "booking_id": f"bk_{message['message_id']}",
            "room_type": "standard",
            "checkin": None,
            "checkout": None,
            "status": "pending",
            "amount_inr": 0,
            "source": "direct",
        },
        push_to_ota=True,
    ))
    reply = (
        "Aapki booking request receive ho gayi! "
        "Confirmation thodi der mein aayega. "
        "(Your booking request has been received. Confirmation coming shortly.)"
    )
    return ("processed", reply)
