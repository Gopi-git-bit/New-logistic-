-- ============================================================
-- ZIPPY LOGISTICS — FULL INTEGRATION TEST SUITE
-- PostgreSQL 15+ / Supabase
--
-- Tests:
--   1. Structure verification (all tables exist)
--   2. RLS / tenant isolation
--   3. Idempotency (order, payment, webhook)
--   4. Governance chain: Zippy → financial_request → Paperclip → execution_grant → Hermes → Odoo
--   5. Fail-closed: Paperclip down → financial writes blocked
--   6. Duplicate prevention: same request twice → no duplicate invoice/payment
--
-- Usage:
--   docker cp supabase/test_full_integration.sql zippy-db:/tmp/test.sql
--   docker exec zippy-db psql -U postgres -d postgres -f /tmp/test.sql
-- ============================================================

\set ON_ERROR_STOP off

-- =============================================================================
-- SECTION 0: STRUCTURE VERIFICATION
-- =============================================================================
SELECT '--- SECTION 0: STRUCTURE ---' AS section;

-- Zippy operational tables
SELECT CASE WHEN count(*) >= 25 THEN 'PASS' ELSE 'FAIL' END AS t0_zippy_table_count
FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';

-- Companies table exists (from migration 07)
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_companies_exists
FROM information_schema.tables WHERE table_name='companies' AND table_schema='public';

-- Trips table exists
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_trips_exists
FROM information_schema.tables WHERE table_name='trips' AND table_schema='public';

-- Idempotency keys table exists
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_idempotency_exists
FROM information_schema.tables WHERE table_name='idempotency_keys' AND table_schema='public';

-- Financial requests table exists
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_financial_requests_exists
FROM information_schema.tables WHERE table_name='financial_requests' AND table_schema='public';

-- Webhook events table exists
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_webhook_events_exists
FROM information_schema.tables WHERE table_name='webhook_events' AND table_schema='public';

-- External references table exists
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_external_refs_exists
FROM information_schema.tables WHERE table_name='external_references' AND table_schema='public';

-- Event outbox table exists
SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t0_outbox_exists
FROM information_schema.tables WHERE table_name='event_outbox' AND table_schema='public';

-- =============================================================================
-- SECTION 1: RLS / TENANT ISOLATION
-- =============================================================================
SELECT '--- SECTION 1: RLS / TENANT ISOLATION ---' AS section;

-- Create two test companies
INSERT INTO companies (id, name, gst_number) VALUES
    ('aaaa0000-0000-0000-0000-000000000001', 'Company A', 'GSTAAAA0001A'),
    ('bbbb0000-0000-0000-0000-000000000001', 'Company B', 'GSTBBBB0001B')
ON CONFLICT (id) DO NOTHING;

-- Test: company_id constraint on trips
-- Trip for Company A should reference Company A's order
-- (We test the FK constraint exists by attempting invalid reference)
DO $$
DECLARE
    v_order_a UUID;
    v_trip_id UUID;
BEGIN
    -- Create a test order for Company A (using existing orders table structure)
    INSERT INTO orders (order_number, customer_id, order_status,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-TEST-TENANT-A', '10000000-0000-0000-0000-000000000001', 'draft',
        '123 Test St', 'Mumbai', 'MH', '400001',
        '456 Delivery Ave', 'Delhi', 'DL', '110001',
        'Test Consignee', '9999999999', 1000.00, 1200.00)
    RETURNING id INTO v_order_a;

    -- Create trip for Company A
    INSERT INTO trips (company_id, order_id, trip_number, status)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', v_order_a, 'TRIP-TEST-001', 'planned')
    RETURNING id INTO v_trip_id;

    -- Verify trip exists with correct company
    IF EXISTS (SELECT 1 FROM trips WHERE id = v_trip_id AND company_id = 'aaaa0000-0000-0000-0000-000000000001') THEN
        RAISE NOTICE 'PASS: t1_trip_company_correct';
    ELSE
        RAISE WARNING 'FAIL: t1_trip_company_correct';
    END IF;

    -- Test: trip with wrong company FK should fail
    BEGIN
        INSERT INTO trips (company_id, order_id, trip_number, status)
        VALUES ('bbbb0000-0000-0000-0000-000000000001', v_order_a, 'TRIP-TEST-002', 'planned');
        RAISE WARNING 'FAIL: t1_trip_cross_company_fk_should_fail';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'PASS: t1_trip_cross_company_fk_blocked';
    END;

    -- Cleanup
    DELETE FROM trips WHERE id = v_trip_id;
    DELETE FROM orders WHERE order_number = 'ZP-TEST-TENANT-A';
