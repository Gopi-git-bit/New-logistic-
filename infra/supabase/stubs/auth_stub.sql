-- Compatibility stub: minimal Supabase auth functions for vanilla Postgres.
-- Load BEFORE RLS migration when not running against real Supabase.
--
-- Simulate a user in a session with:
--   SELECT set_config('app.current_user_id', '00000000-0000-0000-0000-000000000002', false);
--   SELECT set_config('app.current_role',    'authenticated', false);

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

-- JWT stubs used by some Supabase helpers
CREATE OR REPLACE FUNCTION auth.jwt()
RETURNS JSONB AS $$
BEGIN
    RETURN jsonb_build_object(
        'sub', auth.uid(),
        'role', auth.role()
    );
END;
$$ LANGUAGE plpgsql STABLE;
