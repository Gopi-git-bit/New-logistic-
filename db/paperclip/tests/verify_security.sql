-- Runs as the disposable superuser session; functional checks SET ROLE to the restricted roles.
-- psql variables are never interpolated inside $$ bodies; ids cross blocks via m5.* session settings.
\set ON_ERROR_STOP 1

-- D-28 catalog assertions.
DO $$
DECLARE
  allowlist text[] := ARRAY['create_proposal','record_invariant','acquire_decision_lock','release_decision_lock','decide','issue_grant','consume_grant','revoke_grant','record_execution_attempt','record_heartbeat','record_token_cost','evaluate_loop_guard'];
  owner_oid oid := 'paperclip_function_owner'::regrole;
  app_oid oid := 'paperclip_app'::regrole;
  bad text;
BEGIN
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'paperclip' AND p.prosecdef) <> 12
     OR (SELECT count(DISTINCT p.proname) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'paperclip' AND p.prosecdef AND p.proname = ANY (allowlist)) <> 12 THEN
    RAISE EXCEPTION 'privileged governance catalog is not exactly the 12 D-28 functions';
  END IF;
  SELECT string_agg(p.proname, ',') INTO bad FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'paperclip' AND p.prosecdef
     AND (p.prosrc ~* '\mEXECUTE\M' OR p.prosrc ~* '\mformat\s*\(' OR p.prosrc ~* '\mquote_(ident|literal|nullable)\M' OR p.prosrc ~* '::(regclass|regproc|regprocedure|regnamespace)');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'privileged function uses dynamic SQL or caller-controlled identifiers: %', bad; END IF;
  SELECT string_agg(n.nspname || '.' || p.proname, ',') INTO bad FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND NOT (n.nspname = 'paperclip' AND p.proname = ANY (allowlist));
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'SECURITY DEFINER outside D-28 allowlist: %', bad; END IF;
  SELECT string_agg(p.proname, ',') INTO bad FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'paperclip' AND p.prosecdef AND coalesce(p.proconfig, '{}'::text[]) IS DISTINCT FROM ARRAY['search_path=pg_catalog, paperclip, pg_temp'];
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'search_path is not exactly fixed: %', bad; END IF;
  SELECT string_agg(p.proname, ',') INTO bad FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'paperclip' AND p.prosecdef AND p.proowner <> owner_oid;
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'privileged function not owned by dedicated owner: %', bad; END IF;
  SELECT string_agg(p.proname, ',') INTO bad FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'paperclip' AND p.prosecdef
     AND (p.proacl IS NULL OR EXISTS (SELECT 1 FROM aclexplode(p.proacl) a WHERE a.privilege_type = 'EXECUTE' AND a.grantee NOT IN (owner_oid, app_oid)));
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'privileged function executable by PUBLIC or an unapproved role: %', bad; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('paperclip_migrator','paperclip_function_owner','paperclip_app')
              AND (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolcanlogin)) THEN
    RAISE EXCEPTION 'Paperclip group role holds a prohibited attribute';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_class WHERE relowner IN (owner_oid, app_oid))
     OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner IN (owner_oid, app_oid))
     OR EXISTS (SELECT 1 FROM pg_database WHERE datdba IN (owner_oid, app_oid))
     OR EXISTS (SELECT 1 FROM pg_type WHERE typowner IN (owner_oid, app_oid))
     OR EXISTS (SELECT 1 FROM pg_proc WHERE proowner = app_oid) THEN
    RAISE EXCEPTION 'function owner or application role owns a prohibited object';
  END IF;
  IF has_schema_privilege('paperclip_app', 'paperclip', 'CREATE') OR has_schema_privilege('paperclip_app', 'public', 'CREATE')
     OR has_schema_privilege('paperclip_function_owner', 'paperclip', 'CREATE') OR has_schema_privilege('paperclip_function_owner', 'public', 'CREATE')
     OR EXISTS (SELECT 1 FROM pg_namespace n, aclexplode(n.nspacl) a WHERE n.nspname IN ('public', 'paperclip') AND a.grantee = 0 AND a.privilege_type = 'CREATE') THEN
    RAISE EXCEPTION 'untrusted role can create objects in public or paperclip';
  END IF;
  SELECT string_agg(c.relname, ',') INTO bad FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'paperclip' AND c.relkind = 'r'
     AND (has_table_privilege('paperclip_app', c.oid, 'SELECT') OR has_table_privilege('paperclip_app', c.oid, 'INSERT')
       OR has_table_privilege('paperclip_app', c.oid, 'UPDATE') OR has_table_privilege('paperclip_app', c.oid, 'DELETE')
       OR has_table_privilege('paperclip_app', c.oid, 'TRUNCATE'));
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'application role has direct table privileges: %', bad; END IF;
  SELECT string_agg(c.relname, ',') INTO bad FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'paperclip' AND c.relkind = 'r' AND c.relname <> 'schema_migrations' AND NOT (c.relrowsecurity AND c.relforcerowsecurity);
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'table without forced RLS: %', bad; END IF;
END $$;
\echo 'catalog_security=PASS'

