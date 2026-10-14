-- =============================================================================
-- M4 Migration 11: Odoo mirror refs + webhook sweeps + reconciliation
-- Rollback: ALTER TABLE orders DROP COLUMN ...; DROP FUNCTION sweep_dead_webhooks
--           revive_dead_webhooks stale_processing_payments mark_odoo_synced
--           mark_odoo_failed enqueue_agent_task;
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Odoo 18 CE system-of-record mirrors on orders
-- -----------------------------------------------------------------------------
ALTER TABLE public.orders
    ADD COLUMN IF NOT EXISTS odoo_sale_order_id BIGINT,
    ADD COLUMN IF NOT EXISTS odoo_invoice_id    BIGINT,
    ADD COLUMN IF NOT EXISTS odoo_sync_status   VARCHAR(20) DEFAULT 'not_started'
        CHECK (odoo_sync_status IN ('not_started','pending','synced','failed')),
    ADD COLUMN IF NOT EXISTS odoo_synced_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS odoo_error         TEXT;

CREATE INDEX IF NOT EXISTS idx_orders_odoo_status ON public.orders(odoo_sync_status)
    WHERE odoo_sync_status IN ('pending','failed');

-- -----------------------------------------------------------------------------
-- Generic idempotent task enqueue (used by webhook route + sweeper workflows)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enqueue_agent_task(
    p_agent_name VARCHAR(50),
    p_task_type VARCHAR(100),
    p_payload JSONB DEFAULT '{}',
    p_dedupe_key VARCHAR(150) DEFAULT NULL,
    p_priority SMALLINT DEFAULT 5
)
RETURNS UUID AS $$
DECLARE v_id UUID;
BEGIN
    INSERT INTO public.agent_tasks (agent_name, task_type, payload, dedupe_key, priority)
    VALUES (p_agent_name, p_task_type, COALESCE(p_payload,'{}'::jsonb), p_dedupe_key, p_priority)
    ON CONFLICT (dedupe_key) DO NOTHING
    RETURNING task_id INTO v_id;
    RETURN v_id;   -- NULL when duplicate suppressed
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- WF-5: dead-letter handling for failed webhook processing
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sweep_dead_webhooks(
    p_max_attempts INTEGER DEFAULT 5,
    p_quiet_minutes INTEGER DEFAULT 10
)
RETURNS INTEGER AS $$
DECLARE n INTEGER := 0;
BEGIN
    WITH dead AS (
        UPDATE public.webhook_events w
           SET error_message = 'DEAD_LETTERED: ' || COALESCE(w.error_message,'unspecified')
         WHERE w.processed = false
           AND w.processing_attempts >= p_max_attempts
           AND (w.error_message IS NULL OR w.error_message NOT LIKE 'DEAD_LETTERED%')
           AND (COALESCE(w.last_processed_at, w.created_at) < CURRENT_TIMESTAMP - make_interval(mins => p_quiet_minutes))
        RETURNING 1
    )
    SELECT count(*) INTO n FROM dead;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.revive_dead_webhooks(p_limit INTEGER DEFAULT 50)
RETURNS INTEGER AS $$
DECLARE n INTEGER;
BEGIN
    UPDATE public.webhook_events w
       SET processed = false,
           processing_attempts = 0,
           error_message = 'REVIVED:' || COALESCE(w.error_message,''),
           last_processed_at = NULL
     WHERE w.webhook_id IN (
          SELECT w2.webhook_id FROM public.webhook_events w2
           WHERE w2.error_message LIKE 'DEAD_LETTERED%'
             AND w2.processing_attempts >= 1
           LIMIT GREATEST(p_limit,1));
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- WF-1: lost-webhook reconciliation candidates
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.stale_processing_payments(p_minutes INTEGER DEFAULT 30)
RETURNS TABLE (payment_id UUID, order_id UUID, gateway_payment_id VARCHAR(100),
               minutes_stuck NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT p.payment_id, p.order_id, p.gateway_payment_id,
           ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - p.created_at))/60.0, 1)
      FROM public.payments p
     WHERE p.payment_status = 'processing'
       AND p.created_at < CURRENT_TIMESTAMP - make_interval(mins => p_minutes)
     ORDER BY p.created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- -----------------------------------------------------------------------------
-- Odoo mirror bookkeeping
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.mark_odoo_synced(
    p_order_id UUID, p_sale_order_id BIGINT, p_invoice_id BIGINT DEFAULT NULL)
RETURNS VOID AS $$
BEGIN
    UPDATE public.orders
       SET odoo_sale_order_id = p_sale_order_id,
           odoo_invoice_id = p_invoice_id,
           odoo_sync_status = 'synced',
           odoo_synced_at = CURRENT_TIMESTAMP,
           odoo_error = NULL
     WHERE order_id = p_order_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'ORDER_NOT_FOUND %', p_order_id; END IF;

    INSERT INTO public.order_event_log (order_id, event_type, source, payload)
    VALUES (p_order_id, 'odoo_sync_succeeded', 'system',
            jsonb_build_object('sale_order_id', p_sale_order_id,
                               'invoice_id', p_invoice_id));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.mark_odoo_failed(p_order_id UUID, p_reason TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE public.orders
       SET odoo_sync_status = 'failed',
           odoo_error = LEFT(p_reason, 500)
     WHERE order_id = p_order_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'ORDER_NOT_FOUND %', p_order_id; END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
