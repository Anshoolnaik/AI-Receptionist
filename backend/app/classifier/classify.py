"""
2-stage classifier: rules first, LLM fallback.
Also tracks latency for P95 reporting.
"""
import collections
import time
import logging

from app.classifier.rules import rules_classify
from app.classifier.llm import llm_classify

logger = logging.getLogger(__name__)

# Rolling window of the last 1000 classification latencies (ms)
_latencies: collections.deque = collections.deque(maxlen=1000)

LLM_FALLBACK_THRESHOLD = 0.70   # if rules confidence < this, also try LLM


def classify(text: str, property_cfg: dict | None = None) -> tuple[str, float]:
    """
    2-stage classify. Returns (intent, confidence).

    Stage 1: regex rules (fast, < 1ms)
    Stage 2: Groq LLM (only when rules miss or are low-confidence)
    """
    t0 = time.perf_counter()
    property_name = (property_cfg or {}).get("name", "")

    result = rules_classify(text)

    if result is None:
        # No rule matched → LLM
        intent, confidence = llm_classify(text, property_name)
    elif result[1] < LLM_FALLBACK_THRESHOLD:
        # Rule matched but low confidence → LLM (take higher of the two)
        llm_intent, llm_conf = llm_classify(text, property_name)
        if llm_conf > result[1]:
            intent, confidence = llm_intent, llm_conf
        else:
            intent, confidence = result
    else:
        intent, confidence = result

    elapsed_ms = (time.perf_counter() - t0) * 1000
    _latencies.append(elapsed_ms)
    logger.debug("classify(%r) → %s %.2f  [%.1fms]", text[:40], intent, confidence, elapsed_ms)

    return (intent, confidence)


def get_p95_ms() -> float | None:
    """Return P95 classification latency in ms, or None if no data yet."""
    if not _latencies:
        return None
    sorted_lats = sorted(_latencies)
    idx = int(len(sorted_lats) * 0.95)
    return sorted_lats[min(idx, len(sorted_lats) - 1)]


def get_p50_ms() -> float | None:
    if not _latencies:
        return None
    sorted_lats = sorted(_latencies)
    return sorted_lats[len(sorted_lats) // 2]
