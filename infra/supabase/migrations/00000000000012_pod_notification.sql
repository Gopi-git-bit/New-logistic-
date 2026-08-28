-- =============================================================================
-- M5 — Document/POD Pipeline + Notification Queue
-- Depends: M4 (00000000000011)
-- =============================================================================

BEGIN;

-- ----------------------------------------------------------------------------- 
-- order_documents — uploaded images + OCR extraction results
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.order_documents (
    document_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id          UUID NOT NULL REFERENCES public.orders(order_id) ON DELETE CASCADE,
    document_type     TEXT NOT NULL CHECK (document_type IN (
                        'pod','invoice','lorry_receipt','eway_bill',
                        'photo_loading','photo_unloading','other')),
    image_url         TEXT,
    ocr_raw_text      TEXT,
    ocr_confidence    NUMERIC(5,4),   -- 0.0000–1.0000
    ocr_provider      TEXT,           -- 'tesseract' | 'vision_llm' | ...
    uploaded_by       UUID,           -- driver or customer user_id
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_documents_order
    ON public.order_documents (order_id);
CREATE INDEX IF NOT EXISTS idx_order_documents_type
    ON public.order_documents (document_type);

-- RLS: owner (customer who placed order) can see; driver who delivered can see; admin reads all
ALTER TABLE public.order_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS order_documents_select_owner ON public.order_documents;
CREATE POLICY order_documents_select_owner ON public.order_documents
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.orders o
            WHERE o.order_id = order_documents.order_id
              AND (
                  o.customer_id = (SELECT auth.uid())
                  OR o.driver_id = (SELECT auth.uid())
                  OR (SELECT auth.role()) = 'service_role'
              )
        )
    );

DROP POLICY IF EXISTS order_documents_insert_driver ON public.order_documents;
CREATE POLICY order_documents_insert_driver ON public.order_documents
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.orders o
            WHERE o.order_id = order_documents.order_id
              AND (
                  o.driver_id = (SELECT auth.uid())
                  OR (SELECT auth.role()) = 'service_role'
              )
        )
    );