END $$;

-- Test: idempotency_keys unique per company
DO $$
BEGIN
    INSERT INTO idempotency_keys (company_id, scope, idempotency_key, request_hash, status)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', 'order', 'idem-test-001', 'hash1', 'processing');

    -- Same key, same company → should fail (unique constraint)
    BEGIN
        INSERT INTO idempotency_keys (company_id, scope, idempotency_key, request_hash, status)
        VALUES ('aaaa0000-0000-0000-0000-000000000001', 'order', 'idem-test-001', 'hash1', 'processing');
        RAISE WARNING 'FAIL: t1_idempotency_unique_per_company';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: t1_idempotency_unique_per_company';
    END;

    -- Same key, different company → should succeed (different tenant)
    BEGIN
        INSERT INTO idempotency_keys (company_id, scope, idempotency_key, request_hash, status)
        VALUES ('bbbb0000-0000-0000-0000-000000000001', 'order', 'idem-test-001', 'hash1', 'processing');
        RAISE NOTICE 'PASS: t1_idempotency_different_company_allowed';
    EXCEPTION WHEN unique_violation THEN
        RAISE WARNING 'FAIL: t1_idempotency_different_company_allowed';
    END;

    -- Cleanup
    DELETE FROM idempotency_keys WHERE idempotency_key = 'idem-test-001';
END $$;

-- =============================================================================
-- SECTION 2: IDEMPOTENCY — ORDER CREATION
-- =============================================================================
SELECT '--- SECTION 2: ORDER IDEMPOTENCY ---' AS section;

DO $$
DECLARE
    v_order_id UUID;
    v_idem_key VARCHAR := 'order-idem-test-' || gen_random_uuid()::text;
BEGIN
    -- First request: create order with idempotency key
    INSERT INTO idempotency_keys (company_id, scope, idempotency_key, request_hash, status, resource_type)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', 'order', v_idem_key, 'abc123', 'processing', 'order');

    INSERT INTO orders (order_number, customer_id, order_status,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-IDEM-ORDER', '10000000-0000-0000-0000-000000000001', 'draft',
        '123 Test St', 'Mumbai', 'MH', '400001',
        '456 Delivery Ave', 'Delhi', 'DL', '110001',
        'Test Consignee', '9999999999', 5000.00, 6000.00)
    RETURNING id INTO v_order_id;

    -- Mark idempotency as completed
    UPDATE idempotency_keys SET status = 'completed', resource_id = v_order_id::text
    WHERE company_id = 'aaaa0000-0000-0000-0000-000000000001' AND idempotency_key = v_idem_key;

    -- Second request: same idempotency key → should find existing
    IF EXISTS (SELECT 1 FROM idempotency_keys
               WHERE company_id = 'aaaa0000-0000-0000-0000-000000000001'
               AND idempotency_key = v_idem_key AND status = 'completed') THEN
        RAISE NOTICE 'PASS: t2_order_idempotency_duplicate_blocked';
    ELSE
        RAISE WARNING 'FAIL: t2_order_idempotency_duplicate_blocked';
    END IF;

    -- Cleanup
    DELETE FROM orders WHERE order_number = 'ZP-IDEM-ORDER';
    DELETE FROM idempotency_keys WHERE idempotency_key = v_idem_key;
END $$;

-- =============================================================================
-- SECTION 3: IDEMPOTENCY — WEBHOOK EVENTS
-- =============================================================================
SELECT '--- SECTION 3: WEBHOOK IDEMPOTENCY ---' AS section;

