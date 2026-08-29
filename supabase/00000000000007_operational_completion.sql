-- ============================================================
-- ZIPPY OPERATIONAL DB — COMPLETION / HARDENING MIGRATION
-- PostgreSQL 15+ / Supabase
--
-- This file ADDS missing operational/integration structures.
-- It does NOT recreate Odoo accounting tables or Paperclip governance tables.
-- Adapt table names to the canonical Zippy schema before applying.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- 1. MULTI-TENANCY / COMPANY OWNERSHIP
-- ============================================================

CREATE TABLE IF NOT EXISTS companies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    legal_name      VARCHAR(255),
    gst_number      VARCHAR(15),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- IMPORTANT:
-- Add company_id NOT NULL to every tenant-owned table before production:
-- users, customers, vendors, drivers, vehicles, orders, payments operational records,
-- dispatch objects, tracking, notifications, documents, scores, pricing overrides.
--
-- Example:
-- ALTER TABLE orders ADD COLUMN company_id UUID REFERENCES companies(id);
-- Backfill first; then:
-- ALTER TABLE orders ALTER COLUMN company_id SET NOT NULL;
-- CREATE INDEX idx_orders_company_status ON orders(company_id, status);

-- ============================================================
-- 2. TRIPS / SHIPMENTS
-- Separate commercial order from physical execution.
-- One order may be re-dispatched or split in future without corrupting order history.
-- ============================================================

CREATE TABLE IF NOT EXISTS trips (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    trip_number         VARCHAR(30) NOT NULL,
    vehicle_id          UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    driver_id           UUID REFERENCES drivers(id) ON DELETE SET NULL,
    vendor_id           UUID REFERENCES vendors(id) ON DELETE SET NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'planned' CHECK (status IN (
                            'planned','offered','assigned','arriving_pickup',
                            'loading','in_transit','arriving_delivery',
                            'unloading','pod_pending','completed',
                            'cancelled','exception'
                        )),
    pickup_eta          TIMESTAMPTZ,
    delivery_eta        TIMESTAMPTZ,
    actual_start_at     TIMESTAMPTZ,
    actual_end_at       TIMESTAMPTZ,
    started_odometer_km NUMERIC(10,2),
    ended_odometer_km   NUMERIC(10,2),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, trip_number)
);

CREATE INDEX IF NOT EXISTS idx_trips_order ON trips(company_id, order_id);
CREATE INDEX IF NOT EXISTS idx_trips_driver_status ON trips(company_id, driver_id, status);
CREATE INDEX IF NOT EXISTS idx_trips_vehicle_status ON trips(company_id, vehicle_id, status);

-- ============================================================
-- 3. DISPATCH OFFERS
-- Missing in the earlier schema. Do not model an offer only by changing orders.status.
-- ============================================================

CREATE TABLE IF NOT EXISTS dispatch_offers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    trip_id             UUID REFERENCES trips(id) ON DELETE CASCADE,
    vehicle_id          UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    driver_id           UUID REFERENCES drivers(id) ON DELETE SET NULL,
    vendor_id           UUID REFERENCES vendors(id) ON DELETE SET NULL,
    escalation_level    INTEGER NOT NULL CHECK (escalation_level BETWEEN 1 AND 4),
    score               NUMERIC(7,4),
    eta_minutes         INTEGER,
    offered_price       NUMERIC(14,2),
    status              VARCHAR(20) NOT NULL DEFAULT 'sent' CHECK (status IN (
                            'sent','viewed','accepted','declined','expired','cancelled'
                        )),
    sent_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    responded_at        TIMESTAMPTZ,
    decline_reason      TEXT,
    idempotency_key     VARCHAR(180) NOT NULL,
    UNIQUE(company_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_dispatch_offer_order
ON dispatch_offers(company_id, order_id, status);

CREATE INDEX IF NOT EXISTS idx_dispatch_offer_driver
ON dispatch_offers(company_id, driver_id, status);

-- ============================================================
-- 4. OPERATIONAL EXCEPTIONS / HUMAN FALLBACK
-- Fixes SQL-vs-domain mismatch around human_exception.
-- ============================================================

CREATE TABLE IF NOT EXISTS operational_exceptions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    entity_type         VARCHAR(50) NOT NULL,
    entity_id           UUID NOT NULL,
    exception_code      VARCHAR(80) NOT NULL,
    severity            VARCHAR(20) NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    status              VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN (
                            'open','assigned','investigating','resolved','waived','closed'
                        )),
    reason              TEXT NOT NULL,
    assigned_to_ref     VARCHAR(160),
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    resolution_notes    TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_operational_exceptions_open
ON operational_exceptions(company_id, status, severity, opened_at DESC);

