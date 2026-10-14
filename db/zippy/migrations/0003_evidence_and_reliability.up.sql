BEGIN;

CREATE TYPE zippy.processing_status AS ENUM ('pending', 'processing', 'succeeded', 'failed', 'dead_lettered');
CREATE TYPE zippy.financial_request_status AS ENUM ('requested', 'approved_for_send', 'sent', 'acknowledged', 'rejected', 'failed');
CREATE TYPE zippy.refund_status AS ENUM ('requested', 'approved', 'rejected', 'executed', 'failed');
CREATE TYPE zippy.exception_status AS ENUM ('open', 'assigned', 'resolved', 'closed');

CREATE TABLE zippy.webhook_receipts (
    webhook_receipt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    provider text NOT NULL,
    provider_event_id text NOT NULL,
    signature_verified boolean NOT NULL DEFAULT false,
    payload_hash_sha256 text NOT NULL CHECK (payload_hash_sha256 ~ '^[0-9a-f]{64}$'),
    payload_reference text,
    processing_status zippy.processing_status NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    correlation_id uuid NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    processed_at timestamptz,
    UNIQUE (platform_id, webhook_receipt_id),
    UNIQUE (platform_id, provider, provider_event_id)
);

CREATE TABLE zippy.gateway_events (
    gateway_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    webhook_receipt_id uuid NOT NULL,
    order_id uuid NOT NULL,
    gateway text NOT NULL,
    gateway_event_type text NOT NULL,
    amount numeric(18,2) NOT NULL CHECK (amount >= 0),
    currency_code varchar(3) NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
    evidence_hash_sha256 text NOT NULL CHECK (evidence_hash_sha256 ~ '^[0-9a-f]{64}$'),
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, gateway_event_id),
    UNIQUE (platform_id, webhook_receipt_id),
    FOREIGN KEY (platform_id, webhook_receipt_id) REFERENCES zippy.webhook_receipts(platform_id, webhook_receipt_id),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id)
);

CREATE TABLE zippy.payment_projections (
    payment_projection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    gateway_event_id uuid NOT NULL,
    operational_status text NOT NULL CHECK (operational_status IN ('pending', 'evidence_verified', 'failed', 'reversed')),
    amount numeric(18,2) NOT NULL CHECK (amount >= 0),
    currency_code varchar(3) NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
    correlation_id uuid NOT NULL,
    projected_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, payment_projection_id),
    UNIQUE (platform_id, order_id, gateway_event_id, operational_status),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, gateway_event_id) REFERENCES zippy.gateway_events(platform_id, gateway_event_id)
);

CREATE TABLE zippy.financial_requests (
    financial_request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    request_type text NOT NULL CHECK (request_type IN ('partner_sync', 'draft_customer_invoice', 'draft_vendor_bill', 'read_status')),
    amount numeric(18,2),
    currency_code varchar(3),
    status zippy.financial_request_status NOT NULL DEFAULT 'requested',
    requester_account_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_hash_sha256 text NOT NULL CHECK (request_hash_sha256 ~ '^[0-9a-f]{64}$'),
    correlation_id uuid NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, financial_request_id),
    UNIQUE (platform_id, request_type, idempotency_key),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, requester_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK ((amount IS NULL AND currency_code IS NULL) OR (amount >= 0 AND currency_code ~ '^[A-Z]{3}$'))
);

CREATE TABLE zippy.external_references (
    external_reference_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    local_entity_type text NOT NULL,
    local_entity_id uuid NOT NULL,
    external_system text NOT NULL,
    external_model text NOT NULL,
    external_id text NOT NULL,
    external_version text,
    sync_status text NOT NULL CHECK (sync_status IN ('pending', 'synchronized', 'stale', 'failed')),
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, external_reference_id),
    UNIQUE (platform_id, local_entity_type, local_entity_id, external_system, external_model),
    UNIQUE (platform_id, external_system, external_model, external_id)
);

CREATE TABLE zippy.settlement_projections (
    settlement_projection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    financial_request_id uuid NOT NULL,
    external_reference_id uuid,
    operational_status text NOT NULL CHECK (operational_status IN ('not_requested', 'requested', 'pending_external', 'externally_confirmed', 'failed')),
    source_observed_at timestamptz,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, settlement_projection_id),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, financial_request_id) REFERENCES zippy.financial_requests(platform_id, financial_request_id),
    FOREIGN KEY (platform_id, external_reference_id) REFERENCES zippy.external_references(platform_id, external_reference_id),
    CHECK ((operational_status = 'externally_confirmed' AND external_reference_id IS NOT NULL AND source_observed_at IS NOT NULL) OR operational_status <> 'externally_confirmed')
);