-- ----------------------------------------------------------------------------- 
-- notification_queue — pluggable delivery job queue (D-09 idempotency)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notification_queue (
    notification_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    channel           TEXT NOT NULL CHECK (channel IN ('push','sms','email','in_app')),
    notification_type TEXT NOT NULL,
    title             TEXT NOT NULL,
    body              TEXT NOT NULL,
    payload           JSONB DEFAULT '{}'::jsonb,
    idempotency_key   TEXT,                   -- unique per D-09
    status            TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','processing','sent','failed')),
    attempts          INTEGER NOT NULL DEFAULT 0,
    max_attempts      INTEGER NOT NULL DEFAULT 3,
    next_retry_at     TIMESTAMPTZ,
    external_id       TEXT,                   -- provider message id after send
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_notification_queue_idempotency
        UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_notification_queue_status
    ON public.notification_queue (status)
    WHERE status IN ('queued','processing');
CREATE INDEX IF NOT EXISTS idx_notification_queue_retry
    ON public.notification_queue (next_retry_at)
    WHERE status = 'queued';

-- RLS: communication agent service-role only (via RPC)
ALTER TABLE public.notification_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notification_queue_service_all ON public.notification_queue;
CREATE POLICY notification_queue_service_all ON public.notification_queue
    FOR ALL USING ((SELECT auth.role()) = 'service_role');

-- ----------------------------------------------------------------------------- 
-- upsert_order_document — insert document + OCR results, return document_id
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.upsert_order_document(
    p_order_id      UUID,
    p_doc_type      TEXT,
    p_image_url     TEXT DEFAULT NULL,
    p_ocr_raw_text  TEXT DEFAULT NULL,
    p_ocr_confidence NUMERIC DEFAULT NULL,
    p_ocr_provider  TEXT DEFAULT NULL,
    p_uploaded_by   UUID DEFAULT NULL
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO public.order_documents
        (order_id, document_type, image_url, ocr_raw_text,
         ocr_confidence, ocr_provider, uploaded_by)
    VALUES
        (p_order_id, p_doc_type, p_image_url, p_ocr_raw_text,
         p_ocr_confidence, p_ocr_provider, p_uploaded_by)
    RETURNING document_id INTO v_id;

    RETURN v_id;
END;
$$;

-- ----------------------------------------------------------------------------- 
-- enqueue_notification — idempotent RPC (D-09)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enqueue_notification(
    p_user_id       UUID,
    p_channel       TEXT,
    p_type          TEXT,
    p_title         TEXT,
    p_body          TEXT,
    p_payload       JSONB DEFAULT '{}'::jsonb,
    p_idempotency   TEXT DEFAULT NULL
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id UUID;
BEGIN
    IF p_idempotency IS NOT NULL THEN
        SELECT nq.notification_id INTO v_id
        FROM public.notification_queue nq
        WHERE nq.idempotency_key = p_idempotency;

        IF FOUND THEN
            RETURN v_id;   -- already enqueued — D-09 no-op
        END IF;
    END IF;

    INSERT INTO public.notification_queue
        (user_id, channel, notification_type, title, body, payload, idempotency_key)
    VALUES
        (p_user_id, p_channel, p_type, p_title, p_body, p_payload, p_idempotency)
    RETURNING notification_id INTO v_id;

    RETURN v_id;
END;
$$;

-- ----------------------------------------------------------------------------- 
-- grab_notification_jobs — claim N queued items atomically (skip-locked)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.grab_notification_jobs(
    p_limit  INTEGER DEFAULT 5
) RETURNS SETOF public.notification_queue
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    UPDATE public.notification_queue nq
       SET status     = 'processing',
           attempts   = nq.attempts + 1,
           next_retry_at = NULL
     WHERE nq.notification_id IN (
         SELECT nq2.notification_id
           FROM public.notification_queue nq2
          WHERE nq2.status IN ('queued','processing')
            AND (nq2.next_retry_at IS NULL OR nq2.next_retry_at <= now())
            AND nq2.attempts < nq2.max_attempts
          ORDER BY nq2.created_at
          LIMIT GREATEST(p_limit, 1)
          FOR UPDATE SKIP LOCKED
     )
    RETURNING nq.*;
END;
$$;

-- ----------------------------------------------------------------------------- 
-- mark_notification_sent / mark_notification_failed — lifecycle RPCs
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.mark_notification_sent(
    p_notification_id UUID,
    p_external_id    TEXT DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.notification_queue
       SET status      = 'sent',
           external_id = p_external_id
     WHERE notification_id = p_notification_id
       AND status = 'processing';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Invalid notification transition to sent';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_notification_failed(
    p_notification_id UUID,
    p_reason          TEXT DEFAULT NULL
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_row public.notification_queue%ROWTYPE;
BEGIN
    SELECT * INTO v_row
    FROM public.notification_queue
    WHERE notification_id = p_notification_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Notification % not found', p_notification_id;
    END IF;

    IF v_row.status != 'processing' THEN
        RAISE EXCEPTION 'Invalid notification transition to failed from %', v_row.status;
    END IF;

    IF v_row.attempts >= v_row.max_attempts THEN
        -- permanent failure
        UPDATE public.notification_queue
           SET status = 'failed'
         WHERE notification_id = p_notification_id;
    ELSE
        -- retry with exponential backoff: 1min, 5min, 25min
        UPDATE public.notification_queue
           SET status        = 'queued',
               next_retry_at = now() + (INTERVAL '1 minute' * POWER(5, v_row.attempts))
         WHERE notification_id = p_notification_id;
    END IF;
END;
$$;

-- ----------------------------------------------------------------------------- 
-- Register document_processing agent (add to CHECK constraint + insert)
-- ----------------------------------------------------------------------------- 
-- Extend the allowed agent names to include document_processing
ALTER TABLE public.agent_registry DROP CONSTRAINT IF EXISTS agent_registry_agent_name_check;
ALTER TABLE public.agent_registry ADD CONSTRAINT agent_registry_agent_name_check
    CHECK (agent_name::text = ANY (ARRAY[
        'customer_service','order_management','transportation',
        'resource_management','payment_settlement','platform_administration',
        'communication','document_processing'
    ]::text[]));

INSERT INTO public.agent_registry (agent_name, status, daily_budget_usd_cents, budget_spent_cents)
VALUES ('document_processing', 'running', 100000, 0)
ON CONFLICT (agent_name) DO NOTHING;

-- ----------------------------------------------------------------------------- 
-- Grant execute to service_role (only if it exists — Supabase auth stub)
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION public.enqueue_notification(UUID, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT)
            TO service_role;
        GRANT EXECUTE ON FUNCTION public.grab_notification_jobs(INTEGER)
            TO service_role;
        GRANT EXECUTE ON FUNCTION public.mark_notification_sent(UUID, TEXT)
            TO service_role;
        GRANT EXECUTE ON FUNCTION public.mark_notification_failed(UUID, TEXT)
            TO service_role;
    END IF;
END $$;

COMMIT;