-- An unrelated role cannot execute any privileged function.
CREATE ROLE paperclip_m5_intruder NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname = 'paperclip' AND p.prosecdef AND has_function_privilege('paperclip_m5_intruder', p.oid, 'EXECUTE')) THEN
    RAISE EXCEPTION 'unauthorized role can execute a privileged function';
  END IF;
END $$;
SET ROLE paperclip_m5_intruder;
SELECT set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
DO $$ BEGIN
  PERFORM paperclip.issue_grant(gen_random_uuid());
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS intruder execution' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
RESET ROLE;
DROP ROLE paperclip_m5_intruder;
\echo 'unauthorized_role_denied=PASS'

SET ROLE paperclip_app;

-- Missing and malformed tenant context fail closed.
SELECT set_config('paperclip.tenant_id', '', false);
DO $$ BEGIN
  PERFORM paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'sec-no-tenant', '{"ref":"sec"}'::jsonb, 'sec-no-tenant', now() + interval '10 minutes');
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS missing tenant' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
SELECT set_config('paperclip.tenant_id', 'not-a-uuid', false);
DO $$ BEGIN
  PERFORM paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'sec-bad-tenant', '{"ref":"sec"}'::jsonb, 'sec-bad-tenant', now() + interval '10 minutes');
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS malformed tenant' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
SELECT set_config('paperclip.tenant_id', '33333333-3333-3333-3333-333333333333', false);
DO $$ BEGIN
  PERFORM paperclip.issue_grant(gen_random_uuid());
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS unknown tenant' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
SELECT set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
\echo 'tenant_context_fail_closed=PASS'

-- Direct mutation, object creation, and privileged-function replacement are denied.
DO $$ BEGIN
  INSERT INTO paperclip.execution_grants(tenant_id, proposal_id, agent_id, action_key, target_system, entity_type, entity_id, payload_hash, expires_at)
  VALUES ('11111111-1111-1111-1111-111111111111', gen_random_uuid(), '11111111-1111-1111-1111-111111111112', 'REFUND', 'ZIPPY', 'order', 'x', repeat('c', 64), now());
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS direct insert' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
DO $$ BEGIN
  UPDATE paperclip.execution_grants SET consumed_at = NULL;
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS direct update' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
DO $$ BEGIN
  DELETE FROM paperclip.governance_activity_log;
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS audit delete' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
DO $$ BEGIN
  CREATE TABLE public.m5_intrusion (x int);
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS public create' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
DO $$ BEGIN
  CREATE TABLE paperclip.m5_intrusion (x int);
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS paperclip create' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
DO $$ BEGIN
  CREATE OR REPLACE FUNCTION paperclip.issue_grant(p_proposal uuid) RETURNS paperclip.governance_result LANGUAGE sql AS $f$ SELECT ROW(true, 'GRANT_ISSUED', NULL::uuid)::paperclip.governance_result $f$;
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS function replacement' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
RESET ROLE;
\echo 'direct_write_and_ddl_denied=PASS'