-- ============================================================
-- 5. IDEMPOTENCY REGISTRY
-- Required for order creation, payment initiation, Odoo commands and callbacks.
-- ============================================================

CREATE TABLE IF NOT EXISTS idempotency_keys (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    scope               VARCHAR(100) NOT NULL,
    idempotency_key     VARCHAR(200) NOT NULL,
    request_hash        VARCHAR(64) NOT NULL,
    response_code       INTEGER,
    response_body       JSONB,
    resource_type       VARCHAR(80),
    resource_id         VARCHAR(160),
    status              VARCHAR(20) NOT NULL DEFAULT 'processing' CHECK (
                            status IN ('processing','completed','failed','expired')
                        ),
    locked_until        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    UNIQUE(company_id, scope, idempotency_key)
);

-- ============================================================
-- 6. WEBHOOK INBOX
-- HMAC/signature verified before processing.
-- ============================================================

CREATE TABLE IF NOT EXISTS webhook_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID REFERENCES companies(id) ON DELETE CASCADE,
    provider            VARCHAR(60) NOT NULL,
    provider_event_id   VARCHAR(180) NOT NULL,
    event_type          VARCHAR(120) NOT NULL,
    signature_valid     BOOLEAN NOT NULL DEFAULT FALSE,
    payload             JSONB NOT NULL,
    headers             JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              VARCHAR(20) NOT NULL DEFAULT 'received' CHECK (
                            status IN ('received','verified','processing','processed','failed','ignored')
                        ),
    attempts            INTEGER NOT NULL DEFAULT 0,
    last_error          TEXT,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    UNIQUE(provider, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_pending
ON webhook_events(status, received_at);

-- ============================================================
-- 7. TRANSACTIONAL OUTBOX
-- Reliable events from Zippy to Odoo/integration workers.
-- ============================================================

CREATE TABLE IF NOT EXISTS event_outbox (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    aggregate_type      VARCHAR(80) NOT NULL,
    aggregate_id        UUID NOT NULL,
    event_type          VARCHAR(120) NOT NULL,
    event_version       INTEGER NOT NULL DEFAULT 1,
    payload             JSONB NOT NULL,
    idempotency_key     VARCHAR(200) NOT NULL,
    destination         VARCHAR(40) NOT NULL CHECK (
                            destination IN ('ODOO','PAPERCLIP','NOTIFICATION','ANALYTICS','OTHER')
                        ),
    available_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at        TIMESTAMPTZ,
    attempts            INTEGER NOT NULL DEFAULT 0,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending
ON event_outbox(destination, available_at)
WHERE published_at IS NULL;

-- ============================================================
-- 8. INTEGRATION REFERENCES
-- Generic cross-system IDs without copying external authoritative records.
-- ============================================================

CREATE TABLE IF NOT EXISTS external_references (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    local_entity_type   VARCHAR(80) NOT NULL,
    local_entity_id     UUID NOT NULL,
    external_system     VARCHAR(40) NOT NULL CHECK (
                            external_system IN ('ODOO','RAZORPAY','PAPERCLIP','HONCHO','OTHER')
                        ),
    external_model      VARCHAR(100),  -- account.move, res.partner, stock.picking
    external_id         VARCHAR(180) NOT NULL,
    external_number     VARCHAR(180),
    sync_status         VARCHAR(30) NOT NULL DEFAULT 'linked' CHECK (
                            sync_status IN ('pending','linked','stale','error','unlinked')
                        ),
    last_synced_at      TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, local_entity_type, local_entity_id, external_system, external_model)
);

CREATE INDEX IF NOT EXISTS idx_external_ref_lookup
ON external_references(company_id, external_system, external_model, external_id);

-- ============================================================
-- 9. FINANCIAL REQUESTS (OPERATIONAL, NOT LEDGER)
-- Replaces duplicated authoritative invoice/payment tables in Supabase.
-- ============================================================

CREATE TABLE IF NOT EXISTS financial_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    request_type        VARCHAR(30) NOT NULL CHECK (request_type IN (
                            'create_customer_invoice',
                            'create_vendor_bill',
                            'record_customer_payment',
                            'vendor_settlement',
                            'refund',
                            'credit_note'
                        )),
    amount              NUMERIC(14,2),
    currency            VARCHAR(3) NOT NULL DEFAULT 'INR',
    status              VARCHAR(30) NOT NULL DEFAULT 'requested' CHECK (status IN (
                            'requested','governance_pending','approved',
                            'sent_to_odoo','completed','held','rejected','failed'
                        )),
    paperclip_proposal_id UUID, -- external Paperclip DB reference, no FK
    odoo_model          VARCHAR(80),
    odoo_record_id      VARCHAR(80),
    idempotency_key     VARCHAR(200) NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_financial_requests_order
ON financial_requests(company_id, order_id, status);

-- ============================================================
-- 10. GATEWAY PAYMENT EVENTS
-- Operational proof of what Razorpay reported. Odoo remains accounting authority.
-- ============================================================

CREATE TABLE IF NOT EXISTS payment_gateway_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    order_id            UUID REFERENCES orders(id) ON DELETE SET NULL,
    provider            VARCHAR(40) NOT NULL DEFAULT 'razorpay',
    provider_payment_id VARCHAR(160),
    provider_order_id   VARCHAR(160),
    provider_event_id   VARCHAR(180) NOT NULL,
    amount              NUMERIC(14,2),
    currency            VARCHAR(3) DEFAULT 'INR',
    event_type          VARCHAR(80) NOT NULL,
    gateway_status      VARCHAR(60),
    signature_valid     BOOLEAN NOT NULL DEFAULT FALSE,
    raw_payload         JSONB NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider, provider_event_id)
);