CREATE TABLE zippy.refund_requests (
    refund_request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    requester_account_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL CHECK (amount > 0),
    currency_code varchar(3) NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
    target_reference text NOT NULL,
    reason text NOT NULL,
    idempotency_key text NOT NULL,
    status zippy.refund_status NOT NULL DEFAULT 'requested',
    correlation_id uuid NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, refund_request_id),
    UNIQUE (platform_id, idempotency_key),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, requester_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.refund_decisions (
    refund_decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    refund_request_id uuid NOT NULL,
    approver_account_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason text NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    correlation_id uuid NOT NULL,
    UNIQUE (platform_id, refund_decision_id),
    UNIQUE (platform_id, refund_request_id),
    FOREIGN KEY (platform_id, refund_request_id) REFERENCES zippy.refund_requests(platform_id, refund_request_id),
    FOREIGN KEY (platform_id, approver_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.refund_executions (
    refund_execution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    refund_request_id uuid NOT NULL,
    refund_decision_id uuid NOT NULL,
    external_reference_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL CHECK (amount > 0),
    currency_code varchar(3) NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
    target_reference text NOT NULL,
    idempotency_key text NOT NULL,
    evidence_hash_sha256 text NOT NULL CHECK (evidence_hash_sha256 ~ '^[0-9a-f]{64}$'),
    executed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, refund_execution_id),
    UNIQUE (platform_id, refund_request_id),
    UNIQUE (platform_id, idempotency_key),
    FOREIGN KEY (platform_id, refund_request_id) REFERENCES zippy.refund_requests(platform_id, refund_request_id),
    FOREIGN KEY (platform_id, refund_decision_id) REFERENCES zippy.refund_decisions(platform_id, refund_decision_id),
    FOREIGN KEY (platform_id, external_reference_id) REFERENCES zippy.external_references(platform_id, external_reference_id)
);

CREATE TABLE zippy.idempotency_records (
    idempotency_record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    operation_scope text NOT NULL,
    idempotency_key text NOT NULL,
    request_hash_sha256 text NOT NULL CHECK (request_hash_sha256 ~ '^[0-9a-f]{64}$'),
    status zippy.processing_status NOT NULL DEFAULT 'pending',
    response_code integer,
    response_reference text,
    correlation_id uuid NOT NULL,
    lease_owner text,
    lease_expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    UNIQUE (platform_id, operation_scope, idempotency_key),
    CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL))
);

CREATE TABLE zippy.durable_tasks (
    durable_task_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    task_type text NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    payload_reference text NOT NULL,
    idempotency_key text NOT NULL,
    status zippy.processing_status NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts integer NOT NULL CHECK (max_attempts > 0),
    next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    lease_owner text,
    lease_expires_at timestamptz,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, durable_task_id),
    UNIQUE (platform_id, task_type, idempotency_key),
    CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)),
    CHECK (attempt_count <= max_attempts),
    CHECK (status <> 'dead_lettered' OR attempt_count = max_attempts)
);

CREATE TABLE zippy.event_outbox (
    outbox_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    aggregate_version integer NOT NULL CHECK (aggregate_version > 0),
    event_type text NOT NULL,
    destination text NOT NULL,
    payload jsonb NOT NULL,
    idempotency_key text NOT NULL,
    status zippy.processing_status NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz,
    UNIQUE (platform_id, outbox_event_id),
    UNIQUE (platform_id, destination, idempotency_key),
    UNIQUE (platform_id, aggregate_type, aggregate_id, aggregate_version, event_type),
    CHECK (jsonb_typeof(payload) = 'object')
);

CREATE TABLE zippy.event_inbox (
    inbox_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    source text NOT NULL,
    source_event_id text NOT NULL,
    payload_hash_sha256 text NOT NULL CHECK (payload_hash_sha256 ~ '^[0-9a-f]{64}$'),
    status zippy.processing_status NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    correlation_id uuid NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    processed_at timestamptz,
    UNIQUE (platform_id, inbox_event_id),
    UNIQUE (platform_id, source, source_event_id)
);

