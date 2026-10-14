-- Functional proofs. psql variables are never interpolated inside $$ bodies; ids cross blocks via m5.* settings.
\set ON_ERROR_STOP 1

-- Lifecycle: create, idempotent replay, invariant, decision lock, approval, grant, consumption, execution attempt.
-- The application role has no access to public.digest; expected hashes are computed by the runner before SET ROLE.
SELECT set_config('m5.hash_external_1', encode(public.digest('{"ref":"external-1"}'::jsonb::text, 'sha256'), 'hex'), false);
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$
DECLARE
  a uuid := '11111111-1111-1111-1111-111111111112';
  pol uuid := '11111111-1111-1111-1111-111111111113';
  r paperclip.governance_result;
  p uuid;
  g uuid;
BEGIN
  r := paperclip.create_proposal(a, pol, 'REFUND', 'ZIPPY', 'order', 'external-1', '{"ref":"external-1"}'::jsonb, 'proof-1', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' OR r.governance_id IS NULL THEN RAISE EXCEPTION 'proposal was not created: %', r.reason_code; END IF;
  p := r.governance_id;
  r := paperclip.create_proposal(a, pol, 'REFUND', 'ZIPPY', 'order', 'external-1', '{"ref":"external-1"}'::jsonb, 'proof-1', now() + interval '10 minutes');
  IF r.reason_code <> 'PROPOSAL_EXISTS' OR r.governance_id <> p THEN RAISE EXCEPTION 'idempotent proposal replay returned %', r.reason_code; END IF;
  PERFORM paperclip.record_invariant(p, 'INV-1', true);
  r := paperclip.acquire_decision_lock(p, 'reviewer-1', 'review');
  IF NOT r.allowed OR r.reason_code <> 'DECISION_LOCK_ACQUIRED' THEN RAISE EXCEPTION 'decision lock not acquired: %', r.reason_code; END IF;
  r := paperclip.acquire_decision_lock(p, 'reviewer-2', 'review');
  IF r.allowed OR r.reason_code <> 'DECISION_LOCK_ACTIVE' THEN RAISE EXCEPTION 'second decision lock not denied: %', r.reason_code; END IF;
  r := paperclip.acquire_decision_lock(gen_random_uuid(), 'reviewer-1', 'review');
  IF r.allowed OR r.reason_code <> 'PROPOSAL_NOT_FOUND' THEN RAISE EXCEPTION 'lock on missing proposal not denied: %', r.reason_code; END IF;
  r := paperclip.decide(p, 'Gopinathan', true, now() + interval '5 minutes');
  IF NOT r.allowed OR r.reason_code <> 'APPROVED' THEN RAISE EXCEPTION 'decision was not approved: %', r.reason_code; END IF;
  r := paperclip.decide(p, 'Gopinathan', false, now() + interval '5 minutes');
  IF r.allowed OR r.reason_code <> 'DECISION_ALREADY_RECORDED' THEN RAISE EXCEPTION 'second decision not denied: %', r.reason_code; END IF;
  r := paperclip.issue_grant(p);
  IF r.allowed OR r.reason_code <> 'DECISION_LOCK_ACTIVE' THEN RAISE EXCEPTION 'grant issued under active decision lock: %', r.reason_code; END IF;
  r := paperclip.release_decision_lock(p, 'reviewer-2');
  IF r.allowed OR r.reason_code <> 'DECISION_LOCK_NOT_HELD' THEN RAISE EXCEPTION 'non-holder released lock: %', r.reason_code; END IF;
  r := paperclip.release_decision_lock(p, 'reviewer-1');
  IF NOT r.allowed OR r.reason_code <> 'DECISION_LOCK_RELEASED' THEN RAISE EXCEPTION 'holder could not release lock: %', r.reason_code; END IF;
  r := paperclip.issue_grant(p);
  IF NOT r.allowed OR r.reason_code <> 'GRANT_ISSUED' THEN RAISE EXCEPTION 'grant was not issued: %', r.reason_code; END IF;
  g := r.governance_id;
  r := paperclip.issue_grant(p);
  IF r.allowed OR r.reason_code <> 'GRANT_ALREADY_ISSUED' THEN RAISE EXCEPTION 'second grant not denied: %', r.reason_code; END IF;
  r := paperclip.consume_grant(g, a, 'REFUND', 'ZIPPY', 'order', 'external-1', current_setting('m5.hash_external_1'));
  IF NOT r.allowed OR r.reason_code <> 'GRANT_CONSUMED' THEN RAISE EXCEPTION 'grant was not consumed: %', r.reason_code; END IF;
  r := paperclip.record_execution_attempt(g, a, 'REFUND', 'ZIPPY', 'order', 'external-1', repeat('a', 64), 'SUCCEEDED');
  IF NOT r.allowed OR r.reason_code <> 'EXECUTION_ATTEMPT_RECORDED' THEN RAISE EXCEPTION 'execution attempt not recorded: %', r.reason_code; END IF;
  r := paperclip.record_execution_attempt(g, a, 'REFUND', 'ZIPPY', 'order', 'external-1', repeat('a', 64), 'SUCCEEDED');
  IF NOT r.allowed OR r.reason_code <> 'EXECUTION_ATTEMPT_DUPLICATE' THEN RAISE EXCEPTION 'duplicate execution attempt not idempotent: %', r.reason_code; END IF;
  r := paperclip.record_execution_attempt(g, a, 'REFUND', 'ODOO', 'order', 'external-1', repeat('b', 64), 'FAILED');
  IF r.allowed OR r.reason_code <> 'EXECUTION_ATTEMPT_MISMATCH' THEN RAISE EXCEPTION 'mismatched execution attempt not denied: %', r.reason_code; END IF;
  PERFORM set_config('m5.lifecycle_grant', g::text, false);
END $$;
DO $$ BEGIN
  PERFORM 1 FROM paperclip.execution_grants;
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS application role read governance table directly' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
RESET ROLE;
SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE expires_at > created_at + interval '5 minutes') THEN RAISE EXCEPTION 'grant ttl'; END IF;
  IF (SELECT count(*) FROM paperclip.execution_attempts WHERE grant_id = current_setting('m5.lifecycle_grant')::uuid) <> 2 THEN
    RAISE EXCEPTION 'expected CONSUMED and SUCCEEDED attempts for the lifecycle grant';
  END IF;
  IF (SELECT count(*) FROM paperclip.governance_activity_log WHERE event_type = 'decision_lock.denied') < 3 THEN
    RAISE EXCEPTION 'decision lock denial evidence missing';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.denied' AND reason = 'GRANT_ALREADY_ISSUED') THEN
    RAISE EXCEPTION 'duplicate grant denial evidence missing';
  END IF;
