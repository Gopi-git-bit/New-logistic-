SET ROLE paperclip_migrator;
CREATE SCHEMA paperclip AUTHORIZATION paperclip_migrator;
REVOKE ALL ON SCHEMA paperclip FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE paperclip_migrator IN SCHEMA paperclip REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE paperclip_migrator IN SCHEMA paperclip REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Expected governance denials return allowed = false so their audit evidence commits.
CREATE TYPE paperclip.governance_result AS (allowed boolean, reason_code text, governance_id uuid);

CREATE TABLE paperclip.schema_migrations (version text PRIMARY KEY, checksum_sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE paperclip.tenants (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE paperclip.agents (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id), agent_key text NOT NULL, is_active boolean NOT NULL DEFAULT true, budget_exhausted boolean NOT NULL DEFAULT false, monthly_budget_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (monthly_budget_usd >= 0), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, id), UNIQUE (tenant_id, agent_key));
CREATE TABLE paperclip.policy_versions (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id), policy_key text NOT NULL, version text NOT NULL, policy_document jsonb NOT NULL, checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'), is_active boolean NOT NULL DEFAULT false, activated_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, id), UNIQUE (tenant_id, policy_key, version));
CREATE UNIQUE INDEX policy_one_active ON paperclip.policy_versions (tenant_id, policy_key) WHERE is_active;
CREATE TABLE paperclip.initiatives (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id), code text NOT NULL, UNIQUE (tenant_id, id), UNIQUE (tenant_id, code));
CREATE TABLE paperclip.governance_tasks (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id), initiative_id uuid, task_key text NOT NULL, status text NOT NULL DEFAULT 'pending', UNIQUE (tenant_id, id), UNIQUE (tenant_id, task_key), FOREIGN KEY (tenant_id, initiative_id) REFERENCES paperclip.initiatives (tenant_id, id));
CREATE TABLE paperclip.action_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id),
    requested_by_agent_id uuid NOT NULL,
    policy_version_id uuid NOT NULL,
    action_key text NOT NULL CHECK (action_key ~ '^[A-Z][A-Z0-9_]{1,63}$'),
    target_system text NOT NULL CHECK (target_system IN ('ZIPPY', 'ODOO', 'EXTERNAL', 'PAPERCLIP')),
    entity_type text NOT NULL CHECK (entity_type ~ '^[a-z][a-z0-9_.]{0,63}$'),
    entity_id text NOT NULL CHECK (length(entity_id) BETWEEN 1 AND 160),
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 200),
    decision text NOT NULL DEFAULT 'PENDING' CHECK (decision IN ('PENDING', 'APPROVED', 'REJECTED')),
    high_risk boolean NOT NULL,
    loop_fingerprint text NOT NULL CHECK (loop_fingerprint ~ '^[0-9a-f]{64}$'),
    loop_count integer NOT NULL CHECK (loop_count >= 1),
    loop_blocked boolean NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, idempotency_key),
    FOREIGN KEY (tenant_id, requested_by_agent_id) REFERENCES paperclip.agents (tenant_id, id),
    FOREIGN KEY (tenant_id, policy_version_id) REFERENCES paperclip.policy_versions (tenant_id, id)
);
CREATE INDEX action_proposals_loop_window ON paperclip.action_proposals (tenant_id, loop_fingerprint, created_at);
CREATE TABLE paperclip.invariant_results (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, proposal_id uuid NOT NULL, invariant_code text NOT NULL CHECK (length(invariant_code) BETWEEN 1 AND 80), passed boolean NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, proposal_id, invariant_code), FOREIGN KEY (tenant_id, proposal_id) REFERENCES paperclip.action_proposals (tenant_id, id));
CREATE TABLE paperclip.decision_locks (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, proposal_id uuid NOT NULL, holder_ref text NOT NULL CHECK (length(holder_ref) BETWEEN 1 AND 160), reason text NOT NULL, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), released_at timestamptz, released_by text, release_reason text, UNIQUE (tenant_id, id), FOREIGN KEY (tenant_id, proposal_id) REFERENCES paperclip.action_proposals (tenant_id, id));
CREATE UNIQUE INDEX decision_locks_one_active ON paperclip.decision_locks (tenant_id, proposal_id) WHERE active;
CREATE TABLE paperclip.human_approvals (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, proposal_id uuid NOT NULL, approver_ref text NOT NULL CHECK (length(approver_ref) BETWEEN 1 AND 160), status text NOT NULL CHECK (status IN ('APPROVED', 'REJECTED')), expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, proposal_id), FOREIGN KEY (tenant_id, proposal_id) REFERENCES paperclip.action_proposals (tenant_id, id));
CREATE TABLE paperclip.execution_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    agent_id uuid NOT NULL,
    action_key text NOT NULL,
    target_system text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    nonce uuid NOT NULL DEFAULT gen_random_uuid(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    revoked_at timestamptz,
    revoked_by text,
    revoke_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at <= created_at + interval '5 minutes'),
    CHECK (consumed_at IS NULL OR revoked_at IS NULL),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, proposal_id),
    UNIQUE (nonce),
    FOREIGN KEY (tenant_id, proposal_id) REFERENCES paperclip.action_proposals (tenant_id, id),
    FOREIGN KEY (tenant_id, agent_id) REFERENCES paperclip.agents (tenant_id, id)
);
CREATE TABLE paperclip.execution_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    grant_id uuid NOT NULL,
    agent_id uuid NOT NULL,
    action_key text NOT NULL,
    target_system text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('CONSUMED', 'ATTEMPTED', 'SUCCEEDED', 'FAILED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, grant_id, request_fingerprint),
    FOREIGN KEY (tenant_id, grant_id) REFERENCES paperclip.execution_grants (tenant_id, id),
    FOREIGN KEY (tenant_id, agent_id) REFERENCES paperclip.agents (tenant_id, id)
);
CREATE TABLE paperclip.heartbeats (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, agent_id uuid NOT NULL, task_id uuid, run_key text NOT NULL CHECK (length(run_key) BETWEEN 1 AND 160), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, id), UNIQUE (tenant_id, run_key), FOREIGN KEY (tenant_id, agent_id) REFERENCES paperclip.agents (tenant_id, id), FOREIGN KEY (tenant_id, task_id) REFERENCES paperclip.governance_tasks (tenant_id, id));
CREATE TABLE paperclip.token_cost_ledger (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, agent_id uuid NOT NULL, heartbeat_id uuid, cost_usd numeric(14,6) NOT NULL CHECK (cost_usd >= 0), created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY (tenant_id, agent_id) REFERENCES paperclip.agents (tenant_id, id), FOREIGN KEY (tenant_id, heartbeat_id) REFERENCES paperclip.heartbeats (tenant_id, id));
CREATE TABLE paperclip.loop_guard_events (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, proposal_id uuid NOT NULL, fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'), equivalent_count integer NOT NULL, action_taken text NOT NULL CHECK (action_taken = 'BLOCK'), created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY (tenant_id, proposal_id) REFERENCES paperclip.action_proposals (tenant_id, id));
CREATE TABLE paperclip.governance_activity_log (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id), actor_ref text NOT NULL, event_type text NOT NULL CHECK (event_type ~ '^[a-z_]+\.[a-z_]+$'), object_id uuid, reason text, correlation_id uuid NOT NULL DEFAULT gen_random_uuid(), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE paperclip.governance_outbox (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES paperclip.tenants(id), event_type text NOT NULL, aggregate_id uuid NOT NULL, idempotency_key text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, idempotency_key));

