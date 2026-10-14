-- ============================================================
-- ZIPPY LOGISTICS — PAPERCLIP GOVERNANCE DATABASE
-- PostgreSQL 15+
-- PURPOSE:
--   Governance truth only.
--   Paperclip answers: "May this proposed action execute?"
--
-- MUST NOT own:
--   orders, trips, vehicle location, invoice balances, GL entries,
--   Odoo invoices, operational payment truth, customer logistics state.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------- ENUMS ----------
CREATE TYPE governance_decision AS ENUM (
    'PENDING',
    'APPROVED',
    'HOLD',
    'REJECTED',
    'HITL_REQUIRED',
    'EXPIRED',
    'CANCELLED'
);

CREATE TYPE risk_level AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE execution_status AS ENUM (
    'NOT_STARTED',
    'QUEUED',
    'EXECUTING',
    'SUCCEEDED',
    'FAILED',
    'BLOCKED',
    'CANCELLED'
);

CREATE TYPE task_status AS ENUM (
    'PENDING',
    'RUNNING',
    'COMPLETED',
    'BLOCKED',
    'FAILED',
    'REQUIRES_HUMAN_APPROVAL',
    'CANCELLED'
);

CREATE TYPE task_priority AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE heartbeat_trigger AS ENUM (
    'TIMER',
    'TASK_ASSIGNMENT',
    'MANUAL_RUN',
    'RETRY',
    'EVENT'
);

CREATE TYPE approval_status AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'EXPIRED',
    'CANCELLED'
);

-- ---------- TENANCY ----------
CREATE TABLE tenants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_company_id UUID, -- Zippy operational company/tenant reference only
    name                VARCHAR(255) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (external_company_id)
);

-- ---------- AGENT REGISTRY ----------
CREATE TABLE agents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_key           VARCHAR(80) NOT NULL, -- HERMES, HARNESS, PAPERCLIP, ODOO_AGENT
    display_name        VARCHAR(255) NOT NULL,
    model_provider      VARCHAR(100),
    model_name          VARCHAR(150),
    is_paused           BOOLEAN NOT NULL DEFAULT FALSE,
    monthly_budget_usd  NUMERIC(14,4) NOT NULL DEFAULT 0,
    capabilities        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, agent_key)
);

CREATE INDEX idx_agents_tenant ON agents(tenant_id);
CREATE INDEX idx_agents_active ON agents(tenant_id, is_paused);

-- ---------- POLICY VERSIONING ----------
CREATE TABLE policy_versions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    policy_key          VARCHAR(100) NOT NULL, -- FINANCIAL_GUARDRAILS, DISPATCH_GUARDRAILS
    version             VARCHAR(40) NOT NULL,
    policy_document     JSONB NOT NULL,
    checksum_sha256     VARCHAR(64) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
    activated_at        TIMESTAMPTZ,
    activated_by        VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, policy_key, version)
);

CREATE UNIQUE INDEX uq_active_policy_per_key
ON policy_versions(tenant_id, policy_key)
WHERE is_active = TRUE;

-- ---------- INITIATIVES / TASK QUEUE ----------
CREATE TABLE initiatives (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    initiative_code     VARCHAR(30) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    billing_code        VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, initiative_code)
);

CREATE TABLE tasks (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    initiative_id       UUID REFERENCES initiatives(id) ON DELETE SET NULL,
    parent_task_id      UUID REFERENCES tasks(id) ON DELETE SET NULL,
    assigned_agent_id   UUID REFERENCES agents(id) ON DELETE SET NULL,
    task_code           VARCHAR(40) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    context_mode        VARCHAR(10) NOT NULL CHECK (context_mode IN ('THIN','FAT')),
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              task_status NOT NULL DEFAULT 'PENDING',
    priority            task_priority NOT NULL DEFAULT 'MEDIUM',
    billing_code        VARCHAR(100),
    retry_count         INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries         INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    blocked_reason      TEXT,
    locked_at           TIMESTAMPTZ,
    locked_by           VARCHAR(255),
    available_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, task_code)
);

CREATE INDEX idx_tasks_claim
ON tasks(tenant_id, status, priority, available_at);

CREATE INDEX idx_tasks_agent
ON tasks(tenant_id, assigned_agent_id, status);

CREATE INDEX idx_tasks_parent ON tasks(parent_task_id);

