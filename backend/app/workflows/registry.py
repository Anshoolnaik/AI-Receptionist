"""
WorkflowRegistry: maps intent → handler.

Each handler receives (message_data, property_config, queue) and returns
a (status, reply) tuple. Side-effects are ENQUEUED, not executed inline.
"""
import asyncio
from typing import Callable

from app.workflows import booking, cancellation, faq, complaint, wakeup

_REGISTRY: dict[str, Callable] = {
    "booking":      booking.handle,
    "cancellation": cancellation.handle,
    "faq":          faq.handle,
    "complaint":    complaint.handle,
    "wakeup":       wakeup.handle,
}


async def dispatch(
    intent: str,
    confidence: float,
    message: dict,
    property_cfg: dict,
    queue: asyncio.Queue,
) -> tuple[str, str]:
    """
    Route to the correct workflow.
    Returns (status, reply_text).
    """
    handler = _REGISTRY.get(intent)
    if handler is None:
        # Unknown intent — treat as handoff
        from app.workflows.handoff import handle as handoff_handle
        return await handoff_handle(message, property_cfg, queue)

    return await handler(message, confidence, property_cfg, queue)
