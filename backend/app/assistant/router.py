"""
Route a question to NL→SQL or RAG.

Product-help questions (how do I...) → RAG
Data questions (how many, kitni, revenue) → NL→SQL
"""
import re

# Signals that suggest this is a product-help / how-to question → RAG
PRODUCT_HELP_PATTERNS = [
    r"\bhow do i\b", r"\bhow to\b", r"\bwhere do i\b",
    r"\bkaise\b", r"\bkaise karu\b", r"\bkahan\b",
    r"\bsteps?\b", r"\bguide\b", r"\bhelp\b.*\b(change|update|respond|review|onboard)\b",
    r"\bchange.*rate\b", r"\brate.*change\b",
    r"\brespond.*review\b", r"\breview.*respond\b",
    r"\bonboard\b", r"\bonboarding\b",
    r"\bset up\b", r"\bconfigure\b",
    # Policy / timing questions → RAG
    r"\bcheck.?in time\b", r"\bcheck.?out time\b",
    r"\bwhat time\b", r"\bcheck.*kab\b",
    r"\bcancellation policy\b", r"\bcancel.*policy\b",
    r"\brefund policy\b", r"\brefund.*rule\b",
    r"\bpolicy\b", r"\bpolicies\b",
    r"\bcheck.?in.*process\b", r"\bcheck.?out.*process\b",
    r"\bearly check\b", r"\blate check\b",
    r"\btiming\b", r"\bsamay\b",
]

# Signals that suggest this is a data question → NL→SQL
DATA_PATTERNS = [
    r"\bhow many\b", r"\bhow much\b",
    r"\bkitni\b", r"\bkitna\b", r"\bkitne\b",
    r"\brevenue\b", r"\boccupancy\b", r"\bearning\b",
    r"\bno.?show\b", r"\bno show\b",
    r"\bcount\b", r"\btotal\b", r"\bsum\b",
    r"\bbooking(s)?\b.*\b(this month|aaye|hui|confirmed)\b",
    r"\bwhich room type\b",
    r"\bshow me\b", r"\blist\b",
]


def route_question(question: str) -> str:
    """Returns 'rag' or 'nl_sql'."""
    q = question.lower().strip()

    # Product-help signals → RAG
    if any(re.search(p, q) for p in PRODUCT_HELP_PATTERNS):
        return "rag"

    # Data signals → NL→SQL
    if any(re.search(p, q) for p in DATA_PATTERNS):
        return "nl_sql"

    # Default: try NL→SQL for anything that looks numeric/specific,
    # otherwise RAG
    return "nl_sql"
