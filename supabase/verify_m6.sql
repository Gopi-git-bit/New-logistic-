-- =============================================================================
-- M6 Verification Suite — E2E order lifecycle (pending → delivered → settled)
-- Self-contained; uses SAVEPOINT for idempotent re-runs.
-- =============================================================================

\set ON_ERROR_STOP off

BEGIN;

-- T1: RPCs exist
SELECT CASE WHEN count(*) >= 4 THEN 'PASS' ELSE 'FAIL' END AS t1_m6_rpcs_exist
FROM pg_proc WHERE proname IN (
    'generate_order_quote', 'match_nearby_drivers',
    'assign_order_provider', 'validate_payment_plan'
);

-- T2: validate_payment_plan — full payment requires advance = total
SELECT CASE WHEN public.validate_payment_plan('full', 1000, 1000) = true
            THEN 'PASS' ELSE 'FAIL' END AS t2_validate_full;

-- T3: validate_payment_plan — partial >= 50% valid
SELECT CASE WHEN public.validate_payment_plan('partial', 1000, 500) = true
            THEN 'PASS' ELSE 'FAIL' END AS t3_validate_partial_valid;

-- T4: validate_payment_plan — partial < 50% rejected
DO $$
BEGIN
    PERFORM public.validate_payment_plan('partial', 1000, 200);
    RAISE NOTICE 'FAIL t4_validate_partial_reject (should have raised)';
EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE '%PARTIAL_MODE_MIN_50_PCT%' THEN
        RAISE NOTICE 'PASS t4_validate_partial_reject';
    ELSE
        RAISE NOTICE 'FAIL t4_validate_partial_reject (wrong error: %)', SQLERRM;
    END IF;
END $$;

-- T5: validate_payment_plan — to_pay with advance > 0 rejected
DO $$
BEGIN
    PERFORM public.validate_payment_plan('to_pay', 1000, 100);
    RAISE NOTICE 'FAIL t5_validate_topay_reject (should have raised)';
EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE '%TOPAY_MODE_NO_ADVANCE%' THEN
        RAISE NOTICE 'PASS t5_validate_topay_reject';
    ELSE
        RAISE NOTICE 'FAIL t5_validate_topay_reject (wrong error: %)', SQLERRM;
    END IF;
END $$;

-- T5b: validate_payment_plan — to_pay (advance=0) valid
SELECT CASE WHEN public.validate_payment_plan('to_pay', 1000, 0) = true
            THEN 'PASS' ELSE 'FAIL' END AS t5b_validate_topay;

-- T6: generate_order_quote on a pending order with locations
DO $$
DECLARE
    v_order_id UUID;
    v_quote RECORD;
    v_cust UUID;
BEGIN
    SELECT customer_id INTO v_cust FROM public.customer_profiles LIMIT 1;
    IF v_cust IS NULL THEN
        RAISE NOTICE 'FAIL t6_quote (no customer_profiles)';
        RETURN;
    END IF;

    INSERT INTO public.orders (
        order_number, customer_id, order_status,
        pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
        pickup_latitude, pickup_longitude,
        pickup_location,
        delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
        delivery_latitude, delivery_longitude,
        delivery_location,
        consignee_name, consignee_phone, consignee_email,
        cargo_description, cargo_weight, cargo_volume,
        estimated_distance, estimated_duration,
        base_amount, total_amount
    ) VALUES (
        'ZP-M6-TEST-001', v_cust, 'pending',
        'Mumbai Gateway', 'Mumbai', 'Maharashtra', '400001',
        18.9388, 72.8354,
        ST_SetSRID(ST_MakePoint(72.8354, 18.9388), 4326)::geography,
        'Pune Hub', 'Pune', 'Maharashtra', '411001',
        18.5204, 73.8567,
        ST_SetSRID(ST_MakePoint(73.8567, 18.5204), 4326)::geography,
        'Consignee', '+919000000001', 'consignee@zippy.local',
        'Electronics', 2.5, 5.0,
        150.0, 180,
        1, 1
    ) RETURNING order_id INTO v_order_id;

    -- Generate quote
    SELECT * INTO v_quote FROM public.generate_order_quote(v_order_id);

    IF v_quote IS NOT NULL AND v_quote.total_amount > 0 THEN
        RAISE NOTICE 'PASS t6_quote (total=%, class=%)', v_quote.total_amount, v_quote.vehicle_class;
    ELSE
        RAISE NOTICE 'FAIL t6_quote';
    END IF;

    -- Verify order updated with amounts
    IF EXISTS (SELECT 1 FROM public.orders
               WHERE order_id = v_order_id AND total_amount > 0) THEN
        RAISE NOTICE 'PASS t6_amounts_persisted';
    ELSE
        RAISE NOTICE 'FAIL t6_amounts_persisted';
    END IF;

    -- Verify order_event_log entry
    IF EXISTS (SELECT 1 FROM public.order_event_log
               WHERE order_id = v_order_id AND event_type = 'order_quote_generated') THEN
        RAISE NOTICE 'PASS t6_quote_logged';
    ELSE
        RAISE NOTICE 'FAIL t6_quote_logged';
    END IF;