CREATE FUNCTION paperclip.current_tenant() RETURNS uuid
LANGUAGE plpgsql STABLE
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    v uuid;
BEGIN
    BEGIN
        v := nullif(current_setting('paperclip.tenant_id', true), '')::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'tenant context invalid';
    END;
    IF v IS NULL THEN
        RAISE EXCEPTION 'tenant context required';
    END IF;
    -- The migrator bootstraps tenant rows before any application role exists.
    IF current_user <> 'paperclip_migrator' AND NOT EXISTS (SELECT 1 FROM paperclip.tenants WHERE id = v AND is_active) THEN
        RAISE EXCEPTION 'tenant context invalid';
    END IF;
    RETURN v;
END $$;

CREATE FUNCTION paperclip.proposal_fingerprint(p_action text, p_target text, p_type text, p_entity text, p_hash text)
RETURNS text
LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
    SELECT encode(public.digest(concat_ws('|', p_action, p_target, p_type, p_entity, p_hash), 'sha256'), 'hex')
$$;

CREATE FUNCTION paperclip.create_proposal(p_agent uuid, p_policy uuid, p_action text, p_target text, p_type text, p_entity text, p_payload jsonb, p_key text, p_expiry timestamptz)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    existing uuid;
    new_id uuid;
    fingerprint text;
    payload_hash text;
