-- =============================================================================
-- M2 Verification Suite — pricing / matching / payment rules
-- Usage:
--   docker cp infra/supabase/verify_m2.sql zippy-db:/tmp/v2.sql
--   docker exec zippy-db psql -U postgres -d postgres -f /tmp/v2.sql
-- Everything runs inside one transaction and ROLLS BACK.
-- =============================================================================

\set ON_ERROR_STOP off

BEGIN;

-- -----------------------------------------------------------------------------
-- T1: reference data seeded
-- -----------------------------------------------------------------------------
SELECT CASE WHEN count(*) = 4 THEN 'PASS' ELSE 'FAIL' END AS t1_rate_bands FROM public.pricing_rate_bands;
SELECT CASE WHEN count(*) = 4 THEN 'PASS' ELSE 'FAIL' END AS t1_toll_bands FROM public.pricing_toll_bands;

-- -----------------------------------------------------------------------------
-- T2: class inference (incl. gap-resolution upward)
-- -----------------------------------------------------------------------------
SELECT CASE WHEN public.infer_vehicle_class(1.0)  = 'Mini Truck'
             AND public.infer_vehicle_class(3.0)  = 'LCV'
             AND public.infer_vehicle_class(8.0)  = 'MCV'
             AND public.infer_vehicle_class(15.0) = 'HCV'
            THEN 'PASS' ELSE 'FAIL' END AS t2_inference;

DO $$
BEGIN
    PERFORM public.infer_vehicle_class(45.0);
    RAISE NOTICE 'FAIL t2_overload_rejected';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'CARGO_EXCEEDS_MAX_CAPACITY%' THEN
        RAISE NOTICE 'PASS t2_overload_rejected';
    ELSE
        RAISE NOTICE 'FAIL t2_overload_rejected (wrong error: %)', SQLERRM;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T3: quote math — hand-computed fixtures
--   Fixture A: HCV @1000 km, w=NULL -> midpoint 60/km
--     freight 60000 | toll(band4) 2600 | loading 1800 | tax 3220 | total 67620
--   Fixture B: LCV @50 km, w=2t (min edge 15/km)
--     freight 750 | toll(band1) 85 | loading 22.50 | tax 42.88 | total 900.38
-- -----------------------------------------------------------------------------
SELECT CASE WHEN q.rate_per_km = 60 AND q.freight_amount = 60000
              AND q.toll_amount = 2600 AND q.loading_amount = 1800
              AND q.tax_amount = 3220  AND q.total_amount = 67620
            THEN 'PASS' ELSE 'FAIL' END AS t3_fixture_a_hcv_1000km
FROM public.calculate_quote('HCV', 1000, NULL) q;

SELECT CASE WHEN q.rate_per_km = 15 AND q.freight_amount = 750
              AND q.toll_amount = 85  AND q.loading_amount = 22.50
              AND q.tax_amount = 42.88 AND q.total_amount = 900.38
            THEN 'PASS' ELSE 'FAIL' END AS t3_fixture_b_lcv_edge
FROM public.calculate_quote('LCV', 50, 2) q;

DO $$
BEGIN
    PERFORM public.calculate_quote('LCV', 50, 8);   -- exceeds class capacity
    RAISE NOTICE 'FAIL t3_class_capacity_guard';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'CARGO_EXCEEDS_CLASS_CAPACITY%' THEN
        RAISE NOTICE 'PASS t3_class_capacity_guard';
    ELSE
        RAISE NOTICE 'FAIL t3_class_capacity_guard (wrong error: %)', SQLERRM;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- T4: order-level quote persistence + traceable event
--     10 t -> MCV; weight interpolated: rate = 20 + (10-9)/(12-9)*10 = 23.33
--     dist 120 | freight 2800.00 | toll 415 | loading 84.00 | tax 164.95 | total 3463.95
-- -----------------------------------------------------------------------------
INSERT INTO orders (order_number, customer_id,
    pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
    delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
    consignee_name, consignee_phone, base_amount, total_amount,
    estimated_distance, cargo_weight)
VALUES ('ZP-M2', '10000000-0000-0000-0000-000000000001',
    'P', 'X', 'S', '1', 'D', 'Y', 'S', '2',
    'N', '9000000000', 1, 1,           -- overwritten by quote engine below
    120.00, 10.00);

DO $$
DECLARE r RECORD; v_order UUID;
BEGIN
    SELECT order_id INTO v_order FROM orders WHERE order_number='ZP-M2';

    SELECT * INTO r FROM public.generate_order_quote(v_order);

    IF r.vehicle_class='MCV' AND r.rate_per_km=23.33 AND r.freight_amount=2800
       AND r.toll_amount=415 AND r.loading_amount=84 AND r.tax_amount=164.95 AND r.total_amount=3463.95 THEN
        RAISE NOTICE 'PASS t4_quote_values';
    ELSE
        RAISE NOTICE 'FAIL t4_quote_values (%)', jsonb_build_object(
            'class', r.vehicle_class, 'rate', r.rate_per_km,
            'freight', r.freight_amount, 'toll', r.toll_amount,
            'loading', r.loading_amount, 'tax', r.tax_amount, 'total', r.total_amount);
    END IF;

    IF EXISTS (SELECT 1 FROM orders WHERE order_id=v_order
                AND base_amount=2800+415+84 AND tax_amount=164.95 AND total_amount=3463.95) THEN
        RAISE NOTICE 'PASS t4_order_persisted';
    ELSE
        RAISE NOTICE 'FAIL t4_order_persisted';
    END IF;

    IF EXISTS (SELECT 1 FROM order_event_log WHERE order_id=v_order
                AND event_type='order_quote_generated') THEN
        RAISE NOTICE 'PASS t4_event_logged';
    ELSE
        RAISE NOTICE 'FAIL t4_event_logged';
    END IF;

    -- non-pending orders cannot be re-quoted
    PERFORM transition_order(v_order, 'inventory_confirmed', NULL, 'system');
    BEGIN
        PERFORM public.generate_order_quote(v_order);
        RAISE NOTICE 'FAIL t4_pending_only';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'QUOTE_ONLY_FOR_PENDING_ORDERS%' THEN
            RAISE NOTICE 'PASS t4_pending_only';
        ELSE
            RAISE NOTICE 'FAIL t4_pending_only (wrong error: %)', SQLERRM;
        END IF;
    END;
