-- =============================================================================
-- M1 Verification Suite — run after migrations against any zippy DB instance
-- Usage:
--   docker cp infra/supabase/verify_m1.sql zippy-db:/tmp/v.sql
--   docker exec zippy-db psql -U postgres -d postgres -f /tmp/v.sql
-- Every assertion prints PASS / FAIL; intentional-error cases are contained.
-- =============================================================================

\set ON_ERROR_STOP off

-- -----------------------------------------------------------------------------
-- 0. Structure
-- -----------------------------------------------------------------------------
SELECT CASE WHEN count(*) >= 18 THEN 'PASS' ELSE 'FAIL' END AS t0_table_count
FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';

SELECT CASE WHEN count(*) = 4 THEN 'PASS' ELSE 'FAIL' END AS t0_extensions
FROM pg_extension WHERE extname IN ('postgis','vector','uuid-ossp','pgcrypto');

-- -----------------------------------------------------------------------------
-- 1. Commission triggers (deterministic: wipe prior verification rows)
-- -----------------------------------------------------------------------------
DELETE FROM orders WHERE order_number IN ('ZP-VERIFY-DRV', 'ZP-VERIFY-CO');

INSERT INTO orders (order_number, customer_id, provider_type, driver_id, order_status,
    pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
    delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
    consignee_name, consignee_phone, base_amount, total_amount)
VALUES ('ZP-VERIFY-DRV', '10000000-0000-0000-0000-000000000001', 'driver',
    '20000000-0000-0000-0000-000000000001', 'payment_succeeded',
    'A', 'X', 'S', '1', 'B', 'Y', 'S', '2', 'N', '9000000000', 10000, 10000);

INSERT INTO orders (order_number, customer_id, provider_type, transport_company_id, order_status,
    pickup_address_line1, pickup_city, pickup_state, pickup_postal_code,
    delivery_address_line1, delivery_city, delivery_state, delivery_postal_code,
    consignee_name, consignee_phone, base_amount, total_amount)
VALUES ('ZP-VERIFY-CO', '10000000-0000-0000-0000-000000000001', 'transport_company',
    '30000000-0000-0000-0000-000000000001', 'pending',
    'A', 'X', 'S', '1', 'B', 'Y', 'S', '2', 'N', '9000000000', 25000, 25000);

SELECT CASE WHEN commission_amount = 1000 AND service_fee = 0 THEN 'PASS' ELSE 'FAIL' END AS t1_driver_10pct,
       CASE WHEN (SELECT service_fee FROM orders WHERE order_number='ZP-VERIFY-CO') = 700
            AND (SELECT commission_amount FROM orders WHERE order_number='ZP-VERIFY-CO') = 0
            THEN 'PASS' ELSE 'FAIL' END AS t1_company_flat700
FROM orders WHERE order_number='ZP-VERIFY-DRV';

-- -----------------------------------------------------------------------------
-- 2. State machine (row starts at payment_succeeded per section 1)
-- -----------------------------------------------------------------------------
DO $$
DECLARE v_id UUID;
BEGIN
    SELECT order_id INTO v_id FROM orders WHERE order_number='ZP-VERIFY-DRV';

    PERFORM transition_order(v_id, 'driver_assigned', NULL, 'system');           -- legal
    IF (SELECT order_status FROM orders WHERE order_id=v_id) = 'driver_assigned'
       THEN RAISE NOTICE 'PASS t2_legal_transition'; ELSE RAISE NOTICE 'FAIL t2_legal_transition'; END IF;

    PERFORM transition_order(v_id, 'driver_assigned', NULL, 'system');           -- idempotent
    RAISE NOTICE 'PASS t2_idempotent';

    BEGIN
        PERFORM transition_order(v_id, 'delivered', NULL, 'system');             -- illegal skip
        RAISE NOTICE 'FAIL t2_illegal_skip_rejected';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'PASS t2_illegal_skip_rejected';
    END;

    BEGIN
        PERFORM transition_order(v_id, 'payment_succeeded', NULL, 'system');     -- backward
        RAISE NOTICE 'FAIL t2_backward_rejected';
    EXCEPTION WHEN raise_exception THEN
        RAISE NOTICE 'PASS t2_backward_rejected';
    END;
END $$;

-- -----------------------------------------------------------------------------
-- 3. Long-halt alert trigger
-- -----------------------------------------------------------------------------
TRUNCATE vehicle_telemetry;
DELETE FROM driver_alerts WHERE alert_type='long_halt'
   AND created_at > NOW() - INTERVAL '5 minutes';

INSERT INTO vehicle_telemetry (vehicle_id, driver_id, latitude, longitude, recorded_at)
VALUES ('50000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
        19.0760, 72.8777, CLOCK_TIMESTAMP() - INTERVAL '35 minutes');
INSERT INTO vehicle_telemetry (vehicle_id, driver_id, latitude, longitude)
VALUES ('50000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
        19.0761, 72.8778);

SELECT CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS t3_long_halt_alert
FROM driver_alerts WHERE alert_status='active' AND created_at > NOW() - INTERVAL '1 minute';

-- -----------------------------------------------------------------------------
-- 4. Views
-- -----------------------------------------------------------------------------
SELECT CASE WHEN total_customers >= 1 AND total_drivers >= 1 THEN 'PASS' ELSE 'FAIL' END AS t4_admin_view
FROM admin_dashboard_view;
SELECT CASE WHEN count(*) >= 1 THEN 'PASS' ELSE 'FAIL' END AS t4_company_stats
FROM transport_company_role_stats;

-- -----------------------------------------------------------------------------
-- 5. RLS cross-tenant denial (requires non-owner role; owner bypasses RLS)
-- -----------------------------------------------------------------------------
DO $probe$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='m1_rls_probe') THEN
        EXECUTE 'REASSIGN OWNED BY m1_rls_probe TO postgres';
        EXECUTE 'DROP OWNED BY m1_rls_probe';
        EXECUTE 'DROP ROLE m1_rls_probe';
    END IF;
END $probe$;

CREATE ROLE m1_rls_probe LOGIN PASSWORD 'm1probe';
GRANT USAGE ON SCHEMA public TO m1_rls_probe;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO m1_rls_probe;

\echo 'INFO t5: run manual probe: docker exec zippy-db psql -U m1_rls_probe -d postgres -c "SELECT set_config(...current_user_id...,false); SELECT count(*) FROM orders;"'