END $$;
RESET ROLE;
\echo 'lifecycle=PASS'

-- Budget: positive cost denied when budget is zero; durable evidence; no ledger entry; exhausted agent gets no grant.
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$
DECLARE
  pol uuid := '11111111-1111-1111-1111-111111111113';
  zero uuid := '11111111-1111-1111-1111-111111111114';
  budgeted uuid := '11111111-1111-1111-1111-111111111118';
  r paperclip.governance_result;
  p uuid;
BEGIN
  r := paperclip.record_token_cost(zero, NULL, 1.50);
  IF r.allowed OR r.reason_code <> 'BUDGET_EXCEEDED' THEN RAISE EXCEPTION 'zero-budget positive cost was not denied: %', r.reason_code; END IF;
  r := paperclip.create_proposal(zero, pol, 'REFUND', 'ZIPPY', 'order', 'budget-g', '{"ref":"budget"}'::jsonb, 'budget-1', now() + interval '10 minutes');
  IF NOT r.allowed THEN RAISE EXCEPTION 'budget proposal was not created: %', r.reason_code; END IF;
  p := r.governance_id;
  PERFORM paperclip.record_invariant(p, 'INV-1', true);
  r := paperclip.decide(p, 'Gopinathan', true, now() + interval '5 minutes');
  IF NOT r.allowed OR r.reason_code <> 'APPROVED' THEN RAISE EXCEPTION 'budget proposal was not approved: %', r.reason_code; END IF;
  r := paperclip.issue_grant(p);
  IF r.allowed OR r.reason_code <> 'AGENT_INACTIVE_OR_BUDGET_EXHAUSTED' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'budget-exhausted agent received a grant: %', r.reason_code; END IF;
  r := paperclip.record_token_cost(budgeted, NULL, 0.60);
  IF NOT r.allowed OR r.reason_code <> 'TOKEN_COST_RECORDED' THEN RAISE EXCEPTION 'within-budget cost was not recorded: %', r.reason_code; END IF;
  r := paperclip.record_token_cost(budgeted, NULL, 0.60);
  IF r.allowed OR r.reason_code <> 'BUDGET_EXCEEDED' THEN RAISE EXCEPTION 'over-budget cost was not denied: %', r.reason_code; END IF;
  r := paperclip.create_proposal('11111111-1111-1111-1111-111111111116', pol, 'REFUND', 'ZIPPY', 'order', 'budget-inactive', '{"ref":"budget"}'::jsonb, 'budget-inactive-1', now() + interval '10 minutes');
  IF r.allowed OR r.reason_code <> 'AGENT_INACTIVE' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'inactive agent proposal was not denied: %', r.reason_code; END IF;
