\set ON_ERROR_STOP on

\if :{?expected_session_user}
\else
    \echo 'expected_session_user is required'
    \quit 1
\endif

CREATE OR REPLACE FUNCTION pg_temp.assert_true(condition boolean, message text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF condition IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'assertion failed: %', message;
    END IF;
END;
$$;

SELECT pg_temp.assert_true(session_user = :'expected_session_user', 'expected restricted application LOGIN is the session identity');
SELECT pg_temp.assert_true(current_user = :'expected_session_user', 'application LOGIN uses inherited zippy_app membership without owner impersonation');
SELECT pg_temp.assert_true(
    NOT (SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname = current_user),
    'application LOGIN has no superuser, role, database, or RLS-bypass capability'
);
SELECT pg_temp.assert_true(pg_has_role(current_user, 'zippy_app', 'member'), 'application LOGIN is a zippy_app member');
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1
          FROM pg_tables
         WHERE schemaname = 'zippy'
           AND tableowner = current_user
    ),
    'application LOGIN owns no Zippy table'
);
SELECT pg_temp.assert_true(current_database() LIKE 'zippy_m2_disposable_%', 'database is disposable');
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.schema_migrations) = 4,
    'all canonical migrations are recorded'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1
          FROM pg_constraint constraint_record
         WHERE constraint_record.contype = 'f'
           AND constraint_record.confrelid = 0
    ),
    'no unresolved foreign-key targets exist'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1 FROM pg_tables
         WHERE schemaname = 'zippy'
           AND (tablename LIKE 'odoo_%' OR tablename LIKE 'paperclip_%')
    ),
    'no Odoo or Paperclip core tables exist in Zippy'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp', 'postgis')
    ),
    'no unneeded extension is installed'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'zippy'
           AND table_name = 'pod_documents'
           AND data_type = 'bytea'
    ),
    'POD stores integrity and object-reference metadata, not binary content'
);
SELECT pg_temp.assert_true(
    has_schema_privilege('zippy_app', 'zippy', 'USAGE')
    AND has_table_privilege('zippy_readonly', 'zippy.orders', 'SELECT')
    AND NOT has_table_privilege('zippy_readonly', 'zippy.orders', 'INSERT')
    AND has_schema_privilege('zippy_migrator', 'zippy', 'CREATE')
    AND NOT (SELECT rolcanlogin FROM pg_roles WHERE rolname = 'zippy_migrator'),
    'least-privilege role grants are enforced'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM pg_policies WHERE schemaname = 'zippy' AND policyname = 'platform_isolation') = 45,
    'all 45 tenant-scoped tables have platform policies'
);
SELECT pg_temp.assert_true(
    EXISTS (
        SELECT 1 FROM pg_indexes
         WHERE schemaname = 'zippy' AND indexname = 'durable_tasks_claim_idx'
    ),
    'durable task claim index exists'
);

SELECT set_config('zippy.platform_id', '20000000-0000-0000-0000-000000000002', false);
SELECT set_config('zippy.account_id', 'e0000000-0000-0000-0000-000000000001', false);
INSERT INTO zippy.accounts (
    account_id, platform_id, external_subject, email_normalized, status
) VALUES (
    'e0000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
    'other-subject', 'other@example.invalid', 'active'
);

SELECT set_config('zippy.platform_id', '10000000-0000-0000-0000-000000000001', false);
SELECT set_config('zippy.account_id', 'a0000000-0000-0000-0000-000000000001', false);