BEGIN
    IF p_expiry <= now() THEN
        RAISE EXCEPTION 'proposal expired';
    END IF;
    payload_hash := encode(public.digest(p_payload::text, 'sha256'), 'hex');
    fingerprint := paperclip.proposal_fingerprint(p_action, p_target, p_type, p_entity, payload_hash);
    -- Serialize equivalent proposals per tenant so concurrent callers cannot bypass the loop threshold.
    PERFORM pg_advisory_xact_lock(hashtextextended(t::text || ':' || fingerprint, 0));
    SELECT id INTO existing FROM paperclip.action_proposals WHERE tenant_id = t AND idempotency_key = p_key;
    IF existing IS NOT NULL THEN
        RETURN ROW(true, 'PROPOSAL_EXISTS', existing)::paperclip.governance_result;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM paperclip.agents WHERE tenant_id = t AND id = p_agent AND is_active) THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, reason)
        VALUES (t, p_agent::text, 'proposal.denied', 'AGENT_INACTIVE');
        RETURN ROW(false, 'AGENT_INACTIVE', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM paperclip.policy_versions WHERE tenant_id = t AND id = p_policy AND is_active
                    AND checksum_sha256 = encode(public.digest(policy_document::text, 'sha256'), 'hex')) THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, reason)
        VALUES (t, p_agent::text, 'proposal.denied', 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH');
        RETURN ROW(false, 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH', NULL::uuid)::paperclip.governance_result;
    END IF;
    new_id := gen_random_uuid();
    INSERT INTO paperclip.action_proposals (
        id, tenant_id, requested_by_agent_id, policy_version_id, action_key, target_system, entity_type, entity_id,
        payload_hash, idempotency_key, high_risk, loop_fingerprint, loop_count, loop_blocked, expires_at
    )
    SELECT new_id, t_2, p_agent, p_policy, p_action, p_target, p_type, p_entity, payload_hash, p_key,
           (p_action = ANY (ARRAY['REFUND', 'SETTLEMENT_RELEASE', 'ODOO_POSTING', 'ODOO_RECONCILIATION', 'FINANCIAL_ADJUSTMENT', 'POLICY_CHANGE', 'PERMISSION_CHANGE', 'PRODUCTION_ACTION'])),
           fingerprint, fingerprint_count + 1, fingerprint_count + 1 >= 3, p_expiry
    FROM (SELECT t AS t_2, count(*) AS fingerprint_count FROM paperclip.action_proposals
          WHERE tenant_id = t AND loop_fingerprint = fingerprint AND created_at > now() - interval '10 minutes') counts;
    IF (SELECT loop_blocked FROM paperclip.action_proposals WHERE id = new_id) THEN
        INSERT INTO paperclip.loop_guard_events (tenant_id, proposal_id, fingerprint, equivalent_count, action_taken)
        SELECT tenant_id, id, fingerprint, loop_count, 'BLOCK' FROM paperclip.action_proposals WHERE id = new_id;
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'loop_guard.triggered', new_id, 'third equivalent proposal within ten minutes');
        RETURN ROW(false, 'LOOP_GUARD_TRIGGERED', new_id)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id)
    VALUES (t, p_agent::text, 'proposal.created', new_id);
    RETURN ROW(true, 'PROPOSAL_CREATED', new_id)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.record_invariant(p_proposal uuid, p_code text, p_passed boolean)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