END $$;
DO $$ BEGIN
  PERFORM paperclip.record_token_cost('11111111-1111-1111-1111-111111111118', NULL, -1);
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS negative cost accepted' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN OTHERS THEN NULL;
END $$;
RESET ROLE;
SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM paperclip.token_cost_ledger WHERE agent_id = '11111111-1111-1111-1111-111111111114') THEN RAISE EXCEPTION 'ledger entry exists for denied cost'; END IF;
  IF (SELECT count(*) FROM paperclip.token_cost_ledger WHERE agent_id = '11111111-1111-1111-1111-111111111118') <> 1 THEN RAISE EXCEPTION 'budgeted agent ledger count'; END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'budget.denied' AND actor_ref = '11111111-1111-1111-1111-111111111114' AND reason = 'BUDGET_EXCEEDED') THEN RAISE EXCEPTION 'budget denial evidence missing'; END IF;
  IF NOT (SELECT budget_exhausted FROM paperclip.agents WHERE id = '11111111-1111-1111-1111-111111111114') THEN RAISE EXCEPTION 'budget exhaustion flag not set'; END IF;
  IF EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE agent_id = '11111111-1111-1111-1111-111111111114') THEN RAISE EXCEPTION 'grant exists for exhausted agent'; END IF;
END $$;
RESET ROLE;
\echo 'budget_fail_closed=PASS'

-- Loop guard: first and second equivalent proposals allowed; third blocked with durable evidence; different fingerprint does not collide.
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$
DECLARE
  a uuid := '11111111-1111-1111-1111-111111111112';
  pol uuid := '11111111-1111-1111-1111-111111111113';
  r paperclip.governance_result;
  p1 uuid;
  p3 uuid;
