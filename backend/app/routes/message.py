"""
POST /message — the core orchestration route.

Flow:
  1. Check idempotency (message_id already seen → return stored result)
  2. Classify intent (2-stage: rules → Groq LLM)
  3. Low confidence → handoff; ambiguous cancel → confirm_cancel
  4. Store message row (before enqueueing — if enqueue fails, retry is safe)
  5. Dispatch to WorkflowRegistry → workflow ENQUEUES side-effects (not inline)
  6. Return immediately

RLS: all DB access goes through rls_cursor(property_id).
"""
import asyncio
from fastapi import APIRouter, Request, HTTPException

from app.models import Message, MessageResponse
from app.database import rls_cursor
from app.classifier.classify import classify
from app.workflows.registry import dispatch
from app.workflows.handoff import handle as handoff_handle
from app.routes.property import get_property_config
from app.config import CONFIDENCE_THRESHOLD

router = APIRouter()


@router.post("/message", response_model=MessageResponse)
async def handle_message(m: Message, request: Request):
    queue: asyncio.Queue = request.app.state.queue

    # ── 1. Idempotency check ──────────────────────────────────────────────────
    with rls_cursor(m.property_id) as cur:
        cur.execute(
            "SELECT intent, confidence, status FROM messages WHERE message_id = %s",
            (m.message_id,),
        )
        existing = cur.fetchone()

    if existing:
        return MessageResponse(
            message_id=m.message_id,
            intent=existing["intent"],
            confidence=existing["confidence"],
            status=existing["status"],
            reply="(duplicate — already processed)",
        )

    # ── 2. Load property config ───────────────────────────────────────────────
    property_cfg = get_property_config(m.property_id)
    if not property_cfg:
        # Auto-create minimal config so the system still works
        property_cfg = {"name": m.property_id, "language": "en", "custom_faqs": []}

    # ── 3. Classify ───────────────────────────────────────────────────────────
    intent, confidence = classify(m.text, property_cfg)

    # ── 4. Determine status & route ───────────────────────────────────────────
    message_dict = m.model_dump()

    if confidence < CONFIDENCE_THRESHOLD:
        status, reply = await handoff_handle(message_dict, property_cfg, queue)
    else:
        status, reply = await dispatch(intent, confidence, message_dict, property_cfg, queue)

    # ── 5. Persist message (idempotency record written AFTER routing) ─────────
    with rls_cursor(m.property_id) as cur:
        cur.execute(
            """
            INSERT INTO messages
              (message_id, property_id, guest_id, text, intent, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (message_id) DO NOTHING
            """,
            (m.message_id, m.property_id, m.guest_id, m.text, intent, confidence, status),
        )

    return MessageResponse(
        message_id=m.message_id,
        intent=intent,
        confidence=confidence,
        status=status,
        reply=reply,
    )