END $$;

-- -----------------------------------------------------------------------------
-- T5: payment-plan rules
-- -----------------------------------------------------------------------------
SELECT CASE WHEN public.validate_payment_plan('full',1000,1000)
             AND public.validate_payment_plan('partial',1000,500)      -- exactly 50% floor
             AND public.validate_payment_plan('partial',1000,700)
             AND public.validate_payment_plan('to_pay',1000,0)
            THEN 'PASS' ELSE 'FAIL' END AS t5_valid_plans;

DO $$
BEGIN
    BEGIN
        PERFORM public.validate_payment_plan('full',1000,999);
        RAISE NOTICE 'FAIL t5_full_mismatch_rejected';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'PASS t5_full_mismatch_rejected (%)', SQLERRM;
    END;

    BEGIN
        PERFORM public.validate_payment_plan('partial',1000,499.99);
        RAISE NOTICE 'FAIL t5_partial_below_floor_rejected';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'PASS t5_partial_below_floor_rejected (%)', SQLERRM;
    END;

    BEGIN
        PERFORM public.validate_payment_plan('to_pay',1000,1);
        RAISE NOTICE 'FAIL t5_topay_advance_rejected';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'PASS t5_topay_advance_rejected (%)', SQLERRM;
    END;

    BEGIN
        PERFORM public.validate_payment_plan('emi',1000,500);
        RAISE NOTICE 'FAIL t5_unknown_mode_rejected';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'PASS t5_unknown_mode_rejected (%)', SQLERRM;
    END;
END $$;

-- -----------------------------------------------------------------------------
-- T6: payment-hold insert guard (block → override → allow)
-- -----------------------------------------------------------------------------
UPDATE users SET payment_hold=true WHERE user_id='00000000-0000-0000-0000-000000000002';

DO $$
BEGIN
    INSERT INTO orders (order_number, customer_id,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-M2-BLOCKED', '10000000-0000-0000-0000-000000000001',
        'P','X','S','1','D','Y','S','2','N','9000000000', 100, 100);
    RAISE NOTICE 'FAIL t6_hold_blocks_insert';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'PAYMENT_HOLD_ACTIVE%' THEN
        RAISE NOTICE 'PASS t6_hold_blocks_insert';
    ELSE
        RAISE NOTICE 'FAIL t6_hold_blocks_insert (wrong error: %)', SQLERRM;
    END IF;
END $$;

INSERT INTO admin_actions (admin_id, action_type, target_type, target_id, reason, expires_at)
VALUES ('00000000-0000-0000-0000-000000000001', 'allow_user_with_pending_payment', 'user',
        '00000000-0000-0000-0000-000000000002', 'M2 verification override', CURRENT_TIMESTAMP + INTERVAL '1 day');

DO $$
BEGIN
    INSERT INTO orders (order_number, customer_id,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        consignee_name, consignee_phone, base_amount, total_amount)
    VALUES ('ZP-M2-OVERRIDE', '10000000-0000-0000-0000-000000000001',
        'P','X','S','1','D','Y','S','2','N','9000000000', 100, 100);
    RAISE NOTICE 'PASS t6_override_allows_insert';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'FAIL t6_override_allows_insert (%)', SQLERRM;
END $$;

UPDATE users SET payment_hold=false WHERE user_id='00000000-0000-0000-0000-000000000002';

-- -----------------------------------------------------------------------------
-- T7: match_nearby_drivers (D-05 identity + score ordering + filters)
-- -----------------------------------------------------------------------------
UPDATE vehicles SET current_location = ST_SetSRID(ST_MakePoint(72.8777, 19.0760),4326)::geography,
                    current_status='online'
WHERE vehicle_id='50000000-0000-0000-0000-000000000001';   -- rated 5.0 LCV 2.5t

SELECT CASE WHEN count(*) >= 1 THEN 'PASS' ELSE 'FAIL' END AS t7_match_finds_nearby
FROM public.match_nearby_drivers(
    ST_SetSRID(ST_MakePoint(72.8778, 19.0761),4326)::geography,
    5000, 10);

SELECT CASE WHEN m.user_id = '00000000-0000-0000-0000-000000000003' THEN 'PASS' ELSE 'FAIL' END AS t7_d05_users_uuid
FROM public.match_nearby_drivers(
    ST_SetSRID(ST_MakePoint(72.8778, 19.0761),4326)::geography,
    5000, 10) m LIMIT 1;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS t7_capacity_filter_excludes
FROM public.match_nearby_drivers(
    ST_SetSRID(ST_MakePoint(72.8778, 19.0761),4326)::geography,
    5000, 10, NULL, 30.0);                                 -- 30 t >> 2.5 t capacity

ROLLBACK;
