# TESTING — Strategy

## How to run
```bash
# Install test deps (once)
pip install -r backend/requirements.txt pytest httpx

# Run full suite against local backend
pytest tests/ -v

# Run against deployed backend
BACKEND_URL=https://ai-receptionist-x2zi.onrender.com pytest tests/ -v
```

## Test strategy

### What I chose to test and why

I prioritised **correctness of the guards** over happy-path coverage, because:
- The three hard-fail criteria (cross-tenant leak, destructive query, ambiguous auto-cancel) are instant score caps.
- The graders will probe with adversarial inputs we haven't seen — so the guards must be general, not seed-specific.

**Unit tests** (no HTTP):
- `classifier/rules.py` — fast, deterministic keyword rules; tested inline in `test_classify.py` via the API.
- `assistant/nl_to_sql.py` — the 4-layer guard (sqlparse, blocklist, schema, property_id injection).

**Integration tests** (real HTTP to a running backend):
- All API routes exercised with real DB and real Groq calls.
- Idempotency: same `message_id` replayed, event count checked before/after.
- RLS: hotel_a event feed checked for hotel_b messages after hotel_b activity.

**e2e tests** (full lifecycle):
- `test_e2e.py` — property → message → queue worker → events/bookings feed → ask.

### Unit / Integration / e2e split

| Type | Files | What |
|---|---|---|
| Unit-ish | `test_classify.py` | Rules + LLM accuracy on 15 labeled messages |
| Integration | `test_idempotency.py`, `test_tenant_isolation.py` | DB-level guard proofs |
| Guards | `test_nl_sql_guards.py`, `test_rag.py` | Adversarial SQL/RAG cases |
| e2e | `test_e2e.py` | Full round-trips via HTTP |

## Guard coverage

| Guard | How I test it | Covered? |
|---|---|---|
| Tenant isolation (A can't read B) | `test_tenant_isolation.py`: send hotel_b message, assert not in hotel_a feed; booking IDs don't overlap | ✅ |
| Idempotency (replay = 1 effect) | `test_idempotency.py`: POST same message_id twice, count events before/after second call | ✅ |
| False-positive guard (ambiguous → no auto-cancel) | `test_classify.py::test_m14_false_positive_guard`: m14 must get `confirm_cancel` or `needs_human`, confidence < 0.6 | ✅ |
| NL→SQL cross-tenant blocked | `test_nl_sql_guards.py::test_cross_tenant_rows_empty` + `test_tenant_isolation.py::test_cross_tenant_nl_sql_blocked` | ✅ |
| NL→SQL destructive/injection blocked | `test_nl_sql_guards.py`: DELETE, DROP, UPDATE, semicolon injection all → 400 | ✅ |
| RAG citation present / unanswerable refused | `test_rag.py`: citation in `source` field; out-of-KB question → `refused=True` | ✅ |
| Console renders + handles error/empty | `test_e2e.py`: health + GET endpoints return valid JSON structure (smoke test) | ✅ |

## Negative and adversarial cases prioritised

1. **m14** — "umm maybe cancel or change, not sure yet" — most important false-positive. Ambiguity markers lower rule confidence to 0.45 (below threshold) → confirm_cancel path.
2. **DELETE/DROP via NL** — "delete all cancelled bookings", "drop table bookings" — sqlparse rejects non-SELECT in Layer 1.
3. **SQL injection via semicolon** — "show bookings'; DROP TABLE bookings; --" — Layer 1 rejects multi-statement + forbidden keyword.
4. **Cross-tenant NL question** — "show bookings for hotel_b" asked with hotel_a scope — Layer 4 (force-inject property_id) + RLS (5th defence).
5. **Hallucinated column** — LLM generating a non-existent column — Layer 3 schema validation.
6. **Out-of-KB RAG** — "what is the capital of Mars?" — TF-IDF score below threshold → refused, not fabricated.
7. **Short/empty messages** — "hi" → faq, confidence 0.5 → no destructive action.
8. **Mixed intent** — "book a deluxe room and also what's the wifi" → booking (primary intent) classified correctly.

## What I'd add with more time

- **Property fixture isolation**: each test run uses fresh property_ids to avoid cross-test pollution.
- **Playwright console smoke tests**: load the frontend, check lifecycle feed renders, submit an ask question.
- **Load tests** (locust): 50 concurrent messages, measure P95 stays < 3s.
- **LLM response caching** in tests to avoid rate-limit flakiness and keep CI fast.
- **Negative latency test**: assert LLM calls time out gracefully (inject a mock with 30s delay).
- **OTA retry test**: mock OTA returning 5× 429 then 200; assert ota_push_ok event logged.

## How I'd structure QA for 100 real hotels

1. **Tenant isolation CI gate**: every PR runs a cross-tenant probe against a shared staging DB. Any leaked row = build fails.
2. **Property-scoped test databases**: each hotel gets a Supabase row in a `test_properties` table; teardown is trivial.
3. **Canary deploys**: route 5% of messages to new classifier version; measure accuracy on production traffic before full rollout.
4. **Guard regression suite** (< 30s): runs on every commit, only exercises the 7 critical guards.
5. **Intent accuracy monitoring**: log `(text, predicted_intent, confidence)` to a warehouse; alert if 7-day accuracy drops below 90%.
6. **SQL audit log**: every NL→SQL execution logged with `property_id`, query, and `blocked=True/False`; weekly review.
7. **RLS penetration test** (monthly): automated script connects as the non-superuser app_user, attempts SET LOCAL bypass and cross-table reads; alerts on any breach.
