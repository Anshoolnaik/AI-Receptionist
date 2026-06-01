-- Schema additions: messages, events, property_configs + RLS policies
-- Run AFTER schema.sql and data.sql

-- ── Property configs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS property_configs (
  property_id  TEXT PRIMARY KEY REFERENCES properties(property_id) ON DELETE CASCADE,
  config       JSONB NOT NULL DEFAULT '{}'
);

-- ── Messages (idempotency store + classification record) ──────────────────────
CREATE TABLE IF NOT EXISTS messages (
  message_id   TEXT PRIMARY KEY,
  property_id  TEXT NOT NULL REFERENCES properties(property_id),
  guest_id     TEXT NOT NULL,
  text         TEXT NOT NULL,
  intent       TEXT,
  confidence   REAL,
  status       TEXT NOT NULL DEFAULT 'received',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- status values: received | needs_human | confirm_cancel | processed

-- ── Events (side-effect audit log written by queue workers) ───────────────────
CREATE TABLE IF NOT EXISTS events (
  event_id     TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  property_id  TEXT NOT NULL REFERENCES properties(property_id),
  message_id   TEXT,
  event_type   TEXT NOT NULL,
  payload      JSONB,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- event_type values: booking_created | cancellation_confirmed | wakeup_scheduled
--   complaint_logged | faq_answered | handoff_escalated | ota_push_ok | ota_push_failed

-- ── Enable RLS on all tenant-scoped tables ────────────────────────────────────
ALTER TABLE property_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages         ENABLE ROW LEVEL SECURITY;
ALTER TABLE events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms            ENABLE ROW LEVEL SECURITY;
ALTER TABLE rates            ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings         ENABLE ROW LEVEL SECURITY;
-- `properties` gets a permissive policy (it's the identity table, not tenant data)
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON properties;
CREATE POLICY allow_all ON properties USING (true) WITH CHECK (true);

-- ── RLS Policies ──────────────────────────────────────────────────────────────
-- Every tenant table checks current_setting('app.current_property_id', TRUE).
-- TRUE = return NULL when variable not set (never ERROR).
-- NULL → Postgres treats USING clause as FALSE → 0 rows returned (safe default).
-- SET LOCAL inside each transaction means the scope ends with the transaction
-- (connection-pool-safe: the next borrower gets no variable set).

DROP POLICY IF EXISTS tenant_isolation ON property_configs;
CREATE POLICY tenant_isolation ON property_configs
  USING (property_id = current_setting('app.current_property_id', TRUE));

DROP POLICY IF EXISTS tenant_isolation ON messages;
CREATE POLICY tenant_isolation ON messages
  USING (property_id = current_setting('app.current_property_id', TRUE));

DROP POLICY IF EXISTS tenant_isolation ON events;
CREATE POLICY tenant_isolation ON events
  USING (property_id = current_setting('app.current_property_id', TRUE));

DROP POLICY IF EXISTS tenant_isolation ON rooms;
CREATE POLICY tenant_isolation ON rooms
  USING (property_id = current_setting('app.current_property_id', TRUE));

DROP POLICY IF EXISTS tenant_isolation ON rates;
CREATE POLICY tenant_isolation ON rates
  USING (property_id = current_setting('app.current_property_id', TRUE));

DROP POLICY IF EXISTS tenant_isolation ON bookings;
CREATE POLICY tenant_isolation ON bookings
  USING (property_id = current_setting('app.current_property_id', TRUE));