BEGIN
    INSERT INTO paperclip.invariant_results (tenant_id, proposal_id, invariant_code, passed)
    VALUES (t, p_proposal, p_code, p_passed)
    ON CONFLICT (tenant_id, proposal_id, invariant_code) DO NOTHING;
END $$;

CREATE FUNCTION paperclip.acquire_decision_lock(p_proposal uuid, p_holder text, p_reason text)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    new_id uuid;
BEGIN
    PERFORM 1 FROM paperclip.action_proposals WHERE tenant_id = t AND id = p_proposal FOR UPDATE;
    IF NOT FOUND THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_holder, 'decision_lock.denied', p_proposal, 'PROPOSAL_NOT_FOUND');
        RETURN ROW(false, 'PROPOSAL_NOT_FOUND', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF EXISTS (SELECT 1 FROM paperclip.decision_locks WHERE tenant_id = t AND proposal_id = p_proposal AND active) THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_holder, 'decision_lock.denied', p_proposal, 'DECISION_LOCK_ACTIVE');
        RETURN ROW(false, 'DECISION_LOCK_ACTIVE', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.decision_locks (tenant_id, proposal_id, holder_ref, reason) VALUES (t, p_proposal, p_holder, p_reason) RETURNING id INTO new_id;
    RETURN ROW(true, 'DECISION_LOCK_ACQUIRED', new_id)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.release_decision_lock(p_proposal uuid, p_holder text)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    released uuid;
BEGIN
    UPDATE paperclip.decision_locks
    SET active = false, released_at = now(), released_by = p_holder, release_reason = 'holder release'
    WHERE tenant_id = t AND proposal_id = p_proposal AND active AND holder_ref = p_holder
    RETURNING id INTO released;
    IF released IS NULL THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_holder, 'decision_lock.denied', p_proposal, 'DECISION_LOCK_NOT_HELD');
        RETURN ROW(false, 'DECISION_LOCK_NOT_HELD', NULL::uuid)::paperclip.governance_result;
    END IF;
    RETURN ROW(true, 'DECISION_LOCK_RELEASED', released)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.decide(p_proposal uuid, p_approver text, p_approved boolean, p_expiry timestamptz)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    requester uuid;
    current_decision text;
