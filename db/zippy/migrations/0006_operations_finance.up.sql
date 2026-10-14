BEGIN;

-- M4 gap: settlement eligibility must be representable before any Odoo
-- financial request exists. eligibility is an operational projection only;
-- settlement release remains manual and Odoo remains the accounting authority.
ALTER TABLE zippy.settlement_projections
    ALTER COLUMN financial_request_id DROP NOT NULL;

-- PAY-INV-002: no settlement projection without accepted POD evidence.
CREATE FUNCTION zippy.validate_settlement_projection()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.operational_status <> 'failed' AND NOT EXISTS (
        SELECT 1
          FROM zippy.pod_documents pod
         WHERE pod.platform_id = NEW.platform_id
           AND pod.order_id = NEW.order_id
           AND pod.verification_status = 'accepted'
    ) THEN
        RAISE EXCEPTION 'settlement projection requires accepted POD evidence' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER settlement_projection_pod_gate
    BEFORE INSERT OR UPDATE ON zippy.settlement_projections
    FOR EACH ROW EXECUTE FUNCTION zippy.validate_settlement_projection();

-- Match the canonical privilege posture: PUBLIC holds no function privileges.
REVOKE EXECUTE ON FUNCTION zippy.validate_settlement_projection() FROM PUBLIC;

-- Receipt reconciliation sweeps filter by status and age within a platform.
CREATE INDEX webhook_receipts_processing_idx
    ON zippy.webhook_receipts (platform_id, processing_status, received_at);

-- M4 gap: the webhook must resolve orders through an authoritative,
-- server-controlled mapping instead of trusting the payment/refund entity's
-- `notes.zippy_order_id`. `zippy.external_references` already provides a
-- tenant-scoped, provider+external-identifier-unique mapping structure
-- (local_entity_type='order', external_system='razorpay',
-- external_model='payment_order', external_id=<provider order reference>);
-- it cannot express the expected amount/currency the webhook must verify
-- against, so `payment_intents` adds only that missing piece, created solely
-- by the approved server-side payment-intent/order preparation path (see
-- FinanceRepository.prepare_payment_intent).
CREATE TABLE zippy.payment_intents (
    payment_intent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    external_reference_id uuid NOT NULL,
    expected_amount_minor_units bigint NOT NULL
        CHECK (expected_amount_minor_units > 0 AND expected_amount_minor_units <= 999999999999),
    expected_currency_code varchar(3) NOT NULL CHECK (expected_currency_code ~ '^[A-Z]{3}$'),
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, payment_intent_id),
    UNIQUE (platform_id, external_reference_id),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, external_reference_id)
        REFERENCES zippy.external_references(platform_id, external_reference_id)
);

ALTER TABLE zippy.payment_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE zippy.payment_intents FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_isolation ON zippy.payment_intents
    USING (platform_id = nullif(current_setting('zippy.platform_id', true), '')::uuid)
    WITH CHECK (platform_id = nullif(current_setting('zippy.platform_id', true), '')::uuid);

-- Match the canonical least-privilege posture established in 0004, corrected
-- for payment-intent immutability: the runtime role may only ever create the
-- mapping once and read it back. It must never UPDATE or DELETE a mapping
-- (that would allow rebinding an order's provider reference at runtime); a
-- new provider reference for the same order is a distinct conflict the
-- application already rejects, not a row mutation. Only zippy_migrator
-- (schema owner, NOLOGIN) can alter rows outside the running application.
GRANT SELECT, INSERT ON zippy.payment_intents TO zippy_app;
GRANT SELECT ON zippy.payment_intents TO zippy_readonly;

-- ORD-INV-003: dispatch must not auto-assign a vehicle whose body type
-- cannot be proven compatible. Neither zippy.orders nor
-- zippy.vehicle_models.body_type is a canonical enum -- vehicle_models.body_type
-- is plain NOT NULL text with no fixed taxonomy (0002_operations.up.sql), and
-- no approved PRD/decision defines one. This table does not invent a new
-- taxonomy; it stores the customer-declared body-type text captured only
-- through the authenticated server-side order-intake path
-- (CoreRepository.create_order), in the same free-text domain
-- vehicle_models.body_type already uses, so dispatch can compare the two
-- with exact (normalized) equality instead of trusting any later,
-- offer-acceptance-time input. One row per order; never updated.
CREATE TABLE zippy.dispatch_requirements (
    dispatch_requirement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES zippy.platforms(platform_id),
    order_id uuid NOT NULL,
    required_body_type text NOT NULL CHECK (length(required_body_type) BETWEEN 1 AND 64),
    created_by_account_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (platform_id, dispatch_requirement_id),
    UNIQUE (platform_id, order_id),
    FOREIGN KEY (platform_id, order_id) REFERENCES zippy.orders(platform_id, order_id),
    FOREIGN KEY (platform_id, created_by_account_id) REFERENCES zippy.accounts(platform_id, account_id)
);

ALTER TABLE zippy.dispatch_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE zippy.dispatch_requirements FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_isolation ON zippy.dispatch_requirements
    USING (platform_id = nullif(current_setting('zippy.platform_id', true), '')::uuid)
    WITH CHECK (platform_id = nullif(current_setting('zippy.platform_id', true), '')::uuid);

-- Immutable by construction, not merely by convention: zippy_app receives
-- INSERT and SELECT only, never UPDATE/DELETE, so no application code path --
-- including the public dispatch-offer-accept endpoint, which never even
-- references this table -- can create it late or change it, before or after
-- any dispatch_offer/trip_assignment exists. Only zippy_migrator (schema
-- owner, NOLOGIN) can alter rows outside the running application.
GRANT SELECT, INSERT ON zippy.dispatch_requirements TO zippy_app;
GRANT SELECT ON zippy.dispatch_requirements TO zippy_readonly;

COMMIT;