CREATE TABLE zippy.dead_letter_records (
    dead_letter_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    source_kind text NOT NULL CHECK (source_kind IN ('task', 'outbox', 'inbox', 'webhook')),
    source_id uuid NOT NULL,
    terminal_reason text NOT NULL,
    attempt_count integer NOT NULL CHECK (attempt_count > 0),
    payload_reference text,
    correlation_id uuid NOT NULL,
    dead_lettered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, source_kind, source_id)
);

CREATE TABLE zippy.audit_events (
    audit_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    actor_account_id uuid,
    actor_type text NOT NULL CHECK (actor_type IN ('account', 'service', 'system')),
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    before_hash_sha256 text CHECK (before_hash_sha256 IS NULL OR before_hash_sha256 ~ '^[0-9a-f]{64}$'),
    after_hash_sha256 text CHECK (after_hash_sha256 IS NULL OR after_hash_sha256 ~ '^[0-9a-f]{64}$'),
    reason text,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (platform_id, actor_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.operational_exceptions (
    operational_exception_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    exception_code text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    status zippy.exception_status NOT NULL DEFAULT 'open',
    owner_account_id uuid,
    reason text NOT NULL,
    correlation_id uuid NOT NULL,
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    resolved_at timestamptz,
    UNIQUE (platform_id, operational_exception_id),
    FOREIGN KEY (platform_id, owner_account_id) REFERENCES zippy.accounts(platform_id, account_id),
    CHECK ((status IN ('resolved', 'closed') AND resolved_at IS NOT NULL) OR status NOT IN ('resolved', 'closed'))
);

CREATE TABLE zippy.exception_status_history (
    exception_status_history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    operational_exception_id uuid NOT NULL,
    previous_status zippy.exception_status,
    new_status zippy.exception_status NOT NULL,
    actor_account_id uuid NOT NULL,
    reason text NOT NULL,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (platform_id, operational_exception_id) REFERENCES zippy.operational_exceptions(platform_id, operational_exception_id),
    FOREIGN KEY (platform_id, actor_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE TABLE zippy.service_commitments (
    service_commitment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    commitment_type text NOT NULL CHECK (commitment_type IN ('pickup', 'delivery', 'pod')),
    committed_at timestamptz NOT NULL,
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, service_commitment_id),
    UNIQUE (platform_id, order_id, commitment_type),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id)
);

CREATE TABLE zippy.sla_evidence (
    sla_evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    service_commitment_id uuid NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('met', 'breached', 'not_applicable')),
    evidence_reference text NOT NULL,
    measured_at timestamptz NOT NULL,
    correlation_id uuid NOT NULL,
    UNIQUE (platform_id, service_commitment_id),
    FOREIGN KEY (platform_id, service_commitment_id) REFERENCES zippy.service_commitments(platform_id, service_commitment_id)
);

CREATE TABLE zippy.notification_attempts (
    notification_attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    recipient_account_id uuid NOT NULL,
    channel text NOT NULL CHECK (channel IN ('email', 'sms', 'in_app')),
    template_version text NOT NULL,
    business_event_reference uuid NOT NULL,
    idempotency_key text NOT NULL,
    status zippy.processing_status NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at timestamptz,
    provider_reference text,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    delivered_at timestamptz,
    UNIQUE (platform_id, notification_attempt_id),
    UNIQUE (platform_id, channel, idempotency_key),
    FOREIGN KEY (platform_id, recipient_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

CREATE INDEX webhook_status_attempt_idx ON zippy.webhook_receipts (platform_id, processing_status, received_at);
CREATE INDEX payment_order_time_idx ON zippy.payment_projections (platform_id, order_id, projected_at DESC);
CREATE INDEX financial_request_status_idx ON zippy.financial_requests (platform_id, status, requested_at);
CREATE INDEX refund_order_status_idx ON zippy.refund_requests (platform_id, order_id, status);
CREATE INDEX durable_tasks_claim_idx ON zippy.durable_tasks (platform_id, status, next_attempt_at, created_at) WHERE status IN ('pending', 'failed');
CREATE INDEX outbox_claim_idx ON zippy.event_outbox (platform_id, status, next_attempt_at, created_at) WHERE status IN ('pending', 'failed');
CREATE INDEX inbox_status_idx ON zippy.event_inbox (platform_id, status, received_at);
CREATE INDEX audit_entity_time_idx ON zippy.audit_events (platform_id, entity_type, entity_id, occurred_at DESC);
CREATE INDEX exceptions_status_idx ON zippy.operational_exceptions (platform_id, status, severity, opened_at);
CREATE INDEX notifications_status_idx ON zippy.notification_attempts (platform_id, status, next_attempt_at);

COMMIT;