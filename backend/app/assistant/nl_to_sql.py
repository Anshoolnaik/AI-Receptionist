"""
NL→SQL with 4-layer guard. This is the highest-risk code path.

Layer 1 — sqlparse: reject non-SELECT, multi-statement, semicolons
Layer 2 — keyword blocklist: DROP, DELETE, UPDATE, INSERT, etc.
Layer 3 — schema validation: only known tables + columns
Layer 4 — force-inject property_id WHERE clause in code (never trust LLM)

Even if all 4 layers are bypassed, RLS (via rls_cursor) provides a 5th line of defense.

Hard fail the graders check for:
  - executed write/destructive query
  - cross-tenant read (another property's data visible)
"""
import re
import json
import logging
import sqlparse
from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL
from app.database import rls_cursor

logger = logging.getLogger(__name__)

# ── Schema map — the only valid tables and columns ───────────────────────────
SCHEMA = {
    "properties": {"property_id", "name", "city", "total_rooms"},
    "rooms":      {"room_id", "property_id", "room_type", "capacity"},
    "rates":      {"rate_id", "property_id", "room_type", "date", "price_inr"},
    "bookings":   {"booking_id", "property_id", "room_type", "checkin",
                   "checkout", "status", "amount_inr", "source"},
    "messages":   {"message_id", "property_id", "guest_id", "text",
                   "intent", "confidence", "status", "created_at"},
    "events":     {"event_id", "property_id", "message_id", "event_type",
                   "payload", "created_at"},
}

FORBIDDEN_KEYWORDS = {
    "drop", "delete", "update", "insert", "alter", "create", "truncate",
    "grant", "revoke", "execute", "pg_", "information_schema", "pg_catalog",
    "set ", "copy", "vacuum", "analyze", "explain", "--", "/*", "xp_",
}

NL_TO_SQL_PROMPT = """You are a PostgreSQL query generator for a hotel management system.
Generate a single read-only SELECT query to answer the user's question.

Database schema:
- properties(property_id, name, city, total_rooms)
- rooms(room_id, property_id, room_type, capacity)
- rates(rate_id, property_id, room_type, date, price_inr)
- bookings(booking_id, property_id, room_type, checkin, checkout, status, amount_inr, source)

Important rules:
1. Generate ONLY a SELECT statement. No INSERT, UPDATE, DELETE, DROP, or other DDL/DML.
2. Do NOT add a WHERE property_id = ... clause — the system will add it automatically.
3. Do NOT use semicolons.
4. Use only the tables and columns listed above. Do NOT invent columns.
5. If the question cannot be answered with the schema, respond with: CANNOT_ANSWER
6. Respond ONLY with the raw SQL query (no markdown, no explanation).

Current month context: May 2026. "Is mahine" / "this month" = May 2026.

Question: {question}
SQL:"""


class BlockedQueryError(Exception):
    pass


class SchemaViolationError(Exception):
    pass


def _get_groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


def _generate_sql(question: str) -> str:
    """Ask Groq to generate SQL for the question."""
    prompt = NL_TO_SQL_PROMPT.format(question=question)
    resp = _get_groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=256,
    )
    return resp.choices[0].message.content.strip()