BEGIN
    SELECT requested_by_agent_id, decision INTO requester, current_decision
    FROM paperclip.action_proposals WHERE tenant_id = t AND id = p_proposal FOR UPDATE;
    IF requester IS NULL THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_approver, 'approval.denied', p_proposal, 'PROPOSAL_NOT_FOUND');
        RETURN ROW(false, 'PROPOSAL_NOT_FOUND', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF current_decision <> 'PENDING' THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_approver, 'approval.denied', p_proposal, 'DECISION_ALREADY_RECORDED');
        RETURN ROW(false, 'DECISION_ALREADY_RECORDED', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF requester::text = p_approver THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_approver, 'approval.denied', p_proposal, 'SELF_APPROVAL_DENIED');
        INSERT INTO paperclip.governance_outbox (tenant_id, event_type, aggregate_id, idempotency_key)
        VALUES (t, 'approval.denied', p_proposal, 'approval.denied:' || p_proposal::text || ':SELF_APPROVAL_DENIED')
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;
        RETURN ROW(false, 'SELF_APPROVAL_DENIED', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.human_approvals (tenant_id, proposal_id, approver_ref, status, expires_at)
    VALUES (t, p_proposal, p_approver, CASE WHEN p_approved THEN 'APPROVED' ELSE 'REJECTED' END, p_expiry)
    ON CONFLICT (tenant_id, proposal_id) DO NOTHING;
    UPDATE paperclip.action_proposals SET decision = CASE WHEN p_approved THEN 'APPROVED' ELSE 'REJECTED' END WHERE tenant_id = t AND id = p_proposal;
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
    VALUES (t, p_approver, 'approval.recorded', p_proposal, CASE WHEN p_approved THEN 'APPROVED' ELSE 'REJECTED' END);
    RETURN ROW(true, CASE WHEN p_approved THEN 'APPROVED' ELSE 'REJECTED' END, p_proposal)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.issue_grant(p_proposal uuid)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    g uuid;
    reason text;
    v_loop_blocked boolean;
    v_has_lock boolean;
    v_invariant_fail boolean;
    v_policy_ok boolean;
    v_agent_ok boolean;
    v_approved boolean;
    v_already_issued boolean;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(t::text || ':grant:' || p_proposal::text, 0));
    PERFORM 1 FROM paperclip.action_proposals WHERE tenant_id = t AND id = p_proposal FOR UPDATE;
    SELECT p.loop_blocked INTO v_loop_blocked FROM paperclip.action_proposals p WHERE p.tenant_id = t AND p.id = p_proposal;
    v_already_issued := EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE tenant_id = t AND proposal_id = p_proposal);
    v_has_lock := EXISTS (SELECT 1 FROM paperclip.decision_locks WHERE tenant_id = t AND proposal_id = p_proposal AND active);
    v_invariant_fail := EXISTS (SELECT 1 FROM paperclip.invariant_results WHERE tenant_id = t AND proposal_id = p_proposal AND NOT passed);
    v_policy_ok := EXISTS (SELECT 1 FROM paperclip.action_proposals p JOIN paperclip.policy_versions v ON (v.tenant_id = p.tenant_id AND v.id = p.policy_version_id)
                           WHERE p.tenant_id = t AND p.id = p_proposal AND v.is_active AND v.checksum_sha256 = encode(public.digest(v.policy_document::text, 'sha256'), 'hex'));
    v_agent_ok := EXISTS (SELECT 1 FROM paperclip.action_proposals p JOIN paperclip.agents a ON (a.tenant_id = p.tenant_id AND a.id = p.requested_by_agent_id)
                          WHERE p.tenant_id = t AND p.id = p_proposal AND a.is_active AND NOT a.budget_exhausted);
    v_approved := EXISTS (SELECT 1 FROM paperclip.action_proposals p JOIN paperclip.human_approvals h ON (h.tenant_id = p.tenant_id AND h.proposal_id = p.id)
                          WHERE p.tenant_id = t AND p.id = p_proposal AND p.decision = 'APPROVED' AND h.status = 'APPROVED' AND h.expires_at > now());
    reason := CASE
        WHEN v_loop_blocked IS NULL THEN 'PROPOSAL_NOT_FOUND'
        WHEN v_already_issued THEN 'GRANT_ALREADY_ISSUED'
        WHEN v_loop_blocked THEN 'LOOP_GUARD_TRIGGERED'
        WHEN v_has_lock THEN 'DECISION_LOCK_ACTIVE'
        WHEN v_invariant_fail THEN 'INVARIANT_FAILED'
        WHEN NOT v_policy_ok THEN 'POLICY_INACTIVE_OR_CHECKSUM_MISMATCH'
        WHEN NOT v_agent_ok THEN 'AGENT_INACTIVE_OR_BUDGET_EXHAUSTED'
        WHEN NOT v_approved THEN 'APPROVAL_MISSING_REJECTED_OR_EXPIRED'
    END;
    IF reason IS NOT NULL THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, 'paperclip', 'grant.denied', p_proposal, reason);
        INSERT INTO paperclip.governance_outbox (tenant_id, event_type, aggregate_id, idempotency_key)
        VALUES (t, 'grant.denied', p_proposal, 'grant.denied:' || p_proposal::text || ':' || reason)
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;
        RETURN ROW(false, reason, NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.execution_grants (tenant_id, proposal_id, agent_id, action_key, target_system, entity_type, entity_id, payload_hash, expires_at)
    SELECT tenant_id, id, requested_by_agent_id, action_key, target_system, entity_type, entity_id, payload_hash, least(expires_at, now() + interval '5 minutes')
    FROM paperclip.action_proposals WHERE tenant_id = t AND id = p_proposal
    RETURNING id INTO g;
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id) VALUES (t, 'paperclip', 'grant.issued', g);
    INSERT INTO paperclip.governance_outbox (tenant_id, event_type, aggregate_id, idempotency_key)
    VALUES (t, 'grant.issued', g, 'grant.issued:' || g::text)
    ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;
    RETURN ROW(true, 'GRANT_ISSUED', g)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.revoke_grant(p_grant uuid, p_actor text, p_reason text)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    revoked uuid;
