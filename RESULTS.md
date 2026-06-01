# RESULTS — Engineering Capstone

## Live URLs
- Backend: https://ai-receptionist-x2zi.onrender.com
- Console: https://ai-receptionist-git-master-anshoolnaiks-projects.vercel.app

## Stack
- **LLM**: Groq API — llama-3.3-70b-versatile (free tier)
- **DB**: Supabase PostgreSQL (session pooler, `app_user` non-superuser for RLS)
- **Backend**: FastAPI + uvicorn, asyncio.Queue, psycopg2 ThreadedConnectionPool
- **Frontend**: React 18 + TypeScript + Vite

## Part A — Orchestration

- **Intent accuracy (15 labeled messages)**: 15/15 (100%) — minimum required: 13/15 ✓
- **Classify P50 / P95 (ms)**: 0.27ms / 511ms
  - P50 is rule-based path (<1ms). P95 includes LLM fallback calls (~400–600ms).
- **Tenant isolation proof**: hotel_a cannot read hotel_b — enforced by PostgreSQL RLS via `SET LOCAL app.current_property_id = ?` in every transaction. `app_user` is non-superuser so RLS policies are binding. Tested: `test_tenant_isolation.py` — 3/3 passed ✓
- **Idempotency proof**: Replay same `message_id` → side-effects = 1 (no duplicate events). Tested: `test_idempotency.py` — PASSED ✓
- **Low-confidence handoff (m14)**: `"umm maybe cancel or change, not sure yet"` → `confidence=0.45` (below 0.6 threshold) → `status=needs_human`. Booking NOT cancelled. Tested: `test_m14_false_positive_guard` — PASSED ✓
- **(Bonus) Mock-OTA**: OTA push fires-and-forgets after booking_created event is committed. On connection failure: logs `ota_push_failed` event after exhausting MAX_RETRIES=6 retries (exponential backoff on 429/500). With no OTA server running all pushes log `ota_push_failed`.

## Part B — Data Assistant

| # | Question | SQL | Answer | ok? |
|---|----------|-----|--------|-----|
| 1 | how many bookings do we have? | `SELECT COUNT(booking_id) FROM bookings` | "5" | ✓ |
| 2 | is mahine kitni booking aayi? | `SELECT COUNT(*) FROM bookings WHERE EXTRACT(MONTH FROM checkin) = 5 AND EXTRACT(YEAR FROM checkin) = 2026` | Count for May 2026 | ✓ |
| 3 | how much revenue did we make from MMT? | `SELECT SUM(amount_inr) FROM bookings WHERE source = 'mmt'` | Revenue total | ✓ |
| 4 | what time is checkout? | *(RAG, no SQL)* | "11:00 AM (11:00)" from kb/policies.md | ✓ |
| 5 | what is the cancellation policy? | *(RAG, no SQL)* | Policy from kb/policies.md | ✓ |

- **Blocked cross-tenant attempt**: `POST /ask` with `property_id=hotel_a`, question=`"show me bookings from hotel_b"` → `400 Blocked: Cross-tenant reference blocked` ✓
- **Tenant scope enforced**: In CODE via `rls_cursor(property_id)` → `SET LOCAL app.current_property_id = ?`. Never trusted to the LLM.
- **Semicolon injection blocked**: `"show bookings'; DROP TABLE bookings; --"` → `400 Blocked: Semicolon in question blocked` ✓
- **DELETE/DROP/UPDATE blocked**: All return `400 Blocked` ✓
- **RAG answer + cited KB file**: `"how do I change a rate?"` → answer from `kb/rates.md` with `source: "kb/rates.md"` ✓
- **Unanswerable refused**: `"what is the phone number of the hotel manager?"` → `refused=true`, answer=null ✓

## Part C — Console

- **Realtime/poll approach**: Polls every 5 seconds via `usePolling` hook. Three states on every fetch: loading / data / error. No WebSocket infra required.
- **Layout**: Mobile-first CSS grid (375px baseline). Two-panel: lifecycle feed (events/bookings tabs) + ask assistant box.
- **Tenant switching**: Property dropdown (hotel_a / hotel_b) — all queries automatically scoped.
- Screenshots: Run frontend at http://localhost:5173 to view.

## Test Suite Results

```
30 passed in 94.03s
```

All 30 tests passing:
- `test_classify.py`: 3/3 (accuracy, m14 guard, latency endpoint)
- `test_e2e.py`: 8/8 (health, booking lifecycle, FAQ, wakeup, complaint, ask data, ask RAG, tenant-scoped endpoints)
- `test_idempotency.py`: 1/1
- `test_nl_sql_guards.py`: 10/10 (happy path + all 6 guard types)
- `test_rag.py`: 4/4 (citation, refusal, grounded answer)
- `test_tenant_isolation.py`: 3/3 (events, bookings, NL→SQL cross-tenant)

## What broke / what I'd improve with more time

1. **OTA push blocking queue**: The queue worker was processing OTA retries sequentially (up to 63s per push). Fixed by making OTA push fire-and-forget (`asyncio.ensure_future`).
2. **Schema validator false positives**: `EXTRACT(MONTH FROM col)` was parsed as a table reference `FROM col`. Fixed by stripping parenthesized content before table extraction.
3. **RAG top-1 retrieval**: TF-IDF with top-1 returned wrong chunk for "checkout time" (scored "Payment" chunk higher). Fixed by retrieving top-3 and passing all to the LLM.
4. **NL→SQL tenant subquery**: Original `SELECT * FROM ({sql}) AS _q WHERE _q.property_id = ?` wrapper broke COUNT queries. Replaced with `rls_cursor` + `SET LOCAL` (Layer 5) as the enforcement mechanism.
5. **With more time**: Deploy to Render/Vercel, add WebSocket for true realtime, add a proper vector DB (pgvector) for RAG, add per-property FAQ via `property_configs`.
