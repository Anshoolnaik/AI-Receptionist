"""
Stage-2 LLM classifier using Groq.
Only called when rules return None or confidence < 0.7.
"""
import json
import logging
from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

_client: Groq | None = None

INTENTS = ["booking", "cancellation", "faq", "complaint", "wakeup"]

SYSTEM_PROMPT = """You are a hotel guest message intent classifier.
Classify the guest message into exactly one of these intents:
  booking | cancellation | faq | complaint | wakeup

Rules:
- booking: guest wants to reserve / check availability of a room
- cancellation: guest wants to cancel a reservation
- faq: guest has a question about hotel policies, facilities, price, wifi, etc.
- complaint: guest is reporting a problem, dissatisfaction, or issue
- wakeup: guest wants a wake-up call / alarm

Important:
- If the guest is uncertain or ambiguous about cancellation (e.g. "maybe cancel or change"), set confidence to 0.40
- If the message is very short or generic (e.g. "hi", "hello"), return faq with confidence 0.50
- Mixed intent (booking + faq) → return the primary intent with lower confidence 0.65

Respond ONLY with valid JSON (no markdown, no explanation):
{"intent": "<intent>", "confidence": <float 0.0-1.0>}"""


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def llm_classify(text: str, property_name: str = "") -> tuple[str, float]:
    """
    Call Groq to classify the message.
    Returns (intent, confidence). Falls back to ('faq', 0.5) on any error.
    """
    user_msg = f"Property: {property_name}\nGuest message: {text}"
    try:
        resp = get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=64,
        )
        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        intent = data.get("intent", "faq")
        confidence = float(data.get("confidence", 0.5))

        # Validate — never trust a hallucinated intent
        if intent not in INTENTS:
            logger.warning("LLM returned unknown intent %r, defaulting to faq", intent)
            return ("faq", 0.5)

        return (intent, confidence)

    except Exception as exc:
        logger.exception("LLM classify failed: %s", exc)
        return ("faq", 0.5)   # safe default — faq workflow is never destructive