BEGIN
    UPDATE paperclip.execution_grants
    SET revoked_at = now(), revoked_by = p_actor, revoke_reason = p_reason
    WHERE tenant_id = t AND id = p_grant AND consumed_at IS NULL AND revoked_at IS NULL AND expires_at > now()
    RETURNING id INTO revoked;
    IF revoked IS NULL THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_actor, 'grant.denied', p_grant, 'GRANT_REVOCATION_INVALID');
        RETURN ROW(false, 'GRANT_REVOCATION_INVALID', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
    VALUES (t, p_actor, 'grant.revoked', revoked, p_reason);
    RETURN ROW(true, 'GRANT_REVOKED', revoked)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.record_execution_attempt(p_grant uuid, p_agent uuid, p_action text, p_target text, p_type text, p_entity text, p_fingerprint text, p_status text)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    attempt uuid;
BEGIN
    IF p_status NOT IN ('CONSUMED', 'ATTEMPTED', 'SUCCEEDED', 'FAILED') THEN
        RAISE EXCEPTION 'invalid execution attempt status';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM paperclip.execution_grants WHERE tenant_id = t AND id = p_grant AND agent_id = p_agent
                    AND action_key = p_action AND target_system = p_target AND entity_type = p_type AND entity_id = p_entity) THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'execution_attempt.denied', p_grant, 'EXECUTION_ATTEMPT_MISMATCH');
        RETURN ROW(false, 'EXECUTION_ATTEMPT_MISMATCH', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.execution_attempts (tenant_id, grant_id, agent_id, action_key, target_system, entity_type, entity_id, request_fingerprint, status)
    VALUES (t, p_grant, p_agent, p_action, p_target, p_type, p_entity, p_fingerprint, p_status)
    ON CONFLICT (tenant_id, grant_id, request_fingerprint) DO NOTHING
    RETURNING id INTO attempt;
    IF attempt IS NULL THEN
        RETURN ROW(true, 'EXECUTION_ATTEMPT_DUPLICATE', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id) VALUES (t, p_agent::text, 'execution_attempt.recorded', attempt);
    RETURN ROW(true, 'EXECUTION_ATTEMPT_RECORDED', attempt)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.consume_grant(p_grant uuid, p_agent uuid, p_action text, p_target text, p_type text, p_entity text, p_hash text)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
BEGIN
    UPDATE paperclip.execution_grants SET consumed_at = now()
    WHERE tenant_id = t AND id = p_grant AND agent_id = p_agent AND action_key = p_action AND target_system = p_target
      AND entity_type = p_type AND entity_id = p_entity AND payload_hash = p_hash
      AND consumed_at IS NULL AND revoked_at IS NULL AND expires_at > now();
    IF NOT FOUND THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'grant.denied', p_grant, 'GRANT_CONSUMPTION_DENIED');
        INSERT INTO paperclip.governance_outbox (tenant_id, event_type, aggregate_id, idempotency_key)
        VALUES (t, 'grant.consumption.denied', p_grant, 'grant.consumption.denied:' || p_grant::text || ':' || p_agent::text || ':GRANT_CONSUMPTION_DENIED')
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;
        RETURN ROW(false, 'GRANT_CONSUMPTION_DENIED', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.execution_attempts (tenant_id, grant_id, agent_id, action_key, target_system, entity_type, entity_id, request_fingerprint, status)
    VALUES (t, p_grant, p_agent, p_action, p_target, p_type, p_entity, p_hash, 'CONSUMED');
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id) VALUES (t, p_agent::text, 'grant.consumed', p_grant);
    RETURN ROW(true, 'GRANT_CONSUMED', p_grant)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.record_heartbeat(p_agent uuid, p_task uuid, p_run_key text)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    hb uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM paperclip.agents WHERE tenant_id = t AND id = p_agent AND is_active) THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'heartbeat.denied', NULL, 'HEARTBEAT_DENIED');
        RETURN ROW(false, 'HEARTBEAT_DENIED', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF p_task IS NOT NULL AND NOT EXISTS (SELECT 1 FROM paperclip.governance_tasks WHERE tenant_id = t AND id = p_task) THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'heartbeat.denied', NULL, 'HEARTBEAT_DENIED');
        RETURN ROW(false, 'HEARTBEAT_DENIED', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.heartbeats (tenant_id, agent_id, task_id, run_key) VALUES (t, p_agent, p_task, p_run_key)
    ON CONFLICT (tenant_id, run_key) DO NOTHING
    RETURNING id INTO hb;
    IF hb IS NULL THEN
        RETURN ROW(true, 'HEARTBEAT_DUPLICATE', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id) VALUES (t, p_agent::text, 'heartbeat.recorded', hb);
    RETURN ROW(true, 'HEARTBEAT_RECORDED', hb)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.record_token_cost(p_agent uuid, p_heartbeat uuid, p_cost numeric)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    cost_id uuid;
    budget_ok boolean;
BEGIN
    IF p_cost < 0 THEN
        RAISE EXCEPTION 'negative cost rejected';
    END IF;
    PERFORM 1 FROM paperclip.agents WHERE tenant_id = t AND id = p_agent FOR UPDATE;
    SELECT (NOT a.budget_exhausted) AND a.is_active AND (a.monthly_budget_usd - coalesce(spend.total, 0) - p_cost) >= 0
    INTO budget_ok
    FROM paperclip.agents a
    LEFT JOIN (SELECT agent_id, sum(cost_usd) AS total FROM paperclip.token_cost_ledger WHERE tenant_id = t GROUP BY agent_id) spend ON spend.agent_id = a.id
    WHERE a.tenant_id = t AND a.id = p_agent;
    IF budget_ok IS NULL THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'budget.denied', NULL, 'AGENT_NOT_FOUND');
        RETURN ROW(false, 'AGENT_NOT_FOUND', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF NOT budget_ok THEN
        UPDATE paperclip.agents SET budget_exhausted = true WHERE tenant_id = t AND id = p_agent;
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, p_agent::text, 'budget.denied', NULL, 'BUDGET_EXCEEDED');
        RETURN ROW(false, 'BUDGET_EXCEEDED', NULL::uuid)::paperclip.governance_result;
    END IF;
    INSERT INTO paperclip.token_cost_ledger (tenant_id, agent_id, heartbeat_id, cost_usd) VALUES (t, p_agent, p_heartbeat, p_cost) RETURNING id INTO cost_id;
    RETURN ROW(true, 'TOKEN_COST_RECORDED', cost_id)::paperclip.governance_result;