SELECT set_config('m5.hash_inv_fail', encode(public.digest('{"ref":"inv-fail"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_no_appr', encode(public.digest('{"ref":"no-appr"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_self', encode(public.digest('{"ref":"self"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_rej', encode(public.digest('{"ref":"rej"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_exp', encode(public.digest('{"ref":"exp"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_lock', encode(public.digest('{"ref":"lock"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_ok', encode(public.digest('{"ref":"ok"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_rev', encode(public.digest('{"ref":"rev"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_expg', encode(public.digest('{"ref":"expg"}'::jsonb::text, 'sha256'), 'hex'), false);
SELECT set_config('m5.hash_cross', encode(public.digest('{"ref":"cross"}'::jsonb::text, 'sha256'), 'hex'), false);

SET ROLE paperclip_app;

-- Governance-check failures issue no grant and return governance_result denial with durable evidence.
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'inv-fail', '{"ref":"inv-fail"}'::jsonb, 'sec-inv-fail', now() + interval '10 minutes')).governance_id AS p_fail \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'no-appr', '{"ref":"no-appr"}'::jsonb, 'sec-no-appr', now() + interval '10 minutes')).governance_id AS p_noappr \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'self', '{"ref":"self"}'::jsonb, 'sec-self', now() + interval '10 minutes')).governance_id AS p_self \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'rej', '{"ref":"rej"}'::jsonb, 'sec-rej', now() + interval '10 minutes')).governance_id AS p_rej \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'exp', '{"ref":"exp"}'::jsonb, 'sec-exp', now() + interval '10 minutes')).governance_id AS p_exp \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'lock', '{"ref":"lock"}'::jsonb, 'sec-lock', now() + interval '10 minutes')).governance_id AS p_lock \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'ok', '{"ref":"ok"}'::jsonb, 'sec-ok', now() + interval '10 minutes')).governance_id AS p_ok \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'rev', '{"ref":"rev"}'::jsonb, 'sec-rev', now() + interval '10 minutes')).governance_id AS p_rev \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'expg', '{"ref":"expg"}'::jsonb, 'sec-expg', now() + interval '10 minutes')).governance_id AS p_expg \gset
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'cross', '{"ref":"cross"}'::jsonb, 'sec-cross', now() + interval '10 minutes')).governance_id AS p_cross \gset

SELECT set_config('m5.p_fail', :'p_fail', false), set_config('m5.p_noappr', :'p_noappr', false), set_config('m5.p_self', :'p_self', false),
       set_config('m5.p_rej', :'p_rej', false), set_config('m5.p_exp', :'p_exp', false), set_config('m5.p_lock', :'p_lock', false),
       set_config('m5.p_ok', :'p_ok', false), set_config('m5.p_rev', :'p_rev', false), set_config('m5.p_expg', :'p_expg', false),
       set_config('m5.p_cross', :'p_cross', false);

SELECT paperclip.record_invariant(:'p_fail', 'INV-1', false);
SELECT paperclip.decide(:'p_fail', 'Gopinathan', true, now() + interval '5 minutes') AS decide_fail \gset
SELECT paperclip.decide(:'p_rej', 'Gopinathan', false, now() + interval '5 minutes') AS decide_rej \gset
SELECT paperclip.decide(:'p_exp', 'Gopinathan', true, now() - interval '1 second') AS decide_exp \gset
SELECT paperclip.decide(:'p_lock', 'Gopinathan', true, now() + interval '5 minutes') AS decide_lock \gset
DO $$
DECLARE
  res paperclip.governance_result;
BEGIN
  res := paperclip.decide(current_setting('m5.p_self')::uuid, '11111111-1111-1111-1111-111111111112', true, now() + interval '5 minutes');
  IF res.allowed OR res.reason_code <> 'SELF_APPROVAL_DENIED' THEN
    RAISE EXCEPTION 'UNEXPECTED_SUCCESS self approval: %', res.reason_code USING ERRCODE = 'P0009';
  END IF;
END $$;
-- Negative assertion: paperclip_migrator cannot execute privileged application functions.
RESET ROLE;
SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
DO $$ BEGIN
  PERFORM paperclip.acquire_decision_lock(current_setting('m5.p_lock')::uuid, 'migrator-intruder', 'migrator execution denied');
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS migrator executed acquire_decision_lock' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
RESET ROLE;
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
WITH call AS (SELECT paperclip.acquire_decision_lock(:'p_lock', 'app-proof', 'proof lock') AS r)
SELECT (r).allowed AS acquire_lock_allowed, (r).reason_code AS acquire_lock_code, (r).governance_id AS acquire_lock_id FROM call \gset
SELECT CASE WHEN :'acquire_lock_allowed'::boolean IS NOT TRUE THEN (1/0)::int END;
DO $$
DECLARE
  k text;
  res paperclip.governance_result;