END $$;

-- T7: match_nearby_drivers — set up vehicle location + match
DO $$
DECLARE
    v_vehicle UUID;
    v_driver UUID;
    v_user UUID;
    v_result RECORD;
    v_count INTEGER;
BEGIN
    -- Set vehicle MH-01-AB-1234 online with location near Mumbai pickup
    UPDATE public.vehicles
       SET current_status = 'online',
           current_location = ST_SetSRID(ST_MakePoint(72.836, 18.939), 4326)::geography,
           last_seen_at = now()
     WHERE registration_number = 'MH-01-AB-1234'
     RETURNING vehicle_id INTO v_vehicle;

    IF v_vehicle IS NULL THEN
        RAISE NOTICE 'FAIL t7_match (no vehicle MH-01-AB-1234)';
        RETURN;
    END IF;

    -- Match from Mumbai gateway (slightly offset)
    v_count := 0;
    FOR v_result IN
        SELECT * FROM public.match_nearby_drivers(
            ST_SetSRID(ST_MakePoint(72.8354, 18.9388), 4326)::geography,
            10000, 5, NULL, NULL
        )
    LOOP
        v_count := v_count + 1;
        IF v_result.vehicle_id = v_vehicle THEN
            RAISE NOTICE 'PASS t7_match (found vehicle, dist=%m, score=%)',
                v_result.distance_m, v_result.score;
        END IF;
    END LOOP;

    IF v_count = 0 THEN
        RAISE NOTICE 'FAIL t7_match (no drivers found)';
    END IF;
END $$;

-- T8: Full lifecycle — pending → driver_assigned → in_transit → delivered
DO $$
DECLARE
    v_order_id UUID;
BEGIN
    SELECT order_id INTO v_order_id
      FROM public.orders
     WHERE order_status = 'pending'
       AND order_number = 'ZP-M6-TEST-001';

    IF v_order_id IS NULL THEN
        RAISE NOTICE 'FAIL t8_lifecycle (no pending order)';
        RETURN;
    END IF;

    -- pending → inventory_confirmed (payment success)
    PERFORM public.transition_order(v_order_id, 'inventory_confirmed');
    IF (SELECT order_status FROM public.orders WHERE order_id = v_order_id) = 'inventory_confirmed' THEN
        RAISE NOTICE 'PASS t8_pending_to_inventory';
    ELSE
        RAISE NOTICE 'FAIL t8_pending_to_inventory';
    END IF;

    -- inventory_confirmed → payment_succeeded
    PERFORM public.transition_order(v_order_id, 'payment_succeeded');
    IF (SELECT order_status FROM public.orders WHERE order_id = v_order_id) = 'payment_succeeded' THEN
        RAISE NOTICE 'PASS t8_inventory_to_payment';
    ELSE
        RAISE NOTICE 'FAIL t8_inventory_to_payment';
    END IF;

    -- payment_succeeded → driver_assigned
    PERFORM public.transition_order(v_order_id, 'driver_assigned');
    IF (SELECT order_status FROM public.orders WHERE order_id = v_order_id) = 'driver_assigned' THEN
        RAISE NOTICE 'PASS t8_payment_to_assigned';
    ELSE
        RAISE NOTICE 'FAIL t8_payment_to_assigned';
    END IF;

    -- driver_assigned → in_transit
    PERFORM public.transition_order(v_order_id, 'in_transit');
    IF (SELECT order_status FROM public.orders WHERE order_id = v_order_id) = 'in_transit' THEN
        RAISE NOTICE 'PASS t8_assigned_to_transit';
    ELSE
        RAISE NOTICE 'FAIL t8_assigned_to_transit';
    END IF;

    -- in_transit → delivered
    PERFORM public.transition_order(v_order_id, 'delivered');
    IF (SELECT order_status FROM public.orders WHERE order_id = v_order_id) = 'delivered' THEN
        RAISE NOTICE 'PASS t8_transit_to_delivered';
    ELSE
        RAISE NOTICE 'FAIL t8_transit_to_delivered';
    END IF;

    -- delivered → payment_settled
    PERFORM public.transition_order(v_order_id, 'payment_settled');
    IF (SELECT order_status FROM public.orders WHERE order_id = v_order_id) = 'payment_settled' THEN
        RAISE NOTICE 'PASS t8_delivered_to_settled';
    ELSE
        RAISE NOTICE 'FAIL t8_delivered_to_settled';
    END IF;