END $$;

CREATE FUNCTION paperclip.evaluate_loop_guard(p_proposal uuid)
RETURNS paperclip.governance_result
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
DECLARE
    t uuid := paperclip.current_tenant();
    blocked boolean;
BEGIN
    SELECT p.loop_blocked INTO blocked FROM paperclip.action_proposals p WHERE p.tenant_id = t AND p.id = p_proposal FOR UPDATE;
    IF blocked IS NULL THEN
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, 'paperclip', 'loop_guard.denied', p_proposal, 'PROPOSAL_NOT_FOUND');
        RETURN ROW(false, 'PROPOSAL_NOT_FOUND', NULL::uuid)::paperclip.governance_result;
    END IF;
    IF blocked THEN
        INSERT INTO paperclip.loop_guard_events (tenant_id, proposal_id, fingerprint, equivalent_count, action_taken)
        SELECT tenant_id, id, loop_fingerprint, loop_count, 'BLOCK' FROM paperclip.action_proposals WHERE tenant_id = t AND id = p_proposal
        ON CONFLICT DO NOTHING;
        INSERT INTO paperclip.governance_activity_log (tenant_id, actor_ref, event_type, object_id, reason)
        VALUES (t, 'paperclip', 'loop_guard.triggered', p_proposal, 'LOOP_GUARD_TRIGGERED');
        RETURN ROW(false, 'LOOP_GUARD_TRIGGERED', NULL::uuid)::paperclip.governance_result;
    END IF;
    RETURN ROW(true, 'LOOP_GUARD_CLEAR', p_proposal)::paperclip.governance_result;
