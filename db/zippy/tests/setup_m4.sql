\set ON_ERROR_STOP on

-- M4 synthetic fixtures (run after setup_m3.sql in the disposable proof).
-- Ids are deterministic and use .invalid identities only.

INSERT INTO zippy.accounts (
    account_id, platform_id, external_subject, email_normalized, status
) VALUES
    ('a0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'admin2-subject', 'admin2-m4@example.invalid', 'active'),
    ('d0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'vendor-subject', 'vendor-m4@example.invalid', 'active');

INSERT INTO zippy.account_role_memberships (
    platform_id, account_id, role_code, granted_by_account_id, correlation_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000002', 'admin', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000101'),
    ('10000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'vendor', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000102');

INSERT INTO zippy.vendor_profiles (
    vendor_profile_id, platform_id, account_id, eligibility_status
) VALUES
    ('e0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'approved');

INSERT INTO zippy.quotes (
    quote_id, platform_id, customer_profile_id, policy_version, input_hash_sha256,
    input_evidence, amount, currency_code, expires_at, created_by_account_id
) VALUES
    ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', 'test-m4-v1', repeat('a', 64),
     '{"synthetic": true}'::jsonb, 100.00, 'INR',
     clock_timestamp() + interval '1 hour', 'c0000000-0000-0000-0000-000000000001'),
    ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', 'test-m4-v1', repeat('b', 64),
     '{"synthetic": true}'::jsonb, 250.00, 'INR',
     clock_timestamp() + interval '1 hour', 'c0000000-0000-0000-0000-000000000001');

INSERT INTO zippy.orders (
    order_id, platform_id, booking_customer_profile_id, quote_id, status,
    cargo_description, cargo_weight_kg, created_by_account_id, correlation_id
) VALUES
    ('30000000-0000-0000-0000-00000000000a', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
     'pending', 'M4 synthetic order A', 10.000,
     'c0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000201'),
    ('30000000-0000-0000-0000-00000000000b', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
     'pending', 'M4 synthetic order B', 25.000,
     'c0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000202'),
    -- Dedicated to payment-intent mapping conflict regression tests only
    -- (never touched by any other webhook/POD/refund test), since a Zippy
    -- order may hold exactly one Razorpay payment-order reference.
    ('30000000-0000-0000-0000-00000000000c', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
     'pending', 'M4 synthetic order C (mapping conflict fixture)', 1.000,
     'c0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000203'),
    ('30000000-0000-0000-0000-00000000000d', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
     'pending', 'M4 synthetic order D (mapping conflict fixture)', 1.000,
     'c0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000204');

INSERT INTO zippy.transaction_participants (
    platform_id, order_id, participant_role, customer_profile_id, vendor_profile_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000a', 'customer', 'c1000000-0000-0000-0000-000000000001', NULL),
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000a', 'vendor', NULL, 'e0000000-0000-0000-0000-000000000001'),
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000b', 'customer', 'c1000000-0000-0000-0000-000000000001', NULL),
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000b', 'vendor', NULL, 'e0000000-0000-0000-0000-000000000001');

INSERT INTO zippy.trips (
    trip_id, platform_id, order_id, status
) VALUES
    ('50000000-0000-0000-0000-00000000000a', '10000000-0000-0000-0000-000000000001',
     '30000000-0000-0000-0000-00000000000a', 'planned');

-- Second platform: minimal chain to prove cross-tenant payment-intent
-- mappings are invisible to platform 1's webhook resolution even when the
-- provider reference string collides.
INSERT INTO zippy.platforms (
    platform_id, platform_key, display_name
) VALUES
    ('10000000-0000-0000-0000-000000000002', 'm4_cross_tenant_test', 'M4 Cross-Tenant Synthetic Test');

INSERT INTO zippy.accounts (
    account_id, platform_id, external_subject, email_normalized, status
) VALUES
    ('c0000000-0000-0000-0000-000000000099', '10000000-0000-0000-0000-000000000002', 'cross-tenant-customer-subject', 'cross-tenant-customer-m4@example.invalid', 'active');

INSERT INTO zippy.customer_profiles (
    customer_profile_id, platform_id, account_id, verification_status
) VALUES
    ('c1000000-0000-0000-0000-000000000099', '10000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000099', 'verified');

INSERT INTO zippy.quotes (
    quote_id, platform_id, customer_profile_id, policy_version, input_hash_sha256,
    input_evidence, amount, currency_code, expires_at, created_by_account_id
) VALUES
    ('20000000-0000-0000-0000-000000000099', '10000000-0000-0000-0000-000000000002',
     'c1000000-0000-0000-0000-000000000099', 'test-m4-v1', repeat('c', 64),
     '{"synthetic": true}'::jsonb, 100.00, 'INR',
     clock_timestamp() + interval '1 hour', 'c0000000-0000-0000-0000-000000000099');

INSERT INTO zippy.orders (
    order_id, platform_id, booking_customer_profile_id, quote_id, status,
    cargo_description, cargo_weight_kg, created_by_account_id, correlation_id
) VALUES
    ('30000000-0000-0000-0000-000000000c99', '10000000-0000-0000-0000-000000000002',
     'c1000000-0000-0000-0000-000000000099', '20000000-0000-0000-0000-000000000099',
     'pending', 'M4 cross-tenant synthetic order', 5.000,
     'c0000000-0000-0000-0000-000000000099', '90000000-0000-0000-0000-000000000299');

-- Dispatch fixtures: one dispatch-eligible (confirmed) order under vendor
-- e0000000-...0001, plus two fully-eligible vehicle/driver candidates so
-- concurrent competing acceptance can be exercised deterministically.
INSERT INTO zippy.accounts (
    account_id, platform_id, external_subject, email_normalized, status
) VALUES
    ('d2000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'driver1-subject', 'driver1-m4@example.invalid', 'active'),
    ('d2000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'driver2-subject', 'driver2-m4@example.invalid', 'active');

INSERT INTO zippy.account_role_memberships (
    platform_id, account_id, role_code, granted_by_account_id, correlation_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', 'd2000000-0000-0000-0000-000000000001', 'driver', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000301'),
    ('10000000-0000-0000-0000-000000000001', 'd2000000-0000-0000-0000-000000000002', 'driver', 'a0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000302');

INSERT INTO zippy.driver_profiles (
    driver_profile_id, platform_id, account_id, licence_reference, eligibility_status
) VALUES
    ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'd2000000-0000-0000-0000-000000000001', 'DISPATCH-LIC-001', 'approved'),
    ('70000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'd2000000-0000-0000-0000-000000000002', 'DISPATCH-LIC-002', 'approved');

INSERT INTO zippy.driver_associations (
    driver_association_id, platform_id, driver_profile_id, vendor_profile_id, valid_from
) VALUES
    ('71000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', clock_timestamp() - interval '1 day'),
    ('71000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000001', clock_timestamp() - interval '1 day');

INSERT INTO zippy.vehicle_models (
    vehicle_model_id, platform_id, model_code, display_name, capacity_kg, body_type,
    source_version, approved_by_account_id, approved_at
) VALUES
    ('61000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'DISPATCH-MODEL-1', 'Synthetic dispatch flatbed', 10.000, 'flatbed',
     'test-m4-v1', 'a0000000-0000-0000-0000-000000000001', clock_timestamp());

INSERT INTO zippy.vehicles (
    vehicle_id, platform_id, vendor_profile_id, vehicle_model_id, registration_number,
    status, approved_by_account_id, approved_at
) VALUES
    ('62000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'e0000000-0000-0000-0000-000000000001', '61000000-0000-0000-0000-000000000001',
     'DISPATCH-VEH-001', 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()),
    ('62000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
     'e0000000-0000-0000-0000-000000000001', '61000000-0000-0000-0000-000000000001',
     'DISPATCH-VEH-002', 'approved', 'a0000000-0000-0000-0000-000000000001', clock_timestamp());

INSERT INTO zippy.vehicle_documents (
    platform_id, vehicle_id, document_type, object_key, checksum_sha256,
    verification_status, verified_by_account_id, verified_at
) VALUES
    ('10000000-0000-0000-0000-000000000001', '62000000-0000-0000-0000-000000000001', 'fitness', 'synthetic/dispatch/veh1-fitness', repeat('3', 64), 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()),
    ('10000000-0000-0000-0000-000000000001', '62000000-0000-0000-0000-000000000001', 'insurance', 'synthetic/dispatch/veh1-insurance', repeat('4', 64), 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()),
    ('10000000-0000-0000-0000-000000000001', '62000000-0000-0000-0000-000000000002', 'fitness', 'synthetic/dispatch/veh2-fitness', repeat('5', 64), 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp()),
    ('10000000-0000-0000-0000-000000000001', '62000000-0000-0000-0000-000000000002', 'insurance', 'synthetic/dispatch/veh2-insurance', repeat('6', 64), 'verified', 'a0000000-0000-0000-0000-000000000001', clock_timestamp());

INSERT INTO zippy.quotes (
    quote_id, platform_id, customer_profile_id, policy_version, input_hash_sha256,
    input_evidence, amount, currency_code, expires_at, created_by_account_id
) VALUES
    ('20000000-0000-0000-0000-00000000000e', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', 'test-m4-v1', repeat('e', 64),
     '{"synthetic": true}'::jsonb, 500.00, 'INR',
     clock_timestamp() + interval '1 hour', 'c0000000-0000-0000-0000-000000000001');

INSERT INTO zippy.orders (
    order_id, platform_id, booking_customer_profile_id, quote_id, status,
    cargo_description, cargo_weight_kg, created_by_account_id, correlation_id
) VALUES
    ('30000000-0000-0000-0000-00000000000e', '10000000-0000-0000-0000-000000000001',
     'c1000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-00000000000e',
     'confirmed', 'M4 dispatch-eligible synthetic order', 5.000,
     'c0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000401');

INSERT INTO zippy.transaction_participants (
    platform_id, order_id, participant_role, customer_profile_id, vendor_profile_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000e', 'customer', 'c1000000-0000-0000-0000-000000000001', NULL),
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000e', 'vendor', NULL, 'e0000000-0000-0000-0000-000000000001');

-- ORD-INV-003: the shared dispatch-eligible order's captured, server-trusted
-- required body type; matches VEHICLE_MODEL's 'flatbed' so the pre-existing
-- eligibility fixtures (VEHICLE_1/2, and fresh vehicles built on the same
-- model) remain compatible without weakening the new gate.
INSERT INTO zippy.dispatch_requirements (
    platform_id, order_id, required_body_type, created_by_account_id, correlation_id
) VALUES
    ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-00000000000e',
     'flatbed', 'c0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000401');

SELECT 'M4 synthetic fixtures created' AS result;