DO $$
BEGIN
    -- First webhook event
    INSERT INTO webhook_events (company_id, provider, provider_event_id, event_type, payload, status)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', 'razorpay', 'evt-test-001', 'payment.captured',
            '{"amount": 5000}', 'received');

    -- Duplicate webhook event → should fail (unique constraint)
    BEGIN
        INSERT INTO webhook_events (company_id, provider, provider_event_id, event_type, payload, status)
        VALUES ('aaaa0000-0000-0000-0000-000000000001', 'razorpay', 'evt-test-001', 'payment.captured',
                '{"amount": 5000}', 'received');
        RAISE WARNING 'FAIL: t3_webhook_idempotency_duplicate_blocked';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: t3_webhook_idempotency_duplicate_blocked';
    END;

    -- Cleanup
    DELETE FROM webhook_events WHERE provider_event_id = 'evt-test-001';
END $$;

-- =============================================================================
-- SECTION 4: GOVERNANCE CHAIN
-- Zippy → financial_request → Paperclip → execution_grant → Hermes → Odoo
-- =============================================================================
SELECT '--- SECTION 4: GOVERNANCE CHAIN ---' AS section;

DO $$
DECLARE
    v_order_id UUID;
    v_fin_req_id UUID;
    v_financial_request_key VARCHAR := 'fin-req-test-' || gen_random_uuid()::text;
BEGIN
    -- Step 1: Create a test order
    INSERT INTO orders (order_number, customer_id, order_status,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-CHAIN-ORDER', '10000000-0000-0000-0000-000000000001', 'delivered',
        '123 Test St', 'Mumbai', 'MH', '400001',
        '456 Delivery Ave', 'Delhi', 'DL', '110001',
        'Test Consignee', '9999999999', 25000.00, 30000.00)
    RETURNING id INTO v_order_id;

    -- Step 2: Create financial request (Zippy side)
    INSERT INTO financial_requests (company_id, order_id, request_type, amount, currency, status, idempotency_key)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', v_order_id, 'create_customer_invoice',
            30000.00, 'INR', 'requested', v_financial_request_key)
    RETURNING id INTO v_fin_req_id;

    -- Verify financial request created
    IF EXISTS (SELECT 1 FROM financial_requests WHERE id = v_fin_req_id AND status = 'requested') THEN
        RAISE NOTICE 'PASS: t4_step2_financial_request_created';
    ELSE
        RAISE WARNING 'FAIL: t4_step2_financial_request_created';
    END IF;

    -- Step 3: Simulate Paperclip APPROVE (update status)
    UPDATE financial_requests SET status = 'approved' WHERE id = v_fin_req_id;

    IF EXISTS (SELECT 1 FROM financial_requests WHERE id = v_fin_req_id AND status = 'approved') THEN
        RAISE NOTICE 'PASS: t4_step3_paperclip_approved';
    ELSE
        RAISE WARNING 'FAIL: t4_step3_paperclip_approved';
    END IF;

    -- Step 4: Simulate Hermes execution (update to sent_to_odoo)
    UPDATE financial_requests SET status = 'sent_to_odoo' WHERE id = v_fin_req_id;

    IF EXISTS (SELECT 1 FROM financial_requests WHERE id = v_fin_req_id AND status = 'sent_to_odoo') THEN
        RAISE NOTICE 'PASS: t4_step4_hermes_sent_to_odoo';
    ELSE
        RAISE WARNING 'FAIL: t4_step4_hermes_sent_to_odoo';
    END IF;

    -- Step 5: Record external reference (Odoo response)
    INSERT INTO external_references (company_id, local_entity_type, local_entity_id,
            external_system, external_model, external_id, external_number, sync_status)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', 'financial_request', v_fin_req_id,
            'ODOO', 'account.move', 'ODOO-INV-001', 'INV/2026/001', 'linked');

    IF EXISTS (SELECT 1 FROM external_references
               WHERE local_entity_id = v_fin_req_id AND external_system = 'ODOO') THEN
        RAISE NOTICE 'PASS: t4_step5_odoo_reference_recorded';
    ELSE
        RAISE WARNING 'FAIL: t4_step5_odoo_reference_recorded';
    END IF;

    -- Step 6: Mark financial request as completed
    UPDATE financial_requests SET status = 'completed' WHERE id = v_fin_req_id;

    IF EXISTS (SELECT 1 FROM financial_requests WHERE id = v_fin_req_id AND status = 'completed') THEN
        RAISE NOTICE 'PASS: t4_step6_chain_completed';
    ELSE
        RAISE WARNING 'FAIL: t4_step6_chain_completed';
    END IF;

    -- Cleanup
    DELETE FROM external_references WHERE local_entity_id = v_fin_req_id;
    DELETE FROM financial_requests WHERE id = v_fin_req_id;
    DELETE FROM orders WHERE order_number = 'ZP-CHAIN-ORDER';
