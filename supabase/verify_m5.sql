-- =============================================================================
-- M5 Verification Suite — POD pipeline + notification queue
-- Self-contained; single transaction.
-- =============================================================================

\set ON_ERROR_STOP off

BEGIN;

-- T1: order_documents table + columns exist
SELECT CASE WHEN count(*) = 7 THEN 'PASS' ELSE 'FAIL' END AS t1_order_documents_cols
FROM information_schema.columns
WHERE table_name='order_documents'
  AND column_name IN ('document_id','order_id','document_type',
                      'ocr_raw_text','ocr_confidence','ocr_provider','image_url');

-- T2: notification_queue table + columns exist
SELECT CASE WHEN count(*) >= 8 THEN 'PASS' ELSE 'FAIL' END AS t1_notification_queue_cols
FROM information_schema.columns
WHERE table_name='notification_queue'
  AND column_name IN ('notification_id','user_id','channel','title','body',
                      'idempotency_key','status','attempts');

-- T3: document_processing agent registered
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t2_doc_processing_agent
FROM public.agent_registry WHERE agent_name = 'document_processing';

-- T4: upsert_order_document creates a document record
DO $$
DECLARE doc_id UUID; test_order_id UUID;
BEGIN
    -- Use an existing order for FK validity
    SELECT order_id INTO test_order_id FROM public.orders LIMIT 1;
    IF test_order_id IS NULL THEN
        RAISE NOTICE 'FAIL t3_upsert_doc (no orders)';
        RETURN;
    END IF;

    doc_id := public.upsert_order_document(
        test_order_id, 'pod', 'http://example.com/pod.jpg',
        'DELIVERED OK', 0.95, 'tesseract', NULL
    );

    IF doc_id IS NOT NULL THEN
        RAISE NOTICE 'PASS t3_upsert_doc (%)', doc_id;
    ELSE
        RAISE NOTICE 'FAIL t3_upsert_doc';
    END IF;

    -- Verify stored
    IF EXISTS (SELECT 1 FROM public.order_documents
               WHERE document_id = doc_id AND ocr_provider = 'tesseract') THEN
        RAISE NOTICE 'PASS t3_doc_persisted';
    ELSE
        RAISE NOTICE 'FAIL t3_doc_persisted';
    END IF;
END $$;

-- T5: enqueue_notification dedupe (D-09)
DO $$
DECLARE first_id UUID; second_id UUID; uid UUID;
BEGIN
    SELECT user_id INTO uid FROM public.users LIMIT 1;
    IF uid IS NULL THEN uid := '00000000-0000-0000-0000-000000000001'; END IF;

    first_id := public.enqueue_notification(
        uid, 'sms', 'order_update', 'Test', 'Hello',
        '{}'::jsonb, 'm5-dedupe-key-1'
    );
    second_id := public.enqueue_notification(
        uid, 'sms', 'order_update', 'Test', 'Hello',
        '{}'::jsonb, 'm5-dedupe-key-1'
    );

    IF first_id IS NOT NULL AND second_id = first_id THEN
        RAISE NOTICE 'PASS t4_enqueue_dedupe';
    ELSE
        RAISE NOTICE 'FAIL t4_enqueue_dedupe (first=%, second=%)', first_id, second_id;
    END IF;
END $$;

-- T6: grab + mark_sent lifecycle
DO $$
DECLARE uid UUID; n_id UUID;
BEGIN
    SELECT user_id INTO uid FROM public.users LIMIT 1;
    IF uid IS NULL THEN uid := '00000000-0000-0000-0000-000000000001'; END IF;

    n_id := public.enqueue_notification(
        uid, 'email', 'delivery_alert', 'Delivery', 'Your order is arriving',
        '{}'::jsonb, 'm5-lifecycle-test'
    );

    -- grab should claim it
    PERFORM public.grab_notification_jobs(5);

    -- mark sent
    PERFORM public.mark_notification_sent(n_id, 'ext_abc123');

    IF (SELECT status FROM public.notification_queue WHERE notification_id = n_id) = 'sent' THEN
        RAISE NOTICE 'PASS t5_lifecycle_sent';
    ELSE
        RAISE NOTICE 'FAIL t5_lifecycle_sent';
    END IF;

    IF (SELECT external_id FROM public.notification_queue WHERE notification_id = n_id) = 'ext_abc123' THEN
        RAISE NOTICE 'PASS t5_external_id';
    ELSE
        RAISE NOTICE 'FAIL t5_external_id';
    END IF;
END $$;

-- T7: mark_notification_failed — retryable then permanent
DO $$
DECLARE uid UUID; n_id UUID; n2 UUID;
BEGIN
    SELECT user_id INTO uid FROM public.users LIMIT 1;
    IF uid IS NULL THEN uid := '00000000-0000-0000-0000-000000000001'; END IF;

    -- First failure: retryable (attempts < max_attempts)
    n_id := public.enqueue_notification(
        uid, 'push', 'system', 'F1', 'Body',
        '{}'::jsonb, 'm5-fail-retry'
    );
    PERFORM public.grab_notification_jobs(5);
    PERFORM public.mark_notification_failed(n_id, 'provider_timeout');

    IF (SELECT status FROM public.notification_queue WHERE notification_id = n_id) = 'queued' THEN
        RAISE NOTICE 'PASS t6_retryable_failure';
    ELSE
        RAISE NOTICE 'FAIL t6_retryable_failure (status=%)',
            (SELECT status FROM public.notification_queue WHERE notification_id = n_id);
    END IF;

    -- Permanent failure: grab first (so status=processing), THEN force attempts past max
    n2 := public.enqueue_notification(
        uid, 'push', 'system', 'F2', 'Body',
        '{}'::jsonb, 'm5-fail-permanent'
    );
    PERFORM public.grab_notification_jobs(5);
    -- Now status=processing, attempts=1; force to 3 so mark_failed sees attempts >= max
    UPDATE public.notification_queue SET attempts = 3 WHERE notification_id = n2;
    PERFORM public.mark_notification_failed(n2, 'gave_up');

    IF (SELECT status FROM public.notification_queue WHERE notification_id = n2) = 'failed' THEN
        RAISE NOTICE 'PASS t6_permanent_failure';
    ELSE
        RAISE NOTICE 'FAIL t6_permanent_failure';
    END IF;
END $$;

-- T8: notification_queue RLS — service_role only
SELECT CASE WHEN tablename = 'notification_queue' AND policyname LIKE '%service_all%'
            THEN 'PASS' ELSE 'FAIL' END AS t7_nq_rls
FROM pg_policies WHERE tablename = 'notification_queue' LIMIT 1;

ROLLBACK;
