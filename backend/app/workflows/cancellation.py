"""
Cancellation workflow.

CRITICAL GUARD: If confidence < CONFIDENCE_THRESHOLD, we MUST NOT auto-cancel.
We ask the guest to confirm instead. This is the false-positive guard.
Message m14 ("umm maybe cancel or change, not sure yet") must land here.
"""
import asyncio
from app.queue.tasks import EventLogTask
from app.config import CONFIDENCE_THRESHOLD


async def handle(
    message: dict, confidence: float, property_cfg: dict, queue: asyncio.Queue
) -> tuple[str, str]:

    if confidence < CONFIDENCE_THRESHOLD:
        # Low confidence → ASK for confirmation, do NOT cancel anything
        await queue.put(EventLogTask(
            property_id=message["property_id"],
            message_id=message["message_id"],
            event_type="handoff_escalated",
            payload={
                "reason": "ambiguous_cancellation",
                "text": message["text"],
                "confidence": confidence,
            },
        ))
        reply = (
            "Kya aap apni booking cancel karna chahte hain? "
            "Please confirm karein ya staff se baat karein. "
            "(Do you want to cancel your booking? Please confirm or speak to a staff member.)"
        )
        return ("confirm_cancel", reply)

    # High confidence → enqueue the actual cancellation event
    await queue.put(EventLogTask(
        property_id=message["property_id"],
        message_id=message["message_id"],
        event_type="cancellation_confirmed",
        payload={"text": message["text"], "confidence": confidence},
    ))
    reply = (
        "Aapki cancellation request process ho rahi hai. "
        "Confirmation aapko jald milega. "
        "(Your cancellation is being processed. You will receive confirmation shortly.)"
    )
    return ("processed", reply)