END $$;

-- Privileges must be set while the migrator still owns the functions; after transfer these become no-ops.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA paperclip FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA paperclip TO paperclip_app;
GRANT USAGE ON SCHEMA paperclip TO paperclip_function_owner;
GRANT EXECUTE ON FUNCTION paperclip.current_tenant() TO paperclip_function_owner;
GRANT EXECUTE ON FUNCTION paperclip.proposal_fingerprint(text, text, text, text, text) TO paperclip_function_owner;

-- ALTER ... OWNER requires the new owner to hold CREATE on the schema; it is revoked immediately after.
GRANT CREATE ON SCHEMA paperclip TO paperclip_function_owner;
ALTER FUNCTION paperclip.create_proposal(uuid, uuid, text, text, text, text, jsonb, text, timestamptz) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.record_invariant(uuid, text, boolean) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.acquire_decision_lock(uuid, text, text) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.release_decision_lock(uuid, text) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.decide(uuid, text, boolean, timestamptz) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.issue_grant(uuid) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.consume_grant(uuid, uuid, text, text, text, text, text) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.revoke_grant(uuid, text, text) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.record_execution_attempt(uuid, uuid, text, text, text, text, text, text) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.record_heartbeat(uuid, uuid, text) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.record_token_cost(uuid, uuid, numeric) OWNER TO paperclip_function_owner;
ALTER FUNCTION paperclip.evaluate_loop_guard(uuid) OWNER TO paperclip_function_owner;
REVOKE CREATE ON SCHEMA paperclip FROM paperclip_function_owner;

REVOKE ALL ON ALL TABLES IN SCHEMA paperclip FROM PUBLIC, paperclip_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA paperclip FROM PUBLIC, paperclip_app;
REVOKE ALL ON TYPE paperclip.governance_result FROM PUBLIC;
GRANT USAGE ON TYPE paperclip.governance_result TO paperclip_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA paperclip TO paperclip_function_owner;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA paperclip TO paperclip_function_owner;
GRANT USAGE ON SCHEMA paperclip TO paperclip_app;

-- Append-only evidence: runtime mutation of audit/outbox is rejected even where a role holds row privileges.
CREATE FUNCTION paperclip.reject_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, paperclip, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION 'governance evidence is append-only';
END $$;
CREATE TRIGGER governance_activity_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON paperclip.governance_activity_log FOR EACH STATEMENT EXECUTE FUNCTION paperclip.reject_evidence_mutation();
CREATE TRIGGER governance_outbox_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON paperclip.governance_outbox FOR EACH STATEMENT EXECUTE FUNCTION paperclip.reject_evidence_mutation();

-- current_tenant() reads tenants, so this policy must read the setting directly to avoid policy recursion.
CREATE POLICY tenant_self ON paperclip.tenants
    USING (id = nullif(current_setting('paperclip.tenant_id', true), '')::uuid)
    WITH CHECK (id = nullif(current_setting('paperclip.tenant_id', true), '')::uuid);
ALTER TABLE paperclip.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE paperclip.tenants FORCE ROW LEVEL SECURITY;
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'paperclip' AND c.relkind = 'r' AND c.relname NOT IN ('schema_migrations', 'tenants')
    LOOP
        EXECUTE format('ALTER TABLE paperclip.%I ENABLE ROW LEVEL SECURITY; ALTER TABLE paperclip.%I FORCE ROW LEVEL SECURITY; CREATE POLICY tenant_isolation ON paperclip.%I USING (tenant_id = paperclip.current_tenant()) WITH CHECK (tenant_id = paperclip.current_tenant())', r.relname, r.relname, r.relname);
    END LOOP;
END $$;