BEGIN
  FOREACH k IN ARRAY ARRAY['m5.p_fail', 'm5.p_noappr', 'm5.p_self', 'm5.p_rej', 'm5.p_exp', 'm5.p_lock'] LOOP
    res := paperclip.issue_grant(current_setting(k)::uuid);
    IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS grant issued for %', k USING ERRCODE = 'P0009'; END IF;
  END LOOP;
END $$;
\echo 'governance_denials_issue_no_grant=PASS'

-- Grant binding, revocation, expiry, and replay.
SELECT paperclip.decide(:'p_ok', 'Gopinathan', true, now() + interval '5 minutes') AS decide_ok \gset
SELECT paperclip.decide(:'p_rev', 'Gopinathan', true, now() + interval '5 minutes') AS decide_rev \gset
SELECT paperclip.decide(:'p_expg', 'Gopinathan', true, now() + interval '5 minutes') AS decide_expg \gset
SELECT paperclip.decide(:'p_cross', 'Gopinathan', true, now() + interval '5 minutes') AS decide_cross \gset
SELECT (paperclip.issue_grant(:'p_ok')).governance_id AS g_ok \gset
SELECT (paperclip.issue_grant(:'p_rev')).governance_id AS g_rev \gset
SELECT (paperclip.issue_grant(:'p_expg')).governance_id AS g_expg \gset
SELECT (paperclip.issue_grant(:'p_cross')).governance_id AS g_cross \gset
SELECT set_config('m5.g_ok', :'g_ok', false), set_config('m5.g_rev', :'g_rev', false), set_config('m5.g_expg', :'g_expg', false), set_config('m5.g_cross', :'g_cross', false);
WITH call AS (SELECT paperclip.revoke_grant(current_setting('m5.g_rev')::uuid, 'app-proof', 'proof revocation') AS r)
SELECT (r).allowed AS revoke_allowed, (r).reason_code AS revoke_code, (r).governance_id AS revoke_id FROM call \gset
SELECT CASE WHEN :'revoke_allowed'::boolean IS NOT TRUE THEN (1/0)::int END;
RESET ROLE;
SET ROLE paperclip_migrator;
UPDATE paperclip.execution_grants SET expires_at = now() - interval '1 second' WHERE id = current_setting('m5.g_expg')::uuid;
RESET ROLE;
SET ROLE paperclip_app;
DO $$
DECLARE
  g uuid := current_setting('m5.g_ok')::uuid;
  a uuid := '11111111-1111-1111-1111-111111111112';
  h text := current_setting('m5.hash_ok');
  res paperclip.governance_result;
BEGIN
  res := paperclip.consume_grant(g, a, 'REFUND', 'ZIPPY', 'order', 'ok', repeat('e', 64));
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS payload mismatch' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(g, a, 'SETTLE', 'ZIPPY', 'order', 'ok', h);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS action mismatch' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(g, a, 'REFUND', 'ODOO', 'order', 'ok', h);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS target mismatch' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(g, a, 'REFUND', 'ZIPPY', 'trip', 'ok', h);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS entity type mismatch' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(g, a, 'REFUND', 'ZIPPY', 'order', 'other', h);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS entity id mismatch' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(g, gen_random_uuid(), 'REFUND', 'ZIPPY', 'order', 'ok', h);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS actor mismatch' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(current_setting('m5.g_rev')::uuid, a, 'REFUND', 'ZIPPY', 'order', 'rev', current_setting('m5.hash_rev'));
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS revoked grant' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(current_setting('m5.g_expg')::uuid, a, 'REFUND', 'ZIPPY', 'order', 'expg', current_setting('m5.hash_expg'));
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS expired grant' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.consume_grant(g, a, 'REFUND', 'ZIPPY', 'order', 'ok', h);
  IF NOT res.allowed THEN RAISE EXCEPTION 'expected grant consumption failed: %', res.reason_code; END IF;
  res := paperclip.consume_grant(g, a, 'REFUND', 'ZIPPY', 'order', 'ok', h);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS replay' USING ERRCODE = 'P0009'; END IF;
  res := paperclip.record_execution_attempt(g, a, 'REFUND', 'ZIPPY', 'order', 'ok', repeat('f', 64), 'SUCCEEDED');
  IF NOT res.allowed THEN RAISE EXCEPTION 'expected execution attempt recording failed: %', res.reason_code; END IF;
END $$;
\echo 'grant_binding_revocation_expiry_replay=PASS'