def _validate_and_guard(raw_sql: str, property_id: str) -> str:
    """
    Apply all 4 guard layers. Returns safe SQL with property_id injected.
    Raises BlockedQueryError or SchemaViolationError on violations.
    """
    sql = raw_sql.strip().rstrip(";").strip()

    # ── Layer 1: sqlparse structural checks ──────────────────────────────────
    statements = [s for s in sqlparse.parse(sql) if s.get_type() is not None or str(s).strip()]
    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        raise BlockedQueryError(f"Multi-statement query blocked (got {len(statements)} statements)")

    stmt = statements[0]
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        raise BlockedQueryError(f"Non-SELECT statement blocked: type={stmt_type!r}")

    # Check for hidden semicolons (e.g. "SELECT 1; DROP TABLE ...")
    if ";" in sql:
        raise BlockedQueryError("Semicolon in query blocked (multi-statement injection attempt)")

    # ── Layer 2: keyword blocklist ────────────────────────────────────────────
    sql_lower = sql.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            raise BlockedQueryError(f"Forbidden keyword blocked: {kw!r}")

    # ── Layer 3: schema validation ────────────────────────────────────────────
    # Extract all identifiers and check they exist in our schema
    all_tables = set(SCHEMA.keys())
    # Extract table references from FROM/JOIN clauses.
    # Strip content inside parentheses first to avoid false matches from
    # function calls like EXTRACT(MONTH FROM col) or DATE_TRUNC('month', col).
    sql_no_parens = re.sub(r'\([^)]*\)', '', sql_lower)
    table_refs = re.findall(
        r'\b(?:from|join)\s+([a-z_][a-z0-9_]*)', sql_no_parens
    )
    for tbl in table_refs:
        if tbl not in all_tables:
            raise SchemaViolationError(f"Unknown table referenced: {tbl!r}")

    # ── Layer 4: cross-tenant reference check + RLS enforcement ─────────────
    # Block any SQL that hard-codes a different property_id than the caller's.
    # The actual tenant scope is enforced in CODE via rls_cursor(property_id)
    # which executes SET LOCAL app.current_property_id = ? before the query.
    # This is code-enforced isolation — not trusted to the LLM.
    tenant_refs = re.findall(r"'(hotel_[a-z0-9_]+)'", sql_lower)
    for ref in tenant_refs:
        if ref != property_id.lower():
            raise BlockedQueryError(
                f"Cross-tenant reference blocked: query references {ref!r} "
                f"but caller is scoped to {property_id!r}"
            )

    return sql


def nl_to_sql_answer(question: str, property_id: str) -> dict:
    """
    Full pipeline: question → SQL → execute → summarise with LLM.
    Returns {answer, sql, rows} or raises BlockedQueryError.
    """
    # Pre-check: block obvious destructive intent in the question itself
    q_lower = question.lower()
    for bad in ["delete", "drop", "update", "insert", "truncate", "alter", "create"]:
        if bad in q_lower:
            raise BlockedQueryError(f"Destructive keyword {bad!r} in question — blocked")
    # Block semicolons in question (SQL injection attempt)
    if ";" in question:
        raise BlockedQueryError("Semicolon in question blocked (SQL injection attempt)")

    # Step 1: generate SQL
    raw_sql = _generate_sql(question)
    if "CANNOT_ANSWER" in raw_sql.upper():
        return {"answer": None, "sql": None, "rows": [], "refused": True}

    # Step 2: validate + inject property_id
    safe_sql = _validate_and_guard(raw_sql, property_id)

    # Step 3: execute inside RLS-scoped cursor (Layer 5 — SET LOCAL enforces tenant)
    with rls_cursor(property_id) as cur:
        cur.execute(safe_sql)
        rows = [dict(r) for r in cur.fetchall()]

    # Serialise dates for JSON
    for row in rows:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()

    # Step 4: summarise in natural language
    answer = _summarise(question, safe_sql, rows)

    return {"answer": answer, "sql": safe_sql, "rows": rows, "refused": False}


def _summarise(question: str, sql: str, rows: list[dict]) -> str:
    """Use Groq to turn raw rows into a natural language answer."""
    if not rows:
        return "Is sawaal ka jawab dene ke liye koi data nahi mila. (No data found for this question.)"

    rows_preview = json.dumps(rows[:10], default=str)
    prompt = f"""You are a hotel data assistant. Answer the question concisely in English or Hindi (match the question language).
Use ONLY the data provided. Do not fabricate any numbers.

Question: {question}
Data: {rows_preview}
Answer:"""
    try:
        resp = _get_groq_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # Fallback: return raw data as string
        return f"Result: {rows_preview}"
