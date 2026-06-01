# AI_LOG — Engineering Capstone

## Tools used
- **Claude Code (claude-sonnet-4-6)** — architecture planning, full code generation, test writing
- **Groq API (llama-3.3-70b-versatile)** — runtime LLM for intent classification, NL→SQL generation, RAG summarisation

## Most useful prompts

### Intent classifier (runtime)
```
System: You are a hotel guest message intent classifier. Classify into:
  booking | cancellation | faq | complaint | wakeup
  If guest is uncertain about cancellation → confidence 0.40
  Respond ONLY with JSON: {"intent": "<intent>", "confidence": <float>}
User: Property: {name}\nGuest message: {text}
```

### NL→SQL (runtime)
```
[schema listed] Generate a single SELECT. Do NOT add WHERE property_id.
Do NOT invent columns. If unanswerable → CANNOT_ANSWER
Question: {question}
SQL:
```

### RAG summarisation (runtime)
```
Answer using ONLY the provided text. Do not add information not in the text.
KB excerpt (from {source}): {chunk}
Question: {question}
```

## Where AI was WRONG and how I caught it

### 1. Inline side-effects instead of queue
**Issue**: First draft of the booking workflow called the DB and OTA directly inside the route handler (inline, blocking). This violates the async decoupling requirement.
**Caught by**: Code review — noticed `await db.insert(...)` inside the route. The spec says "side-effect via a QUEUE (not inline)".
**Fix**: Moved all DB writes and OTA calls to queue/worker.py. Route only enqueues a task and returns.

### 2. LLM generating SQL with non-existent column joins
**Issue**: Groq generated `JOIN rooms ON bookings.room_id = rooms.room_id` — but `bookings` has no `room_id` column (only `room_type`). Would silently return empty rows or throw a DB error.
**Caught by**: Schema validation (Layer 3) + manual review of generated SQL in tests.
**Fix**: Added explicit schema map to the prompt ("Do NOT invent columns") and the Layer 3 validator.

### 3. SET LOCAL not working in autocommit mode
**Issue**: `rls_cursor` initially used the connection in autocommit mode. `SET LOCAL` requires a transaction — it silently does nothing without `BEGIN`.
**Caught by**: Running the tenant isolation test: hotel_a's booking list included hotel_b rows.
**Fix**: Added `conn.autocommit = False` before `SET LOCAL` in `rls_cursor`.

### 4. Queue worker blocking the event loop
**Issue**: Sync psycopg2 calls inside the async worker blocked the FastAPI event loop. Under load, all responses stalled.
**Caught by**: Running ab (apache bench) against /message and seeing all requests queue up.
**Fix**: Wrapped all sync DB calls in `loop.run_in_executor(None, sync_fn)`.

### 5. OTA push blocking queue worker
**Issue**: `_handle_booking_create` awaited `_handle_ota_push` before processing the next queue task. With no OTA server running, each push took up to 63 seconds (6 retries × exponential backoff). The `booking_created` event was committed but the queue was stuck — e2e tests timed out waiting for events.
**Caught by**: `test_full_lifecycle_booking` and `test_full_lifecycle_complaint` failing (no events found within 1s sleep).
**Fix**: Changed OTA push to `asyncio.ensure_future(...)` (fire-and-forget). The booking event is committed in step 1; OTA push runs independently in background.

### 6. Schema validator false-positive on EXTRACT(MONTH FROM col)
**Issue**: Groq generated `EXTRACT(MONTH FROM checkin)` for month-based Hindi queries. The regex `r'\b(?:from|join)\s+([a-z_][a-z0-9_]*)'` falsely matched `FROM checkin` inside the EXTRACT function call, treating `checkin` as an unknown table → SchemaViolationError on valid queries.
**Caught by**: `test_nl_sql_hinglish` failing with 400 instead of 200.
**Fix**: Strip parenthesized content (`re.sub(r'\([^)]*\)', '', sql_lower)`) before running the table extraction regex.

### 7. RAG top-1 returning wrong chunk
**Issue**: TF-IDF ranked the "Payment" chunk higher than "Check-in / Check-out Times" for the query "what time is checkout?" — because common tokens skewed scores. Result: LLM answered "I don't know."
**Caught by**: Manual frontend test — ask assistant returned wrong answer.
**Fix**: Changed `top_k=1` to `top_k=3`, concatenated all three chunks as context for the LLM. The LLM then picks the relevant information from the combined context.

### 8. RAG refusing valid KB questions (threshold too high)
**Issue**: Initial threshold=0.15 caused "how do I onboard?" to return refused=True because the KB chunk was short and TF-IDF score was low.
**Caught by**: test_rag.py::test_rag_answer_grounded failing.
**Fix**: Lowered threshold to 0.05 (KB is 3 tiny files; any overlap should match).

## Design decisions

- **Intent classifier**: 2-stage (rules → Groq LLM). Rules handle >80% of messages in <1ms. LLM fallback adds ~400ms but only fires for genuinely ambiguous cases. Cancellation rule deliberately returns confidence=0.45 when ambiguity markers are present — below the 0.6 threshold — to trigger the confirm_cancel guard without needing LLM.

- **Tenant isolation (RLS)**: `SET LOCAL app.current_property_id = ?` inside every transaction, not app-code WHERE. The app connects as a non-superuser role (`app_user`) so Postgres enforces the RLS policies. Even if a bug existed in application code, RLS would catch it.

- **Idempotency + queue**: The message row is inserted BEFORE the queue task is enqueued. On replay, the idempotency check (`SELECT ... WHERE message_id = ?`) returns the stored result immediately without re-enqueueing. Queue tasks are also idempotent (ON CONFLICT DO NOTHING on booking_id).

- **NL→SQL guardrails**: 4 layers of defence + RLS as 5th. The key insight is Layer 4: property_id is injected by wrapping the LLM query in a subquery with `WHERE _q.property_id = %(property_id)s`. This is done in Python code, not trusted to the LLM. Even if the LLM tries to cross-tenant query, the Python wrapper overrides it.

- **RAG + citation**: TF-IDF cosine similarity over KB chunks (no vector DB needed for 3 files). Every response includes `source` (the KB filename). If score < threshold → `refused=True`, answer=None. No fabrication.

- **Console realtime + states**: Polls every 5s (simple, works with any backend, no WebSocket infra needed). Three explicit states for every async fetch: loading → data / error / empty. Mobile-first CSS grid with 375px baseline.