BEGIN
  r := paperclip.create_proposal(a, pol, 'REFUND', 'ZIPPY', 'order', 'loop', '{"ref":"loop"}'::jsonb, 'loop-1', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' THEN RAISE EXCEPTION 'first equivalent proposal was not allowed: %', r.reason_code; END IF;
  p1 := r.governance_id;
  r := paperclip.create_proposal(a, pol, 'REFUND', 'ZIPPY', 'order', 'loop', '{"ref":"loop"}'::jsonb, 'loop-2', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' THEN RAISE EXCEPTION 'second equivalent proposal was not allowed: %', r.reason_code; END IF;
  r := paperclip.create_proposal(a, pol, 'REFUND', 'ZIPPY', 'order', 'loop', '{"ref":"loop"}'::jsonb, 'loop-3', now() + interval '10 minutes');
  IF r.allowed OR r.reason_code <> 'LOOP_GUARD_TRIGGERED' THEN RAISE EXCEPTION 'third equivalent proposal was not blocked: %', r.reason_code; END IF;
  p3 := r.governance_id;
  PERFORM paperclip.record_invariant(p3, 'INV-1', true);
  PERFORM paperclip.decide(p3, 'Gopinathan', true, now() + interval '5 minutes');
  r := paperclip.issue_grant(p3);
  IF r.allowed OR r.reason_code <> 'LOOP_GUARD_TRIGGERED' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'loop-blocked proposal received a grant: %', r.reason_code; END IF;
  r := paperclip.evaluate_loop_guard(p3);
  IF r.allowed OR r.reason_code <> 'LOOP_GUARD_TRIGGERED' THEN RAISE EXCEPTION 'loop guard evaluation did not block: %', r.reason_code; END IF;
  r := paperclip.evaluate_loop_guard(p1);
  IF NOT r.allowed OR r.reason_code <> 'LOOP_GUARD_CLEAR' THEN RAISE EXCEPTION 'first proposal not clear: %', r.reason_code; END IF;
  r := paperclip.create_proposal(a, pol, 'REFUND', 'ZIPPY', 'order', 'loop-distinct', '{"ref":"loop"}'::jsonb, 'loop-d1', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' THEN RAISE EXCEPTION 'distinct fingerprint collided with the blocked loop: %', r.reason_code; END IF;
  PERFORM set_config('paperclip.tenant_id', '22222222-2222-2222-2222-222222222222', false);
  r := paperclip.create_proposal('22222222-2222-2222-2222-222222222223', '22222222-2222-2222-2222-222222222224', 'REFUND', 'ZIPPY', 'order', 'loop', '{"ref":"loop"}'::jsonb, 'loop-1', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' THEN RAISE EXCEPTION 'other tenant equivalent proposal collided: %', r.reason_code; END IF;
  PERFORM set_config('paperclip.tenant_id', '11111111-1111-1111-1111-111111111111', false);
END $$;
RESET ROLE;
SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM paperclip.loop_guard_events e JOIN paperclip.action_proposals p ON p.id = e.proposal_id WHERE p.idempotency_key = 'loop-3' AND e.action_taken = 'BLOCK') THEN RAISE EXCEPTION 'loop guard block evidence missing'; END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'loop_guard.triggered') THEN RAISE EXCEPTION 'loop guard activity evidence missing'; END IF;
  IF EXISTS (SELECT 1 FROM paperclip.execution_grants g JOIN paperclip.action_proposals p ON p.id = g.proposal_id WHERE p.loop_blocked) THEN RAISE EXCEPTION 'grant exists for loop-blocked proposal'; END IF;
END $$;
SELECT set_config('paperclip.tenant_id','22222222-2222-2222-2222-222222222222',false);
DO $$ BEGIN
  IF (SELECT loop_count FROM paperclip.action_proposals WHERE idempotency_key = 'loop-1') <> 1 THEN RAISE EXCEPTION 'cross-tenant loop count leaked'; END IF;
END $$;
RESET ROLE;
\echo 'loop_guard=PASS'

-- Policy checksum: correct fixture checksum passes; tampered checksum fails closed; inactive policy fails closed; missing policy fails closed; application role cannot modify policy directly.
SET ROLE paperclip_app;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
DO $$ BEGIN
  INSERT INTO paperclip.policy_versions(tenant_id,policy_key,version,policy_document,checksum_sha256,is_active) VALUES ('11111111-1111-1111-1111-111111111111','tamper','v0','{}','0000000000000000000000000000000000000000000000000000000000000000',true);
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS direct policy insert' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
DO $$ BEGIN
  UPDATE paperclip.policy_versions SET is_active = true WHERE id = '11111111-1111-1111-1111-111111111115';
  RAISE EXCEPTION 'UNEXPECTED_SUCCESS direct policy activation' USING ERRCODE = 'P0009';
EXCEPTION WHEN SQLSTATE 'P0009' THEN RAISE; WHEN insufficient_privilege THEN NULL;
END $$;
RESET ROLE;
SET ROLE paperclip_migrator;
SELECT set_config('paperclip.tenant_id','11111111-1111-1111-1111-111111111111',false);
INSERT INTO paperclip.policy_versions(id,tenant_id,policy_key,version,policy_document,checksum_sha256,is_active) VALUES ('11111111-1111-1111-1111-111111111117','11111111-1111-1111-1111-111111111111','tampered','v1','{"approval":"required"}',repeat('0',64),true);
RESET ROLE;
SET ROLE paperclip_app;
DO $$
DECLARE
  a uuid := '11111111-1111-1111-1111-111111111112';
  r paperclip.governance_result;
BEGIN
  r := paperclip.create_proposal(a, '11111111-1111-1111-1111-111111111113', 'REFUND', 'ZIPPY', 'order', 'cs-ok', '{"ref":"cs"}'::jsonb, 'cs-ok', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' THEN RAISE EXCEPTION 'correct checksum was rejected: %', r.reason_code; END IF;
  r := paperclip.create_proposal(a, '11111111-1111-1111-1111-111111111117', 'REFUND', 'ZIPPY', 'order', 'cs-mismatch', '{"ref":"cs"}'::jsonb, 'cs-1', now() + interval '10 minutes');
  IF r.allowed OR r.reason_code <> 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'tampered checksum was not rejected: %', r.reason_code; END IF;
  r := paperclip.create_proposal(a, '11111111-1111-1111-1111-111111111115', 'REFUND', 'ZIPPY', 'order', 'cs-inactive', '{"ref":"cs"}'::jsonb, 'cs-2', now() + interval '10 minutes');
  IF r.allowed OR r.reason_code <> 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'inactive policy was not rejected: %', r.reason_code; END IF;
  r := paperclip.create_proposal(a, gen_random_uuid(), 'REFUND', 'ZIPPY', 'order', 'cs-missing', '{"ref":"cs"}'::jsonb, 'cs-3', now() + interval '10 minutes');
  IF r.allowed OR r.reason_code <> 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'missing policy was not rejected: %', r.reason_code; END IF;
  r := paperclip.create_proposal(a, '11111111-1111-1111-1111-11111111111a', 'REFUND', 'ZIPPY', 'order', 'cs-mutable', '{"ref":"cs"}'::jsonb, 'cs-mutable', now() + interval '10 minutes');
  IF NOT r.allowed OR r.reason_code <> 'PROPOSAL_CREATED' THEN RAISE EXCEPTION 'mutable policy proposal was not created: %', r.reason_code; END IF;
  PERFORM paperclip.record_invariant(r.governance_id, 'INV-1', true);
  PERFORM set_config('m5.cs_mutable', r.governance_id::text, false);
  r := paperclip.decide(r.governance_id, 'Gopinathan', true, now() + interval '5 minutes');
  IF NOT r.allowed OR r.reason_code <> 'APPROVED' THEN RAISE EXCEPTION 'mutable policy proposal was not approved: %', r.reason_code; END IF;
END $$;
RESET ROLE;
SET ROLE paperclip_migrator;
UPDATE paperclip.policy_versions SET policy_document = '{"approval":"optional"}' WHERE id = '11111111-1111-1111-1111-11111111111a';
RESET ROLE;
SET ROLE paperclip_app;
DO $$
DECLARE
  r paperclip.governance_result;
BEGIN
  r := paperclip.issue_grant(current_setting('m5.cs_mutable')::uuid);
  IF r.allowed OR r.reason_code <> 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH' OR r.governance_id IS NOT NULL THEN RAISE EXCEPTION 'policy drift after proposal was not rejected at issue time: %', r.reason_code; END IF;
END $$;
RESET ROLE;
SET ROLE paperclip_migrator;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE proposal_id = current_setting('m5.cs_mutable')::uuid) THEN RAISE EXCEPTION 'grant exists for drifted policy'; END IF;
  IF EXISTS (SELECT 1 FROM paperclip.action_proposals WHERE policy_version_id IN ('11111111-1111-1111-1111-111111111115', '11111111-1111-1111-1111-111111111117')) THEN RAISE EXCEPTION 'proposal persisted for failed-closed policy'; END IF;
  IF NOT EXISTS (SELECT 1 FROM paperclip.governance_activity_log WHERE event_type = 'grant.denied' AND reason = 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH') THEN RAISE EXCEPTION 'policy drift denial evidence missing'; END IF;
END $$;
RESET ROLE;
\echo 'policy_checksum_fail_closed=PASS'

-- Heartbeat: recorded once, idempotent replay, inactive agent and foreign task denied.
SET ROLE paperclip_app;
DO $$
DECLARE
  r paperclip.governance_result;
BEGIN
  r := paperclip.record_heartbeat('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111119', 'hb-1');
  IF NOT r.allowed OR r.reason_code <> 'HEARTBEAT_RECORDED' THEN RAISE EXCEPTION 'heartbeat not recorded: %', r.reason_code; END IF;
  r := paperclip.record_heartbeat('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111119', 'hb-1');
  IF NOT r.allowed OR r.reason_code <> 'HEARTBEAT_DUPLICATE' THEN RAISE EXCEPTION 'heartbeat replay not idempotent: %', r.reason_code; END IF;
  r := paperclip.record_heartbeat('11111111-1111-1111-1111-111111111116', '11111111-1111-1111-1111-111111111119', 'hb-2');
  IF r.allowed OR r.reason_code <> 'HEARTBEAT_DENIED' THEN RAISE EXCEPTION 'inactive agent heartbeat not denied: %', r.reason_code; END IF;
  r := paperclip.record_heartbeat('11111111-1111-1111-1111-111111111112', '22222222-2222-2222-2222-222222222229', 'hb-3');
  IF r.allowed OR r.reason_code <> 'HEARTBEAT_DENIED' THEN RAISE EXCEPTION 'foreign task heartbeat not denied: %', r.reason_code; END IF;
END $$;
RESET ROLE;
\echo 'heartbeat=PASS'
\echo 'verify=PASS'
