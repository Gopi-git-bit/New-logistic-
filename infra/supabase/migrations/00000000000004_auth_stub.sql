-- M1: Minimal Supabase auth compatibility for vanilla Postgres.
-- On real Supabase, auth.uid()/auth.role() already exist — this migration
-- uses CREATE OR REPLACE and is safe in both environments.
--
-- Simulate a user in a session:
--   SELECT set_config('app.current_user_id', '<uuid>', false);
--   SELECT set_config('app.current_role', 'authenticated', false);

CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS UUID AS $$
DECLARE
    v_uid TEXT;
BEGIN
    BEGIN
        v_uid := current_setting('app.current_user_id', true);
    EXCEPTION WHEN OTHERS THEN
        v_uid := NULL;
    END;
    RETURN v_uid::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION auth.role()
RETURNS TEXT AS $$
DECLARE
    v_role TEXT;
BEGIN
    BEGIN
        v_role := current_setting('app.current_role', true);
    EXCEPTION WHEN OTHERS THEN
        v_role := 'anon';
    END;
    RETURN COALESCE(v_role, 'anon');
END;
$$ LANGUAGE plpgsql STABLE;