END $$;

-- T9: assign_order_provider assigns correctly
DO $$
DECLARE
    v_order_id UUID;
    v_driver_user UUID;
    v_driver_id UUID;
BEGIN
    SELECT order_id INTO v_order_id
      FROM public.orders
     WHERE order_number = 'ZP-M6-TEST-001';

    IF v_order_id IS NULL THEN
        RAISE NOTICE 'FAIL t9_assign (no order)';
        RETURN;
    END IF;

    -- Get driver's user_id
    SELECT dp.user_id, dp.driver_id INTO v_driver_user, v_driver_id
      FROM public.driver_profiles dp
     LIMIT 1;

    IF v_driver_user IS NULL THEN
        RAISE NOTICE 'FAIL t9_assign (no driver)';
        RETURN;
    END IF;

    -- Reset order to inventory_confirmed for assignment
    UPDATE public.orders SET order_status = 'inventory_confirmed',
                              provider_id = NULL, driver_id = NULL
     WHERE order_id = v_order_id;

    PERFORM public.assign_order_provider(v_order_id, v_driver_user, 'driver');

    IF EXISTS (SELECT 1 FROM public.orders
               WHERE order_id = v_order_id
                 AND provider_id = v_driver_user
                 AND driver_id = v_driver_id
                 AND provider_type = 'driver') THEN
        RAISE NOTICE 'PASS t9_assign (provider_id=%, driver_id=%)', v_driver_user, v_driver_id;
    ELSE
        RAISE NOTICE 'FAIL t9_assign';
    END IF;
END $$;

-- T10: Idempotent re-quote on non-pending order
DO $$
DECLARE
    v_order_id UUID;
    v_quote RECORD;
BEGIN
    SELECT order_id INTO v_order_id
      FROM public.orders
     WHERE order_number = 'ZP-M6-TEST-001';

    IF v_order_id IS NULL THEN
        RAISE NOTICE 'FAIL t10_idempotent_quote (no order)';
        RETURN;
    END IF;

    -- Order is no longer pending → should raise
    BEGIN
        SELECT * INTO v_quote FROM public.generate_order_quote(v_order_id);
        RAISE NOTICE 'FAIL t10_idempotent_quote (should have raised)';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE '%QUOTE_ONLY_FOR_PENDING%' THEN
            RAISE NOTICE 'PASS t10_idempotent_quote';
        ELSE
            RAISE NOTICE 'FAIL t10_idempotent_quote (wrong error: %)', SQLERRM;
        END IF;
    END;
END $$;

-- T11: Commission auto-calculated on provider assignment
DO $$
DECLARE
    v_order_id UUID;
    v_comm NUMERIC;
BEGIN
    SELECT order_id INTO v_order_id
      FROM public.orders
     WHERE order_number = 'ZP-M6-TEST-001'
       AND provider_type = 'driver';

    IF v_order_id IS NULL THEN
        RAISE NOTICE 'FAIL t11_commission (no assigned order)';
        RETURN;
    END IF;

    SELECT commission_amount INTO v_comm FROM public.orders WHERE order_id = v_order_id;

    IF v_comm IS NOT NULL AND v_comm > 0 THEN
        RAISE NOTICE 'PASS t11_commission (amount=%)', v_comm;
    ELSE
        RAISE NOTICE 'FAIL t11_commission (commission=%)', v_comm;
    END IF;
END $$;

-- T12: order_event_log has lifecycle entries
DO $$
DECLARE
    v_order_id UUID;
    v_event_count INTEGER;
BEGIN
    SELECT order_id INTO v_order_id
      FROM public.orders
     WHERE order_number = 'ZP-M6-TEST-001';

    SELECT count(*) INTO v_event_count
      FROM public.order_event_log
     WHERE order_id = v_order_id;

    IF v_event_count >= 1 THEN
        RAISE NOTICE 'PASS t12_event_log (events=%)', v_event_count;
    ELSE
        RAISE NOTICE 'FAIL t12_event_log (events=%)', v_event_count;
    END IF;
END $$;

ROLLBACK;
