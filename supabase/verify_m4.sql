-- =============================================================================
-- M4 Verification Suite — Odoo mirror refs + webhook sweeps + reconciliation
-- Self-contained; single transaction.
-- =============================================================================

\set ON_ERROR_STOP off

BEGIN;

-- -----------------------------------------------------------------------------
-- T1: odoo columns exist + default status
-- -----------------------------------------------------------------------------
SELECT CASE WHEN count(*) = 5 THEN 'PASS' ELSE 'FAIL' END AS t1_odoo_columns
FROM information_schema.columns
WHERE table_name='orders'
  AND column_name IN ('odoo_sale_order_id','odoo_invoice_id','odoo_sync_status',
                      'odoo_synced_at','odoo_error');

INSERT INTO orders (order_number, customer_id,
    pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
    delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
    consignee_name, consignee_phone, base_amount, total_amount)
VALUES ('ZP-M4', '10000000-0000-0000-0000-000000000001',
    'P','X','S','1','D','Y','S','2','N','9000000000', 3463.95, 3463.95);

SELECT CASE WHEN odoo_sync_status='not_started' THEN 'PASS' ELSE 'FAIL' END AS t1_default_status
FROM orders WHERE order_number='ZP-M4';

DO $$
DECLARE oid UUID;
BEGIN
    SELECT order_id INTO oid FROM orders WHERE order_number='ZP-M4';
    PERFORM public.mark_odoo_failed(oid, 'simulated:connect_error');

    IF (SELECT odoo_sync_status FROM orders WHERE order_id=oid)='failed' THEN
        RAISE NOTICE 'PASS t2_mark_failed';
    ELSE RAISE NOTICE 'FAIL t2_mark_failed'; END IF;

    PERFORM public.mark_odoo_synced(oid, 9001, 7001);

    IF (SELECT odoo_sync_status FROM orders WHERE order_id=oid)='synced'
       AND (SELECT odoo_sale_order_id FROM orders WHERE order_id=oid)=9001 THEN
        RAISE NOTICE 'PASS t2_mark_synced';
    ELSE RAISE NOTICE 'FAIL t2_mark_synced'; END IF;

    IF EXISTS (SELECT 1 FROM order_event_log WHERE order_id=oid
                AND event_type='odoo_sync_succeeded') THEN
        RAISE NOTICE 'PASS t2_sync_event_logged';
    ELSE RAISE NOTICE 'FAIL t2_sync_event_logged'; END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T3: enqueue_agent_task dedupe — second insert suppressed (NULL id)
-- -----------------------------------------------------------------------------
DO $$
DECLARE first_id UUID; second_id UUID;
BEGIN
    SELECT public.enqueue_agent_task('payment_settlement','process_payment_event',
        '{"order_id":"x"}'::jsonb, 'm4-task-1') INTO first_id;
    SELECT public.enqueue_agent_task('payment_settlement','process_payment_event',
        '{"order_id":"x"}'::jsonb, 'm4-task-1') INTO second_id;

    IF first_id IS NOT NULL AND second_id IS NULL THEN
        RAISE NOTICE 'PASS t3_enqueue_dedupe';
    ELSE
        RAISE NOTICE 'FAIL t3_enqueue_dedupe (% vs %)', first_id, second_id;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T4: WF-5 dead-letter sweep → revive resets attempts
-- -----------------------------------------------------------------------------
INSERT INTO webhook_events (provider, event_type, payload, processed,
    processing_attempts, error_message, created_at)
VALUES ('razorpay','unknown','{}', false, 7, 'too many hops',
        CURRENT_TIMESTAMP - INTERVAL '30 minutes');

DO $$
DECLARE swept INT; revived INT;
BEGIN
    SELECT count(*) INTO swept FROM public.sweep_dead_webhooks();
    IF swept >= 1 THEN
        RAISE NOTICE 'PASS t4_sweep_dead_letters (%)', swept;
    ELSE RAISE NOTICE 'FAIL t4_sweep_dead_letters'; END IF;

    -- marker present?
    IF EXISTS (SELECT 1 FROM webhook_events WHERE provider='razorpay'
                AND error_message LIKE 'DEAD_LETTERED%') THEN
        RAISE NOTICE 'PASS t4_marker_stamped';
    ELSE RAISE NOTICE 'FAIL t4_marker_stamped'; END IF;

    SELECT count(*) INTO revived FROM public.revive_dead_webhooks(10);
    IF revived >= 1 THEN
        RAISE NOTICE 'PASS t4_revive_resets (%)', revived;
    ELSE RAISE NOTICE 'FAIL t4_revive_resets'; END IF;

    IF EXISTS (SELECT 1 FROM webhook_events WHERE processing_attempts=0
                AND error_message LIKE 'REVIVED:%') THEN
        RAISE NOTICE 'PASS t4_revived_reprocessable';
    ELSE RAISE NOTICE 'FAIL t4_revived_reprocessable'; END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T5: WF-1 stale payment reconciliation candidates
-- -----------------------------------------------------------------------------
INSERT INTO payments (order_id, amount, payment_status, payment_gateway,
                      gateway_payment_id, created_at)
VALUES ((SELECT order_id FROM orders WHERE order_number='ZP-M4'),
        1000, 'processing', 'razorpay', 'pay_STUCK_9',
        CURRENT_TIMESTAMP - INTERVAL '45 minutes');

DO $$
DECLARE n INT;
BEGIN
    SELECT count(*) INTO n FROM stale_processing_payments(30);
    IF n >= 1 THEN
        RAISE NOTICE 'PASS t5_stale_candidates_found (%)', n;
    ELSE RAISE NOTICE 'FAIL t5_stale_candidates_found'; END IF;
END $$;

SELECT CASE WHEN gateway_payment_id='pay_STUCK_9' AND minutes_stuck >= 44
            THEN 'PASS' ELSE 'FAIL' END AS t5_candidate_fields
FROM stale_processing_payments(30)
ORDER BY minutes_stuck DESC LIMIT 1;

ROLLBACK;