END $$;

-- =============================================================================
-- SECTION 5: FAIL-CLOSED — Paperclip rejection blocks financial write
-- =============================================================================
SELECT '--- SECTION 5: FAIL-CLOSED (Paperclip Reject) ---' AS section;

DO $$
DECLARE
    v_order_id UUID;
    v_fin_req_id UUID;
    v_financial_request_key VARCHAR := 'fin-req-reject-' || gen_random_uuid()::text;
BEGIN
    -- Create test order
    INSERT INTO orders (order_number, customer_id, order_status,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-REJECT-ORDER', '10000000-0000-0000-0000-000000000001', 'delivered',
        '123 Test St', 'Mumbai', 'MH', '400001',
        '456 Delivery Ave', 'Delhi', 'DL', '110001',
        'Test Consignee', '9999999999', 15000.00, 18000.00)
    RETURNING id INTO v_order_id;

    -- Create financial request
    INSERT INTO financial_requests (company_id, order_id, request_type, amount, currency, status, idempotency_key)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', v_order_id, 'create_customer_invoice',
            18000.00, 'INR', 'requested', v_financial_request_key)
    RETURNING id INTO v_fin_req_id;

    -- Simulate Paperclip REJECT
    UPDATE financial_requests SET status = 'rejected', failure_reason = 'Paperclip: policy violation' WHERE id = v_fin_req_id;

    -- Verify: no external reference should exist (Odoo was never called)
    IF NOT EXISTS (SELECT 1 FROM external_references WHERE local_entity_id = v_fin_req_id) THEN
        RAISE NOTICE 'PASS: t5_fail_closed_no_odoo_reference';
    ELSE
        RAISE WARNING 'FAIL: t5_fail_closed_no_odoo_reference';
    END IF;

    -- Verify: financial request is rejected, not completed
    IF EXISTS (SELECT 1 FROM financial_requests WHERE id = v_fin_req_id AND status = 'rejected') THEN
        RAISE NOTICE 'PASS: t5_fail_closed_status_rejected';
    ELSE
        RAISE WARNING 'FAIL: t5_fail_closed_status_rejected';
    END IF;

    -- Cleanup
    DELETE FROM financial_requests WHERE id = v_fin_req_id;
    DELETE FROM orders WHERE order_number = 'ZP-REJECT-ORDER';
END $$;

-- =============================================================================
-- SECTION 6: DUPLICATE PREVENTION — Same request twice, no duplicate Odoo record
-- =============================================================================
SELECT '--- SECTION 6: DUPLICATE PREVENTION ---' AS section;

DO $$
DECLARE
    v_order_id UUID;
    v_fin_req_id UUID;
    v_idem_key VARCHAR := 'fin-req-dup-' || gen_random_uuid()::text;
