-- Run this ONCE as the Supabase superuser (postgres role).
-- This creates the app_user role that the backend connects as.
-- Non-superuser role = Postgres enforces RLS policies.
-- IMPORTANT: If using Supabase, you can also just use the anon/service_role
-- with RLS policies and skip creating a separate role.

-- Option A: Create a dedicated app_user (recommended for prod)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'changeme_strong_password' NOINHERIT;
  END IF;
END
$$;

GRANT CONNECT ON DATABASE postgres TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Ensure future tables are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_user;

-- Option B (simpler for Supabase): Just use the postgres superuser URL
-- but enable RLS bypass only for the migration, then use anon key at runtime.
-- NOT recommended — superuser bypasses RLS.