-- Malformed and unsupported arguments fail closed with durable denial evidence.
-- Malformed target system is rejected by the table CHECK constraint before governance logic can return a result.
DO $$ BEGIN
  PERFORM paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'BOGUS', 'order', 'x', '{"ref":"x"}'::jsonb, 'sec-bad-target', now() + interval '10 minutes');
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS unsupported target' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN check_violation THEN NULL;
END $$;
-- Malformed entity type is rejected by the table CHECK constraint before governance logic can return a result.
DO $$ BEGIN
  PERFORM paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'bad entity!', 'x', '{"ref":"x"}'::jsonb, 'sec-bad-type', now() + interval '10 minutes');
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS malformed entity type' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN check_violation THEN NULL;
END $$;
WITH call AS (SELECT paperclip.consume_grant(gen_random_uuid(), '11111111-1111-1111-1111-111111111112', 'REFUND', 'ZIPPY', 'order', 'x', 'abc') AS r)
SELECT (r).allowed AS bad_hash_allowed, (r).reason_code AS bad_hash_code FROM call \gset
SELECT CASE WHEN :'bad_hash_allowed'::boolean IS NOT FALSE THEN (1/0)::int END;
SELECT CASE WHEN :'bad_hash_code' <> 'GRANT_CONSUMPTION_DENIED' THEN (1/0)::int END;
\echo 'malformed_arguments_denied=PASS'

-- Temporary-object and hostile search_path shadowing cannot redirect resolution.
SET search_path = pg_temp, public;
CREATE TEMP TABLE action_proposals (id uuid, tenant_id uuid);
CREATE FUNCTION pg_temp.current_tenant() RETURNS uuid LANGUAGE sql AS $f$ SELECT '22222222-2222-2222-2222-222222222222'::uuid $f$;
SELECT (paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'shadow', '{"ref":"shadow"}'::jsonb, 'sec-shadow', now() + interval '10 minutes')).governance_id AS p_shadow \gset
SELECT set_config('m5.p_shadow', :'p_shadow', false);
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_temp.action_proposals) THEN RAISE EXCEPTION 'function wrote to a temporary shadow table'; END IF; END $$;
RESET search_path;
DROP FUNCTION pg_temp.current_tenant();
DROP TABLE pg_temp.action_proposals;
\echo 'shadowing_resisted=PASS'

