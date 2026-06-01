"""
Stage-1 rule-based classifier.

Returns (intent, confidence) or None if no rule matched (→ LLM fallback).

Key guard: cancellation messages with ambiguity markers (maybe, or, not sure, umm)
get confidence 0.45 — below CONFIDENCE_THRESHOLD — which triggers the
confirm_cancel path instead of auto-cancelling.
"""
import re

INTENTS = ["booking", "cancellation", "faq", "complaint", "wakeup"]

# Words/phrases that indicate genuine uncertainty about cancellation.
# If these appear alongside a cancellation keyword, confidence drops to 0.45.
AMBIGUITY_MARKERS = [
    "maybe", "not sure", "or ", "change", "umm", "hmm", "perhaps",
    "shayad", "sochna", "pata nahi", "ya nahi", "ya change",
]

RULES = {
    "booking": {
        "patterns": [
            r"\bbook\b", r"\breservation\b", r"\broom available\b",
            r"\broom chahiye\b", r"\bmilega\b", r"\bavailability\b",
            r"\bcheck.?in\b", r"\bstay\b", r"\bnight\b", r"\brooms?\b.*\bfor\b",
            r"\bsingle room\b", r"\bdouble room\b", r"\bdeluxe\b",
            r"\bsuite\b", r"\bbed\b.*\bnight\b", r"from \d+",
            # common Hinglish booking
            r"\broom do\b", r"\broom dena\b", r"\broom book\b",
            r"\bkal ke liye\b", r"\baaj raat\b", r"\bkal raat\b",
            r"\braat ke liye\b", r"\bkamra chahiye\b", r"\bkamra milega\b",
            r"\baccomod\b", r"\bacco\b", r"\bplace to stay\b",
        ],
        "confidence": 0.85,
    },
    "cancellation": {
        "patterns": [
            r"\bcancel\b", r"\bcancellation\b", r"\bcancel kar\b",
            r"\bband kar\b", r"\bcancel karna\b", r"\bcancel karo\b",
            r"\bcancel krdo\b", r"\bcancel krna\b", r"\bcancel krdena\b",
            r"\bbooking cancel\b", r"\bcancel booking\b",
        ],
        "ambiguity_markers": AMBIGUITY_MARKERS,
        "confidence": 0.88,
        "ambiguous_confidence": 0.45,   # below threshold → confirm guard fires
    },
    "faq": {
        "patterns": [
            r"\bcheckout\b", r"\bcheck.?out time\b", r"\bwifi\b",
            r"\bwi.?fi\b", r"\bpassword\b", r"\bparking\b",
            r"\bkya hai\b", r"\bkitna\b", r"\brent\b", r"\bdeposit\b",
            r"\bfood\b", r"\bmess\b", r"\binclud\b", r"\btiming\b",
            r"\bhours\b", r"\bprice\b", r"\brate\b", r"\bcost\b",
            r"\bhow much\b", r"\bkab tak\b", r"\bkab se\b",
            r"\bfacilities\b", r"\bamenities\b",
            # common Hinglish FAQ
            r"\bkhana\b", r"\bkhaana\b", r"\bkhaane\b",
            r"\bpaani\b", r"\bpani\b", r"\bgaram paani\b",
            r"\bkab milega\b", r"\bkya milta\b", r"\bkya milti\b",
            r"\blaundry\b", r"\bwashing\b", r"\bcheck out kab\b",
            r"\bcheck in kab\b", r"\bkitne baje\b", r"\bkonse time\b",
            r"\bkya time\b", r"\bwhat time\b",
        ],
        "confidence": 0.80,
    },
    "complaint": {
        "patterns": [
            r"\bnot working\b", r"\bbroken\b", r"\bbad\b", r"\bcold\b",
            r"\bdirty\b", r"\bcomplaint\b", r"\bproblem\b", r"\bissue\b",
            r"\bkharab\b", r"\bbanda\b", r"\bnahi chal raha\b",
            r"\bnoisy\b", r"\bsmell\b", r"\bstink\b", r"\bunclean\b",
            r"\bleaking\b", r"\bloc kaam nahi kar raha\b",
            # common Hinglish complaints
            r"\bganda\b", r"\bgandagi\b", r"\bsaaf nahi\b",
            r"\bac nahi\b", r"\bac band\b", r"\bgeyser nahi\b",
            r"\bgeyser kharab\b", r"\bpaani nahi\b", r"\blight nahi\b",
            r"\bbijli nahi\b", r"\blift kharab\b", r"\bnoise\b",
            r"\bshikayat\b", r"\bpareshani\b", r"\btakleef\b",
            r"\bnahi aa raha\b", r"\bnahi chal rahi\b",
        ],
        "confidence": 0.85,
    },
    "wakeup": {
        "patterns": [
            r"\bwake.?up\b", r"\bwakeup\b", r"\balarm\b",
            r"\bcall at\b", r"\bmorning call\b", r"\bjagana\b",
            r"\bjaga dena\b", r"\bjaga do\b", r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b",
            r"\bbajne par\b", r"\bsakal\b",
            # more wakeup patterns
            r"\bjagao\b", r"\bjagao mujhe\b", r"\bsubah jagana\b",
            r"\bwake me\b", r"\bcall me at\b", r"\bbell bajao\b",
            r"\b\d{1,2} baje\b", r"\b\d{1,2}:\d{2} baje\b",
        ],
        "confidence": 0.90,
    },
}


def rules_classify(text: str) -> tuple[str, float] | None:
    """
    Try to classify text with keyword/regex rules.
    Returns (intent, confidence) or None if no rule matched.
    """
    text_lower = text.lower().strip()
    scores: dict[str, float] = {}

    for intent, cfg in RULES.items():
        matched = any(re.search(p, text_lower) for p in cfg["patterns"])
        if not matched:
            continue

        conf = cfg["confidence"]

        # Special guard: cancellation with ambiguity drops confidence below threshold
        if intent == "cancellation":
            is_ambiguous = any(m in text_lower for m in cfg.get("ambiguity_markers", []))
            if is_ambiguous:
                conf = cfg["ambiguous_confidence"]

        scores[intent] = conf

    if not scores:
        return None

    best = max(scores, key=scores.__getitem__)
    return (best, scores[best])