-- ============================================================
-- 11. DOCUMENT VERIFICATION
-- POD/document binary metadata separate from verification result.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_verifications (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_type       VARCHAR(40) NOT NULL,
    document_id         UUID NOT NULL,
    verifier_type       VARCHAR(20) NOT NULL CHECK (verifier_type IN ('system','agent','human','external')),
    verifier_ref        VARCHAR(160),
    verification_status VARCHAR(20) NOT NULL CHECK (
                            verification_status IN ('pending','verified','rejected','partial','needs_review')
                        ),
    confidence_score    NUMERIC(5,4),
    extracted_data      JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason              TEXT,
    verified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_verification
ON document_verifications(company_id, document_type, document_id, verification_status);

-- ============================================================
-- 12. SLA / SERVICE COMMITMENTS
-- Earlier architecture references SLA commitments but the large schema lacks a first-class table.
-- ============================================================

CREATE TABLE IF NOT EXISTS service_commitments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    commitment_type     VARCHAR(40) NOT NULL CHECK (
                            commitment_type IN ('pickup','delivery','temperature','communication','pod','other')
                        ),
    committed_at        TIMESTAMPTZ,
    threshold_value     NUMERIC(14,4),
    threshold_unit      VARCHAR(30),
    status              VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (
                            status IN ('active','met','breached','waived','cancelled')
                        ),
    breached_at         TIMESTAMPTZ,
    evidence            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 13. OPERATIONAL EVENT STREAM
-- Immutable business events; Langfuse is not the business audit DB.
-- ============================================================

CREATE TABLE IF NOT EXISTS operational_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    entity_type         VARCHAR(60) NOT NULL,
    entity_id           UUID NOT NULL,
    event_type          VARCHAR(120) NOT NULL,
    event_version       INTEGER NOT NULL DEFAULT 1,
    actor_type          VARCHAR(30) NOT NULL,
    actor_ref           VARCHAR(160),
    correlation_id      UUID,
    causation_id        UUID,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operational_events_entity
ON operational_events(company_id, entity_type, entity_id, occurred_at);

-- ============================================================
-- 14. ORDER STATE FIX
-- DO NOT execute blindly; adapt to your current CHECK constraint.
--
-- Canonical operational states should include an explicit exception path.
-- Recommended:
-- draft
-- payment_pending
-- confirmed
-- vehicle_search
-- driver_assigned
-- enroute
-- delivered
-- settlement_pending
-- closed
-- cancelled
-- human_exception
--
-- Prefer a transition_order(...) RPC/service that validates transitions.
-- Agents must never UPDATE orders.status directly.
-- ============================================================

-- ============================================================
-- 15. RLS RULE
-- Enable RLS on every tenant-owned table and enforce company_id.
-- Service-role workers must ALSO enforce capability checks in application code.
-- RLS alone is not sufficient for agent authorization.
-- ============================================================