-- ---------- GOVERNANCE ACTION PROPOSALS ----------
CREATE TABLE action_proposals (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    task_id                 UUID REFERENCES tasks(id) ON DELETE SET NULL,
    requested_by_agent_id   UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,

    -- Cross-system reference: never FK across databases
    target_system           VARCHAR(30) NOT NULL CHECK (
                                target_system IN ('ZIPPY','ODOO','EXTERNAL')
                            ),
    entity_type             VARCHAR(80) NOT NULL, -- order, payment, account.move, stock.picking
    entity_id               VARCHAR(160) NOT NULL, -- UUID or Odoo integer id serialized as text

    action_key              VARCHAR(120) NOT NULL, -- CREATE_INVOICE, POST_INVOICE, REFUND, ASSIGN_DRIVER
    idempotency_key         VARCHAR(200) NOT NULL,
    proposal_payload        JSONB NOT NULL,
    requested_amount        NUMERIC(16,2),
    currency                VARCHAR(3) DEFAULT 'INR',
    risk_level              risk_level NOT NULL DEFAULT 'LOW',

    policy_version_id       UUID REFERENCES policy_versions(id) ON DELETE RESTRICT,
    decision                governance_decision NOT NULL DEFAULT 'PENDING',
    decision_reason         TEXT,
    decision_metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,

    expires_at              TIMESTAMPTZ,
    decided_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX idx_proposals_entity
ON action_proposals(tenant_id, target_system, entity_type, entity_id);

CREATE INDEX idx_proposals_decision
ON action_proposals(tenant_id, decision, created_at DESC);

-- ---------- INVARIANT EVALUATION ----------
CREATE TABLE invariant_results (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         UUID NOT NULL REFERENCES action_proposals(id) ON DELETE CASCADE,
    invariant_code      VARCHAR(80) NOT NULL, -- PAY-INV-002, DSP-INV-001
    policy_version      VARCHAR(40),
    passed              BOOLEAN NOT NULL,
    severity            risk_level NOT NULL DEFAULT 'MEDIUM',
    observed_values     JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason              TEXT,
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (proposal_id, invariant_code)
);

CREATE INDEX idx_invariants_proposal ON invariant_results(proposal_id);

-- ---------- DECISION LOCK ----------
CREATE TABLE decision_locks (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         UUID NOT NULL REFERENCES action_proposals(id) ON DELETE CASCADE,
    lock_key            VARCHAR(160) NOT NULL,
    reason              TEXT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at         TIMESTAMPTZ,
    released_by         VARCHAR(255),
    release_reason      TEXT,
    UNIQUE (proposal_id, lock_key)
);

CREATE UNIQUE INDEX uq_active_lock
ON decision_locks(proposal_id)
WHERE is_active = TRUE;

-- ---------- HUMAN APPROVAL ----------
CREATE TABLE human_approvals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         UUID NOT NULL REFERENCES action_proposals(id) ON DELETE CASCADE,
    requested_role      VARCHAR(80) NOT NULL, -- ops_manager, finance_head, board
    status              approval_status NOT NULL DEFAULT 'PENDING',
    approver_user_ref   VARCHAR(160), -- external identity reference only
    decision_reason     TEXT,
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at          TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ
);

CREATE INDEX idx_human_approvals_pending
ON human_approvals(status, requested_role, requested_at);

-- ---------- APPROVED EXECUTION GRANT ----------
-- This is the anti-bypass object Hermes must present before consequential execution.
CREATE TABLE execution_grants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         UUID NOT NULL UNIQUE REFERENCES action_proposals(id) ON DELETE CASCADE,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    granted_to_agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
    capability          VARCHAR(120) NOT NULL,
    target_system       VARCHAR(30) NOT NULL,
    entity_type         VARCHAR(80) NOT NULL,
    entity_id           VARCHAR(160) NOT NULL,
    payload_hash        VARCHAR(64) NOT NULL,
    nonce               UUID NOT NULL DEFAULT uuid_generate_v4(),
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    consumed_at         TIMESTAMPTZ,
    revoked_at          TIMESTAMPTZ,
    revoke_reason       TEXT
);

CREATE INDEX idx_grants_agent
ON execution_grants(tenant_id, granted_to_agent_id, expires_at);

-- ---------- EXECUTION ATTEMPTS ----------
CREATE TABLE execution_attempts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         UUID NOT NULL REFERENCES action_proposals(id) ON DELETE CASCADE,
    grant_id            UUID REFERENCES execution_grants(id) ON DELETE SET NULL,
    executing_agent_id  UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
    target_system       VARCHAR(30) NOT NULL,
    operation           VARCHAR(120) NOT NULL,
    request_fingerprint VARCHAR(64) NOT NULL,
    status              execution_status NOT NULL DEFAULT 'NOT_STARTED',
    external_request_id VARCHAR(160),
    external_result_ref VARCHAR(255),
    response_summary    JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (proposal_id, request_fingerprint)
);

-- ---------- HEARTBEAT RUNS ----------
CREATE TABLE heartbeat_runs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id            UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    task_id             UUID REFERENCES tasks(id) ON DELETE SET NULL,
    trigger_type        heartbeat_trigger NOT NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'IN_PROGRESS'
                        CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED','LOOP_TERMINATED','CANCELLED')),
    run_key             VARCHAR(160) NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    exit_code           INTEGER,
    error_summary       TEXT,
    UNIQUE (tenant_id, run_key)
);