INSERT INTO zippy.accounts (
    account_id, platform_id, external_subject, email_normalized, status
) VALUES
    ('a0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'admin-subject', 'admin@example.invalid', 'active'),
    ('c0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'customer-subject', 'customer@example.invalid', 'active'),
    ('b0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'vendor-subject', 'vendor@example.invalid', 'active'),
    ('d0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'driver-subject', 'driver@example.invalid', 'active'),
    ('f0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'blocked-subject', 'blocked@example.invalid', 'blocked'),
    ('f0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'suspended-subject', 'suspended@example.invalid', 'suspended'),
    ('f0000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', 'outsider-subject', 'outsider@example.invalid', 'active'),
    ('f0000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', 'second-customer-subject', 'second-customer@example.invalid', 'active');

INSERT INTO zippy.account_role_memberships (
    platform_id, account_id, role_code, granted_by_account_id, correlation_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'admin', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000001'),
    ('10000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'customer', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000002'),
    ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'vendor', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000003'),
    ('10000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'driver', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000004');

INSERT INTO zippy.customer_profiles (
    customer_profile_id, platform_id, account_id, verification_status
) VALUES (
    '11000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000001', 'verified'
);
INSERT INTO zippy.vendor_profiles (
    vendor_profile_id, platform_id, account_id, eligibility_status
) VALUES (
    '12000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000001', 'approved'
);
INSERT INTO zippy.legal_entities (
    legal_entity_id, platform_id, legal_name, registration_reference
) VALUES (
    '15000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'Synthetic Dual Role Logistics', 'SYNTHETIC-LEGAL-001'
);
UPDATE zippy.customer_profiles
   SET legal_entity_id = '15000000-0000-0000-0000-000000000001'
 WHERE customer_profile_id = '11000000-0000-0000-0000-000000000001';
INSERT INTO zippy.customer_profiles (
    customer_profile_id, platform_id, account_id, verification_status
) VALUES (
    '11000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    'f0000000-0000-0000-0000-000000000004', 'verified'
);
INSERT INTO zippy.vendor_profiles (
    vendor_profile_id, platform_id, legal_entity_id, eligibility_status
) VALUES (
    '12000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    '15000000-0000-0000-0000-000000000001', 'approved'
);
INSERT INTO zippy.company_memberships (
    company_membership_id, platform_id, legal_entity_id, account_id, membership_role, valid_from
) VALUES (
    '16000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '15000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001',
    'owner', clock_timestamp() - interval '1 day'
);
INSERT INTO zippy.driver_profiles (
    driver_profile_id, platform_id, account_id, licence_reference, eligibility_status
) VALUES (
    '13000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'd0000000-0000-0000-0000-000000000001', 'SYNTHETIC-LICENCE-001', 'approved'
);
INSERT INTO zippy.driver_profiles (
    driver_profile_id, platform_id, account_id, licence_reference, eligibility_status
) VALUES (
    '13000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    'f0000000-0000-0000-0000-000000000001', 'SYNTHETIC-LICENCE-BLOCKED', 'approved'
);
INSERT INTO zippy.driver_associations (
    driver_association_id, platform_id, driver_profile_id, vendor_profile_id, valid_from
) VALUES (
    '14000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '13000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000001',
    clock_timestamp() - interval '1 day'
);
INSERT INTO zippy.driver_associations (
    driver_association_id, platform_id, driver_profile_id, vendor_profile_id, valid_from
) VALUES (
    '14000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    '13000000-0000-0000-0000-000000000002', '12000000-0000-0000-0000-000000000001',
    clock_timestamp() - interval '1 day'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.customer_profiles (
            platform_id, account_id, verification_status
        ) VALUES (
            '10000000-0000-0000-0000-000000000001',
            'e0000000-0000-0000-0000-000000000001', 'verified'
        );
        RAISE EXCEPTION 'expected platform-scoped foreign key rejection';
    EXCEPTION WHEN foreign_key_violation THEN
        NULL;
    END;
END;
$$;

INSERT INTO zippy.vehicle_models (
    vehicle_model_id, platform_id, model_code, display_name, capacity_kg,
    body_type, source_version, approved_by_account_id, approved_at
) VALUES (
    '21000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'SYNTHETIC-TRUCK', 'Synthetic Test Truck', 5000, 'closed', 'm2-test-v1',
    'a0000000-0000-0000-0000-000000000001', clock_timestamp()
);
INSERT INTO zippy.vehicles (
    vehicle_id, platform_id, vendor_profile_id, vehicle_model_id,
    registration_number, status, approved_by_account_id, approved_at
) VALUES (
    '22000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '12000000-0000-0000-0000-000000000001', '21000000-0000-0000-0000-000000000001',
    'SYNTHETIC-REG-001', 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()
);
INSERT INTO zippy.vehicles (
    vehicle_id, platform_id, vendor_profile_id, vehicle_model_id,
    registration_number, status, approved_by_account_id, approved_at
) VALUES (
    '22000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    '12000000-0000-0000-0000-000000000002', '21000000-0000-0000-0000-000000000001',
    'SYNTHETIC-REG-002', 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()
);
INSERT INTO zippy.vehicle_documents (
    platform_id, vehicle_id, document_type, object_key, checksum_sha256,
    verification_status, verified_by_account_id, verified_at
) VALUES (
    '10000000-0000-0000-0000-000000000001', '22000000-0000-0000-0000-000000000001',
    'fitness', 'synthetic/vehicle/fitness-001', repeat('1', 64),
    'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()
);

INSERT INTO zippy.quotes (
    quote_id, platform_id, customer_profile_id, policy_version, input_hash_sha256,
    input_evidence, amount, currency_code, expires_at, created_by_account_id
) VALUES (
    '23000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000001', 'synthetic-policy-v1', repeat('2', 64),
    '{"fixture":"synthetic"}'::jsonb, 1000.00, 'INR', clock_timestamp() + interval '1 hour',
    'c0000000-0000-0000-0000-000000000001'
);
INSERT INTO zippy.orders (
    order_id, platform_id, booking_customer_profile_id, quote_id,
    cargo_description, cargo_weight_kg, created_by_account_id, correlation_id
) VALUES (
    '30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000001',
    'Synthetic non-hazardous cargo', 1000, 'c0000000-0000-0000-0000-000000000001',
    '90000000-0000-0000-0000-000000000010'
);
INSERT INTO zippy.quotes (
    quote_id, platform_id, customer_profile_id, policy_version, input_hash_sha256,
    input_evidence, amount, currency_code, expires_at, created_by_account_id
) VALUES (
    '23000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000002', 'synthetic-policy-v1', repeat('1', 64),
    '{"fixture":"synthetic-dual-role"}'::jsonb, 750.00, 'INR', clock_timestamp() + interval '1 hour',
    'f0000000-0000-0000-0000-000000000004'
);
INSERT INTO zippy.orders (
    order_id, platform_id, booking_customer_profile_id, quote_id,
    cargo_description, cargo_weight_kg, created_by_account_id, correlation_id
) VALUES (
    '30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000002',
    'Synthetic company vendor cargo', 500, 'f0000000-0000-0000-0000-000000000004',
    '90000000-0000-0000-0000-000000000014'
);
INSERT INTO zippy.order_stops (
    platform_id, order_id, stop_sequence, stop_kind, address_text,
    latitude, longitude, accuracy_meters, source, created_by_account_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 1, 'pickup', 'Synthetic pickup', 10.000000, 78.000000, 5, 'fixture', 'c0000000-0000-0000-0000-000000000001'),
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 2, 'delivery', 'Synthetic delivery', 11.000000, 79.000000, 5, 'fixture', 'c0000000-0000-0000-0000-000000000001');
INSERT INTO zippy.transaction_participants (
    platform_id, order_id, participant_role, customer_profile_id
) VALUES (
    '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
    'customer', '11000000-0000-0000-0000-000000000001'
);
INSERT INTO zippy.transaction_participants (
    platform_id, order_id, participant_role, vendor_profile_id
) VALUES (
    '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
    'vendor', '12000000-0000-0000-0000-000000000001'
);
INSERT INTO zippy.transaction_participants (
        platform_id, order_id, participant_role, customer_profile_id
) VALUES (
        '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002',
        'customer', '11000000-0000-0000-0000-000000000002'
);
INSERT INTO zippy.transaction_participants (
        platform_id, order_id, participant_role, vendor_profile_id
) VALUES (
        '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002',
        'vendor', '12000000-0000-0000-0000-000000000002'
);
SELECT pg_temp.assert_true(
        (SELECT count(*) FROM zippy.legal_entities WHERE legal_entity_id = '15000000-0000-0000-0000-000000000001') = 1
        AND EXISTS (
                SELECT 1
                    FROM zippy.transaction_participants participant
                    JOIN zippy.orders order_record USING (platform_id, order_id)
                    JOIN zippy.customer_profiles customer
                        ON customer.platform_id = order_record.platform_id
                     AND customer.customer_profile_id = order_record.booking_customer_profile_id
                 WHERE participant.order_id = '30000000-0000-0000-0000-000000000001'
                     AND participant.participant_role = 'customer'
                     AND customer.legal_entity_id = '15000000-0000-0000-0000-000000000001'
        )
        AND EXISTS (
                SELECT 1
                    FROM zippy.transaction_participants participant
                    JOIN zippy.vendor_profiles vendor
                        ON vendor.platform_id = participant.platform_id
                     AND vendor.vendor_profile_id = participant.vendor_profile_id
                 WHERE participant.order_id = '30000000-0000-0000-0000-000000000002'
                     AND participant.participant_role = 'vendor'
                     AND vendor.legal_entity_id = '15000000-0000-0000-0000-000000000001'
        ),
        'one legal identity can be customer in one transaction and vendor in another'
);

DO $$
BEGIN
    BEGIN
        UPDATE zippy.transaction_participants
           SET customer_profile_id = NULL,
               vendor_profile_id = '12000000-0000-0000-0000-000000000001'
         WHERE order_id = '30000000-0000-0000-0000-000000000001'
           AND participant_role = 'customer';
        RAISE EXCEPTION 'expected booking-party participant rejection';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;

DO $$
BEGIN
    BEGIN
        UPDATE zippy.orders SET status = 'quoted'
         WHERE order_id = '30000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'expected direct status update rejection';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;

SELECT pg_temp.assert_true(
    zippy.transition_order(
        '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
        'pending', 'quoted', 'a0000000-0000-0000-0000-000000000001', 'synthetic transition',
        'transition-001', repeat('3', 64), '90000000-0000-0000-0000-000000000011'
    ) = 'quoted',
    'legal order transition succeeds'
);
SELECT pg_temp.assert_true(
    zippy.transition_order(
        '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
        'pending', 'quoted', 'a0000000-0000-0000-0000-000000000001', 'synthetic transition',
        'transition-001', repeat('3', 64), '90000000-0000-0000-0000-000000000011'
    ) = 'quoted',
    'same transition replay returns prior result'
);

DO $$
BEGIN
    BEGIN
        PERFORM zippy.transition_order(
            '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
            'quoted', 'delivered', 'a0000000-0000-0000-0000-000000000001', 'illegal synthetic transition',
            'transition-002', repeat('4', 64), '90000000-0000-0000-0000-000000000012'
        );
        RAISE EXCEPTION 'expected illegal transition rejection';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
    BEGIN
        PERFORM zippy.transition_order(
            '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
            'quoted', 'confirmed', 'a0000000-0000-0000-0000-000000000001', 'changed replay',
            'transition-001', repeat('5', 64), '90000000-0000-0000-0000-000000000013'
        );
        RAISE EXCEPTION 'expected idempotency hash conflict';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END;
$$;

INSERT INTO zippy.dispatch_offers (
    dispatch_offer_id, platform_id, order_id, vendor_profile_id, vehicle_id,
    driver_profile_id, status, scoring_input_version, idempotency_key,
    expires_at, responded_at
) VALUES (
    '50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000001',
    '22000000-0000-0000-0000-000000000001', '13000000-0000-0000-0000-000000000001',
    'accepted', 'synthetic-score-v1', 'offer-001', clock_timestamp() + interval '1 hour', clock_timestamp()
);
INSERT INTO zippy.trips (
    trip_id, platform_id, order_id, status
) VALUES (
    '40000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001', 'active'
);
DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.trip_assignments (
            platform_id, trip_id, dispatch_offer_id, vendor_profile_id,
            vehicle_id, driver_profile_id, assigned_by_account_id, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001',
            '50000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000002',
            '22000000-0000-0000-0000-000000000001', '13000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000015'
        );
        RAISE EXCEPTION 'expected accepted-offer vendor mismatch rejection';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO zippy.trip_assignments (
            platform_id, trip_id, dispatch_offer_id, vendor_profile_id,
            vehicle_id, driver_profile_id, assigned_by_account_id, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001',
            '50000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000001',
            '22000000-0000-0000-0000-000000000002', '13000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000016'
        );
        RAISE EXCEPTION 'expected accepted-offer vehicle mismatch rejection';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO zippy.trip_assignments (
            platform_id, trip_id, dispatch_offer_id, vendor_profile_id,
            vehicle_id, driver_profile_id, assigned_by_account_id, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001',
            '50000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000001',
            '22000000-0000-0000-0000-000000000001', '13000000-0000-0000-0000-000000000002',
            'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000017'
        );
        RAISE EXCEPTION 'expected accepted-offer driver or blocked-actor mismatch rejection';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;
INSERT INTO zippy.trip_assignments (
    trip_assignment_id, platform_id, trip_id, dispatch_offer_id, vendor_profile_id,
    vehicle_id, driver_profile_id, assigned_by_account_id, correlation_id
) VALUES (
    '60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001',
    '12000000-0000-0000-0000-000000000001', '22000000-0000-0000-0000-000000000001',
    '13000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001',
    '90000000-0000-0000-0000-000000000020'
);
INSERT INTO zippy.trip_milestones (
    platform_id, trip_id, milestone, sequence_no, actor_account_id, source, correlation_id
) VALUES (
    '10000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001',
    'pickup', 1, 'd0000000-0000-0000-0000-000000000001', 'manual',
    '90000000-0000-0000-0000-000000000021'
);
INSERT INTO zippy.trip_location_history (
    location_sample_id, platform_id, trip_id, vehicle_id, actor_account_id,
    latitude, longitude, accuracy_meters, source, consent_reference, correlation_id, captured_at
) VALUES (
    '61000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001', '22000000-0000-0000-0000-000000000001',
    'd0000000-0000-0000-0000-000000000001', 10.100000, 78.100000, 8,
    'browser', 'synthetic-consent', '90000000-0000-0000-0000-000000000022', clock_timestamp()
);
INSERT INTO zippy.pod_documents (
    pod_document_id, platform_id, order_id, trip_id, uploaded_by_account_id,
    object_key, content_type, byte_size, checksum_sha256, verification_status,
    verified_by_account_id, verified_at
) VALUES (
    '62000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001',
    'd0000000-0000-0000-0000-000000000001', 'synthetic/pod/001', 'application/pdf', 128,
    repeat('6', 64), 'accepted', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()
);

DO $$
BEGIN
    BEGIN
        UPDATE zippy.trip_location_history SET accuracy_meters = 1
         WHERE location_sample_id = '61000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'expected append-only location rejection';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN
        NULL;
    END;
    BEGIN
        UPDATE zippy.quotes SET amount = 1
         WHERE quote_id = '23000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'expected immutable quote rejection';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN
        NULL;
    END;
END;
$$;

INSERT INTO zippy.webhook_receipts (
    webhook_receipt_id, platform_id, provider, provider_event_id,
    signature_verified, payload_hash_sha256, correlation_id
) VALUES (
    '70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'synthetic_gateway', 'synthetic-event-001', false, repeat('7', 64),
    '90000000-0000-0000-0000-000000000030'
);
INSERT INTO zippy.gateway_events (
    gateway_event_id, platform_id, webhook_receipt_id, order_id, gateway,
    gateway_event_type, amount, currency_code, evidence_hash_sha256, verified_at
) VALUES (
    '71000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    '70000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
    'synthetic_gateway', 'payment.captured', 1000, 'INR', repeat('8', 64), clock_timestamp()
);

DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.payment_projections (
            platform_id, order_id, gateway_event_id, operational_status,
            amount, currency_code, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
            '71000000-0000-0000-0000-000000000001', 'evidence_verified', 1000, 'INR',
            '90000000-0000-0000-0000-000000000031'
        );
        RAISE EXCEPTION 'expected unsigned payment evidence rejection';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;

UPDATE zippy.webhook_receipts
   SET signature_verified = true
 WHERE webhook_receipt_id = '70000000-0000-0000-0000-000000000001';
INSERT INTO zippy.payment_projections (
    platform_id, order_id, gateway_event_id, operational_status,
    amount, currency_code, correlation_id
) VALUES (
    '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
    '71000000-0000-0000-0000-000000000001', 'evidence_verified', 1000, 'INR',
    '90000000-0000-0000-0000-000000000032'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.webhook_receipts (
            platform_id, provider, provider_event_id, signature_verified,
            payload_hash_sha256, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', 'synthetic_gateway',
            'synthetic-event-001', true, repeat('7', 64),
            '90000000-0000-0000-0000-000000000033'
        );
        RAISE EXCEPTION 'expected duplicate webhook rejection';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END;
$$;

INSERT INTO zippy.external_references (
    external_reference_id, platform_id, local_entity_type, local_entity_id,
    external_system, external_model, external_id, sync_status, correlation_id
) VALUES (
    '72000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'refund_request', '73000000-0000-0000-0000-000000000002', 'synthetic_erp',
    'refund_evidence', 'synthetic-external-001', 'synchronized',
    '90000000-0000-0000-0000-000000000034'
);
INSERT INTO zippy.refund_requests (
    refund_request_id, platform_id, order_id, requester_account_id, amount,
    currency_code, target_reference, reason, idempotency_key, correlation_id
) VALUES
    ('73000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 100, 'INR', 'synthetic-target-1', 'synthetic self approval rejection', 'refund-001', '90000000-0000-0000-0000-000000000035'),
    ('73000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 200, 'INR', 'synthetic-target-2', 'synthetic approved refund', 'refund-002', '90000000-0000-0000-0000-000000000036');
DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.refund_decisions (
            refund_decision_id, platform_id, refund_request_id, approver_account_id,
            decision, reason, correlation_id
        ) VALUES (
            '74000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
            '73000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001',
            'approved', 'synthetic invalid self approval', '90000000-0000-0000-0000-000000000037'
        );
        RAISE EXCEPTION 'expected self-approved refund decision rejection';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;

DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.refund_decisions (
            refund_decision_id, platform_id, refund_request_id, approver_account_id,
            decision, reason, correlation_id
        ) VALUES (
            '74000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
            '73000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001',
            'approved', 'synthetic unauthorized approval', '90000000-0000-0000-0000-000000000039'
        );
        RAISE EXCEPTION 'expected unauthorized refund approver rejection';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;

INSERT INTO zippy.refund_decisions (
    refund_decision_id, platform_id, refund_request_id, approver_account_id,
    decision, reason, correlation_id
) VALUES (
    '74000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
    '73000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001',
    'approved', 'synthetic manual approval', '90000000-0000-0000-0000-000000000038'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.refund_executions (
            platform_id, refund_request_id, refund_decision_id, external_reference_id,
            amount, currency_code, target_reference, idempotency_key,
            evidence_hash_sha256, executed_at
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', '73000000-0000-0000-0000-000000000001',
            '74000000-0000-0000-0000-000000000004', '72000000-0000-0000-0000-000000000001',
            100, 'INR', 'synthetic-target-1', 'refund-execution-missing-approval', repeat('9', 64), clock_timestamp()
        );
        RAISE EXCEPTION 'expected missing refund approval rejection';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
    BEGIN
        INSERT INTO zippy.refund_executions (
            platform_id, refund_request_id, refund_decision_id, external_reference_id,
            amount, currency_code, target_reference, idempotency_key,
            evidence_hash_sha256, executed_at
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', '73000000-0000-0000-0000-000000000001',
            '74000000-0000-0000-0000-000000000002', '72000000-0000-0000-0000-000000000001',
            100, 'INR', 'synthetic-target-1', 'refund-execution-001', repeat('9', 64), clock_timestamp()
        );
        RAISE EXCEPTION 'expected mismatched refund decision rejection';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;

DO $$
BEGIN
    BEGIN
        UPDATE zippy.external_references
           SET external_id = 'synthetic-external-changed'
         WHERE external_reference_id = '72000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'expected external reference identity rejection';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN
        NULL;
    END;
END;
$$;

UPDATE zippy.external_references
   SET sync_status = 'stale',
       external_version = 'synthetic-version-2',
       updated_at = clock_timestamp()
 WHERE external_reference_id = '72000000-0000-0000-0000-000000000001';
SELECT pg_temp.assert_true(
    (SELECT sync_status FROM zippy.external_references WHERE external_reference_id = '72000000-0000-0000-0000-000000000001') = 'stale'
    AND (SELECT external_id FROM zippy.external_references WHERE external_reference_id = '72000000-0000-0000-0000-000000000001') = 'synthetic-external-001',
    'external reference sync status is mutable while identity remains unchanged'
);

INSERT INTO zippy.refund_executions (
    platform_id, refund_request_id, refund_decision_id, external_reference_id,
    amount, currency_code, target_reference, idempotency_key,
    evidence_hash_sha256, executed_at
) VALUES (
    '10000000-0000-0000-0000-000000000001', '73000000-0000-0000-0000-000000000002',
    '74000000-0000-0000-0000-000000000002', '72000000-0000-0000-0000-000000000001',
    200, 'INR', 'synthetic-target-2', 'refund-execution-002', repeat('a', 64), clock_timestamp()
);

DO $$
BEGIN
    PERFORM set_config('zippy.account_id', 'f0000000-0000-0000-0000-000000000001', false);
    BEGIN
        PERFORM zippy.transition_order(
            '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
            'quoted', 'confirmed', 'f0000000-0000-0000-0000-000000000001', 'blocked actor attempt',
            'transition-blocked', repeat('d', 64), '90000000-0000-0000-0000-000000000040'
        );
        RAISE EXCEPTION 'expected blocked actor rejection';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    PERFORM set_config('zippy.account_id', 'f0000000-0000-0000-0000-000000000002', false);
    BEGIN
        PERFORM zippy.transition_order(
            '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
            'quoted', 'confirmed', 'f0000000-0000-0000-0000-000000000002', 'suspended actor attempt',
            'transition-suspended', repeat('e', 64), '90000000-0000-0000-0000-000000000041'
        );
        RAISE EXCEPTION 'expected suspended actor rejection';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    PERFORM set_config('zippy.account_id', 'a0000000-0000-0000-0000-000000000001', false);
END;
$$;

INSERT INTO zippy.durable_tasks (
    durable_task_id, platform_id, task_type, aggregate_type, aggregate_id,
    payload_reference, idempotency_key, max_attempts, correlation_id
) VALUES
    ('80000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'synthetic_retry', 'order', '30000000-0000-0000-0000-000000000001', 'synthetic-payload-1', 'task-001', 2, '90000000-0000-0000-0000-000000000050'),
    ('80000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'synthetic_concurrent', 'order', '30000000-0000-0000-0000-000000000001', 'synthetic-payload-2', 'task-002', 3, '90000000-0000-0000-0000-000000000051'),
    ('80000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', 'synthetic_concurrent', 'order', '30000000-0000-0000-0000-000000000001', 'synthetic-payload-3', 'task-003', 3, '90000000-0000-0000-0000-000000000052'),
    ('80000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', 'synthetic_expired', 'order', '30000000-0000-0000-0000-000000000001', 'synthetic-payload-4', 'task-004', 3, '90000000-0000-0000-0000-000000000053');

UPDATE zippy.durable_tasks
   SET status = 'processing',
       lease_owner = 'expired-worker',
       lease_expires_at = clock_timestamp() - interval '1 minute'
 WHERE durable_task_id = '80000000-0000-0000-0000-000000000004';
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.claim_durable_tasks(
        '10000000-0000-0000-0000-000000000001', 'synthetic_expired', 'recovery-worker', 60, 1
    )) = 1,
    'expired processing lease can be reclaimed'
);
SELECT pg_temp.assert_true(
    (SELECT lease_owner FROM zippy.durable_tasks WHERE durable_task_id = '80000000-0000-0000-0000-000000000004') = 'recovery-worker',
    'expired lease ownership moves to the reclaimer'
);

SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.claim_durable_tasks(
        '10000000-0000-0000-0000-000000000001', 'synthetic_retry', 'worker-a', 60, 1
    )) = 1,
    'task claim succeeds'
);
SELECT pg_temp.assert_true(
    zippy.fail_durable_task(
        '10000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000001',
        'worker-a', 'synthetic first failure', clock_timestamp() - interval '1 second'
    ) = 'failed',
    'first task failure schedules retry'
);
SELECT pg_temp.assert_true(
    NOT EXISTS (
        SELECT 1 FROM zippy.dead_letter_records
         WHERE source_id = '80000000-0000-0000-0000-000000000001'
    ),
    'retryable failure does not create dead-letter evidence before terminal attempt'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.claim_durable_tasks(
        '10000000-0000-0000-0000-000000000001', 'synthetic_retry', 'worker-b', 60, 1
    )) = 1,
    'expired/retryable task can be reclaimed'
);
SELECT pg_temp.assert_true(
    zippy.fail_durable_task(
        '10000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000001',
        'worker-b', 'synthetic terminal failure', clock_timestamp()
    ) = 'dead_lettered',
    'terminal failure dead-letters task'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.dead_letter_records WHERE source_id = '80000000-0000-0000-0000-000000000001') = 1,
    'dead-letter evidence is durable'
);

INSERT INTO zippy.event_inbox (
    platform_id, source, source_event_id, payload_hash_sha256, correlation_id
) VALUES (
    '10000000-0000-0000-0000-000000000001', 'synthetic_source', 'source-event-001',
    repeat('b', 64), '90000000-0000-0000-0000-000000000053'
);
DO $$
BEGIN
    BEGIN
        INSERT INTO zippy.event_inbox (
            platform_id, source, source_event_id, payload_hash_sha256, correlation_id
        ) VALUES (
            '10000000-0000-0000-0000-000000000001', 'synthetic_source', 'source-event-001',
            repeat('b', 64), '90000000-0000-0000-0000-000000000054'
        );
        RAISE EXCEPTION 'expected inbox duplicate rejection';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END;
$$;

INSERT INTO zippy.audit_events (
    audit_event_id, platform_id, actor_account_id, actor_type, action,
    entity_type, entity_id, after_hash_sha256, correlation_id
) VALUES (
    '81000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001', 'account', 'synthetic.audit',
    'order', '30000000-0000-0000-0000-000000000001', repeat('c', 64),
    '90000000-0000-0000-0000-000000000055'
);
DO $$
BEGIN
    BEGIN
        DELETE FROM zippy.audit_events
         WHERE audit_event_id = '81000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'expected append-only audit rejection';
    EXCEPTION WHEN object_not_in_prerequisite_state THEN
        NULL;
    END;
END;
$$;

SELECT pg_temp.assert_true((SELECT count(*) FROM zippy.accounts) = 8, 'application role sees only selected platform');
SELECT pg_temp.assert_true(
    NOT EXISTS (SELECT 1 FROM zippy.accounts WHERE platform_id = '20000000-0000-0000-0000-000000000002'),
    'RLS hides another platform'
);

DO $$
DECLARE
    affected_rows bigint;
BEGIN
    BEGIN
        INSERT INTO zippy.accounts (
            account_id, platform_id, external_subject, email_normalized, status
        ) VALUES (
            'e0000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002',
            'cross-platform-insert', 'cross-platform-insert@example.invalid', 'active'
        );
        RAISE EXCEPTION 'expected cross-platform insert rejection';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;

    UPDATE zippy.accounts
       SET external_subject = 'cross-platform-update'
     WHERE account_id = 'e0000000-0000-0000-0000-000000000001';
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    IF affected_rows <> 0 THEN
        RAISE EXCEPTION 'cross-platform update affected % rows', affected_rows;
    END IF;

    DELETE FROM zippy.accounts
     WHERE account_id = 'e0000000-0000-0000-0000-000000000001';
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    IF affected_rows <> 0 THEN
        RAISE EXCEPTION 'cross-platform delete affected % rows', affected_rows;
    END IF;
END;
$$;

SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.trip_location_history WHERE trip_id = '40000000-0000-0000-0000-000000000001') = 1,
    'location history persists'
);
SELECT set_config('zippy.account_id', 'f0000000-0000-0000-0000-000000000003', false);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.trip_location_history WHERE trip_id = '40000000-0000-0000-0000-000000000001') = 0,
    'same-platform non-participant cannot read location history'
);
SELECT set_config('zippy.account_id', 'c0000000-0000-0000-0000-000000000001', false);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.trip_location_history WHERE trip_id = '40000000-0000-0000-0000-000000000001') = 1,
    'participating customer can read location history'
);
SELECT set_config('zippy.account_id', 'a0000000-0000-0000-0000-000000000001', false);
SELECT pg_temp.assert_true(
    (SELECT checksum_sha256 FROM zippy.pod_documents WHERE pod_document_id = '62000000-0000-0000-0000-000000000001') = repeat('6', 64),
    'POD checksum metadata persists'
);
SELECT pg_temp.assert_true(
    (SELECT count(*) FROM zippy.order_state_transitions WHERE order_id = '30000000-0000-0000-0000-000000000001') = 1
    AND (SELECT count(*) FROM zippy.event_outbox WHERE aggregate_id = '30000000-0000-0000-0000-000000000001') = 1,
    'state transition and outbox evidence are atomic and replay-safe'
);

SELECT 'M2 database assertions passed' AS result;