-- Cross-tenant arguments fail.
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id', '22222222-2222-2222-2222-222222222222', false);
DO $$
DECLARE res paperclip.governance_result;
BEGIN
  res := paperclip.create_proposal('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'x', '{"ref":"x"}'::jsonb, 'sec-cross-create', now() + interval '10 minutes');
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS cross-tenant proposal' USING ERRCODE = 'P0009'; END IF;
END $$;
DO $$
DECLARE res paperclip.governance_result;
BEGIN
  res := paperclip.issue_grant(current_setting('m5.p_noappr')::uuid);
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS cross-tenant grant issue' USING ERRCODE = 'P0009'; END IF;
END $$;
DO $$
DECLARE res paperclip.governance_result;
BEGIN
  res := paperclip.consume_grant(current_setting('m5.g_cross')::uuid, '11111111-1111-1111-1111-111111111112', 'REFUND', 'ZIPPY', 'order', 'cross', current_setting('m5.hash_cross'));
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS cross-tenant consume' USING ERRCODE = 'P0009'; END IF;
END $$;
DO $$
DECLARE res paperclip.governance_result;
BEGIN
  res := paperclip.decide(current_setting('m5.p_noappr')::uuid, 'Gopinathan', true, now() + interval '5 minutes');
  IF res.allowed THEN RAISE EXCEPTION 'UNEXPECTED_SUCCESS cross-tenant approval' USING ERRCODE = 'P0009'; END IF;
END $$;
RESET ROLE;
\echo 'cross_tenant_arguments_denied=PASS'

-- Append-only evidence cannot be mutated by runtime roles.
SET ROLE paperclip_app;
DO $$ BEGIN
  UPDATE paperclip.governance_activity_log SET reason = 'tampered';
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS audit update' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
  DELETE FROM paperclip.governance_activity_log;
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS audit delete' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
  TRUNCATE paperclip.governance_outbox;
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS outbox truncate' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
RESET ROLE;
\echo 'append_only_evidence=PASS'

-- Durable state after denials, shadowing, and evidence completeness (inspected by the table owner under forced RLS).
SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE proposal_id IN (
      current_setting('m5.p_fail')::uuid, current_setting('m5.p_noappr')::uuid, current_setting('m5.p_self')::uuid,
      current_setting('m5.p_rej')::uuid, current_setting('m5.p_exp')::uuid, current_setting('m5.p_lock')::uuid)) THEN
    RAISE EXCEPTION 'a grant exists for a proposal that failed governance checks';
  END IF;
  IF EXISTS (SELECT 1 FROM paperclip.human_approvals WHERE proposal_id = current_setting('m5.p_self')::uuid) THEN
    RAISE EXCEPTION 'self approval was recorded';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.action_proposals WHERE id = current_setting('m5.p_shadow')::uuid) THEN
    RAISE EXCEPTION 'shadowed call did not resolve to the caller tenant';
  END IF;
  IF (SELECT consumed_at FROM paperclip.execution_grants WHERE id = current_setting('m5.g_cross')::uuid) IS NOT NULL THEN
    RAISE EXCEPTION 'cross-tenant consumption mutated the grant';
  END IF;
  IF (SELECT count(*) FROM paperclip.execution_attempts WHERE grant_id = current_setting('m5.g_ok')::uuid) <> 2 THEN
    RAISE EXCEPTION 'expected exactly two execution attempts for the consumed grant (consume + explicit record)';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'proposal.created' AND object_id = current_setting('m5.p_ok')::uuid)
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'approval.recorded' AND object_id = current_setting('m5.p_ok')::uuid)
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.issued' AND object_id = current_setting('m5.g_ok')::uuid)
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.consumed' AND object_id = current_setting('m5.g_ok')::uuid)
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_outbox WHERE event_type = 'grant.issued' AND aggregate_id = current_setting('m5.g_ok')::uuid) THEN
    RAISE EXCEPTION 'successful controlled transitions lack required governance evidence';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'approval.denied' AND object_id = current_setting('m5.p_self')::uuid AND reason = 'SELF_APPROVAL_DENIED')
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.denied' AND object_id = current_setting('m5.p_fail')::uuid AND reason = 'INVARIANT_FAILED')
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.denied' AND object_id = current_setting('m5.p_rej')::uuid AND reason = 'APPROVAL_MISSING_REJECTED_OR_EXPIRED')
     OR NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.denied' AND object_id = current_setting('m5.p_lock')::uuid AND reason = 'DECISION_LOCK_ACTIVE') THEN
    RAISE EXCEPTION 'denied transitions lack required governance denial evidence';
  END IF;
  IF EXISTS (SELECT 1 FROM paperclip.governance_activity_log
              WHERE concat_ws(' ', actor_ref, event_type, reason) ~* '(password|secret|token|bearer|postgres(ql)?://)') THEN
    RAISE EXCEPTION 'governance evidence contains secret-like content';
  END IF;
END $$;
SELECT set_config('paperclip.tenant_id', '22222222-2222-2222-2222-222222222222', false);
DO $$ BEGIN
  -- verify.sql creates exactly one tenant-two loop fixture; any other visible row is a cross-tenant leak.
  IF (SELECT count(*) FROM paperclip.action_proposals WHERE tenant_id = current_setting('paperclip.tenant_id', true)::uuid) <> 1 THEN
    RAISE EXCEPTION 'tenant two proposal count is not the expected functional fixture';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.action_proposals WHERE tenant_id = current_setting('paperclip.tenant_id', true)::uuid
                   AND idempotency_key = 'loop-1'
                   AND requested_by_agent_id = '22222222-2222-2222-2222-222222222223'::uuid
                   AND policy_version_id = '22222222-2222-2222-2222-222222222224'::uuid) THEN
    RAISE EXCEPTION 'tenant two proposal is not the authorized fixture or a cross-tenant leak occurred';
  END IF;
  IF EXISTS (SELECT 1 FROM paperclip.human_approvals WHERE tenant_id = current_setting('paperclip.tenant_id', true)::uuid) THEN RAISE EXCEPTION 'tenant two can see or received approvals'; END IF;
  IF EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE tenant_id = current_setting('paperclip.tenant_id', true)::uuid) THEN RAISE EXCEPTION 'tenant two can see or received grants'; END IF;
END $$;
SELECT set_config('paperclip.tenant_id', '', false);
RESET ROLE;
\echo 'durable_state_and_evidence=PASS'
\echo 'security=PASS'