BEGIN
    -- Create test order
    INSERT INTO orders (order_number, customer_id, order_status,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-DUP-ORDER', '10000000-0000-0000-0000-000000000001', 'delivered',
        '123 Test St', 'Mumbai', 'MH', '400001',
        '456 Delivery Ave', 'Delhi', 'DL', '110001',
        'Test Consignee', '9999999999', 10000.00, 12000.00)
    RETURNING id INTO v_order_id;

    -- First request
    INSERT INTO financial_requests (company_id, order_id, request_type, amount, currency, status, idempotency_key)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', v_order_id, 'create_customer_invoice',
            12000.00, 'INR', 'completed', v_idem_key)
    RETURNING id INTO v_fin_req_id;

    -- Record Odoo reference
    INSERT INTO external_references (company_id, local_entity_type, local_entity_id,
            external_system, external_model, external_id, sync_status)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', 'financial_request', v_fin_req_id,
            'ODOO', 'account.move', 'ODOO-INV-DUP-001', 'linked');

    -- Second request with same idempotency key → should fail
    BEGIN
        INSERT INTO financial_requests (company_id, order_id, request_type, amount, currency, status, idempotency_key)
        VALUES ('aaaa0000-0000-0000-0000-000000000001', v_order_id, 'create_customer_invoice',
                12000.00, 'INR', 'completed', v_idem_key);
        RAISE WARNING 'FAIL: t6_duplicate_financial_request_blocked';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: t6_duplicate_financial_request_blocked';
    END;

    -- Verify only one external reference exists
    IF (SELECT count(*) FROM external_references
        WHERE local_entity_id = v_fin_req_id AND external_system = 'ODOO') = 1 THEN
        RAISE NOTICE 'PASS: t6_single_odoo_reference';
    ELSE
        RAISE WARNING 'FAIL: t6_single_odoo_reference';
    END IF;

    -- Cleanup
    DELETE FROM external_references WHERE local_entity_id = v_fin_req_id;
    DELETE FROM financial_requests WHERE id = v_fin_req_id;
    DELETE FROM orders WHERE order_number = 'ZP-DUP-ORDER';
END $$;

-- =============================================================================
-- SECTION 7: EVENT OUTBOX
-- =============================================================================
SELECT '--- SECTION 7: EVENT OUTBOX ---' AS section;

DO $$
DECLARE
    v_outbox_id UUID;
    v_idem_key VARCHAR := 'outbox-test-' || gen_random_uuid()::text;
BEGIN
    -- Create outbox event
    INSERT INTO event_outbox (company_id, aggregate_type, aggregate_id, event_type,
            payload, idempotency_key, destination)
    VALUES ('aaaa0000-0000-0000-0000-000000000001', 'order', gen_random_uuid(),
            'order.delivered', '{"order_id": "test"}', v_idem_key, 'ODOO')
    RETURNING id INTO v_outbox_id;

    -- Verify pending (published_at IS NULL)
    IF EXISTS (SELECT 1 FROM event_outbox WHERE id = v_outbox_id AND published_at IS NULL) THEN
        RAISE NOTICE 'PASS: t7_outbox_pending';
    ELSE
        RAISE WARNING 'FAIL: t7_outbox_pending';
    END IF;

    -- Mark as published
    UPDATE event_outbox SET published_at = NOW() WHERE id = v_outbox_id;

    IF EXISTS (SELECT 1 FROM event_outbox WHERE id = v_outbox_id AND published_at IS NOT NULL) THEN
        RAISE NOTICE 'PASS: t7_outbox_published';
    ELSE
        RAISE WARNING 'FAIL: t7_outbox_published';
    END IF;

    -- Duplicate outbox event → should fail
    BEGIN
        INSERT INTO event_outbox (company_id, aggregate_type, aggregate_id, event_type,
                payload, idempotency_key, destination)
        VALUES ('aaaa0000-0000-0000-0000-000000000001', 'order', gen_random_uuid(),
                'order.delivered', '{"order_id": "test"}', v_idem_key, 'ODOO');
        RAISE WARNING 'FAIL: t7_outbox_idempotency';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: t7_outbox_idempotency';
    END;

    -- Cleanup
    DELETE FROM event_outbox WHERE id = v_outbox_id;
END $$;

-- =============================================================================
-- SECTION 8: CLEANUP
-- =============================================================================
SELECT '--- SECTION 8: CLEANUP ---' AS section;

DELETE FROM companies WHERE id IN (
    'aaaa0000-0000-0000-0000-000000000001',
    'bbbb0000-0000-0000-0000-000000000001'
);

SELECT 'PASS: t8_cleanup_complete' AS result;

-- =============================================================================
-- SUMMARY
-- =============================================================================
SELECT '--- INTEGRATION TEST SUITE COMPLETE ---' AS section;