CREATE INDEX idx_heartbeats_agent
ON heartbeat_runs(tenant_id, agent_id, started_at DESC);

-- ---------- LOOP GUARDIAN ----------
CREATE TABLE loop_guard_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    heartbeat_id        UUID NOT NULL REFERENCES heartbeat_runs(id) ON DELETE CASCADE,
    task_id             UUID REFERENCES tasks(id) ON DELETE SET NULL,
    exact_repeat_count  INTEGER NOT NULL DEFAULT 0,
    semantic_similarity NUMERIC(5,4),
    db_state_changed    BOOLEAN,
    trigger_reason      TEXT NOT NULL,
    action_taken        VARCHAR(40) NOT NULL CHECK (
                            action_taken IN ('WARN','PAUSE','BLOCK_TASK','TERMINATE_RUN','ESCALATE')
                        ),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------- COST LEDGER ----------
CREATE TABLE token_billing_ledger (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id            UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
    heartbeat_id        UUID REFERENCES heartbeat_runs(id) ON DELETE RESTRICT,
    task_id             UUID REFERENCES tasks(id) ON DELETE RESTRICT,
    billing_code        VARCHAR(100),
    model_used          VARCHAR(150) NOT NULL,
    prompt_tokens       INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
    completion_tokens   INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
    cached_tokens       INTEGER NOT NULL DEFAULT 0 CHECK (cached_tokens >= 0),
    cost_usd            NUMERIC(14,6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_billing_agent_month
ON token_billing_ledger(tenant_id, agent_id, created_at DESC);

CREATE INDEX idx_billing_task ON token_billing_ledger(task_id);

-- ---------- APPEND-ONLY GOVERNANCE ACTIVITY ----------
CREATE TABLE governance_activity_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id            UUID REFERENCES agents(id) ON DELETE SET NULL,
    task_id             UUID REFERENCES tasks(id) ON DELETE SET NULL,
    proposal_id         UUID REFERENCES action_proposals(id) ON DELETE SET NULL,
    event_type          VARCHAR(120) NOT NULL,
    description         TEXT NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_governance_activity
ON governance_activity_log(tenant_id, created_at DESC);

-- ---------- OUTBOX ----------
-- Reliable publication of governance decisions to integration workers.
CREATE TABLE governance_outbox (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    aggregate_type      VARCHAR(80) NOT NULL,
    aggregate_id        UUID NOT NULL,
    event_type          VARCHAR(120) NOT NULL,
    payload             JSONB NOT NULL,
    idempotency_key     VARCHAR(200) NOT NULL,
    published_at        TIMESTAMPTZ,
    publish_attempts    INTEGER NOT NULL DEFAULT 0,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX idx_governance_outbox_pending
ON governance_outbox(created_at)
WHERE published_at IS NULL;

-- ---------- BUDGET CIRCUIT BREAKER ----------
CREATE OR REPLACE FUNCTION paperclip_check_agent_budget()
RETURNS TRIGGER AS $$
DECLARE
    month_spend NUMERIC(14,4);
    budget NUMERIC(14,4);
BEGIN
    SELECT COALESCE(SUM(cost_usd), 0)
      INTO month_spend
      FROM token_billing_ledger
     WHERE agent_id = NEW.agent_id
       AND created_at >= date_trunc('month', NOW());

    SELECT monthly_budget_usd
      INTO budget
      FROM agents
     WHERE id = NEW.agent_id;

    IF budget > 0 AND month_spend >= budget THEN
        UPDATE agents SET is_paused = TRUE, updated_at = NOW()
        WHERE id = NEW.agent_id;

        INSERT INTO governance_activity_log(
            tenant_id, agent_id, task_id, event_type, description
        ) VALUES (
            NEW.tenant_id,
            NEW.agent_id,
            NEW.task_id,
            'HARD_BUDGET_CEILING_HIT',
            'Agent automatically paused because its monthly budget ceiling was reached.'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_paperclip_budget
AFTER INSERT ON token_billing_ledger
FOR EACH ROW EXECUTE FUNCTION paperclip_check_agent_budget();

-- ============================================================
-- RELATIONSHIP SUMMARY
-- tenant
--   ├─ agents
--   ├─ policies
--   ├─ initiatives ── tasks ── heartbeat_runs ── cost ledger
--   └─ action_proposals
--        ├─ invariant_results
--        ├─ decision_locks
--        ├─ human_approvals
--        ├─ execution_grant
--        └─ execution_attempts
--
-- Cross-database entities use external IDs, NEVER cross-database FKs.
-- ============================================================
